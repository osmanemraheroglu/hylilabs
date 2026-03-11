"""
CV Intelligence - Aday Profil Analizi

CV yüklendiğinde tek seferlik AI analizi yapar.
Sonuç candidate_intelligence tablosuna kaydedilir.

Kullanım:
    from api.core.scoring_v3 import analyze_candidate_intelligence, analyze_sync

    # Async kullanım
    result = await analyze_candidate_intelligence(candidate_id, company_id, candidate_data)

    # Sync kullanım
    result = analyze_sync(candidate_id, company_id, candidate_data)

    if result.success:
        # database.save_candidate_intelligence(candidate_id, company_id, result.to_dict())
        print(f"Kariyer: {result.career_path}")
"""

import os
import re
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# aiohttp import (async HTTP client)
try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════════════════

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
API_TIMEOUT = 60  # saniye
MAX_RETRIES = 2
RETRY_DELAY = 2  # saniye


# ═══════════════════════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IntelligenceResult:
    """CV Intelligence analiz sonucu."""
    success: bool
    candidate_id: int
    company_id: int

    # Kariyer
    career_path: str = ""
    career_path_alternatives: List[str] = field(default_factory=list)
    specializations: List[str] = field(default_factory=list)

    # Sektör ve Seviye
    sectors: List[str] = field(default_factory=list)
    level: str = ""  # junior / mid / senior / lead
    experience_years: int = 0

    # Eğitim
    education_level: str = ""  # lise / on_lisans / lisans / yuksek_lisans / doktora
    education_field: str = ""

    # Lokasyon
    current_location: str = ""
    preferred_locations: List[str] = field(default_factory=list)
    relocation_willing: bool = True

    # Uygun Pozisyonlar (EN ÖNEMLİ - max 10)
    suitable_positions: List[str] = field(default_factory=list)

    # Yetkinlikler
    key_skills: List[Dict[str, str]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    languages: List[Dict[str, str]] = field(default_factory=list)

    # Meta
    raw_analysis: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Dict'e çevir (database.save_candidate_intelligence için uyumlu)"""
        return {
            "career_path": self.career_path,
            "career_path_alternatives": self.career_path_alternatives,
            "specializations": self.specializations,
            "sectors": self.sectors,
            "level": self.level,
            "experience_years": self.experience_years,
            "education_level": self.education_level,
            "education_field": self.education_field,
            "current_location": self.current_location,
            "preferred_locations": self.preferred_locations,
            "relocation_willing": self.relocation_willing,
            "suitable_positions": self.suitable_positions,
            "key_skills": self.key_skills,
            "certifications": self.certifications,
            "languages": self.languages,
            "raw_analysis": self.raw_analysis
        }


# ═══════════════════════════════════════════════════════════════════════════════
# JSON REPAIR
# ═══════════════════════════════════════════════════════════════════════════════

def _repair_json(text: str) -> str:
    """
    Bozuk JSON'u düzeltmeye çalışır.
    LLM'lerin ürettiği yaygın JSON hatalarını düzeltir.
    """
    if not text:
        return ""

    # 1. Markdown code block temizle
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # 2. Virgül eksikliği düzelt: "value"\n"key" → "value",\n"key"
    text = re.sub(r'"\s*\n\s*"', '",\n"', text)

    # 3. Sayı/bool sonrası virgül eksikliği: 85\n"key" → 85,\n"key"
    text = re.sub(r'(\d)\s*\n\s*"', r'\1,\n"', text)
    text = re.sub(r'(true|false|null)\s*\n\s*"', r'\1,\n"', text)

    # 4. Array sonrası virgül eksikliği: ]\n"key" → ],\n"key"
    text = re.sub(r'\]\s*\n\s*"', '],\n"', text)

    # 5. Object sonrası virgül eksikliği: }\n"key" → },\n"key"
    text = re.sub(r'\}\s*\n\s*"', '},\n"', text)

    # 6. Trailing comma kaldır: ,} → } ve ,] → ]
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # 7. Çift virgül kaldır: ,, → ,
    text = re.sub(r',\s*,', ',', text)

    # 8. Eksik kapanış parantezleri
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    if open_braces > 0:
        text += '}' * open_braces
    if open_brackets > 0:
        text += ']' * open_brackets

    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_intelligence_prompt(candidate_data: dict) -> str:
    """CV analizi için prompt oluşturur."""

    def safe_get(key: str, default: str = "Belirtilmemiş") -> str:
        val = candidate_data.get(key)
        if val is None or val == "":
            return default
        return str(val)

    prompt = f"""Sen bir İK uzmanısın. Aşağıdaki CV bilgilerini analiz et ve adayın profilini çıkar.

## ADAY BİLGİLERİ

Ad Soyad: {safe_get('ad_soyad')}
Mevcut Pozisyon: {safe_get('mevcut_pozisyon')}
Mevcut Şirket: {safe_get('mevcut_sirket')}
Toplam Deneyim: {safe_get('toplam_deneyim_yil', '0')} yıl
Lokasyon: {safe_get('lokasyon')}

Eğitim: {safe_get('egitim')}
Üniversite: {safe_get('universite')}
Bölüm: {safe_get('bolum')}

Teknik Beceriler: {safe_get('teknik_beceriler')}
Sertifikalar: {safe_get('sertifikalar')}
Diller: {safe_get('diller')}

Deneyim Detayı:
{safe_get('deneyim_detay')}

Deneyim Açıklaması:
{safe_get('deneyim_aciklama')}

## GÖREV

Bu adayın profilini analiz et ve aşağıdaki JSON formatında yanıt ver:

```json
{{
    "career_path": "Ana kariyer yolu (örn: Elektrik Mühendisi, Yazılım Geliştirici, Satış Uzmanı)",
    "career_path_alternatives": ["Alternatif kariyer yolu 1", "Alternatif kariyer yolu 2"],
    "specializations": ["Uzmanlık alanı 1", "Uzmanlık alanı 2"],
    "sectors": ["Sektör 1", "Sektör 2"],
    "level": "junior | mid | senior | lead",
    "experience_years": 5,
    "education_level": "lise | on_lisans | lisans | yuksek_lisans | doktora",
    "education_field": "Eğitim alanı",
    "current_location": "Şehir",
    "preferred_locations": ["Şehir 1", "Şehir 2"],
    "relocation_willing": true,
    "suitable_positions": [
        "Bu adaya en uygun pozisyon 1",
        "Bu adaya en uygun pozisyon 2",
        "Bu adaya en uygun pozisyon 3"
    ],
    "key_skills": [
        {{"skill": "Beceri adı", "level": "beginner | intermediate | advanced | expert"}}
    ],
    "certifications": ["Sertifika 1", "Sertifika 2"],
    "languages": [
        {{"lang": "Dil", "level": "A1 | A2 | B1 | B2 | C1 | C2 | Native"}}
    ]
}}
```

## KURALLAR

1. suitable_positions EN ÖNEMLİ alan - bu adayın gerçekten başarılı olabileceği pozisyonları listele (max 10)
2. Türkçe pozisyon isimleri kullan (örn: "Elektrik Mühendisi", "Proje Yöneticisi", "Satış Temsilcisi")
3. level için deneyim yılına göre karar ver: 0-2 yıl=junior, 3-5 yıl=mid, 6-10 yıl=senior, 10+ yıl=lead
4. Eğer bilgi eksikse, mevcut verilerden mantıklı çıkarımlar yap
5. SADECE JSON döndür, başka açıklama ekleme

JSON:"""

    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI API
# ═══════════════════════════════════════════════════════════════════════════════

async def call_gemini_for_intelligence(prompt: str, retry_count: int = 0) -> Optional[dict]:
    """
    Gemini API ile CV analizi yapar.
    Retry mekanizması ve JSON repair destekli.
    """
    if aiohttp is None:
        logger.error("aiohttp yüklü değil. pip install aiohttp")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY bulunamadı")
        return None

    url = f"{GEMINI_API_URL}?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Gemini API hatası: {response.status} - {error_text[:200]}")

                    # Retry için uygun mu?
                    if response.status in {500, 502, 503, 504, 529} and retry_count < MAX_RETRIES:
                        logger.warning(f"Gemini {response.status}, {RETRY_DELAY}s sonra retry ({retry_count + 1}/{MAX_RETRIES})...")
                        await asyncio.sleep(RETRY_DELAY)
                        return await call_gemini_for_intelligence(prompt, retry_count + 1)
                    return None

                data = await response.json()

                # Yanıtı parse et
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.error("Gemini yanıtında candidate yok")
                    return None

                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    logger.error("Gemini yanıtında parts yok")
                    return None

                text = parts[0].get("text", "")

                # JSON parse (repair destekli)
                try:
                    # İlk deneme - direkt parse
                    result = json.loads(text.strip())
                    return result
                except json.JSONDecodeError as first_error:
                    # JSON repair dene
                    logger.warning(f"JSON parse hatası, repair deneniyor: {first_error}")
                    repaired = _repair_json(text)
                    try:
                        result = json.loads(repaired)
                        logger.info("JSON repair başarılı")
                        return result
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parse hatası (repair sonrası): {e}")
                        logger.error(f"Raw text: {text[:500]}")

                        # Retry dene
                        if retry_count < MAX_RETRIES:
                            logger.warning(f"JSON hatası, retry ({retry_count + 1}/{MAX_RETRIES})...")
                            await asyncio.sleep(RETRY_DELAY)
                            return await call_gemini_for_intelligence(prompt, retry_count + 1)
                        return None

    except asyncio.TimeoutError:
        logger.error(f"Gemini API timeout ({API_TIMEOUT}s)")
        if retry_count < MAX_RETRIES:
            logger.warning(f"Timeout, retry ({retry_count + 1}/{MAX_RETRIES})...")
            await asyncio.sleep(RETRY_DELAY)
            return await call_gemini_for_intelligence(prompt, retry_count + 1)
        return None
    except Exception as e:
        logger.error(f"Gemini API çağrı hatası: {e}")
        if retry_count < MAX_RETRIES:
            logger.warning(f"Hata, retry ({retry_count + 1}/{MAX_RETRIES}): {e}")
            await asyncio.sleep(RETRY_DELAY)
            return await call_gemini_for_intelligence(prompt, retry_count + 1)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════════════════════

async def analyze_candidate_intelligence(
    candidate_id: int,
    company_id: int,
    candidate_data: dict
) -> IntelligenceResult:
    """
    Adayın CV'sini analiz eder ve IntelligenceResult döndürür.

    Args:
        candidate_id: Aday ID
        company_id: Şirket ID
        candidate_data: Aday bilgileri (ad_soyad, mevcut_pozisyon, deneyim_detay, vs.)

    Returns:
        IntelligenceResult: Analiz sonucu
    """
    start_time = time.time()

    logger.info(f"CV Intelligence analizi başlıyor: candidate_id={candidate_id}")

    # Prompt oluştur
    prompt = build_intelligence_prompt(candidate_data)

    # Gemini ile analiz
    result = await call_gemini_for_intelligence(prompt)

    elapsed = time.time() - start_time

    if not result:
        return IntelligenceResult(
            success=False,
            candidate_id=candidate_id,
            company_id=company_id,
            error_message="AI analizi başarısız oldu",
            processing_time=round(elapsed, 2)
        )

    # Sonucu IntelligenceResult'a dönüştür
    try:
        intelligence = IntelligenceResult(
            success=True,
            candidate_id=candidate_id,
            company_id=company_id,
            career_path=result.get("career_path", ""),
            career_path_alternatives=result.get("career_path_alternatives", []),
            specializations=result.get("specializations", []),
            sectors=result.get("sectors", []),
            level=result.get("level", "mid"),
            experience_years=int(result.get("experience_years", 0) or 0),
            education_level=result.get("education_level", ""),
            education_field=result.get("education_field", ""),
            current_location=result.get("current_location", ""),
            preferred_locations=result.get("preferred_locations", []),
            relocation_willing=result.get("relocation_willing", True),
            suitable_positions=result.get("suitable_positions", [])[:10],
            key_skills=result.get("key_skills", []),
            certifications=result.get("certifications", []),
            languages=result.get("languages", []),
            raw_analysis=result,
            processing_time=round(elapsed, 2)
        )

        logger.info(f"CV Intelligence tamamlandı: candidate_id={candidate_id}, "
                   f"career_path={intelligence.career_path}, süre={elapsed:.2f}s")
        return intelligence

    except Exception as e:
        logger.error(f"IntelligenceResult oluşturma hatası: {e}")
        return IntelligenceResult(
            success=False,
            candidate_id=candidate_id,
            company_id=company_id,
            error_message=f"Sonuç işleme hatası: {str(e)}",
            processing_time=round(elapsed, 2)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TOPLU ANALİZ
# ═══════════════════════════════════════════════════════════════════════════════

async def analyze_candidates_batch(
    candidates: List[dict],
    company_id: int,
    max_concurrent: int = 5
) -> List[IntelligenceResult]:
    """
    Birden fazla adayı paralel analiz eder.

    Args:
        candidates: Aday listesi (her biri dict olmalı, id alanı zorunlu)
        company_id: Şirket ID
        max_concurrent: Eşzamanlı istek sayısı

    Returns:
        IntelligenceResult listesi
    """
    if not candidates:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_with_semaphore(candidate: dict) -> IntelligenceResult:
        async with semaphore:
            candidate_id = candidate.get("id", 0)
            return await analyze_candidate_intelligence(candidate_id, company_id, candidate)

    tasks = [analyze_with_semaphore(c) for c in candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Exception'ları IntelligenceResult'a çevir
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append(IntelligenceResult(
                success=False,
                candidate_id=candidates[i].get("id", 0),
                company_id=company_id,
                error_message=str(result)
            ))
        else:
            processed_results.append(result)

    successful = sum(1 for r in processed_results if r.success)
    logger.info(f"Batch analiz tamamlandı: {successful}/{len(candidates)} başarılı")

    return processed_results


# ═══════════════════════════════════════════════════════════════════════════════
# SENKRON WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_sync(
    candidate_id: int,
    company_id: int,
    candidate_data: dict
) -> IntelligenceResult:
    """
    Senkron analyze fonksiyonu (FastAPI veya senkron kod için).

    Args:
        candidate_id: Aday ID
        company_id: Şirket ID
        candidate_data: Aday bilgileri

    Returns:
        IntelligenceResult: Analiz sonucu
    """
    return asyncio.run(analyze_candidate_intelligence(candidate_id, company_id, candidate_data))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("\n" + "=" * 77)
    print("CV Intelligence Modül Testi")
    print("=" * 77)

    print(f"\n📌 API Key Durumu:")
    print(f"   Gemini API Key: {'✅ Mevcut' if os.environ.get('GEMINI_API_KEY') else '❌ YOK'}")
    print(f"   aiohttp: {'✅ Yüklü' if aiohttp else '❌ Yüklü değil'}")

    print(f"\n📌 Ayarlar:")
    print(f"   API Timeout: {API_TIMEOUT}s")
    print(f"   Max Retry: {MAX_RETRIES}")
    print(f"   Retry Delay: {RETRY_DELAY}s")

    print("\n" + "=" * 77)
    print("Modül başarıyla yüklendi. Kullanım:")
    print("  from cv_intelligence import analyze_candidate_intelligence, analyze_sync")
    print("  from cv_intelligence import IntelligenceResult")
    print("=" * 77)
