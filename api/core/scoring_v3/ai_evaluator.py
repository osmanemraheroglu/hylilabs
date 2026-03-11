"""
AIEvaluator - Scoring V3 Multi-Model Değerlendirme Motoru

Gemini + Hermes paralel çalışır, fark > 15 puan veya eligible uyumsuzluğu varsa Claude hakim olur.

Kullanım:
    from ai_evaluator import AIEvaluator
    import asyncio

    evaluator = AIEvaluator()
    result = asyncio.run(evaluator.evaluate(system_prompt, evaluation_prompt))
"""

import os
import json
import asyncio
import time
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv

# aiohttp import (async HTTP client)
try:
    import aiohttp
except ImportError:
    aiohttp = None
    print("⚠️ aiohttp yüklü değil. pip install aiohttp")

load_dotenv()

# Logger ayarla
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvaluationResult:
    """Tek bir AI modelinin değerlendirme sonucu"""
    model_name: str
    eligible: bool
    total_score: int
    scores: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]
    notes_for_hr: List[str]
    interview_questions: List[str]
    overall_assessment: str
    elimination_reason: Optional[str]
    response_time: float
    tokens_used: Dict[str, int]
    raw_response: str
    parse_success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Dict'e çevir"""
        return asdict(self)


@dataclass
class FinalEvaluation:
    """Final değerlendirme sonucu"""
    # Ana değerlendirme
    eligible: bool
    total_score: int
    scores: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]
    notes_for_hr: List[str]
    interview_questions: List[str]
    overall_assessment: str
    elimination_reason: Optional[str]

    # Meta bilgiler
    gemini_score: int
    hermes_score: int
    score_difference: int
    eligible_disagreement: bool
    claude_used: bool
    consensus_method: str  # "average", "claude_decision", "single_model"

    # Performans
    total_response_time: float
    total_tokens: Dict[str, int]

    # Debug bilgileri (opsiyonel)
    gemini_result: Optional[EvaluationResult] = None
    hermes_result: Optional[EvaluationResult] = None
    claude_result: Optional[EvaluationResult] = None

    def to_dict(self, include_debug: bool = False) -> Dict[str, Any]:
        """Dict'e çevir"""
        result = {
            "eligible": self.eligible,
            "total_score": self.total_score,
            "scores": self.scores,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "notes_for_hr": self.notes_for_hr,
            "interview_questions": self.interview_questions,
            "overall_assessment": self.overall_assessment,
            "elimination_reason": self.elimination_reason,
            "meta": {
                "gemini_score": self.gemini_score,
                "hermes_score": self.hermes_score,
                "score_difference": self.score_difference,
                "eligible_disagreement": self.eligible_disagreement,
                "claude_used": self.claude_used,
                "consensus_method": self.consensus_method,
                "total_response_time": self.total_response_time,
                "total_tokens": self.total_tokens
            }
        }

        if include_debug:
            result["debug"] = {
                "gemini_result": self.gemini_result.to_dict() if self.gemini_result else None,
                "hermes_result": self.hermes_result.to_dict() if self.hermes_result else None,
                "claude_result": self.claude_result.to_dict() if self.claude_result else None
            }

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# AI EVALUATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class AIEvaluator:
    """
    Multi-model CV değerlendirme motoru.
    Gemini + Hermes paralel çalışır, fark > 15 puan veya eligible uyumsuzluğu varsa Claude hakim olur.
    """

    # API Endpoints
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
    HERMES_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

    # Model names
    HERMES_MODEL = "Hermes-4-70B"
    CLAUDE_MODEL = "claude-sonnet-4-20250514"

    # Thresholds
    SCORE_DIFFERENCE_THRESHOLD = 15  # Bu farkın üzerinde Claude devreye girer

    # Retry settings
    MAX_RETRIES = 1
    RETRY_DELAY = 2  # saniye
    RETRY_STATUS_CODES = {500, 502, 503, 504, 529}  # 5xx hatalar

    # Timeout settings
    API_TIMEOUT = 90  # saniye

    def __init__(self):
        """AIEvaluator başlat ve API key'leri yükle"""
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.hermes_api_key = os.environ.get("HERMES_API_KEY")
        self.claude_api_key = os.environ.get("ANTHROPIC_API_KEY")  # Opsiyonel

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY bulunamadı! .env dosyasını kontrol et.")
        if not self.hermes_api_key:
            raise ValueError("HERMES_API_KEY bulunamadı! .env dosyasını kontrol et.")

        logger.info(f"AIEvaluator başlatıldı. Claude API: {'✅' if self.claude_api_key else '❌ (opsiyonel)'}")

    async def evaluate(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> FinalEvaluation:
        """
        Ana değerlendirme fonksiyonu.

        Args:
            system_prompt: SmartPromptBuilder'dan gelen sistem promptu
            evaluation_prompt: SmartPromptBuilder'dan gelen değerlendirme promptu

        Returns:
            FinalEvaluation: Final değerlendirme sonucu
        """
        start_time = time.time()
        logger.info("Değerlendirme başlatıldı...")

        # 1. Gemini ve Hermes'i paralel çalıştır
        gemini_result, hermes_result = await self._evaluate_parallel(
            system_prompt, evaluation_prompt
        )

        logger.info(f"Paralel değerlendirme tamamlandı. "
                   f"Gemini: {gemini_result.total_score if not gemini_result.error else 'HATA'}, "
                   f"Hermes: {hermes_result.total_score if not hermes_result.error else 'HATA'}")

        # 2. Sonuçları kontrol et
        if gemini_result.error and hermes_result.error:
            # İki model de başarısız
            logger.error(f"Her iki model de başarısız! Gemini: {gemini_result.error}, Hermes: {hermes_result.error}")
            raise Exception(f"Her iki model de başarısız: Gemini={gemini_result.error}, Hermes={hermes_result.error}")

        if gemini_result.error:
            # Sadece Hermes başarılı
            logger.warning(f"Gemini başarısız, sadece Hermes kullanılıyor. Hata: {gemini_result.error}")
            return self._create_final_from_single(
                hermes_result, gemini_result, None, time.time() - start_time
            )

        if hermes_result.error:
            # Sadece Gemini başarılı
            logger.warning(f"Hermes başarısız, sadece Gemini kullanılıyor. Hata: {hermes_result.error}")
            return self._create_final_from_single(
                gemini_result, None, hermes_result, time.time() - start_time
            )

        # 3. Fark ve uyumsuzluk kontrolü
        score_diff = abs(gemini_result.total_score - hermes_result.total_score)
        eligible_disagreement = gemini_result.eligible != hermes_result.eligible

        logger.info(f"Puan farkı: {score_diff}, eligible uyumsuzluğu: {eligible_disagreement}")

        # 4. Claude tetikleme koşulları
        should_call_claude = (
            score_diff > self.SCORE_DIFFERENCE_THRESHOLD or eligible_disagreement
        )

        claude_result = None
        if should_call_claude:
            if self.claude_api_key:
                logger.info(f"Claude tetikleniyor. Sebep: {'puan farkı > 15' if score_diff > 15 else 'eligible uyumsuzluğu'}")
                claude_result = await self._evaluate_claude(
                    system_prompt, evaluation_prompt,
                    gemini_result, hermes_result
                )

                if claude_result.error:
                    logger.warning(f"Claude başarısız: {claude_result.error}. Ortalama alınacak.")
                else:
                    logger.info(f"Claude kararı: score={claude_result.total_score}, eligible={claude_result.eligible}")
            else:
                logger.warning("Claude API key yok, ortalama alınacak.")

        # 5. Final sonuç oluştur
        total_time = time.time() - start_time
        result = self._create_final_evaluation(
            gemini_result, hermes_result, claude_result,
            score_diff, eligible_disagreement, total_time
        )

        logger.info(f"Değerlendirme tamamlandı. Final: {result.total_score} puan, "
                   f"method={result.consensus_method}, süre={total_time:.2f}s")

        return result

    async def _evaluate_parallel(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> Tuple[EvaluationResult, EvaluationResult]:
        """Gemini ve Hermes'i paralel çalıştırır"""
        if aiohttp is None:
            raise ImportError("aiohttp yüklü değil. pip install aiohttp")

        async with aiohttp.ClientSession() as session:
            gemini_task = self._evaluate_gemini(session, system_prompt, evaluation_prompt)
            hermes_task = self._evaluate_hermes(session, system_prompt, evaluation_prompt)

            results = await asyncio.gather(gemini_task, hermes_task, return_exceptions=True)

            # Exception handling
            gemini_result = results[0] if not isinstance(results[0], Exception) else self._error_result("Gemini", str(results[0]))
            hermes_result = results[1] if not isinstance(results[1], Exception) else self._error_result("Hermes", str(results[1]))

            return gemini_result, hermes_result

    async def _evaluate_gemini(
        self,
        session: aiohttp.ClientSession,
        system_prompt: str,
        evaluation_prompt: str
    ) -> EvaluationResult:
        """Gemini API çağrısı (retry destekli, thinkingBudget ile)"""
        start_time = time.time()

        url = f"{self.GEMINI_API_URL}?key={self.gemini_api_key}"

        # Başlangıç thinkingBudget: 1024 (Gemini 2.5 Pro thinking mode)
        current_thinking_budget = 1024

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{evaluation_prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 4096,
                "thinkingConfig": {
                    "thinkingBudget": current_thinking_budget
                }
            }
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug(f"Gemini API çağrısı (deneme {attempt + 1}/{self.MAX_RETRIES + 1}, thinkingBudget={current_thinking_budget})")

                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.API_TIMEOUT)
                ) as response:
                    elapsed = time.time() - start_time

                    if response.status != 200:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"

                        # Retry için uygun mu?
                        if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                            logger.warning(f"Gemini {response.status} hatası, {self.RETRY_DELAY}s sonra retry...")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue

                        return self._error_result("Gemini", last_error, elapsed)

                    data = await response.json()

                    # parts kontrolü (güvenlik - thinking overflow durumu)
                    candidate = data.get("candidates", [{}])[0]
                    content_data = candidate.get("content", {})
                    parts = content_data.get("parts", [])

                    if not parts:
                        finish_reason = candidate.get("finishReason", "")
                        thinking_tokens = data.get("usageMetadata", {}).get("thoughtsTokenCount", 0)

                        if finish_reason == "MAX_TOKENS" and thinking_tokens > 0 and attempt < self.MAX_RETRIES:
                            # thinkingBudget artırarak retry
                            current_thinking_budget = 2048
                            payload["generationConfig"]["thinkingConfig"]["thinkingBudget"] = current_thinking_budget
                            logger.warning(f"Gemini thinking overflow ({thinking_tokens} token), retry: thinkingBudget → 2048")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue

                        return self._error_result("Gemini", f"No parts in response: {finish_reason}", elapsed)

                    content = parts[0]["text"]

                    # Token bilgisi
                    usage = data.get("usageMetadata", {})
                    tokens = {
                        "input": usage.get("promptTokenCount", 0),
                        "output": usage.get("candidatesTokenCount", 0),
                        "thinking": usage.get("thoughtsTokenCount", 0)
                    }

                    logger.debug(f"Gemini yanıt: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token (thinking: {tokens['thinking']})")

                    # JSON parse
                    return self._parse_response("Gemini", content, elapsed, tokens)

            except asyncio.TimeoutError:
                last_error = f"Timeout ({self.API_TIMEOUT}s)"
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Gemini timeout, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

            except Exception as e:
                last_error = str(e)
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Gemini hata: {e}, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

        return self._error_result("Gemini", last_error or "Bilinmeyen hata", time.time() - start_time)

    async def _evaluate_hermes(
        self,
        session: aiohttp.ClientSession,
        system_prompt: str,
        evaluation_prompt: str
    ) -> EvaluationResult:
        """Hermes API çağrısı (retry destekli)"""
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.hermes_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.HERMES_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": evaluation_prompt}
            ],
            "max_tokens": 2048,
            "temperature": 0.3
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug(f"Hermes API çağrısı (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

                async with session.post(
                    self.HERMES_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.API_TIMEOUT)
                ) as response:
                    elapsed = time.time() - start_time

                    if response.status != 200:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"

                        # Retry için uygun mu?
                        if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                            logger.warning(f"Hermes {response.status} hatası, {self.RETRY_DELAY}s sonra retry...")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue

                        return self._error_result("Hermes", last_error, elapsed)

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]

                    # Token bilgisi
                    usage = data.get("usage", {})
                    tokens = {
                        "input": usage.get("prompt_tokens", 0),
                        "output": usage.get("completion_tokens", 0)
                    }

                    logger.debug(f"Hermes yanıt: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

                    # JSON parse (hata durumunda retry)
                    result = self._parse_response("Hermes", content, elapsed, tokens)
                    if result.error and attempt < self.MAX_RETRIES:
                        logger.warning(f"Hermes JSON parse hatası, {self.RETRY_DELAY}s sonra retry...")
                        last_error = result.error
                        await asyncio.sleep(self.RETRY_DELAY)
                        continue
                    return result

            except asyncio.TimeoutError:
                last_error = f"Timeout ({self.API_TIMEOUT}s)"
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Hermes timeout, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

            except Exception as e:
                last_error = str(e)
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Hermes hata: {e}, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

        return self._error_result("Hermes", last_error or "Bilinmeyen hata", time.time() - start_time)

    async def _evaluate_claude(
        self,
        system_prompt: str,
        evaluation_prompt: str,
        gemini_result: EvaluationResult,
        hermes_result: EvaluationResult
    ) -> EvaluationResult:
        """Claude API çağrısı - Hakim rolü (retry destekli)"""
        start_time = time.time()

        # Claude için özel hakim promptu
        judge_prompt = self._build_judge_prompt(
            evaluation_prompt, gemini_result, hermes_result
        )

        headers = {
            "x-api-key": self.claude_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.CLAUDE_MODEL,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": judge_prompt}
            ]
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug(f"Claude API çağrısı (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.CLAUDE_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.API_TIMEOUT)
                    ) as response:
                        elapsed = time.time() - start_time

                        if response.status != 200:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200]}"

                            # Retry için uygun mu?
                            if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                                logger.warning(f"Claude {response.status} hatası, {self.RETRY_DELAY}s sonra retry...")
                                await asyncio.sleep(self.RETRY_DELAY)
                                continue

                            return self._error_result("Claude", last_error, elapsed)

                        data = await response.json()
                        content = data["content"][0]["text"]

                        # Token bilgisi
                        usage = data.get("usage", {})
                        tokens = {
                            "input": usage.get("input_tokens", 0),
                            "output": usage.get("output_tokens", 0)
                        }

                        logger.debug(f"Claude yanıt: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

                        return self._parse_response("Claude", content, elapsed, tokens)

            except asyncio.TimeoutError:
                last_error = f"Timeout ({self.API_TIMEOUT}s)"
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Claude timeout, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

            except Exception as e:
                last_error = str(e)
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Claude hata: {e}, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

        return self._error_result("Claude", last_error or "Bilinmeyen hata", time.time() - start_time)

    def _build_judge_prompt(
        self,
        original_prompt: str,
        gemini_result: EvaluationResult,
        hermes_result: EvaluationResult
    ) -> str:
        """Claude hakim için özel prompt oluşturur"""
        return f"""İki farklı AI modeli aynı adayı değerlendirdi ve farklı sonuçlara ulaştı.
Sen hakim olarak final kararı vereceksin.

═══════════════════════════════════════════════════════════════════════════════
ORIJINAL DEĞERLENDİRME TALEBİ
═══════════════════════════════════════════════════════════════════════════════
{original_prompt[:3000]}

═══════════════════════════════════════════════════════════════════════════════
MODEL 1 (GEMİNİ) DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════════════════
Toplam Puan: {gemini_result.total_score}
Uygun mu (eligible): {gemini_result.eligible}
Genel Değerlendirme: {gemini_result.overall_assessment}

Detaylı Puanlar:
{json.dumps(gemini_result.scores, ensure_ascii=False, indent=2)}

Güçlü Yönler: {', '.join(gemini_result.strengths[:3]) if gemini_result.strengths else 'Belirtilmemiş'}
Zayıf Yönler: {', '.join(gemini_result.weaknesses[:3]) if gemini_result.weaknesses else 'Belirtilmemiş'}

═══════════════════════════════════════════════════════════════════════════════
MODEL 2 (HERMES) DEĞERLENDİRMESİ
═══════════════════════════════════════════════════════════════════════════════
Toplam Puan: {hermes_result.total_score}
Uygun mu (eligible): {hermes_result.eligible}
Genel Değerlendirme: {hermes_result.overall_assessment}

Detaylı Puanlar:
{json.dumps(hermes_result.scores, ensure_ascii=False, indent=2)}

Güçlü Yönler: {', '.join(hermes_result.strengths[:3]) if hermes_result.strengths else 'Belirtilmemiş'}
Zayıf Yönler: {', '.join(hermes_result.weaknesses[:3]) if hermes_result.weaknesses else 'Belirtilmemiş'}

═══════════════════════════════════════════════════════════════════════════════
HAKİM TALİMATI
═══════════════════════════════════════════════════════════════════════════════

İki modelin değerlendirmelerini incele ve final kararını ver:

1. Hangi model daha tutarlı ve mantıklı argümanlar sunuyor?
2. Hangi puanlama daha adil ve objektif?
3. Eksik veya yanlış değerlendirme var mı?
4. Eğer iki model eligible konusunda uyuşmuyorsa, hangisi doğru?

SADECE JSON formatında yanıt ver (aynı şema kullan).
Kendi bağımsız değerlendirmeni yap, sadece modellerin ortalamasını alma.
"""

    def _repair_json(self, text: str) -> str:
        """
        Bozuk JSON'u düzeltmeye çalışır.
        LLM'lerin ürettiği yaygın JSON hatalarını düzeltir.
        """
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

        return text.strip()

    def _parse_response(
        self,
        model_name: str,
        content: str,
        elapsed: float,
        tokens: Dict[str, int]
    ) -> EvaluationResult:
        """API yanıtını parse eder (JSON repair destekli)"""
        try:
            # JSON bloğunu çıkar
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    json_str = parts[1]

            # İlk parse denemesi
            try:
                data = json.loads(json_str.strip())
            except json.JSONDecodeError as first_error:
                # JSON repair dene
                logger.warning(f"{model_name} JSON parse hatası, repair deneniyor: {first_error}")
                repaired = self._repair_json(json_str)
                try:
                    data = json.loads(repaired)
                    logger.info(f"{model_name} JSON repair başarılı")
                except json.JSONDecodeError:
                    # Repair de başarısız, orijinal hatayı fırlat
                    raise first_error

            return EvaluationResult(
                model_name=model_name,
                eligible=data.get("eligible", False),
                total_score=int(data.get("total_score", 0)),
                scores=data.get("scores", {}),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                notes_for_hr=data.get("notes_for_hr", []),
                interview_questions=data.get("interview_questions", []),
                overall_assessment=data.get("overall_assessment", ""),
                elimination_reason=data.get("elimination_reason"),
                response_time=round(elapsed, 2),
                tokens_used=tokens,
                raw_response=content,
                parse_success=True
            )

        except json.JSONDecodeError as e:
            logger.warning(f"{model_name} JSON parse hatası: {e}")
            return EvaluationResult(
                model_name=model_name,
                eligible=False,
                total_score=0,
                scores={},
                strengths=[],
                weaknesses=[],
                notes_for_hr=[],
                interview_questions=[],
                overall_assessment="",
                elimination_reason=None,
                response_time=round(elapsed, 2),
                tokens_used=tokens,
                raw_response=content,
                parse_success=False,
                error=f"JSON parse hatası: {str(e)}"
            )

    def _error_result(
        self,
        model_name: str,
        error: str,
        elapsed: float = 0
    ) -> EvaluationResult:
        """Hata durumunda EvaluationResult döndürür"""
        return EvaluationResult(
            model_name=model_name,
            eligible=False,
            total_score=0,
            scores={},
            strengths=[],
            weaknesses=[],
            notes_for_hr=[],
            interview_questions=[],
            overall_assessment="",
            elimination_reason=None,
            response_time=round(elapsed, 2),
            tokens_used={"input": 0, "output": 0},
            raw_response="",
            parse_success=False,
            error=error
        )

    def _create_final_from_single(
        self,
        success_result: EvaluationResult,
        gemini_result: Optional[EvaluationResult],
        hermes_result: Optional[EvaluationResult],
        total_time: float
    ) -> FinalEvaluation:
        """Tek model başarılı olduğunda final sonuç oluşturur"""
        return FinalEvaluation(
            eligible=success_result.eligible,
            total_score=success_result.total_score,
            scores=success_result.scores,
            strengths=success_result.strengths,
            weaknesses=success_result.weaknesses,
            notes_for_hr=success_result.notes_for_hr + ["⚠️ Sadece tek model değerlendirdi (diğer model başarısız)"],
            interview_questions=success_result.interview_questions,
            overall_assessment=success_result.overall_assessment,
            elimination_reason=success_result.elimination_reason,
            gemini_score=gemini_result.total_score if gemini_result and not gemini_result.error else 0,
            hermes_score=hermes_result.total_score if hermes_result and not hermes_result.error else 0,
            score_difference=0,
            eligible_disagreement=False,
            claude_used=False,
            consensus_method="single_model",
            total_response_time=round(total_time, 2),
            total_tokens={
                "input": success_result.tokens_used.get("input", 0),
                "output": success_result.tokens_used.get("output", 0)
            },
            gemini_result=gemini_result,
            hermes_result=hermes_result,
            claude_result=None
        )

    def _create_final_evaluation(
        self,
        gemini_result: EvaluationResult,
        hermes_result: EvaluationResult,
        claude_result: Optional[EvaluationResult],
        score_diff: int,
        eligible_disagreement: bool,
        total_time: float
    ) -> FinalEvaluation:
        """İki veya üç modelden final sonuç oluşturur"""

        # Token toplamı
        total_tokens = {
            "input": gemini_result.tokens_used.get("input", 0) + hermes_result.tokens_used.get("input", 0),
            "output": gemini_result.tokens_used.get("output", 0) + hermes_result.tokens_used.get("output", 0)
        }

        if claude_result and not claude_result.error:
            # Claude hakim kararı
            total_tokens["input"] += claude_result.tokens_used.get("input", 0)
            total_tokens["output"] += claude_result.tokens_used.get("output", 0)

            return FinalEvaluation(
                eligible=claude_result.eligible,
                total_score=claude_result.total_score,
                scores=claude_result.scores,
                strengths=claude_result.strengths,
                weaknesses=claude_result.weaknesses,
                notes_for_hr=claude_result.notes_for_hr + [
                    f"🔍 Claude hakim kararı (Gemini: {gemini_result.total_score}, Hermes: {hermes_result.total_score})"
                ],
                interview_questions=claude_result.interview_questions,
                overall_assessment=claude_result.overall_assessment,
                elimination_reason=claude_result.elimination_reason,
                gemini_score=gemini_result.total_score,
                hermes_score=hermes_result.total_score,
                score_difference=score_diff,
                eligible_disagreement=eligible_disagreement,
                claude_used=True,
                consensus_method="claude_decision",
                total_response_time=round(total_time, 2),
                total_tokens=total_tokens,
                gemini_result=gemini_result,
                hermes_result=hermes_result,
                claude_result=claude_result
            )

        # Ortalama al
        avg_score = (gemini_result.total_score + hermes_result.total_score) // 2

        # Her iki model de eligible ise eligible, biri bile değilse değil
        # (Bu durumda Claude'a sormak gerekirdi ama API key yoksa)
        final_eligible = gemini_result.eligible and hermes_result.eligible

        # Scores ortalaması
        final_scores = self._average_scores(gemini_result.scores, hermes_result.scores)

        # Strengths/weaknesses birleştir (unique)
        final_strengths = list(dict.fromkeys(gemini_result.strengths + hermes_result.strengths))[:5]
        final_weaknesses = list(dict.fromkeys(gemini_result.weaknesses + hermes_result.weaknesses))[:5]

        # Notes birleştir
        final_notes = list(dict.fromkeys(gemini_result.notes_for_hr + hermes_result.notes_for_hr))

        # Uyarı notları ekle
        if score_diff > self.SCORE_DIFFERENCE_THRESHOLD:
            final_notes.append(f"⚠️ Modeller arasında {score_diff} puan fark var")
        if eligible_disagreement:
            final_notes.append(f"⚠️ eligible uyumsuzluğu: Gemini={gemini_result.eligible}, Hermes={hermes_result.eligible}")
        if (score_diff > self.SCORE_DIFFERENCE_THRESHOLD or eligible_disagreement) and not self.claude_api_key:
            final_notes.append("⚠️ Claude API key olmadığı için ortalama alındı")

        # Interview questions birleştir
        final_questions = list(dict.fromkeys(gemini_result.interview_questions + hermes_result.interview_questions))[:5]

        # Overall assessment birleştir
        overall = f"[Gemini ({gemini_result.total_score})] {gemini_result.overall_assessment}\n\n[Hermes ({hermes_result.total_score})] {hermes_result.overall_assessment}"

        return FinalEvaluation(
            eligible=final_eligible,
            total_score=avg_score,
            scores=final_scores,
            strengths=final_strengths,
            weaknesses=final_weaknesses,
            notes_for_hr=final_notes,
            interview_questions=final_questions,
            overall_assessment=overall,
            elimination_reason=gemini_result.elimination_reason or hermes_result.elimination_reason,
            gemini_score=gemini_result.total_score,
            hermes_score=hermes_result.total_score,
            score_difference=score_diff,
            eligible_disagreement=eligible_disagreement,
            claude_used=False,
            consensus_method="average",
            total_response_time=round(total_time, 2),
            total_tokens=total_tokens,
            gemini_result=gemini_result,
            hermes_result=hermes_result,
            claude_result=claude_result
        )

    def _average_scores(
        self,
        scores1: Dict[str, Any],
        scores2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """İki skor setinin ortalamasını alır"""
        result = {}

        all_keys = set(scores1.keys()) | set(scores2.keys())

        for key in all_keys:
            s1 = scores1.get(key, {})
            s2 = scores2.get(key, {})

            if isinstance(s1, dict) and isinstance(s2, dict):
                result[key] = {
                    "score": (s1.get("score", 0) + s2.get("score", 0)) // 2,
                    "reason": f"{s1.get('reason', '')} | {s2.get('reason', '')}"
                }

                # matched_skills ve missing_skills varsa birleştir
                if "matched_skills" in s1 or "matched_skills" in s2:
                    result[key]["matched_skills"] = list(dict.fromkeys(
                        s1.get("matched_skills", []) + s2.get("matched_skills", [])
                    ))
                if "missing_skills" in s1 or "missing_skills" in s2:
                    result[key]["missing_skills"] = list(dict.fromkeys(
                        s1.get("missing_skills", []) + s2.get("missing_skills", [])
                    ))
            elif isinstance(s1, dict):
                result[key] = s1
            elif isinstance(s2, dict):
                result[key] = s2
            else:
                result[key] = s1 or s2

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SENKRON WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_sync(system_prompt: str, evaluation_prompt: str) -> FinalEvaluation:
    """
    Senkron evaluate fonksiyonu (FastAPI veya senkron kod için).

    Args:
        system_prompt: Sistem promptu
        evaluation_prompt: Değerlendirme promptu

    Returns:
        FinalEvaluation: Final değerlendirme sonucu
    """
    evaluator = AIEvaluator()
    return asyncio.run(evaluator.evaluate(system_prompt, evaluation_prompt))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Logging ayarla (test için)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("\n" + "=" * 77)
    print("AIEvaluator Modül Testi")
    print("=" * 77)

    print(f"\n📌 API Key Durumu:")
    print(f"   Gemini API Key:  {'✅ Mevcut' if os.environ.get('GEMINI_API_KEY') else '❌ YOK'}")
    print(f"   Hermes API Key:  {'✅ Mevcut' if os.environ.get('HERMES_API_KEY') else '❌ YOK'}")
    print(f"   Claude API Key:  {'✅ Mevcut' if os.environ.get('ANTHROPIC_API_KEY') else '⚠️ Opsiyonel (YOK)'}")

    print(f"\n📌 Ayarlar:")
    print(f"   Score fark eşiği: {AIEvaluator.SCORE_DIFFERENCE_THRESHOLD} puan")
    print(f"   Max retry: {AIEvaluator.MAX_RETRIES}")
    print(f"   API timeout: {AIEvaluator.API_TIMEOUT}s")

    print(f"\n📌 aiohttp durumu: {'✅ Yüklü' if aiohttp else '❌ Yüklü değil'}")

    print("\n" + "=" * 77)
    print("Modül başarıyla yüklendi. Kullanım için:")
    print("  from ai_evaluator import AIEvaluator, evaluate_sync")
    print("=" * 77)
