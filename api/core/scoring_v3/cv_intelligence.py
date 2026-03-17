"""
CV Intelligence - Aday Profil Analizi (Fallback Destekli)

CV yuklendiginde tek seferlik AI analizi yapar.
Sonuc candidate_intelligence tablosuna kaydedilir.

FALLBACK ZINCIRI:
1. Gemini (PRIMARY)
2. Hermes (FALLBACK 1)
3. OpenAI (FALLBACK 2)
4. Claude (FALLBACK 3 - SON CARE)
"""

import os
import re
import json
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

try:
    import aiohttp
except ImportError:
    aiohttp = None

logger = logging.getLogger(__name__)

# API URLs
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
HERMES_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# Model Isimleri
HERMES_MODEL = "Hermes-4-70B"
OPENAI_MODEL = "gpt-4o"
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Timeout ve Retry
API_TIMEOUT = 45
MAX_RETRIES = 1
RETRY_DELAY = 2
RETRY_STATUS_CODES = {500, 502, 503, 504, 529}


@dataclass
class IntelligenceResult:
    """CV Intelligence analiz sonucu."""
    success: bool
    candidate_id: int
    company_id: int
    career_path: str = ""
    career_path_alternatives: List[str] = field(default_factory=list)
    specializations: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)
    level: str = ""
    experience_years: int = 0
    education_level: str = ""
    education_field: str = ""
    current_location: str = ""
    preferred_locations: List[str] = field(default_factory=list)
    relocation_willing: bool = True
    suitable_positions: List[str] = field(default_factory=list)
    key_skills: List[Dict[str, str]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    languages: List[Dict[str, str]] = field(default_factory=list)
    raw_analysis: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    processing_time: float = 0.0
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
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
            "raw_analysis": self.raw_analysis,
            "model_used": self.model_used
        }


def _repair_json(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    text = re.sub(r'"\s*\n\s*"', '",\n"', text)
    text = re.sub(r'(\d)\s*\n\s*"', r'\1,\n"', text)
    text = re.sub(r'(true|false|null)\s*\n\s*"', r'\1,\n"', text)
    text = re.sub(r'\]\s*\n\s*"', '],\n"', text)
    text = re.sub(r'\}\s*\n\s*"', '},\n"', text)
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    text = re.sub(r',\s*,', ',', text)
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0:
        text += '}' * open_braces
    if open_brackets > 0:
        text += ']' * open_brackets
    return text.strip()


def _parse_json_response(text: str, model_name: str) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"{model_name} JSON parse hatasi, repair deneniyor: {e}")
        repaired = _repair_json(text)
        try:
            result = json.loads(repaired)
            logger.info(f"{model_name} JSON repair basarili")
            return result
        except json.JSONDecodeError as e2:
            logger.error(f"{model_name} JSON parse hatasi (repair sonrasi): {e2}")
            return None


def build_intelligence_prompt(candidate_data: dict) -> str:
    def safe_get(key: str, default: str = "Belirtilmemis") -> str:
        val = candidate_data.get(key)
        if val is None or val == "":
            return default
        return str(val)

    json_template = '''
{
    "career_path": "Ana kariyer yolu",
    "career_path_alternatives": ["Alternatif 1", "Alternatif 2"],
    "specializations": ["Uzmanlik 1", "Uzmanlik 2"],
    "sectors": ["Sektor 1", "Sektor 2"],
    "level": "junior | mid | senior | lead",
    "experience_years": 5,
    "education_level": "lise | on_lisans | lisans | yuksek_lisans | doktora",
    "education_field": "Egitim alani",
    "current_location": "Sehir",
    "preferred_locations": ["Sehir 1", "Sehir 2"],
    "relocation_willing": true,
    "suitable_positions": ["Uygun pozisyon 1", "Uygun pozisyon 2", "Uygun pozisyon 3"],
    "key_skills": [{"skill": "Beceri", "level": "advanced"}],
    "certifications": ["Sertifika 1"],
    "languages": [{"lang": "Dil", "level": "B2"}]
}
'''

    prompt = f"""Sen bir IK uzmanisin. Asagidaki CV bilgilerini analiz et ve adayin profilini cikar.

## ADAY BILGILERI

Ad Soyad: {safe_get("ad_soyad")}
Mevcut Pozisyon: {safe_get("mevcut_pozisyon")}
Mevcut Sirket: {safe_get("mevcut_sirket")}
Toplam Deneyim: {safe_get("toplam_deneyim_yil", "0")} yil
Lokasyon: {safe_get("lokasyon")}

Egitim: {safe_get("egitim")}
Universite: {safe_get("universite")}
Bolum: {safe_get("bolum")}

Teknik Beceriler: {safe_get("teknik_beceriler")}
Sertifikalar: {safe_get("sertifikalar")}
Diller: {safe_get("diller")}

Deneyim Detayi:
{safe_get("deneyim_detay")}

Deneyim Aciklamasi:
{safe_get("deneyim_aciklama")}

## GOREV

Bu adayin profilini analiz et ve asagidaki JSON formatinda yanit ver:
{json_template}

KURALLAR:
1. suitable_positions EN ONEMLI alan - max 10 pozisyon
2. Turkce pozisyon isimleri kullan
3. SADECE JSON dondur, baska aciklama ekleme

JSON:"""
    return prompt


async def call_gemini_for_intelligence(prompt: str, retry_count: int = 0) -> Optional[dict]:
    if aiohttp is None:
        logger.error("aiohttp yuklu degil")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY bulunamadi")
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
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Gemini API hatasi: {response.status} - {error_text[:200]}")
                    if response.status in RETRY_STATUS_CODES and retry_count < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        return await call_gemini_for_intelligence(prompt, retry_count + 1)
                    return None

                data = await response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return None
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    return None
                text = parts[0].get("text", "")
                return _parse_json_response(text, "Gemini")

    except asyncio.TimeoutError:
        logger.error(f"Gemini API timeout ({API_TIMEOUT}s)")
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_gemini_for_intelligence(prompt, retry_count + 1)
        return None
    except Exception as e:
        logger.error(f"Gemini API cagri hatasi: {e}")
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_gemini_for_intelligence(prompt, retry_count + 1)
        return None


async def call_hermes_for_intelligence(prompt: str, retry_count: int = 0) -> Optional[dict]:
    if aiohttp is None:
        return None

    api_key = os.getenv("HERMES_API_KEY")
    if not api_key:
        logger.error("HERMES_API_KEY bulunamadi")
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": HERMES_MODEL,
        "messages": [
            {"role": "system", "content": "Sen bir IK uzmanisin. Yanitlarini SADECE JSON formatinda ver."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
        "temperature": 0.3
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HERMES_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Hermes API hatasi: {response.status} - {error_text[:200]}")
                    if response.status in RETRY_STATUS_CODES and retry_count < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        return await call_hermes_for_intelligence(prompt, retry_count + 1)
                    return None

                data = await response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return _parse_json_response(content, "Hermes")

    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_hermes_for_intelligence(prompt, retry_count + 1)
        return None
    except Exception as e:
        logger.error(f"Hermes API cagri hatasi: {e}")
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_hermes_for_intelligence(prompt, retry_count + 1)
        return None


async def call_openai_for_intelligence(prompt: str, retry_count: int = 0) -> Optional[dict]:
    if aiohttp is None:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY bulunamadi")
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept-Encoding": "identity"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "Sen bir IK uzmanisin. Yanitlarini SADECE JSON formatinda ver."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENAI_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI API hatasi: {response.status} - {error_text[:200]}")
                    if response.status in RETRY_STATUS_CODES and retry_count < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        return await call_openai_for_intelligence(prompt, retry_count + 1)
                    return None

                data = await response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return _parse_json_response(content, "OpenAI")

    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_openai_for_intelligence(prompt, retry_count + 1)
        return None
    except Exception as e:
        logger.error(f"OpenAI API cagri hatasi: {e}")
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_openai_for_intelligence(prompt, retry_count + 1)
        return None


async def call_claude_for_intelligence(prompt: str, retry_count: int = 0) -> Optional[dict]:
    if aiohttp is None:
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY bulunamadi")
        return None

    headers = {"x-api-key": api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
        "system": "Sen bir IK uzmanisin. Yanitlarini SADECE JSON formatinda ver, baska aciklama ekleme."
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Claude API hatasi: {response.status} - {error_text[:200]}")
                    if response.status in RETRY_STATUS_CODES and retry_count < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        return await call_claude_for_intelligence(prompt, retry_count + 1)
                    return None

                data = await response.json()
                content_blocks = data.get("content", [])
                if not content_blocks:
                    return None
                text = content_blocks[0].get("text", "")
                return _parse_json_response(text, "Claude")

    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_claude_for_intelligence(prompt, retry_count + 1)
        return None
    except Exception as e:
        logger.error(f"Claude API cagri hatasi: {e}")
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await call_claude_for_intelligence(prompt, retry_count + 1)
        return None


async def call_ai_with_fallback(prompt: str) -> tuple:
    """
    CV Intelligence icin fallback zinciri.
    Sira: Gemini -> Hermes -> OpenAI -> Claude
    """
    # 1. Gemini (PRIMARY)
    logger.info("CV Intelligence: Gemini deneniyor...")
    result = await call_gemini_for_intelligence(prompt)
    if result:
        logger.info("CV Intelligence: Gemini basarili")
        return result, "Gemini"

    # 2. Hermes (FALLBACK 1)
    logger.warning("CV Intelligence: Gemini basarisiz, Hermes deneniyor...")
    result = await call_hermes_for_intelligence(prompt)
    if result:
        logger.info("CV Intelligence: Hermes basarili")
        return result, "Hermes"

    # 3. OpenAI (FALLBACK 2)
    logger.warning("CV Intelligence: Hermes basarisiz, OpenAI deneniyor...")
    result = await call_openai_for_intelligence(prompt)
    if result:
        logger.info("CV Intelligence: OpenAI basarili")
        return result, "OpenAI"

    # 4. Claude (FALLBACK 3 - SON CARE)
    logger.warning("CV Intelligence: OpenAI basarisiz, Claude deneniyor (son care)...")
    result = await call_claude_for_intelligence(prompt)
    if result:
        logger.info("CV Intelligence: Claude basarili")
        return result, "Claude"

    # Hepsi basarisiz
    logger.error("CV Intelligence: TUM MODELLER BASARISIZ!")
    return None, ""


async def analyze_candidate_intelligence(
    candidate_id: int,
    company_id: int,
    candidate_data: dict
) -> IntelligenceResult:
    """
    Adayin CV'sini analiz eder ve IntelligenceResult dondurur.
    FALLBACK ZINCIRI: Gemini -> Hermes -> OpenAI -> Claude
    """
    start_time = time.time()
    logger.info(f"CV Intelligence analizi basliyor: candidate_id={candidate_id}")

    prompt = build_intelligence_prompt(candidate_data)
    result, model_used = await call_ai_with_fallback(prompt)
    elapsed = time.time() - start_time

    if not result:
        return IntelligenceResult(
            success=False,
            candidate_id=candidate_id,
            company_id=company_id,
            error_message="Tum AI modelleri basarisiz oldu (Gemini, Hermes, OpenAI, Claude)",
            processing_time=round(elapsed, 2),
            model_used=""
        )

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
            processing_time=round(elapsed, 2),
            model_used=model_used
        )

        logger.info(f"CV Intelligence tamamlandi: candidate_id={candidate_id}, model={model_used}, career_path={intelligence.career_path}, sure={elapsed:.2f}s")
        return intelligence

    except Exception as e:
        logger.error(f"IntelligenceResult olusturma hatasi: {e}")
        return IntelligenceResult(
            success=False,
            candidate_id=candidate_id,
            company_id=company_id,
            error_message=f"Sonuc isleme hatasi: {str(e)}",
            processing_time=round(elapsed, 2),
            model_used=model_used
        )


async def analyze_candidates_batch(
    candidates: List[dict],
    company_id: int,
    max_concurrent: int = 5
) -> List[IntelligenceResult]:
    if not candidates:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_with_semaphore(candidate: dict) -> IntelligenceResult:
        async with semaphore:
            candidate_id = candidate.get("id", 0)
            return await analyze_candidate_intelligence(candidate_id, company_id, candidate)

    tasks = [analyze_with_semaphore(c) for c in candidates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

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
    logger.info(f"Batch analiz tamamlandi: {successful}/{len(candidates)} basarili")
    return processed_results


def analyze_sync(
    candidate_id: int,
    company_id: int,
    candidate_data: dict
) -> IntelligenceResult:
    return asyncio.run(analyze_candidate_intelligence(candidate_id, company_id, candidate_data))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    print("CV Intelligence Modul Testi (Fallback Destekli)")
    print(f"Gemini API Key: {bool(os.environ.get('GEMINI_API_KEY'))}")
    print(f"Hermes API Key: {bool(os.environ.get('HERMES_API_KEY'))}")
    print(f"OpenAI API Key: {bool(os.environ.get('OPENAI_API_KEY'))}")
    print(f"Anthropic API Key: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
    print("Fallback Zinciri: Gemini -> Hermes -> OpenAI -> Claude")
