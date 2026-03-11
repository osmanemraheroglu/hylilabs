"""
Gemini API Bağlantı Testi - CV Değerlendirme
"""
import os
import sys
import time
import json
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

GEMINI_MODEL = "gemini-2.5-pro"

def test_gemini_cv_evaluation():
    """Gemini CV değerlendirme testi"""

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("❌ HATA: GEMINI_API_KEY bulunamadı!")
        return False

    print(f"✅ API Key bulundu: {api_key[:10]}...")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    test_prompt = """
Sen Türkiye'de 15 yıllık deneyime sahip kıdemli bir İK Yöneticisisin.

ADAY:
- Ad: Test Aday
- Pozisyon: Python Developer (3 yıl)
- Beceriler: Python, Django, PostgreSQL

POZİSYON:
- Aranan: Senior Python Developer
- Gerekli: Python, FastAPI, 5+ yıl deneyim

Bu adayı 0-100 puan üzerinden değerlendir.
SADECE JSON döndür:
{
  "eligible": true/false,
  "score": 0-100,
  "reason": "kısa açıklama"
}
"""

    try:
        start_time = time.time()
        response = model.generate_content(test_prompt)
        elapsed = time.time() - start_time

        content = response.text
        usage = response.usage_metadata

        print(f"\n✅ Gemini 2.5 Pro bağlantısı BAŞARILI!")
        print(f"⏱️  Response time: {elapsed:.2f} saniye")
        print(f"📊 Token: {usage.prompt_token_count} input / {usage.candidates_token_count} output")

        # JSON parse dene
        try:
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            result = json.loads(json_str.strip())
            print(f"\n✅ JSON Parse BAŞARILI!")
            print(f"\n📋 Değerlendirme Sonucu:")
            print(f"   eligible: {result.get('eligible')}")
            print(f"   score: {result.get('score')}")
            print(f"   reason: {result.get('reason')}")
        except json.JSONDecodeError as e:
            print(f"\n⚠️ JSON Parse BAŞARISIZ: {e}")
            print(f"   Ham yanıt: {content}")

        return True

    except Exception as e:
        print(f"❌ HATA: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GEMINI 2.5 PRO CV DEĞERLENDİRME TESTİ")
    print("="*60 + "\n")

    test_gemini_cv_evaluation()

    print("\n" + "="*60)
    print("TEST TAMAMLANDI")
    print("="*60)
