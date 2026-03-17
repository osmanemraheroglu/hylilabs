"""
Scoring V3 - Tum Mevcut Eslestmeleri Test Et (DEMO)

Bu script:
1. Sunucudan candidate_positions verilerini ceker
2. Her eslestme icin AI degerlendirmesi yapar
3. Sonuclari JSON ve konsol raporu olarak kaydeder

Kullanim:
    python test_all_matches.py

NOT: Veritabanina YAZMA yapmaz, sadece okuma yapar!
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# .env yukle (API key'ler icin)
load_dotenv()

# Scoring V3 modullerini import et
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoring_v3 import evaluate_candidate_sync, CandidateEvaluationResponse


# ═══════════════════════════════════════════════════════════════════════════════
# YAPILANDIRMA
# ═══════════════════════════════════════════════════════════════════════════════

# SERVER_HOST removed for security - use environment variable or local connection
SERVER_HOST = None  # Set via SSH_HOST env variable if needed
SERVER_DB_PATH = "/var/www/hylilabs/api/data/talentflow.db"
COMPANY_ID = 1
PROGRESS_INTERVAL = 5  # Her 5 testte bir progress goster


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    """Tek bir test sonucu"""
    candidate_id: int
    candidate_name: str
    position_id: int
    position_name: str
    score: int
    eligible: bool
    gemini_score: int
    hermes_score: int
    score_difference: int
    claude_used: bool
    consensus_method: str
    success: bool
    error_message: Optional[str]
    response_time: float
    strengths: List[str]
    weaknesses: List[str]
    overall_assessment: str
    elimination_reason: Optional[str]


# ═══════════════════════════════════════════════════════════════════════════════
# SUNUCU VERI CEKME
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_data_from_server() -> Dict[str, Any]:
    """
    Sunucudan tum eslestme verilerini ceker.

    Returns:
        Dict: matches, candidates, positions verileri
    """
    print("\n" + "=" * 70)
    print("SUNUCUDAN VERI CEKILIYOR...")
    print("=" * 70)

    # Python scripti sunucuda calistir
    fetch_script = '''
import sqlite3
import json

conn = sqlite3.connect("/var/www/hylilabs/api/data/talentflow.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. Tum eslestmeleri cek
cursor.execute("""
    SELECT cp.candidate_id, cp.position_id, cp.match_score as current_score
    FROM candidate_positions cp
    JOIN candidates c ON cp.candidate_id = c.id
    JOIN department_pools dp ON cp.position_id = dp.id
    WHERE c.company_id = 1
    ORDER BY cp.position_id, cp.candidate_id
""")
matches = [dict(row) for row in cursor.fetchall()]

# 2. Tum adaylari cek
cursor.execute("""
    SELECT id, ad_soyad, email, lokasyon, toplam_deneyim_yil, egitim, bolum,
           universite, mevcut_pozisyon, mevcut_sirket, teknik_beceriler,
           sertifikalar, diller, deneyim_detay, deneyim_aciklama, cv_raw_text
    FROM candidates
    WHERE company_id = 1
""")
candidates = {row["id"]: dict(row) for row in cursor.fetchall()}

# 3. Tum pozisyonlari cek
cursor.execute("""
    SELECT id, name, description, keywords, gerekli_deneyim_yil,
           gerekli_egitim, lokasyon, aranan_nitelikler, is_tanimi
    FROM department_pools
    WHERE company_id = 1 AND is_active = 1
""")
positions = {row["id"]: dict(row) for row in cursor.fetchall()}

# 4. Sirket bilgisi
cursor.execute("SELECT ad FROM companies WHERE id = 1")
company = cursor.fetchone()
company_name = company["ad"] if company else "Bilinmeyen Sirket"

conn.close()

result = {
    "matches": matches,
    "candidates": candidates,
    "positions": positions,
    "company_name": company_name
}

print(json.dumps(result, ensure_ascii=False, default=str))
'''

    # SSH ile calistir
    cmd = f'ssh {SERVER_HOST} "cd /var/www/hylilabs/api && python3 -c \\"{fetch_script}\\""'

    try:
        # Alternatif yontem: scripti dosyaya yaz ve calistir
        result = subprocess.run(
            ['ssh', SERVER_HOST, f'cd /var/www/hylilabs/api && python3 << "PYEOF"\n{fetch_script}\nPYEOF'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"SSH Hatasi: {result.stderr}")
            raise Exception(f"SSH hatasi: {result.stderr}")

        # JSON parse et (son satiri al - oncesinde SSH banner olabilir)
        output_lines = result.stdout.strip().split('\n')
        json_line = None
        for line in reversed(output_lines):
            if line.startswith('{'):
                json_line = line
                break

        if not json_line:
            raise Exception(f"JSON bulunamadi. Output: {result.stdout[:500]}")

        data = json.loads(json_line)

        # JSON serializasyonu dict key'lerini string yapar, integer'a cevir
        data['candidates'] = {int(k): v for k, v in data['candidates'].items()}
        data['positions'] = {int(k): v for k, v in data['positions'].items()}

        print(f"  Eslestme sayisi: {len(data['matches'])}")
        print(f"  Aday sayisi: {len(data['candidates'])}")
        print(f"  Pozisyon sayisi: {len(data['positions'])}")
        print(f"  Sirket: {data['company_name']}")

        return data

    except subprocess.TimeoutExpired:
        raise Exception("SSH timeout (60s)")
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse hatasi: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST CALISTIRMA
# ═══════════════════════════════════════════════════════════════════════════════

def run_all_tests(data: Dict[str, Any]) -> List[TestResult]:
    """
    Tum eslestmeler icin AI degerlendirmesi yapar.

    Args:
        data: Sunucudan cekilen veriler

    Returns:
        List[TestResult]: Test sonuclari
    """
    matches = data["matches"]
    candidates = data["candidates"]
    positions = data["positions"]
    company_name = data["company_name"]

    results = []
    total = len(matches)

    print("\n" + "=" * 70)
    print(f"AI DEGERLENDIRMESI BASLATILIYOR ({total} eslestme)")
    print("=" * 70)

    start_time = time.time()

    for i, match in enumerate(matches, 1):
        candidate_id = match["candidate_id"]
        position_id = match["position_id"]

        # Aday ve pozisyon verisini al
        candidate = candidates.get(candidate_id)
        position = positions.get(position_id)

        if not candidate or not position:
            print(f"\n[{i}/{total}] ATLANDI: Aday({candidate_id}) veya Pozisyon({position_id}) bulunamadi")
            continue

        candidate_name = candidate.get("ad_soyad", "Bilinmeyen")
        position_name = position.get("name", "Bilinmeyen")

        # Progress goster
        if i == 1 or i % PROGRESS_INTERVAL == 0 or i == total:
            elapsed = time.time() - start_time
            eta = (elapsed / i) * (total - i) if i > 0 else 0
            print(f"\n[{i}/{total}] {candidate_name[:25]:<25} -> {position_name[:30]:<30}")
            print(f"         Gecen: {elapsed:.1f}s | Kalan: ~{eta:.1f}s")

        # Pozisyon verisini hazirla
        position_data = {
            "name": position.get("name"),
            "company_name": company_name,
            "lokasyon": position.get("lokasyon"),
            "gerekli_deneyim_yil": position.get("gerekli_deneyim_yil"),
            "gerekli_egitim": position.get("gerekli_egitim"),
            "description": position.get("description") or position.get("aranan_nitelikler") or position.get("is_tanimi"),
            "keywords": json.loads(position.get("keywords") or "[]") if isinstance(position.get("keywords"), str) else position.get("keywords", [])
        }

        # Aday verisini hazirla
        candidate_data = {
            "ad_soyad": candidate.get("ad_soyad"),
            "email": candidate.get("email"),
            "lokasyon": candidate.get("lokasyon"),
            "toplam_deneyim_yil": candidate.get("toplam_deneyim_yil"),
            "egitim": candidate.get("egitim"),
            "bolum": candidate.get("bolum"),
            "universite": candidate.get("universite"),
            "mevcut_pozisyon": candidate.get("mevcut_pozisyon"),
            "mevcut_sirket": candidate.get("mevcut_sirket"),
            "teknik_beceriler": candidate.get("teknik_beceriler"),
            "sertifikalar": candidate.get("sertifikalar"),
            "diller": candidate.get("diller"),
            "deneyim_detay": candidate.get("deneyim_detay"),
            "deneyim_aciklama": candidate.get("deneyim_aciklama"),
            "cv_raw_text": candidate.get("cv_raw_text")
        }

        # AI degerlendirmesi yap
        test_start = time.time()
        try:
            response: CandidateEvaluationResponse = evaluate_candidate_sync(
                candidate_id=candidate_id,
                position_id=position_id,
                candidate_data=candidate_data,
                position_data=position_data
            )
            test_time = time.time() - test_start

            result = TestResult(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                position_id=position_id,
                position_name=position_name,
                score=response.total_score,
                eligible=response.eligible,
                gemini_score=response.gemini_score,
                hermes_score=response.hermes_score,
                score_difference=response.score_difference,
                claude_used=response.claude_used,
                consensus_method=response.consensus_method,
                success=response.success,
                error_message=response.error_message,
                response_time=round(test_time, 2),
                strengths=response.strengths[:3],
                weaknesses=response.weaknesses[:3],
                overall_assessment=response.overall_assessment[:200] if response.overall_assessment else "",
                elimination_reason=response.elimination_reason
            )

            # Sonuc goster
            status = "OK" if response.eligible else "NO"
            claude_flag = " [Claude]" if response.claude_used else ""
            print(f"         Skor: {response.total_score}/100 | {status} | G:{response.gemini_score} H:{response.hermes_score} ({test_time:.1f}s){claude_flag}")

        except Exception as e:
            test_time = time.time() - test_start
            result = TestResult(
                candidate_id=candidate_id,
                candidate_name=candidate_name,
                position_id=position_id,
                position_name=position_name,
                score=0,
                eligible=False,
                gemini_score=0,
                hermes_score=0,
                score_difference=0,
                claude_used=False,
                consensus_method="error",
                success=False,
                error_message=str(e),
                response_time=round(test_time, 2),
                strengths=[],
                weaknesses=[],
                overall_assessment="",
                elimination_reason=None
            )
            print(f"         HATA: {str(e)[:50]}")

        results.append(result)

    total_time = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"TAMAMLANDI: {len(results)} test, {total_time:.1f} saniye")
    print("=" * 70)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# RAPOR OLUSTURMA
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report(results: List[TestResult], total_time: float) -> str:
    """
    Test sonuclarindan rapor olusturur.

    Args:
        results: Test sonuclari
        total_time: Toplam sure

    Returns:
        str: Formatli rapor
    """
    # Istatistikler
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    eligible = [r for r in successful if r.eligible]
    not_eligible = [r for r in successful if not r.eligible]

    scores = [r.score for r in successful]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_result = max(successful, key=lambda x: x.score) if successful else None
    min_result = min(successful, key=lambda x: x.score) if successful else None

    # Skor dagilimi
    excellent = len([s for s in scores if s >= 80])
    good = len([s for s in scores if 60 <= s < 80])
    medium = len([s for s in scores if 40 <= s < 60])
    low = len([s for s in scores if s < 40])

    # Model uyumu
    concordant = len([r for r in successful if r.score_difference <= 15])
    discordant = len([r for r in successful if r.score_difference > 15])
    claude_used = len([r for r in successful if r.claude_used])

    # Maliyet tahmini
    gemini_cost = len(successful) * 0.00125
    hermes_cost = len(successful) * 0.0008
    claude_cost = claude_used * 0.015
    total_cost = gemini_cost + hermes_cost + claude_cost

    # Rapor olustur
    report = []
    report.append("")
    report.append("+" + "-" * 85 + "+")
    report.append("| SCORING V3 - TUM ESLESTMELER TESTI (DEMO)" + " " * 43 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append(f"| Test Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + " " * 52 + "|")
    report.append(f"| Toplam Test: {len(results):<5} | Basarili: {len(successful):<3} | Basarisiz: {len(failed):<3}" + " " * 35 + "|")
    report.append(f"| Toplam Sure: {total_time:.1f} saniye (~{total_time/60:.1f} dakika)" + " " * 43 + "|")
    report.append(f"| Tahmini Maliyet: ~${total_cost:.2f}" + " " * 57 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append("| OZET" + " " * 80 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append(f"| Ortalama Skor: {avg_score:.1f}/100" + " " * 62 + "|")
    if max_result:
        report.append(f"| En Yuksek: {max_result.score} ({max_result.candidate_name[:20]} -> {max_result.position_name[:25]})" + " " * 15 + "|")
    if min_result:
        report.append(f"| En Dusuk: {min_result.score} ({min_result.candidate_name[:20]} -> {min_result.position_name[:25]})" + " " * 16 + "|")
    report.append(f"| Eligible (Uygun): {len(eligible)} aday" + " " * 57 + "|")
    report.append(f"| Not Eligible: {len(not_eligible)} aday" + " " * 61 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append("| SKOR DAGILIMI" + " " * 71 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append(f"| [YESIL]  80-100 puan: {excellent:>3} eslestme (mukemmel)" + " " * 40 + "|")
    report.append(f"| [SARI]   60-79 puan:  {good:>3} eslestme (iyi)" + " " * 45 + "|")
    report.append(f"| [TURUNCU]40-59 puan:  {medium:>3} eslestme (orta)" + " " * 43 + "|")
    report.append(f"| [KIRMIZI]0-39 puan:   {low:>3} eslestme (dusuk - supheli)" + " " * 33 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append("| MODEL UYUMU" + " " * 73 + "|")
    report.append("+" + "-" * 85 + "+")
    report.append(f"| Gemini-Hermes fark <= 15: {concordant:>3} eslestme (uyumlu)" + " " * 36 + "|")
    report.append(f"| Gemini-Hermes fark > 15:  {discordant:>3} eslestme (Claude devrede)" + " " * 29 + "|")
    report.append(f"| Claude kullanilan: {claude_used:>3} eslestme" + " " * 49 + "|")
    report.append("+" + "-" * 85 + "+")

    # Detayli sonuclar (skordan dusukten yuksege)
    report.append("")
    report.append("DETAYLI SONUCLAR (Skordan dusukten yuksege):")
    report.append("+" + "-" * 4 + "+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 9 + "+" + "-" * 7 + "+" + "-" * 9 + "+")
    report.append("| #  | Aday                      | Pozisyon                          | Skor  | Eligible| G-H   | Claude? |")
    report.append("+" + "-" * 4 + "+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 9 + "+" + "-" * 7 + "+" + "-" * 9 + "+")

    sorted_results = sorted(results, key=lambda x: x.score)
    for i, r in enumerate(sorted_results, 1):
        eligible_str = "OK" if r.eligible else "NO"
        claude_str = "Evet" if r.claude_used else "Hayir"
        diff_str = f"{r.score_difference:>3}" if r.success else "ERR"
        report.append(f"| {i:>2} | {r.candidate_name[:25]:<25} | {r.position_name[:33]:<33} | {r.score:>5} | {eligible_str:^7} | {diff_str:>5} | {claude_str:^7} |")

    report.append("+" + "-" * 4 + "+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 9 + "+" + "-" * 7 + "+" + "-" * 9 + "+")

    # Supheli eslestmeler (Skor < 40)
    suspicious = [r for r in results if r.score < 40 and r.success]
    if suspicious:
        report.append("")
        report.append("SUPHELI ESLESTMELER (Skor < 40):")
        report.append("+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 50 + "+")
        report.append("| Aday                      | Pozisyon                          | Skor  | Sebep                                            |")
        report.append("+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 50 + "+")
        for r in suspicious:
            reason = r.elimination_reason or r.overall_assessment[:45] or "Dusuk puan"
            report.append(f"| {r.candidate_name[:25]:<25} | {r.position_name[:33]:<33} | {r.score:>5} | {reason[:48]:<48} |")
        report.append("+" + "-" * 27 + "+" + "-" * 35 + "+" + "-" * 7 + "+" + "-" * 50 + "+")

    return "\n".join(report)


def save_results(results: List[TestResult], report: str) -> str:
    """
    Sonuclari JSON dosyasina kaydeder.

    Args:
        results: Test sonuclari
        report: Rapor metni

    Returns:
        str: JSON dosya yolu
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(os.path.dirname(__file__), f"test_results_{timestamp}.json")

    data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "successful": len([r for r in results if r.success]),
        "failed": len([r for r in results if not r.success]),
        "results": [asdict(r) for r in results],
        "report": report
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSonuclar kaydedildi: {json_path}")
    return json_path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Ana fonksiyon"""
    print("\n" + "=" * 70)
    print("SCORING V3 - TUM ESLESTMELER TESTI")
    print("=" * 70)
    print(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # API key kontrolu
    print("\nAPI Key Kontrolu:")
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    hermes_ok = bool(os.environ.get("HERMES_API_KEY"))
    anthropic_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"  Gemini:    {'OK' if gemini_ok else 'YOK'}")
    print(f"  Hermes:    {'OK' if hermes_ok else 'YOK'}")
    print(f"  Anthropic: {'OK' if anthropic_ok else 'Opsiyonel'}")

    if not gemini_ok or not hermes_ok:
        print("\nHATA: Gemini ve Hermes API key'leri gerekli!")
        sys.exit(1)

    try:
        # 1. Veri cek
        data = fetch_data_from_server()

        # 2. Testleri calistir
        start_time = time.time()
        results = run_all_tests(data)
        total_time = time.time() - start_time

        # 3. Rapor olustur
        report = generate_report(results, total_time)
        print(report)

        # 4. Sonuclari kaydet
        json_path = save_results(results, report)

        print("\n" + "=" * 70)
        print("TEST TAMAMLANDI")
        print("=" * 70)

    except Exception as e:
        print(f"\nKRITIK HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
