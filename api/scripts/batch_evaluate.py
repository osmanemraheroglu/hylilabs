#!/usr/bin/env python3
"""
Batch V3 Degerlendirme Scripti
Tum degerlendirilmemis adaylari V3 ile degerlendirir.

Kullanim:
  python3 batch_evaluate.py --dry-run              # Simulasyon (kaydetmez)
  python3 batch_evaluate.py --limit 10             # Sadece 10 aday
  python3 batch_evaluate.py --fallback-hermes      # Sadece Hermes kullan
  python3 batch_evaluate.py --resume               # Kaldiqi yerden devam
  python3 batch_evaluate.py --verbose              # Detayli log
  python3 batch_evaluate.py                        # Tum adaylari isle

Ozellikler:
  - Retry mekanizmasi: Gemini 503 -> 30s bekle, max 3 deneme
  - Hermes fallback: 3 deneme basarisiz -> sadece Hermes skoru
  - Resume modu: progress.json ile kaldiqi yerden devam
  - Rapor: Basarili/basarisiz sayisi, ortalama skor
"""

import sys
import os

# Path setup
sys.path.insert(0, "/var/www/hylilabs/api")
sys.path.insert(0, "/var/www/hylilabs/api/core")
os.chdir("/var/www/hylilabs/api")

import argparse
import asyncio
import sqlite3
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# V3 imports
from core.scoring_v3 import evaluate_candidate, CandidateEvaluationResponse
from core.scoring_v3.data_integration import get_v2_data_for_prompt

# Constants
DB_PATH = "/var/www/hylilabs/api/data/talentflow.db"
SCRIPTS_DIR = "/var/www/hylilabs/api/scripts"
PROGRESS_FILE = os.path.join(SCRIPTS_DIR, "progress.json")
REPORTS_DIR = os.path.join(SCRIPTS_DIR, "reports")

MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds
RATE_LIMIT_DELAY = 2  # seconds between evaluations


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_connection():
    """SQLite baglantisi olusturur (WAL mode, busy_timeout)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def safe_get(row, key, default=""):
    """Row'dan guvenli deger alma."""
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, IndexError):
        return default


def get_pending_candidates(limit: Optional[int] = None, resume_from_id: Optional[int] = None) -> List[Dict]:
    """
    V3 degerlendirmesi olmayan adaylari getirir.
    Sadece keyword'lu havuzlardaki adaylar.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT DISTINCT
            c.id as candidate_id,
            cp.position_id,
            c.ad_soyad,
            dp.name as pool_name
        FROM candidates c
        JOIN candidate_positions cp ON cp.candidate_id = c.id
        JOIN department_pools dp ON cp.position_id = dp.id
        LEFT JOIN ai_evaluations ae ON c.id = ae.candidate_id
            AND ae.position_id = cp.position_id
            AND ae.evaluation_text LIKE '%"version"%'
        WHERE ae.id IS NULL
          AND dp.keywords IS NOT NULL
          AND dp.keywords != ''
          AND dp.keywords != '[]'
    """

    if resume_from_id:
        query += f" AND c.id > {resume_from_id}"

    query += " ORDER BY c.id ASC"

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "candidate_id": row["candidate_id"],
            "position_id": row["position_id"],
            "ad_soyad": row["ad_soyad"],
            "pool_name": row["pool_name"]
        }
        for row in rows
    ]


def get_candidate_data(candidate_id: int) -> Optional[Dict]:
    """Aday verilerini getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "ad_soyad": safe_get(row, "ad_soyad"),
        "email": safe_get(row, "email"),
        "telefon": safe_get(row, "telefon"),
        "lokasyon": safe_get(row, "lokasyon"),
        "egitim": safe_get(row, "egitim"),
        "universite": safe_get(row, "universite"),
        "bolum": safe_get(row, "bolum"),
        "toplam_deneyim_yil": safe_get(row, "toplam_deneyim_yil", 0),
        "mevcut_pozisyon": safe_get(row, "mevcut_pozisyon"),
        "mevcut_sirket": safe_get(row, "mevcut_sirket"),
        "deneyim_detay": safe_get(row, "deneyim_detay"),
        "deneyim_aciklama": safe_get(row, "deneyim_aciklama"),
        "teknik_beceriler": safe_get(row, "teknik_beceriler"),
        "diller": safe_get(row, "diller"),
        "sertifikalar": safe_get(row, "sertifikalar"),
        "ozet": ""
    }


def get_position_data(pool_id: int) -> Optional[Dict]:
    """Pozisyon verilerini getirir (V2 data dahil)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM department_pools WHERE id = ?", (pool_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    keywords = safe_get(row, "keywords", "[]")
    try:
        keywords = json.loads(keywords) if isinstance(keywords, str) else keywords
    except:
        keywords = []

    # V2 verilerini al
    v2_data = get_v2_data_for_prompt(pool_id)

    return {
        "name": safe_get(row, "name"),
        "lokasyon": safe_get(row, "lokasyon"),
        "gerekli_deneyim_yil": safe_get(row, "gerekli_deneyim_yil", 0),
        "gerekli_egitim": safe_get(row, "gerekli_egitim"),
        "keywords": keywords,
        "aranan_nitelikler": safe_get(row, "aranan_nitelikler"),
        "is_tanimi": safe_get(row, "is_tanimi"),
        "gorev_tanimi": safe_get(row, "gorev_tanimi"),
        "v2_data": v2_data
    }


def save_evaluation(candidate_id: int, position_id: int, result, company_id: int = 1):
    """Degerlendirmeyi DB'ye kaydeder."""
    conn = get_connection()
    cursor = conn.cursor()

    # FIX: layer_scores yerine mevcut alanlar kullaniliyor
    evaluation_data = {
        "version": "v3",
        "total_score": result.total_score,
        "eligible": result.eligible,
        "gemini_score": result.gemini_score,
        "hermes_score": result.hermes_score,
        "openai_score": getattr(result, 'openai_score', 0),
        "models_used": getattr(result, 'models_used', []),
        "consensus_method": result.consensus_method,
        "scores": getattr(result, 'scores', {}),
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "notes_for_hr": result.notes_for_hr,
        "overall_assessment": result.overall_assessment
    }

    cursor.execute("""
        INSERT INTO ai_evaluations (candidate_id, position_id, evaluation_text, v2_score, company_id, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (candidate_id, position_id, json.dumps(evaluation_data, ensure_ascii=False), result.total_score, company_id))

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_progress() -> Optional[Dict]:
    """Progress dosyasini yukler."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None


def save_progress(data: Dict):
    """Progress dosyasini kaydeder."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clear_progress():
    """Progress dosyasini siler."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)


# ═══════════════════════════════════════════════════════════════════════════════
# EVALUATION WITH RETRY
# ═══════════════════════════════════════════════════════════════════════════════

async def evaluate_with_retry(
    candidate_id: int,
    position_id: int,
    candidate_data: Dict,
    position_data: Dict,
    verbose: bool = False
) -> Tuple[Any, int, bool]:
    """
    Retry mekanizmali degerlendirme.

    Returns:
        (result, retry_count, gemini_503_occurred)
    """
    gemini_503_occurred = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await evaluate_candidate(
                candidate_id, position_id, candidate_data, position_data
            )

            if result.success:
                return result, attempt, gemini_503_occurred

            # Hata mesajinda 503 var mi?
            error_msg = str(result.error_message) if result.error_message else ""
            if "503" in error_msg:
                gemini_503_occurred = True
                if attempt < MAX_RETRIES:
                    if verbose:
                        print(f"      Gemini 503, {RETRY_DELAY}s bekleniyor... (deneme {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(RETRY_DELAY)
                    continue

            # Baska hata veya son deneme
            return result, attempt, gemini_503_occurred

        except Exception as e:
            error_str = str(e)
            if "503" in error_str:
                gemini_503_occurred = True
                if attempt < MAX_RETRIES:
                    if verbose:
                        print(f"      Gemini 503 exception, {RETRY_DELAY}s bekleniyor... (deneme {attempt}/{MAX_RETRIES})")
                    await asyncio.sleep(RETRY_DELAY)
                    continue

            # Son deneme veya farkli hata - basarisiz sonuc olustur
            if attempt == MAX_RETRIES:
                class FailedResult:
                    success = False
                    error_message = error_str
                    total_score = 0
                    eligible = False
                    gemini_score = 0
                    hermes_score = 0
                return FailedResult(), attempt, gemini_503_occurred

    # Buraya ulasilmamali
    class FailedResult:
        success = False
        error_message = "Max retry exceeded"
        total_score = 0
        eligible = False
        gemini_score = 0
        hermes_score = 0
    return FailedResult(), MAX_RETRIES, gemini_503_occurred


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BATCH PROCESS
# ═══════════════════════════════════════════════════════════════════════════════

async def run_batch(args):
    """Ana batch islemi."""

    print("=" * 60)
    print("BATCH V3 DEGERLENDIRME")
    print("=" * 60)
    print(f"Baslama: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mod: {'DRY-RUN (kaydetmez)' if args.dry_run else 'GERCEK'}")
    if args.limit:
        print(f"Limit: {args.limit} aday")
    if args.fallback_hermes:
        print(f"Fallback: Sadece Hermes")
    if args.resume:
        print(f"Resume: Kaldiqi yerden devam")
    print("-" * 60)

    # Resume kontrolu
    resume_from_id = None
    if args.resume:
        progress = load_progress()
        if progress and progress.get("last_processed"):
            resume_from_id = progress["last_processed"]["candidate_id"]
            print(f"Resume: ID {resume_from_id}'den devam ediliyor...")

    # Aday listesi
    candidates = get_pending_candidates(limit=args.limit, resume_from_id=resume_from_id)
    total = len(candidates)

    if total == 0:
        print("\nDegerlendirilecek aday bulunamadi!")
        return

    print(f"\nToplam islenecek: {total} aday")
    print("-" * 60)

    # Istatistikler
    stats = {
        "total": total,
        "processed": 0,
        "success": 0,
        "errors": 0,
        "gemini_503_count": 0,
        "scores": [],
        "eligible_count": 0,
        "error_list": []
    }

    start_time = time.time()

    # Reports klasoru
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Ana dongu
    for i, candidate in enumerate(candidates):
        cid = candidate["candidate_id"]
        pid = candidate["position_id"]
        name = candidate["ad_soyad"]
        pool = candidate["pool_name"]

        print(f"\n[{i+1}/{total}] {name} (ID:{cid}) -> {pool}")

        # Aday ve pozisyon verisi
        candidate_data = get_candidate_data(cid)
        if not candidate_data:
            print(f"  HATA: Aday verisi bulunamadi")
            stats["errors"] += 1
            stats["error_list"].append({"candidate_id": cid, "error": "Aday verisi yok"})
            continue

        position_data = get_position_data(pid)
        if not position_data:
            print(f"  HATA: Pozisyon verisi bulunamadi")
            stats["errors"] += 1
            stats["error_list"].append({"candidate_id": cid, "error": "Pozisyon verisi yok"})
            continue

        # Degerlendirme
        try:
            result, retries, gemini_503 = await evaluate_with_retry(
                cid, pid, candidate_data, position_data, args.verbose
            )

            if gemini_503:
                stats["gemini_503_count"] += 1

            if result.success:
                print(f"  BASARILI: Skor={result.total_score}, Eligible={result.eligible}")
                if args.verbose:
                    openai_score = getattr(result, 'openai_score', 0)
                    models_used = getattr(result, 'models_used', [])
                    print(f"    Gemini={result.gemini_score}, Hermes={result.hermes_score}, OpenAI={openai_score}")
                    print(f"    Models: {models_used}, Retries={retries}")
                    print(f"    Consensus: {result.consensus_method}, Claude used: {result.claude_used}")

                stats["success"] += 1
                stats["scores"].append(result.total_score)
                if result.eligible:
                    stats["eligible_count"] += 1

                # Kaydet (dry-run degilse)
                if not args.dry_run:
                    save_evaluation(cid, pid, result)
            else:
                error_msg = result.error_message if hasattr(result, 'error_message') else "Bilinmeyen hata"
                print(f"  HATA: {error_msg}")
                stats["errors"] += 1
                stats["error_list"].append({
                    "candidate_id": cid,
                    "position_id": pid,
                    "error": error_msg
                })

        except Exception as e:
            print(f"  EXCEPTION: {str(e)}")
            stats["errors"] += 1
            stats["error_list"].append({
                "candidate_id": cid,
                "position_id": pid,
                "error": str(e)
            })

        stats["processed"] += 1

        # Progress kaydet
        if not args.dry_run:
            save_progress({
                "started_at": datetime.now().isoformat(),
                "last_processed": {
                    "candidate_id": cid,
                    "position_id": pid,
                    "index": i
                },
                "stats": {
                    "total": total,
                    "processed": stats["processed"],
                    "success": stats["success"],
                    "errors": stats["errors"],
                    "gemini_503_count": stats["gemini_503_count"]
                }
            })

        # Rate limiting
        if i < total - 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)

    # Bitis
    elapsed = time.time() - start_time
    avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
    eligible_pct = (stats["eligible_count"] / stats["success"] * 100) if stats["success"] else 0

    # Rapor
    print("\n" + "=" * 60)
    print("BATCH DEGERLENDIRME RAPORU")
    print("=" * 60)
    print(f"Toplam islenen: {stats['processed']}")
    print(f"Basarili: {stats['success']}")
    print(f"Hata: {stats['errors']}")
    print(f"Gemini 503 hatasi: {stats['gemini_503_count']}")
    print(f"Ortalama skor: {avg_score:.1f}")
    print(f"Eligible: {stats['eligible_count']} ({eligible_pct:.0f}%)")
    print(f"Sure: {elapsed/60:.1f} dakika")
    print("=" * 60)

    # Rapor dosyasi kaydet
    report_file = os.path.join(REPORTS_DIR, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    report_data = {
        "completed_at": datetime.now().isoformat(),
        "mode": "dry-run" if args.dry_run else "real",
        "stats": stats,
        "avg_score": avg_score,
        "eligible_pct": eligible_pct,
        "elapsed_seconds": elapsed,
        "errors": stats["error_list"]
    }

    if not args.dry_run:
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"\nRapor kaydedildi: {report_file}")

        # Basarili tamamlandiysa progress sil
        if stats["errors"] == 0:
            clear_progress()
            print("Progress temizlendi.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Batch V3 Degerlendirme Scripti",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python3 batch_evaluate.py --dry-run              # Simulasyon
  python3 batch_evaluate.py --limit 10             # Ilk 10 aday
  python3 batch_evaluate.py --resume               # Kaldiqi yerden devam
  python3 batch_evaluate.py --verbose              # Detayli log
        """
    )

    parser.add_argument("--dry-run", action="store_true",
                        help="Simulasyon modu (DB'ye kaydetmez)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Islenecek maksimum aday sayisi")
    parser.add_argument("--fallback-hermes", action="store_true",
                        help="Gemini atla, sadece Hermes kullan")
    parser.add_argument("--resume", action="store_true",
                        help="progress.json'dan kaldiqi yerden devam et")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Detayli log")

    args = parser.parse_args()

    # Async calistir
    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
