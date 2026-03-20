"""
AIEvaluator - Scoring V3 Multi-Model Degerlendirme Motoru

Gemini + Hermes paralel calisir.
Biri basarisiz olursa OpenAI sigorta devreye girer.
Fark > 15 puan veya eligible uyumsuzlugu varsa Claude hakim olur.

Fallback Zinciri:
- SENARYO 1: Gemini OK + Hermes OK -> Consensus (OpenAI cagrilmaz)
- SENARYO 2: Gemini FAIL + Hermes OK -> OpenAI cagrilir -> OpenAI + Hermes consensus
- SENARYO 3: Gemini OK + Hermes FAIL -> OpenAI cagrilir -> Gemini + OpenAI consensus
- SENARYO 4: Gemini FAIL + Hermes FAIL -> OpenAI cagrilir -> Tek skor (son care)

Kullanim:
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
    print("aiohttp yuklu degil. pip install aiohttp")

# OpenAI import
try:
    import openai
except ImportError:
    openai = None
    print("openai yuklu degil. pip install openai")

load_dotenv()

# Logger ayarla
logger = logging.getLogger(__name__)


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class EvaluationResult:
    """Tek bir AI modelinin degerlendirme sonucu"""
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
        """Dict'e cevir"""
        return asdict(self)


@dataclass
class FinalEvaluation:
    """Final degerlendirme sonucu"""
    # Ana degerlendirme
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
    openai_score: int  # YENi: OpenAI skoru
    score_difference: int
    eligible_disagreement: bool
    claude_used: bool
    consensus_method: str  # "average", "claude_decision", "single_model"
    models_used: List[str]  # YENi: Kullanilan modeller ["Gemini", "Hermes"] vb.

    # Performans
    total_response_time: float
    total_tokens: Dict[str, int]

    # Debug bilgileri (opsiyonel)
    gemini_result: Optional[EvaluationResult] = None
    hermes_result: Optional[EvaluationResult] = None
    openai_result: Optional[EvaluationResult] = None  # YENi
    claude_result: Optional[EvaluationResult] = None

    def to_dict(self, include_debug: bool = False) -> Dict[str, Any]:
        """Dict'e cevir"""
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
                "openai_score": self.openai_score,
                "score_difference": self.score_difference,
                "eligible_disagreement": self.eligible_disagreement,
                "claude_used": self.claude_used,
                "consensus_method": self.consensus_method,
                "models_used": self.models_used,
                "total_response_time": self.total_response_time,
                "total_tokens": self.total_tokens
            }
        }

        if include_debug:
            result["debug"] = {
                "gemini_result": self.gemini_result.to_dict() if self.gemini_result else None,
                "hermes_result": self.hermes_result.to_dict() if self.hermes_result else None,
                "openai_result": self.openai_result.to_dict() if self.openai_result else None,
                "claude_result": self.claude_result.to_dict() if self.claude_result else None
            }

        return result


# ==============================================================================
# AI EVALUATOR CLASS
# ==============================================================================

class AIEvaluator:
    """
    Multi-model CV degerlendirme motoru.
    Gemini + Hermes paralel calisir.
    Biri basarisiz olursa OpenAI sigorta devreye girer.
    Fark > 15 puan veya eligible uyumsuzlugu varsa Claude hakim olur.
    """

    # API Endpoints - FLASH MODEL (maliyet optimizasyonu)
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    HERMES_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
    OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

    # Model names
    HERMES_MODEL = "Hermes-4-70B"
    OPENAI_MODEL = "gpt-4o"
    CLAUDE_MODEL = "claude-sonnet-4-20250514"

    # Thresholds
    SCORE_DIFFERENCE_THRESHOLD = 15  # Bu farkin uzerinde Claude devreye girer

    # Retry settings
    MAX_RETRIES = 3  # HyliLabs Protocol: 0 skor için 3 retry
    RETRY_DELAY = 2  # saniye
    RETRY_STATUS_CODES = {500, 502, 503, 504, 529}  # 5xx hatalar

    # Timeout settings
    API_TIMEOUT = 90  # saniye

    def __init__(self):
        """AIEvaluator baslat ve API key'leri yukle"""
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.hermes_api_key = os.environ.get("HERMES_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.claude_api_key = os.environ.get("ANTHROPIC_API_KEY")  # Opsiyonel

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY bulunamadi! .env dosyasini kontrol et.")
        if not self.hermes_api_key:
            raise ValueError("HERMES_API_KEY bulunamadi! .env dosyasini kontrol et.")

        logger.info(f"AIEvaluator baslatildi. OpenAI: {'OK' if self.openai_api_key else 'YOK'}, Claude: {'OK' if self.claude_api_key else 'YOK (opsiyonel)'}")

    async def evaluate(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> FinalEvaluation:
        """
        Ana degerlendirme fonksiyonu.

        Yeni Mantik:
        1. Gemini + Hermes paralel calistir
        2. Ikisi de basarili -> Consensus hesapla (OpenAI cagrilmaz)
        3. Biri basarisiz -> OpenAI sigorta devreye
        4. 2 basarili model ile consensus hesapla
        5. Tek model basarili -> Tek skor kullan (son care)

        Args:
            system_prompt: SmartPromptBuilder'dan gelen sistem promptu
            evaluation_prompt: SmartPromptBuilder'dan gelen degerlendirme promptu

        Returns:
            FinalEvaluation: Final degerlendirme sonucu
        """
        start_time = time.time()
        logger.info("Degerlendirme baslatildi...")

        # 1. Gemini ve Hermes'i paralel calistir
        gemini_result, hermes_result = await self._evaluate_parallel(
            system_prompt, evaluation_prompt
        )

        # Basari durumlarini kontrol et
        # HyliLabs Protocol: total_score > 0 kontrolü EKLENDİ
        gemini_ok = (gemini_result is not None and
                     gemini_result.error is None and
                     gemini_result.total_score is not None and
                     gemini_result.total_score > 0)
        hermes_ok = (hermes_result is not None and
                     hermes_result.error is None and
                     hermes_result.total_score is not None and
                     hermes_result.total_score > 0)

        logger.info(f"Paralel degerlendirme tamamlandi. "
                   f"Gemini: {gemini_result.total_score if gemini_ok else 'HATA/0'}, "
                   f"Hermes: {hermes_result.total_score if hermes_ok else 'HATA/0'}")

        openai_result = None

        # HyliLabs Protocol Adim 1: İkisi de 0 ise çık
        both_zero = (
            (gemini_result is not None and gemini_result.error is None and gemini_result.total_score == 0) and
            (hermes_result is not None and hermes_result.error is None and hermes_result.total_score == 0)
        )
        if both_zero:
            logger.warning("HyliLabs Protocol: İkisi de 0 skor döndü, değerlendirme sonlandırılıyor")
            raise Exception("Tüm AI modelleri 0 skor döndü - CV değerlendirilemedi")

        # HyliLabs Protocol Adim 2: Biri 0+ diğeri 0 ise, 0 olana retry
        if gemini_ok and not hermes_ok:
            # Hermes 0 veya hata - retry
            if hermes_result is not None and hermes_result.error is None and hermes_result.total_score == 0:
                logger.info("HyliLabs Protocol: Hermes 0 skor döndü, retry başlatılıyor...")
                hermes_result = await self._retry_zero_score_model(
                    "Hermes", system_prompt, evaluation_prompt
                )
                hermes_ok = (hermes_result is not None and
                             hermes_result.error is None and
                             hermes_result.total_score is not None and
                             hermes_result.total_score > 0)
                logger.info(f"Hermes retry sonucu: {hermes_result.total_score if hermes_ok else 'HATA/0'}")

        if hermes_ok and not gemini_ok:
            # Gemini 0 veya hata - retry
            if gemini_result is not None and gemini_result.error is None and gemini_result.total_score == 0:
                logger.info("HyliLabs Protocol: Gemini 0 skor döndü, retry başlatılıyor...")
                gemini_result = await self._retry_gemini_zero_score(
                    system_prompt, evaluation_prompt
                )
                gemini_ok = (gemini_result is not None and
                             gemini_result.error is None and
                             gemini_result.total_score is not None and
                             gemini_result.total_score > 0)
                logger.info(f"Gemini retry sonucu: {gemini_result.total_score if gemini_ok else 'HATA/0'}")

        # 2. Ikisi de basarili -> Normal consensus (OpenAI cagrilmaz)
        if gemini_ok and hermes_ok:
            logger.info("Iki model de basarili, OpenAI cagrilmayacak")
            return await self._finalize_evaluation(
                gemini_result, hermes_result, None, None,
                system_prompt, evaluation_prompt, start_time
            )

        # HyliLabs Protocol Adim 3: Retry sonrası hala tek pozitif skor varsa -> OpenAI fallback
        if not gemini_ok or not hermes_ok:
            failed_model = "Gemini" if not gemini_ok else "Hermes"
            logger.warning(f"HyliLabs Protocol: {failed_model} retry sonrası hala başarısız, OpenAI fallback devreye giriyor...")

            if self.openai_api_key:
                openai_result = await self._evaluate_openai(
                    system_prompt, evaluation_prompt
                )
                # HyliLabs Protocol: OpenAI için de total_score > 0 kontrolü
                if openai_result.error:
                    logger.warning(f"OpenAI de basarisiz: {openai_result.error}")
                elif openai_result.total_score is None or openai_result.total_score == 0:
                    logger.warning(f"OpenAI 0 skor döndü, başarısız sayılıyor")
                else:
                    logger.info(f"OpenAI basarili: skor={openai_result.total_score}")
            else:
                logger.warning("OpenAI API key yok, sigorta kullanilamadi")

        # 4. Basarili modelleri topla
        # HyliLabs Protocol: total_score > 0 kontrolü zorunlu
        successful_results = []
        if gemini_ok:  # Zaten total_score > 0 kontrolü var
            successful_results.append(("Gemini", gemini_result))
        if hermes_ok:  # Zaten total_score > 0 kontrolü var
            successful_results.append(("Hermes", hermes_result))
        # OpenAI için de aynı total_score > 0 kontrolü
        if (openai_result and
            openai_result.error is None and
            openai_result.total_score is not None and
            openai_result.total_score > 0):
            successful_results.append(("OpenAI", openai_result))

        logger.info(f"Basarili model sayisi: {len(successful_results)}")

        # 5. Sonuc hesapla
        if len(successful_results) >= 2:
            # 2+ model basarili -> ilk 2'yi kullanarak consensus
            model1_name, model1_result = successful_results[0]
            model2_name, model2_result = successful_results[1]
            logger.info(f"Consensus: {model1_name} + {model2_name}")

            return await self._finalize_evaluation(
                gemini_result if gemini_ok else None,
                hermes_result if hermes_ok else None,
                openai_result if openai_result and openai_result.error is None else None,
                None,  # claude_result
                system_prompt, evaluation_prompt, start_time,
                primary_results=(model1_result, model2_result),
                models_used=[model1_name, model2_name]
            )

        elif len(successful_results) == 1:
            # Tek model basarili -> tek skor (son care)
            model_name, single_result = successful_results[0]
            logger.warning(f"Sadece {model_name} basarili, tek skor kullaniliyor (son care)")

            return self._create_final_from_single(
                single_result,
                gemini_result,
                hermes_result,
                openai_result,
                time.time() - start_time,
                models_used=[model_name]
            )

        else:
            # Hicbiri basarili degil
            logger.error("Tum AI modelleri basarisiz oldu!")
            raise Exception(f"Tum AI modelleri basarisiz: Gemini={gemini_result.error}, Hermes={hermes_result.error}, OpenAI={openai_result.error if openai_result else 'cagrilmadi'}")

    async def _finalize_evaluation(
        self,
        gemini_result: Optional[EvaluationResult],
        hermes_result: Optional[EvaluationResult],
        openai_result: Optional[EvaluationResult],
        claude_result: Optional[EvaluationResult],
        system_prompt: str,
        evaluation_prompt: str,
        start_time: float,
        primary_results: Optional[Tuple[EvaluationResult, EvaluationResult]] = None,
        models_used: Optional[List[str]] = None
    ) -> FinalEvaluation:
        """
        Final degerlendirme hesapla.
        2 basarili model varsa consensus, fark buyukse Claude hakim.
        """
        # Hangi modeller kullanilacak?
        if primary_results:
            result1, result2 = primary_results
        else:
            # Varsayilan: Gemini + Hermes
            result1 = gemini_result
            result2 = hermes_result
            models_used = ["Gemini", "Hermes"]

        # Fark ve uyumsuzluk kontrolu
        score_diff = abs(result1.total_score - result2.total_score)
        eligible_disagreement = result1.eligible != result2.eligible

        logger.info(f"Puan farki: {score_diff}, eligible uyumsuzlugu: {eligible_disagreement}")

        # Claude tetikleme kosullari
        should_call_claude = (
            score_diff > self.SCORE_DIFFERENCE_THRESHOLD or eligible_disagreement
        )

        if should_call_claude:
            if self.claude_api_key:
                logger.info(f"Claude tetikleniyor. Sebep: {'puan farki > 15' if score_diff > 15 else 'eligible uyumsuzlugu'}")
                claude_result = await self._evaluate_claude(
                    system_prompt, evaluation_prompt,
                    result1, result2
                )

                if claude_result.error:
                    logger.warning(f"Claude basarisiz: {claude_result.error}. Ortalama alinacak.")
                else:
                    logger.info(f"Claude karari: score={claude_result.total_score}, eligible={claude_result.eligible}")
            else:
                logger.warning("Claude API key yok, ortalama alinacak.")

        # Final sonuc olustur
        total_time = time.time() - start_time
        return self._create_final_evaluation(
            gemini_result, hermes_result, openai_result, claude_result,
            score_diff, eligible_disagreement, total_time,
            primary_results, models_used
        )

    async def _retry_zero_score_model(
        self,
        model_name: str,
        system_prompt: str,
        evaluation_prompt: str
    ) -> EvaluationResult:
        """
        HyliLabs Protocol: 0 skor dönen modele MAX_RETRIES kadar tekrar dene.
        Hermes için kullanılır.
        """
        logger.info(f"HyliLabs Protocol: {model_name} için {self.MAX_RETRIES} retry başlatılıyor...")

        for attempt in range(self.MAX_RETRIES):
            logger.info(f"{model_name} retry {attempt + 1}/{self.MAX_RETRIES}")

            async with aiohttp.ClientSession() as session:
                if model_name == "Hermes":
                    result = await self._evaluate_hermes(session, system_prompt, evaluation_prompt)
                else:
                    # Varsayılan olarak error dön
                    return self._error_result(model_name, f"Bilinmeyen model: {model_name}")

                # Başarılı mı kontrol et
                if result.error is None and result.total_score is not None and result.total_score > 0:
                    logger.info(f"{model_name} retry {attempt + 1} başarılı: skor={result.total_score}")
                    return result

                logger.warning(f"{model_name} retry {attempt + 1} başarısız: skor={result.total_score}")
                await asyncio.sleep(self.RETRY_DELAY)

        logger.warning(f"{model_name} tüm retry'lar başarısız")
        return result  # Son denemenin sonucunu dön

    async def _retry_gemini_zero_score(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> EvaluationResult:
        """
        HyliLabs Protocol: 0 skor dönen Gemini'ye MAX_RETRIES kadar tekrar dene.
        """
        logger.info(f"HyliLabs Protocol: Gemini için {self.MAX_RETRIES} retry başlatılıyor...")

        for attempt in range(self.MAX_RETRIES):
            logger.info(f"Gemini retry {attempt + 1}/{self.MAX_RETRIES}")

            async with aiohttp.ClientSession() as session:
                result = await self._evaluate_gemini(session, system_prompt, evaluation_prompt)

                # Başarılı mı kontrol et
                if result.error is None and result.total_score is not None and result.total_score > 0:
                    logger.info(f"Gemini retry {attempt + 1} başarılı: skor={result.total_score}")
                    return result

                logger.warning(f"Gemini retry {attempt + 1} başarısız: skor={result.total_score}")
                await asyncio.sleep(self.RETRY_DELAY)

        logger.warning(f"Gemini tüm retry'lar başarısız")
        return result  # Son denemenin sonucunu dön

    async def _evaluate_parallel(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> Tuple[EvaluationResult, EvaluationResult]:
        """Gemini ve Hermes'i paralel calistirir"""
        if aiohttp is None:
            raise ImportError("aiohttp yuklu degil. pip install aiohttp")

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
        """Gemini API cagrisi (retry destekli, Flash model - thinking KAPALI)"""
        start_time = time.time()

        url = f"{self.GEMINI_API_URL}?key={self.gemini_api_key}"

        # Flash model - thinking mode KAPALI (maliyet optimizasyonu)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{evaluation_prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192
            }
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug(f"Gemini API cagrisi (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.API_TIMEOUT)
                ) as response:
                    elapsed = time.time() - start_time

                    if response.status != 200:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"

                        # Retry icin uygun mu?
                        if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                            logger.warning(f"Gemini {response.status} hatasi, {self.RETRY_DELAY}s sonra retry...")
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue

                        return self._error_result("Gemini", last_error, elapsed)

                    data = await response.json()

                    # parts kontrolu
                    candidate = data.get("candidates", [{}])[0]
                    content_data = candidate.get("content", {})
                    parts = content_data.get("parts", [])

                    if not parts:
                        finish_reason = candidate.get("finishReason", "")
                        return self._error_result("Gemini", f"No parts in response: {finish_reason}", elapsed)

                    content = parts[0]["text"]

                    # Token bilgisi
                    usage = data.get("usageMetadata", {})
                    tokens = {
                        "input": usage.get("promptTokenCount", 0),
                        "output": usage.get("candidatesTokenCount", 0)
                    }

                    logger.debug(f"Gemini yanit: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

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
        """Hermes API cagrisi (retry destekli)"""
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.hermes_api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"
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
                logger.debug(f"Hermes API cagrisi (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

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

                        # Retry icin uygun mu?
                        if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                            logger.warning(f"Hermes {response.status} hatasi, {self.RETRY_DELAY}s sonra retry...")
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

                    logger.debug(f"Hermes yanit: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

                    # JSON parse (hata durumunda retry)
                    result = self._parse_response("Hermes", content, elapsed, tokens)
                    if result.error and attempt < self.MAX_RETRIES:
                        logger.warning(f"Hermes JSON parse hatasi, {self.RETRY_DELAY}s sonra retry...")
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

    async def _evaluate_openai(
        self,
        system_prompt: str,
        evaluation_prompt: str
    ) -> EvaluationResult:
        """OpenAI GPT-4o API cagrisi (sigorta modeli, retry destekli)"""
        start_time = time.time()

        if not self.openai_api_key:
            return self._error_result("OpenAI", "OPENAI_API_KEY bulunamadi", 0)

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"
        }

        payload = {
            "model": self.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": evaluation_prompt}
            ],
            "max_tokens": 4096,
            "temperature": 0.3
        }

        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                logger.debug(f"OpenAI API cagrisi (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.OPENAI_API_URL,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.API_TIMEOUT)
                    ) as response:
                        elapsed = time.time() - start_time

                        if response.status != 200:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text[:200]}"

                            # Retry icin uygun mu?
                            if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                                logger.warning(f"OpenAI {response.status} hatasi, {self.RETRY_DELAY}s sonra retry...")
                                await asyncio.sleep(self.RETRY_DELAY)
                                continue

                            return self._error_result("OpenAI", last_error, elapsed)

                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]

                        # Token bilgisi
                        usage = data.get("usage", {})
                        tokens = {
                            "input": usage.get("prompt_tokens", 0),
                            "output": usage.get("completion_tokens", 0)
                        }

                        logger.debug(f"OpenAI yanit: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

                        # JSON parse
                        result = self._parse_response("OpenAI", content, elapsed, tokens)
                        if result.error and attempt < self.MAX_RETRIES:
                            logger.warning(f"OpenAI JSON parse hatasi, {self.RETRY_DELAY}s sonra retry...")
                            last_error = result.error
                            await asyncio.sleep(self.RETRY_DELAY)
                            continue
                        return result

            except asyncio.TimeoutError:
                last_error = f"Timeout ({self.API_TIMEOUT}s)"
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"OpenAI timeout, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

            except Exception as e:
                last_error = str(e)
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"OpenAI hata: {e}, {self.RETRY_DELAY}s sonra retry...")
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

        return self._error_result("OpenAI", last_error or "Bilinmeyen hata", time.time() - start_time)

    async def _evaluate_claude(
        self,
        system_prompt: str,
        evaluation_prompt: str,
        result1: EvaluationResult,
        result2: EvaluationResult
    ) -> EvaluationResult:
        """Claude API cagrisi - Hakim rolu (retry destekli)"""
        start_time = time.time()

        # Claude icin ozel hakim promptu
        judge_prompt = self._build_judge_prompt(
            evaluation_prompt, result1, result2
        )

        headers = {
            "x-api-key": self.claude_api_key,
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
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
                logger.debug(f"Claude API cagrisi (deneme {attempt + 1}/{self.MAX_RETRIES + 1})")

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

                            # Retry icin uygun mu?
                            if response.status in self.RETRY_STATUS_CODES and attempt < self.MAX_RETRIES:
                                logger.warning(f"Claude {response.status} hatasi, {self.RETRY_DELAY}s sonra retry...")
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

                        logger.debug(f"Claude yanit: {elapsed:.2f}s, {tokens['input']}/{tokens['output']} token")

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
        result1: EvaluationResult,
        result2: EvaluationResult
    ) -> str:
        """Claude hakim icin ozel prompt olusturur"""
        return f"""Iki farkli AI modeli ayni adayi degerlendirdi ve farkli sonuclara ulasti.
Sen hakim olarak final karari vereceksin.

===============================================================================
ORIJINAL DEGERLENDIRME TALEBI
===============================================================================
{original_prompt[:3000]}

===============================================================================
MODEL 1 ({result1.model_name}) DEGERLENDIRMESI
===============================================================================
Toplam Puan: {result1.total_score}
Uygun mu (eligible): {result1.eligible}
Genel Degerlendirme: {result1.overall_assessment}

Detayli Puanlar:
{json.dumps(result1.scores, ensure_ascii=False, indent=2)}

Guclu Yonler: {', '.join(result1.strengths[:3]) if result1.strengths else 'Belirtilmemis'}
Zayif Yonler: {', '.join(result1.weaknesses[:3]) if result1.weaknesses else 'Belirtilmemis'}

===============================================================================
MODEL 2 ({result2.model_name}) DEGERLENDIRMESI
===============================================================================
Toplam Puan: {result2.total_score}
Uygun mu (eligible): {result2.eligible}
Genel Degerlendirme: {result2.overall_assessment}

Detayli Puanlar:
{json.dumps(result2.scores, ensure_ascii=False, indent=2)}

Guclu Yonler: {', '.join(result2.strengths[:3]) if result2.strengths else 'Belirtilmemis'}
Zayif Yonler: {', '.join(result2.weaknesses[:3]) if result2.weaknesses else 'Belirtilmemis'}

===============================================================================
HAKIM TALIMATI
===============================================================================

Iki modelin degerlendirmelerini incele ve final kararini ver:

1. Hangi model daha tutarli ve mantikli argumanlar sunuyor?
2. Hangi puanlama daha adil ve objektif?
3. Eksik veya yanlis degerlendirme var mi?
4. Eger iki model eligible konusunda uyusmuyorsa, hangisi dogru?

SADECE JSON formatinda yanit ver (ayni sema kullan).
Kendi bagimsiz degerlendirmeni yap, sadece modellerin ortalamasini alma.
"""

    def _repair_json(self, text: str) -> str:
        """
        Bozuk JSON'u duzeltmeye calisir.
        LLM'lerin urettigi yaygin JSON hatalarini duzeltir.
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

        # 2. Virgul eksikligi duzelt: "value"\n"key" -> "value",\n"key"
        text = re.sub(r'"\s*\n\s*"', '",\n"', text)

        # 3. Sayi/bool sonrasi virgul eksikligi: 85\n"key" -> 85,\n"key"
        text = re.sub(r'(\d)\s*\n\s*"', r'\1,\n"', text)
        text = re.sub(r'(true|false|null)\s*\n\s*"', r'\1,\n"', text)

        # 4. Array sonrasi virgul eksikligi: ]\n"key" -> ],\n"key"
        text = re.sub(r'\]\s*\n\s*"', '],\n"', text)

        # 5. Object sonrasi virgul eksikligi: }\n"key" -> },\n"key"
        text = re.sub(r'\}\s*\n\s*"', '},\n"', text)

        # 6. Trailing comma kaldir: ,} -> } ve ,] -> ]
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # 7. Cift virgul kaldir: ,, -> ,
        text = re.sub(r',\s*,', ',', text)

        return text.strip()

    def _parse_response(
        self,
        model_name: str,
        content: str,
        elapsed: float,
        tokens: Dict[str, int]
    ) -> EvaluationResult:
        """API yanitini parse eder (JSON repair destekli)"""
        try:
            # JSON blogunu cikar
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    json_str = parts[1]

            # Ilk parse denemesi
            try:
                data = json.loads(json_str.strip())
            except json.JSONDecodeError as first_error:
                # JSON repair dene
                logger.warning(f"{model_name} JSON parse hatasi, repair deneniyor: {first_error}")
                repaired = self._repair_json(json_str)
                try:
                    data = json.loads(repaired)
                    logger.info(f"{model_name} JSON repair basarili")
                except json.JSONDecodeError:
                    # Repair de basarisiz, orijinal hatayi firlat
                    raise first_error

            # FAZ 13.3: Scores validation
            raw_scores = data.get("scores", {})
            validated_scores = {}

            # 5 kategori için validation
            required_categories = ["position_match", "experience_quality", "technical_skills", "education", "other"]
            max_scores = {"position_match": 25, "experience_quality": 25, "technical_skills": 25, "education": 15, "other": 10}

            for cat in required_categories:
                if cat in raw_scores and isinstance(raw_scores[cat], dict):
                    score = raw_scores[cat].get("score", 0)
                    # Score'u min/max ile sinirla
                    validated_scores[cat] = {
                        "score": min(max_scores[cat], max(0, int(score) if score else 0)),
                        "reason": raw_scores[cat].get("reason", ""),
                        "matched_skills": raw_scores[cat].get("matched_skills", []),
                        "missing_skills": raw_scores[cat].get("missing_skills", [])
                    }
                else:
                    # Kategori eksikse fallback: total_score'dan orantili hesapla
                    total = int(data.get("total_score", 0))
                    if total > 0:
                        ratio = max_scores[cat] / 100
                        estimated = int(total * ratio)
                        validated_scores[cat] = {
                            "score": min(max_scores[cat], estimated),
                            "reason": "AI tarafindan detaylandirilmadi",
                            "matched_skills": [],
                            "missing_skills": []
                        }
                    else:
                        validated_scores[cat] = {
                            "score": 0,
                            "reason": "Degerlendirilemedi",
                            "matched_skills": [],
                            "missing_skills": []
                        }

            # Log: scores bossa uyari
            if not raw_scores or len(raw_scores) < 5:
                logger.warning(f"{model_name} scores eksik/bos ({len(raw_scores)}/5 kategori), fallback uygulandi")

            return EvaluationResult(
                model_name=model_name,
                eligible=data.get("eligible", False),
                total_score=min(100, max(0, int(data.get("total_score", 0)))),
                scores=validated_scores,
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
            logger.warning(f"{model_name} JSON parse hatasi: {e}")
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
                error=f"JSON parse hatasi: {str(e)}"
            )

    def _error_result(
        self,
        model_name: str,
        error: str,
        elapsed: float = 0
    ) -> EvaluationResult:
        """Hata durumunda EvaluationResult dondurur"""
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
        openai_result: Optional[EvaluationResult],
        total_time: float,
        models_used: List[str]
    ) -> FinalEvaluation:
        """Tek model basarili oldugunda final sonuc olusturur"""
        # Skorlari dogru model'den al
        gemini_score = 0
        hermes_score = 0
        openai_score = 0

        if success_result.model_name == "Gemini":
            gemini_score = success_result.total_score
        elif success_result.model_name == "Hermes":
            hermes_score = success_result.total_score
        elif success_result.model_name == "OpenAI":
            openai_score = success_result.total_score

        return FinalEvaluation(
            eligible=success_result.eligible,
            total_score=success_result.total_score,
            scores=success_result.scores,
            strengths=success_result.strengths,
            weaknesses=success_result.weaknesses,
            notes_for_hr=success_result.notes_for_hr + [f"Sadece {success_result.model_name} degerlendirdi (diger modeller basarisiz)"],
            interview_questions=success_result.interview_questions,
            overall_assessment=success_result.overall_assessment,
            elimination_reason=success_result.elimination_reason,
            gemini_score=gemini_score,
            hermes_score=hermes_score,
            openai_score=openai_score,
            score_difference=0,
            eligible_disagreement=False,
            claude_used=False,
            consensus_method="single_model",
            models_used=models_used,
            total_response_time=round(total_time, 2),
            total_tokens={
                "input": success_result.tokens_used.get("input", 0),
                "output": success_result.tokens_used.get("output", 0)
            },
            gemini_result=gemini_result,
            hermes_result=hermes_result,
            openai_result=openai_result,
            claude_result=None
        )

    def _create_final_evaluation(
        self,
        gemini_result: Optional[EvaluationResult],
        hermes_result: Optional[EvaluationResult],
        openai_result: Optional[EvaluationResult],
        claude_result: Optional[EvaluationResult],
        score_diff: int,
        eligible_disagreement: bool,
        total_time: float,
        primary_results: Optional[Tuple[EvaluationResult, EvaluationResult]] = None,
        models_used: Optional[List[str]] = None
    ) -> FinalEvaluation:
        """Iki veya uc modelden final sonuc olusturur"""

        # Hangi modeller kullanildi?
        if primary_results:
            result1, result2 = primary_results
        else:
            result1 = gemini_result
            result2 = hermes_result
            models_used = ["Gemini", "Hermes"]

        # Skorlari hesapla
        gemini_score = gemini_result.total_score if gemini_result and gemini_result.error is None else 0
        hermes_score = hermes_result.total_score if hermes_result and hermes_result.error is None else 0
        openai_score = openai_result.total_score if openai_result and openai_result.error is None else 0

        # Token toplami
        total_tokens = {"input": 0, "output": 0}
        if gemini_result:
            total_tokens["input"] += gemini_result.tokens_used.get("input", 0)
            total_tokens["output"] += gemini_result.tokens_used.get("output", 0)
        if hermes_result:
            total_tokens["input"] += hermes_result.tokens_used.get("input", 0)
            total_tokens["output"] += hermes_result.tokens_used.get("output", 0)
        if openai_result:
            total_tokens["input"] += openai_result.tokens_used.get("input", 0)
            total_tokens["output"] += openai_result.tokens_used.get("output", 0)

        # FAZ 12.1: Claude 0 fallback - Claude 0 dönerse average fallback kullan
        if claude_result and claude_result.error is None and claude_result.total_score > 0:
            # Claude hakim karari (skor > 0)
            total_tokens["input"] += claude_result.tokens_used.get("input", 0)
            total_tokens["output"] += claude_result.tokens_used.get("output", 0)

            return FinalEvaluation(
                eligible=claude_result.eligible,
                total_score=claude_result.total_score,
                scores=claude_result.scores,
                strengths=claude_result.strengths,
                weaknesses=claude_result.weaknesses,
                notes_for_hr=claude_result.notes_for_hr + [
                    f"Claude hakim karari ({result1.model_name}: {result1.total_score}, {result2.model_name}: {result2.total_score})"
                ],
                interview_questions=claude_result.interview_questions,
                overall_assessment=claude_result.overall_assessment,
                elimination_reason=claude_result.elimination_reason,
                gemini_score=gemini_score,
                hermes_score=hermes_score,
                openai_score=openai_score,
                score_difference=score_diff,
                eligible_disagreement=eligible_disagreement,
                claude_used=True,
                consensus_method="claude_decision",
                models_used=models_used,
                total_response_time=round(total_time, 2),
                total_tokens=total_tokens,
                gemini_result=gemini_result,
                hermes_result=hermes_result,
                openai_result=openai_result,
                claude_result=claude_result
            )

        # FAZ 12.1: Claude 0 döndü uyarısı
        if claude_result and claude_result.error is None and claude_result.total_score == 0:
            logger.warning(f"Claude 0 döndü, average fallback kullanılıyor. Model skorları: {result1.model_name}={result1.total_score}, {result2.model_name}={result2.total_score}")

        # Ortalama al (2 basarili model)
        avg_score = (result1.total_score + result2.total_score) // 2

        # Her iki model de eligible ise eligible, biri bile degilse degil
        final_eligible = result1.eligible and result2.eligible

        # Scores ortalamasi
        final_scores = self._average_scores(result1.scores, result2.scores)

        # Strengths/weaknesses birlestir (unique)
        final_strengths = list(dict.fromkeys(result1.strengths + result2.strengths))[:5]
        final_weaknesses = list(dict.fromkeys(result1.weaknesses + result2.weaknesses))[:5]

        # Notes birlestir
        final_notes = list(dict.fromkeys(result1.notes_for_hr + result2.notes_for_hr))

        # Uyari notlari ekle
        if score_diff > self.SCORE_DIFFERENCE_THRESHOLD:
            final_notes.append(f"Modeller arasinda {score_diff} puan fark var")
        if eligible_disagreement:
            final_notes.append(f"eligible uyumsuzlugu: {result1.model_name}={result1.eligible}, {result2.model_name}={result2.eligible}")
        if (score_diff > self.SCORE_DIFFERENCE_THRESHOLD or eligible_disagreement) and not self.claude_api_key:
            final_notes.append("Claude API key olmadigi icin ortalama alindi")
        # FAZ 12.1: Claude 0 döndüğünde not ekle
        if claude_result and claude_result.error is None and claude_result.total_score == 0:
            final_notes.append("Claude 0 döndüğü için ortalama alındı")

        # Interview questions birlestir
        final_questions = list(dict.fromkeys(result1.interview_questions + result2.interview_questions))[:5]

        # Overall assessment birlestir
        overall = f"[{result1.model_name} ({result1.total_score})] {result1.overall_assessment}\n\n[{result2.model_name} ({result2.total_score})] {result2.overall_assessment}"

        return FinalEvaluation(
            eligible=final_eligible,
            total_score=avg_score,
            scores=final_scores,
            strengths=final_strengths,
            weaknesses=final_weaknesses,
            notes_for_hr=final_notes,
            interview_questions=final_questions,
            overall_assessment=overall,
            elimination_reason=result1.elimination_reason or result2.elimination_reason,
            gemini_score=gemini_score,
            hermes_score=hermes_score,
            openai_score=openai_score,
            score_difference=score_diff,
            eligible_disagreement=eligible_disagreement,
            claude_used=False,
            consensus_method="average",
            models_used=models_used,
            total_response_time=round(total_time, 2),
            total_tokens=total_tokens,
            gemini_result=gemini_result,
            hermes_result=hermes_result,
            openai_result=openai_result,
            claude_result=claude_result
        )

    def _average_scores(
        self,
        scores1: Dict[str, Any],
        scores2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Iki skor setinin ortalamasini alir"""
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

                # matched_skills ve missing_skills varsa birlestir
                if "matched_skills" in s1 or "matched_skills" in s2:
                    result[key]["matched_skills"] = list(dict.fromkeys(
                        s1.get("matched_skills", []) + s2.get("missing_skills", [])
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


# ==============================================================================
# SENKRON WRAPPER
# ==============================================================================

def evaluate_sync(system_prompt: str, evaluation_prompt: str) -> FinalEvaluation:
    """
    Senkron evaluate fonksiyonu (FastAPI veya senkron kod icin).

    Args:
        system_prompt: Sistem promptu
        evaluation_prompt: Degerlendirme promptu

    Returns:
        FinalEvaluation: Final degerlendirme sonucu
    """
    evaluator = AIEvaluator()
    return asyncio.run(evaluator.evaluate(system_prompt, evaluation_prompt))


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    # Logging ayarla (test icin)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("\n" + "=" * 77)
    print("AIEvaluator Modul Testi (Flash Model - Maliyet Optimize)")
    print("=" * 77)

    print(f"\n API Key Durumu:")
    print(f"   Gemini API Key:  {'OK' if os.environ.get('GEMINI_API_KEY') else 'YOK'}")
    print(f"   Hermes API Key:  {'OK' if os.environ.get('HERMES_API_KEY') else 'YOK'}")
    print(f"   OpenAI API Key:  {'OK' if os.environ.get('OPENAI_API_KEY') else 'YOK (sigorta devre disi)'}")
    print(f"   Claude API Key:  {'OK' if os.environ.get('ANTHROPIC_API_KEY') else 'YOK (opsiyonel)'}")

    print(f"\n Ayarlar:")
    print(f"   Model: gemini-2.5-flash (maliyet optimize)")
    print(f"   Thinking Mode: KAPALI")
    print(f"   Score fark esigi: {AIEvaluator.SCORE_DIFFERENCE_THRESHOLD} puan")
    print(f"   Max retry: {AIEvaluator.MAX_RETRIES}")
    print(f"   API timeout: {AIEvaluator.API_TIMEOUT}s")

    print(f"\n Fallback Zinciri:")
    print(f"   1. Gemini + Hermes paralel -> basarili ise consensus")
    print(f"   2. Biri basarisiz -> OpenAI sigorta devreye")
    print(f"   3. 2 model basarili -> consensus")
    print(f"   4. Tek model basarili -> tek skor (son care)")

    print(f"\n aiohttp durumu: {'OK' if aiohttp else 'YOK'}")
    print(f"   openai durumu: {'OK' if openai else 'YOK'}")

    print("\n" + "=" * 77)
    print("Modul basariyla yuklendi. Kullanim icin:")
    print("  from ai_evaluator import AIEvaluator, evaluate_sync")
    print("=" * 77)
