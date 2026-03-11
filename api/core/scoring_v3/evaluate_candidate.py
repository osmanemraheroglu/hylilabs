"""
CandidateEvaluator - Scoring V3 Ana Değerlendirme Modülü

SmartPromptBuilder + AIEvaluator'ı birleştiren orchestrator.
Veritabanından aday/pozisyon verisi alıp AI değerlendirmesi yapar.

Kullanım:
    from evaluate_candidate import evaluate_candidate_sync

    result = evaluate_candidate_sync(
        candidate_id=444,
        position_id=7807,
        candidate_data={"ad_soyad": "...", "teknik_beceriler": "..."},
        position_data={"name": "...", "keywords": [...]}
    )

    if result.success:
        print(f"Score: {result.total_score}, Eligible: {result.eligible}")
    else:
        print(f"Hata: {result.error_message}")
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from .smart_prompt_builder import SmartPromptBuilder
from .ai_evaluator import AIEvaluator, FinalEvaluation


# Logger ayarla
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CandidateEvaluationRequest:
    """
    Değerlendirme isteği.

    Attributes:
        candidate_id: Aday ID (veritabanından)
        position_id: Pozisyon ID (veritabanından)
        candidate_data: Aday bilgileri dict'i
        position_data: Pozisyon bilgileri dict'i
    """
    candidate_id: int
    position_id: int
    candidate_data: Dict[str, Any]
    position_data: Dict[str, Any]


@dataclass
class CandidateEvaluationResponse:
    """
    Değerlendirme sonucu.

    Attributes:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        eligible: Aday uygun mu?
        total_score: Toplam puan (0-100)
        scores: Kategori bazlı puanlar
        strengths: Güçlü yönler listesi
        weaknesses: Zayıf yönler listesi
        notes_for_hr: İK için notlar
        interview_questions: Mülakat soruları
        overall_assessment: Genel değerlendirme metni
        elimination_reason: Eleme sebebi (varsa)
        gemini_score: Gemini puanı
        hermes_score: Hermes puanı
        score_difference: Puan farkı
        claude_used: Claude kullanıldı mı?
        consensus_method: Konsensüs yöntemi (average, claude_decision, single_model, error)
        success: İşlem başarılı mı?
        error_message: Hata mesajı (varsa)
    """
    candidate_id: int
    position_id: int
    eligible: bool
    total_score: int
    scores: Dict[str, Any]
    strengths: list
    weaknesses: list
    notes_for_hr: list
    interview_questions: list
    overall_assessment: str
    elimination_reason: Optional[str]

    # Meta bilgiler
    gemini_score: int
    hermes_score: int
    score_difference: int
    claude_used: bool
    consensus_method: str

    # Durum bilgileri
    success: bool
    error_message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Response'u dict'e çevirir"""
        return asdict(self)

    def to_summary(self) -> str:
        """Özet metin döndürür"""
        if not self.success:
            return f"❌ Hata: {self.error_message}"

        status = "✅ Uygun" if self.eligible else "❌ Uygun Değil"
        return (
            f"{status} | Puan: {self.total_score}/100 | "
            f"Gemini: {self.gemini_score}, Hermes: {self.hermes_score} | "
            f"Method: {self.consensus_method}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CANDIDATE EVALUATOR CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class CandidateEvaluator:
    """
    Aday değerlendirme orchestrator'ı.
    SmartPromptBuilder ve AIEvaluator'ı birleştirir.

    Kullanım:
        evaluator = CandidateEvaluator()
        request = CandidateEvaluationRequest(...)
        response = evaluator.evaluate_sync(request)
    """

    def __init__(self):
        """
        CandidateEvaluator başlat.

        Raises:
            ValueError: API key'ler eksikse
        """
        try:
            self.prompt_builder = SmartPromptBuilder()
            self.ai_evaluator = AIEvaluator()
            logger.info("CandidateEvaluator başlatıldı")
        except ValueError as e:
            logger.error(f"CandidateEvaluator başlatılamadı: {e}")
            raise

    async def evaluate(
        self,
        request: CandidateEvaluationRequest
    ) -> CandidateEvaluationResponse:
        """
        Ana değerlendirme fonksiyonu (async).

        Args:
            request: Aday ve pozisyon bilgilerini içeren istek

        Returns:
            CandidateEvaluationResponse: Değerlendirme sonucu
        """
        start_time = time.time()
        logger.info(
            f"Değerlendirme başlatıldı: candidate_id={request.candidate_id}, "
            f"position_id={request.position_id}"
        )

        try:
            # 1. Prompt oluştur
            logger.debug("Prompt oluşturuluyor...")
            evaluation_prompt = self.prompt_builder.build_evaluation_prompt(
                candidate_data=request.candidate_data,
                position_data=request.position_data
            )
            logger.debug(f"Prompt oluşturuldu: {len(evaluation_prompt)} karakter")

            # 2. AI değerlendirmesi yap
            logger.debug("AI değerlendirmesi başlatılıyor...")
            result: FinalEvaluation = await self.ai_evaluator.evaluate(
                system_prompt=self.prompt_builder.system_prompt,
                evaluation_prompt=evaluation_prompt
            )

            # 3. Response oluştur
            response = CandidateEvaluationResponse(
                candidate_id=request.candidate_id,
                position_id=request.position_id,
                eligible=result.eligible,
                total_score=result.total_score,
                scores=result.scores,
                strengths=result.strengths,
                weaknesses=result.weaknesses,
                notes_for_hr=result.notes_for_hr,
                interview_questions=result.interview_questions,
                overall_assessment=result.overall_assessment,
                elimination_reason=result.elimination_reason,
                gemini_score=result.gemini_score,
                hermes_score=result.hermes_score,
                score_difference=result.score_difference,
                claude_used=result.claude_used,
                consensus_method=result.consensus_method,
                success=True,
                error_message=None
            )

            logger.info(
                f"Değerlendirme başarılı: candidate_id={request.candidate_id}, "
                f"score={result.total_score}, eligible={result.eligible}, "
                f"method={result.consensus_method}"
            )

            return response

        except ValueError as e:
            # Validasyon hatası (eksik veri vb.)
            logger.error(f"Validasyon hatası: {e}")
            return self._error_response(request, f"Validasyon hatası: {str(e)}")

        except Exception as e:
            # Beklenmeyen hata
            logger.exception(f"Değerlendirme hatası: {e}")
            return self._error_response(request, f"Değerlendirme hatası: {str(e)}")

        finally:
            elapsed = time.time() - start_time
            logger.info(
                f"Değerlendirme tamamlandı: candidate_id={request.candidate_id}, "
                f"süre={elapsed:.2f}s"
            )

    def evaluate_sync(
        self,
        request: CandidateEvaluationRequest
    ) -> CandidateEvaluationResponse:
        """
        Senkron değerlendirme wrapper'ı.

        Args:
            request: Aday ve pozisyon bilgilerini içeren istek

        Returns:
            CandidateEvaluationResponse: Değerlendirme sonucu
        """
        return asyncio.run(self.evaluate(request))

    def _error_response(
        self,
        request: CandidateEvaluationRequest,
        error_message: str
    ) -> CandidateEvaluationResponse:
        """
        Hata durumunda boş response döndürür.

        Args:
            request: Orijinal istek
            error_message: Hata mesajı

        Returns:
            CandidateEvaluationResponse: Hata response'u
        """
        return CandidateEvaluationResponse(
            candidate_id=request.candidate_id,
            position_id=request.position_id,
            eligible=False,
            total_score=0,
            scores={},
            strengths=[],
            weaknesses=[],
            notes_for_hr=[f"⚠️ {error_message}"],
            interview_questions=[],
            overall_assessment="",
            elimination_reason=None,
            gemini_score=0,
            hermes_score=0,
            score_difference=0,
            claude_used=False,
            consensus_method="error",
            success=False,
            error_message=error_message
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def evaluate_candidate(
    candidate_id: int,
    position_id: int,
    candidate_data: Dict[str, Any],
    position_data: Dict[str, Any]
) -> CandidateEvaluationResponse:
    """
    Tek satırda aday değerlendirme (async).

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        candidate_data: Aday bilgileri dict'i
        position_data: Pozisyon bilgileri dict'i

    Returns:
        CandidateEvaluationResponse: Değerlendirme sonucu

    Kullanım:
        result = await evaluate_candidate(
            candidate_id=444,
            position_id=7807,
            candidate_data={"ad_soyad": "Test", ...},
            position_data={"name": "Developer", ...}
        )
    """
    evaluator = CandidateEvaluator()
    request = CandidateEvaluationRequest(
        candidate_id=candidate_id,
        position_id=position_id,
        candidate_data=candidate_data,
        position_data=position_data
    )
    return await evaluator.evaluate(request)


def evaluate_candidate_sync(
    candidate_id: int,
    position_id: int,
    candidate_data: Dict[str, Any],
    position_data: Dict[str, Any]
) -> CandidateEvaluationResponse:
    """
    Tek satırda aday değerlendirme (senkron).

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        candidate_data: Aday bilgileri dict'i
        position_data: Pozisyon bilgileri dict'i

    Returns:
        CandidateEvaluationResponse: Değerlendirme sonucu

    Kullanım:
        result = evaluate_candidate_sync(
            candidate_id=444,
            position_id=7807,
            candidate_data={"ad_soyad": "Test", ...},
            position_data={"name": "Developer", ...}
        )

        if result.success:
            print(f"Score: {result.total_score}")
        else:
            print(f"Hata: {result.error_message}")
    """
    return asyncio.run(evaluate_candidate(
        candidate_id, position_id, candidate_data, position_data
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Logging ayarla
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("\n" + "=" * 77)
    print("CandidateEvaluator Modül Testi")
    print("=" * 77)

    print(f"\n📌 API Key Durumu:")
    print(f"   Gemini:    {'✅' if os.environ.get('GEMINI_API_KEY') else '❌'}")
    print(f"   Hermes:    {'✅' if os.environ.get('HERMES_API_KEY') else '❌'}")
    print(f"   Anthropic: {'✅' if os.environ.get('ANTHROPIC_API_KEY') else '⚠️ Opsiyonel'}")

    print(f"\n📌 Modül yapısı:")
    print(f"   CandidateEvaluationRequest  - İstek dataclass")
    print(f"   CandidateEvaluationResponse - Sonuç dataclass")
    print(f"   CandidateEvaluator          - Orchestrator class")
    print(f"   evaluate_candidate          - Async convenience function")
    print(f"   evaluate_candidate_sync     - Sync convenience function")

    print(f"\n📌 Kullanım örneği:")
    print("""
    from evaluate_candidate import evaluate_candidate_sync

    result = evaluate_candidate_sync(
        candidate_id=444,
        position_id=7807,
        candidate_data={
            "ad_soyad": "Emir Kaan Yıldız",
            "email": "emir.yildiz.eng@gmail.com",
            "lokasyon": "Tekirdağ",
            "toplam_deneyim_yil": 10,
            "egitim": "Yüksek Lisans",
            "mevcut_pozisyon": "Electrical Manager",
            "teknik_beceriler": "SCADA, ETAP, AutoCAD"
        },
        position_data={
            "name": "System Integration Specialist",
            "company_name": "AKSA",
            "lokasyon": "Tekirdağ",
            "gerekli_deneyim_yil": 3,
            "keywords": ["scada", "autocad", "e-plan"]
        }
    )

    print(result.to_summary())
    # ✅ Uygun | Puan: 85/100 | Gemini: 87, Hermes: 83 | Method: average
    """)

    print("=" * 77)
    print("Modül başarıyla yüklendi.")
    print("=" * 77)
