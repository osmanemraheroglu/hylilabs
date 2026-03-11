"""
Hermes 4 API Bağlantı Testi
Nous Research - hermes-4-70b
"""
import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

HERMES_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
HERMES_MODEL = "Hermes-4-70B"

def test_hermes_cv_evaluation():
    """Hermes 4 CV değerlendirme testi"""

    api_key = os.environ.get("HERMES_API_KEY")

    if not api_key:
        print("❌ HATA: HERMES_API_KEY bulunamadı!")
        return False

    print(f"✅ API Key bulundu: {api_key[:10]}...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

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

    payload = {
        "model": HERMES_MODEL,
        "messages": [
            {"role": "user", "content": test_prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.3
    }

    try:
        start_time = time.time()
        response = requests.post(HERMES_API_URL, headers=headers, json=payload, timeout=90)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            print(f"\n✅ Hermes 4 bağlantısı BAŞARILI!")
            print(f"⏱️  Response time: {elapsed:.2f} saniye")
            print(f"📊 Token: {usage.get('prompt_tokens', '?')} input / {usage.get('completion_tokens', '?')} output")

            # JSON parse dene
            try:
                # JSON bloğunu çıkar
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
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ HATA: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("HERMES 4 CV DEĞERLENDİRME TESTİ")
    print("="*60 + "\n")

    test_hermes_cv_evaluation()

    print("\n" + "="*60)
    print("TEST TAMAMLANDI")
    print("="*60)
