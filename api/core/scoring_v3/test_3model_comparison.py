"""
3 Model Karşılaştırma Testi
Gemini 2.5 Pro vs Hermes 4 70B vs Claude API

Gerçek CV + Pozisyon verisi ile test
"""
import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

# API Ayarları
GEMINI_MODEL = "gemini-2.5-pro"
HERMES_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
HERMES_MODEL = "Hermes-4-70B"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

# Gerçek Pozisyon Verisi
POSITION_DATA = {
    "title": "Gas Groups System Integration Specialist",
    "company": "AKSA",
    "location": "Tekirdağ",
    "experience_years": 3,
    "education": "Lisans",
    "keywords": ["scada", "sincal", "e-plan", "solidworks", "3d", "microsoft project",
                 "pss-e", "tasarım", "proje", "digsilent powerfactory", "autocad", "etap", "cad"],
    "description": """Aranan Nitelikler:
• Tekirdağ ve/veya İstanbul'un batı ilçelerinde ikamet etmek
• Elektrik Mühendisliği Fakültesi mezunu olmak
• Benzer pozisyonlarda minimum 3 yıl deneyim
• Yazılı ve sözlü mükemmel İngilizce bilgisi
• Microsoft Project, E-PLAN, SolidWorks, AutoCAD ve Microsoft Office uygulamalarında güçlü bilgi
• ETAP, PSS-E, Sincal veya DigSilent PowerFactory deneyimi tercih edilir
• Bilgisayar destekli tasarım (CAD), 3D ve 2D modelleme deneyimi
• Gaz jeneratör tasarımı, prototip montajı ve test konularında kapsamlı bilgi
• Güçlü analitik düşünme ve sonuç odaklı yaklaşım
• Mükemmel iletişim becerileri ve üst düzey raporlama yetenekleri
• Erkek adaylar için askerlik yükümlülüğünün tamamlanmış olması

İş Tanımı:
• Proje ve ürünler için sistem entegrasyon gereksinimlerini yönetmek ve gerçekleştirmek
• Elektriksel tasarım için gerekli sinyal listelerini paylaşmak
• Başarılı proje tamamlanmasını sağlamak
• Gaz jeneratör güç sistemlerinin otomasyon/SCADA sistemleri için sinyal listeleri hazırlamak
• Tasarım ekiplerine otomasyon altyapı planlamasında yardımcı olmak
• Uygun otomasyon topolojileri geliştirmek"""
}

# Gerçek Aday Verisi
CANDIDATE_DATA = {
    "name": "Emir Kaan Yıldız",
    "email": "emir.yildiz.eng@gmail.com",
    "location": "Tekirdağ",
    "experience_years": 10,
    "education": "Yüksek Lisans (Elektrik ve Elektronik Mühendisliği)",
    "current_position": "Electrical & Instrument Manager",
    "current_company": "Khor Mor Gas Field Expansion Project",
    "skills": ["Gaz jeneratör sistem entegrasyonu", "PLC ve SCADA programlama", "FAT ve SAT",
               "ETAP güç sistem simülasyonu", "Sinyal listesi hazırlama",
               "Jeneratör prototip test ve devreye alma", "AutoCAD", "SolidWorks",
               "E-PLAN", "MS Project", "Güç sistemleri", "Sistem entegrasyonu",
               "QA/QC yönetimi", "Multidisipliner sistem koordinasyonu"],
    "languages": "İngilizce (İleri)",
    "cv_summary": """Electrical Engineer with 10+ years experience in power plants, refinery and industrial facilities.
Extensive background in gas turbine power systems, generator integration, SCADA automation,
QA/QC management and multidisciplinary system coordination. Experienced in signal list
preparation, PLC-SCADA integration, FAT and SAT execution and prototype system testing.

PROFESSIONAL EXPERIENCE:
• Electrical & Instrument Manager - Khor Mor Gas Field Expansion Project (Iraq)
  - Managed electrical and instrumentation integration works of gas processing systems
  - Supervised gas generator auxiliary systems and pressure regulation equipment installation
  - Ensured compatibility between mechanical, electrical and automation components
  - Conducted FAT and SAT testing for generator and automation systems
  - Prepared signal lists and coordinated with automation teams

• Electrical & Instrument QC Chief - Combined Cycle Power Plant Project
  - Generator set integration and transformer coordination
  - ETAP based power system analysis and short circuit calculations
  - AutoCAD and E-PLAN electrical design review
  - MS Project planning and reporting
  - SCADA and PLC coordination during commissioning

EDUCATION:
BSc Electrical Engineering - Kocaeli University (2014)
MSc Electrical & Electronics Engineering - 2023"""
}

# Değerlendirme Prompt'u
EVALUATION_PROMPT = f"""Sen Türkiye'de 15 yıllık deneyime sahip kıdemli bir İK Yöneticisisin.
Aşağıdaki aday ve pozisyon bilgilerini değerlendir.

═══════════════════════════════════════════════════════════════════════════════
POZİSYON BİLGİLERİ
═══════════════════════════════════════════════════════════════════════════════
Pozisyon: {POSITION_DATA['title']}
Şirket: {POSITION_DATA['company']}
Lokasyon: {POSITION_DATA['location']}
Gerekli Deneyim: {POSITION_DATA['experience_years']} yıl
Gerekli Eğitim: {POSITION_DATA['education']}
Anahtar Kelimeler: {', '.join(POSITION_DATA['keywords'])}

{POSITION_DATA['description']}

═══════════════════════════════════════════════════════════════════════════════
ADAY BİLGİLERİ
═══════════════════════════════════════════════════════════════════════════════
Ad Soyad: {CANDIDATE_DATA['name']}
Lokasyon: {CANDIDATE_DATA['location']}
Toplam Deneyim: {CANDIDATE_DATA['experience_years']} yıl
Eğitim: {CANDIDATE_DATA['education']}
Mevcut Pozisyon: {CANDIDATE_DATA['current_position']}
Mevcut Şirket: {CANDIDATE_DATA['current_company']}
Teknik Beceriler: {', '.join(CANDIDATE_DATA['skills'])}
Diller: {CANDIDATE_DATA['languages']}

CV ÖZETİ:
{CANDIDATE_DATA['cv_summary']}

═══════════════════════════════════════════════════════════════════════════════
DEĞERLENDİRME TALİMATI
═══════════════════════════════════════════════════════════════════════════════
Bu adayı pozisyona uygunluk açısından 0-100 puan üzerinden değerlendir.

Değerlendirme kriterleri:
1. Teknik beceri eşleşmesi (pozisyon keywords vs aday skills)
2. Deneyim yılı uyumu
3. Eğitim seviyesi uyumu
4. Lokasyon uyumu
5. Sektör/alan deneyimi

SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir şey yazma:
{{
  "eligible": true/false,
  "score": 0-100,
  "reason": "Türkçe kısa açıklama (max 100 kelime)",
  "matched_skills": ["eşleşen beceriler listesi"],
  "missing_skills": ["eksik beceriler listesi"]
}}
"""


def parse_json_response(content: str) -> dict:
    """JSON yanıtı parse et"""
    try:
        # Markdown code block temizle
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        return json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse hatası: {e}", "raw": content[:500]}


def test_gemini():
    """Gemini 2.5 Pro testi"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY bulunamadı"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    try:
        start_time = time.time()
        response = model.generate_content(EVALUATION_PROMPT)
        elapsed = time.time() - start_time

        content = response.text
        usage = response.usage_metadata

        result = parse_json_response(content)
        result["_meta"] = {
            "model": GEMINI_MODEL,
            "response_time": round(elapsed, 2),
            "tokens_input": usage.prompt_token_count,
            "tokens_output": usage.candidates_token_count
        }
        return result

    except Exception as e:
        return {"error": str(e)}


def test_hermes():
    """Hermes 4 70B testi"""
    api_key = os.environ.get("HERMES_API_KEY")
    if not api_key:
        return {"error": "HERMES_API_KEY bulunamadı"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": HERMES_MODEL,
        "messages": [{"role": "user", "content": EVALUATION_PROMPT}],
        "max_tokens": 2048,
        "temperature": 0.3
    }

    try:
        start_time = time.time()
        response = requests.post(HERMES_API_URL, headers=headers, json=payload, timeout=120)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            result = parse_json_response(content)
            result["_meta"] = {
                "model": HERMES_MODEL,
                "response_time": round(elapsed, 2),
                "tokens_input": usage.get("prompt_tokens", "?"),
                "tokens_output": usage.get("completion_tokens", "?")
            }
            return result
        else:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}

    except Exception as e:
        return {"error": str(e)}


def test_claude():
    """Claude API testi"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY bulunamadı", "_note": "Manuel değerlendirme gerekli"}

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": EVALUATION_PROMPT}]
    }

    try:
        start_time = time.time()
        response = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=120)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            content = data["content"][0]["text"]
            usage = data.get("usage", {})

            result = parse_json_response(content)
            result["_meta"] = {
                "model": CLAUDE_MODEL,
                "response_time": round(elapsed, 2),
                "tokens_input": usage.get("input_tokens", "?"),
                "tokens_output": usage.get("output_tokens", "?")
            }
            return result
        else:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}

    except Exception as e:
        return {"error": str(e)}


def print_comparison_table(gemini_result, hermes_result, claude_result):
    """Karşılaştırma tablosu yazdır"""

    def get_value(result, key, default="N/A"):
        if "error" in result:
            return f"HATA"
        return result.get(key, default)

    def get_meta(result, key, default="?"):
        if "error" in result or "_meta" not in result:
            return default
        return result["_meta"].get(key, default)

    print("\n")
    print("┌" + "─" * 77 + "┐")
    print("│" + " 3 MODEL KARŞILAŞTIRMA - Emir Kaan Yıldız".ljust(77) + "│")
    print("├" + "─" * 15 + "┬" + "─" * 20 + "┬" + "─" * 20 + "┬" + "─" * 20 + "┤")
    print("│" + " Metrik".ljust(15) + "│" + " Gemini 2.5 Pro".ljust(20) + "│" + " Hermes 4 70B".ljust(20) + "│" + " Claude 3.5 Sonnet".ljust(20) + "│")
    print("├" + "─" * 15 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┤")

    # eligible
    g_elig = "✓ Evet" if get_value(gemini_result, "eligible") == True else ("✗ Hayır" if get_value(gemini_result, "eligible") == False else get_value(gemini_result, "eligible"))
    h_elig = "✓ Evet" if get_value(hermes_result, "eligible") == True else ("✗ Hayır" if get_value(hermes_result, "eligible") == False else get_value(hermes_result, "eligible"))
    c_elig = "✓ Evet" if get_value(claude_result, "eligible") == True else ("✗ Hayır" if get_value(claude_result, "eligible") == False else get_value(claude_result, "eligible"))
    print("│" + " eligible".ljust(15) + "│" + f" {g_elig}".ljust(20) + "│" + f" {h_elig}".ljust(20) + "│" + f" {c_elig}".ljust(20) + "│")

    # score
    g_score = get_value(gemini_result, "score")
    h_score = get_value(hermes_result, "score")
    c_score = get_value(claude_result, "score")
    print("│" + " score".ljust(15) + "│" + f" {g_score}".ljust(20) + "│" + f" {h_score}".ljust(20) + "│" + f" {c_score}".ljust(20) + "│")

    # response time
    g_time = f"{get_meta(gemini_result, 'response_time')} sn"
    h_time = f"{get_meta(hermes_result, 'response_time')} sn"
    c_time = f"{get_meta(claude_result, 'response_time')} sn"
    print("│" + " Response Time".ljust(15) + "│" + f" {g_time}".ljust(20) + "│" + f" {h_time}".ljust(20) + "│" + f" {c_time}".ljust(20) + "│")

    # tokens
    g_tok = f"{get_meta(gemini_result, 'tokens_input')}/{get_meta(gemini_result, 'tokens_output')}"
    h_tok = f"{get_meta(hermes_result, 'tokens_input')}/{get_meta(hermes_result, 'tokens_output')}"
    c_tok = f"{get_meta(claude_result, 'tokens_input')}/{get_meta(claude_result, 'tokens_output')}"
    print("│" + " Tokens (I/O)".ljust(15) + "│" + f" {g_tok}".ljust(20) + "│" + f" {h_tok}".ljust(20) + "│" + f" {c_tok}".ljust(20) + "│")

    print("└" + "─" * 15 + "┴" + "─" * 20 + "┴" + "─" * 20 + "┴" + "─" * 20 + "┘")

    # Reason detayları
    print("\n" + "=" * 77)
    print("REASON DETAYLARI")
    print("=" * 77)

    print(f"\n📊 Gemini 2.5 Pro:")
    if "error" in gemini_result:
        print(f"   HATA: {gemini_result['error']}")
    else:
        print(f"   {get_value(gemini_result, 'reason', 'N/A')}")
        matched = get_value(gemini_result, 'matched_skills', [])
        if matched and matched != "N/A":
            print(f"   ✓ Eşleşen: {', '.join(matched[:5])}{'...' if len(matched) > 5 else ''}")
        missing = get_value(gemini_result, 'missing_skills', [])
        if missing and missing != "N/A":
            print(f"   ✗ Eksik: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

    print(f"\n📊 Hermes 4 70B:")
    if "error" in hermes_result:
        print(f"   HATA: {hermes_result['error']}")
    else:
        print(f"   {get_value(hermes_result, 'reason', 'N/A')}")
        matched = get_value(hermes_result, 'matched_skills', [])
        if matched and matched != "N/A":
            print(f"   ✓ Eşleşen: {', '.join(matched[:5])}{'...' if len(matched) > 5 else ''}")
        missing = get_value(hermes_result, 'missing_skills', [])
        if missing and missing != "N/A":
            print(f"   ✗ Eksik: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

    print(f"\n📊 Claude 3.5 Sonnet:")
    if "error" in claude_result:
        print(f"   HATA: {claude_result['error']}")
        if "_note" in claude_result:
            print(f"   NOT: {claude_result['_note']}")
    else:
        print(f"   {get_value(claude_result, 'reason', 'N/A')}")
        matched = get_value(claude_result, 'matched_skills', [])
        if matched and matched != "N/A":
            print(f"   ✓ Eşleşen: {', '.join(matched[:5])}{'...' if len(matched) > 5 else ''}")
        missing = get_value(claude_result, 'missing_skills', [])
        if missing and missing != "N/A":
            print(f"   ✗ Eksik: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}")

    print("\n" + "=" * 77)


if __name__ == "__main__":
    print("\n" + "=" * 77)
    print("3 MODEL KARŞILAŞTIRMA TESTİ")
    print("Pozisyon: Gas Groups System Integration Specialist")
    print("Aday: Emir Kaan Yıldız")
    print("=" * 77)

    print("\n🔄 Gemini 2.5 Pro test ediliyor...")
    gemini_result = test_gemini()
    print(f"   {'✅ Tamamlandı' if 'error' not in gemini_result else '❌ Hata'}")

    print("\n🔄 Hermes 4 70B test ediliyor...")
    hermes_result = test_hermes()
    print(f"   {'✅ Tamamlandı' if 'error' not in hermes_result else '❌ Hata'}")

    print("\n🔄 Claude 3.5 Sonnet test ediliyor...")
    claude_result = test_claude()
    print(f"   {'✅ Tamamlandı' if 'error' not in claude_result else '❌ Hata'}")

    # Karşılaştırma tablosu
    print_comparison_table(gemini_result, hermes_result, claude_result)

    # JSON çıktı kaydet
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "position": POSITION_DATA["title"],
        "candidate": CANDIDATE_DATA["name"],
        "results": {
            "gemini": gemini_result,
            "hermes": hermes_result,
            "claude": claude_result
        }
    }

    with open("/Users/emraheroglu/hylilabs/api/core/scoring_v3/comparison_result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n📁 Sonuçlar kaydedildi: comparison_result.json")
    print("\n" + "=" * 77)
    print("TEST TAMAMLANDI")
    print("=" * 77)
