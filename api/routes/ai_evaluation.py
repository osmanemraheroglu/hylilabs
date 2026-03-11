"""
Scoring V3 - AI Değerlendirme API Route'ları

Endpoints:
- POST /api/ai-evaluation/evaluate - Tek aday değerlendirmesi
- POST /api/ai-evaluation/evaluate-batch - Toplu değerlendirme
- GET /api/ai-evaluation/status/{candidate_id}/{position_id} - Değerlendirme durumu
- GET /api/ai-evaluation/daily-limit - Günlük limit durumu
"""

from fastapi import APIRouter, Depends, HTTPException
from routes.auth import get_current_user
from database import (
    get_candidate,
    get_department_pool,
    verify_department_pool_ownership,
    save_ai_evaluation,
    get_ai_evaluation,
    check_ai_daily_limit,
    save_candidate_intelligence,
    get_candidate_intelligence,
    get_candidates_without_intelligence,
    get_intelligence_stats
)
from typing import Optional
import json
import logging
import time
import traceback
from datetime import datetime

# Scoring V3 import
from core.scoring_v3 import (
    evaluate_candidate,
    CandidateEvaluationResponse,
    analyze_candidate_intelligence,
    analyze_candidates_batch as analyze_intelligence_batch,
    IntelligenceResult
)

router = APIRouter(prefix="/api/ai-evaluation", tags=["AI Evaluation"])
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════

def _get_candidate_data(candidate) -> dict:
    """Candidate modelini dict'e çevirir (AI için)"""
    return {
        "ad_soyad": candidate.ad_soyad,
        "email": candidate.email,
        "telefon": candidate.telefon,
        "lokasyon": candidate.lokasyon,
        "egitim": candidate.egitim,
        "universite": candidate.universite,
        "bolum": candidate.bolum,
        "toplam_deneyim_yil": candidate.toplam_deneyim_yil,
        "mevcut_pozisyon": candidate.mevcut_pozisyon,
        "mevcut_sirket": candidate.mevcut_sirket,
        "deneyim_detay": candidate.deneyim_detay,
        "deneyim_aciklama": candidate.deneyim_aciklama,
        "teknik_beceriler": candidate.teknik_beceriler,
        "diller": candidate.diller,
        "sertifikalar": candidate.sertifikalar,
        "ozet": candidate.ozet
    }


def _get_position_data(pool: dict) -> dict:
    """Pozisyon havuzunu dict'e çevirir (AI için)"""
    keywords = pool.get("keywords", [])
    if isinstance(keywords, str):
        try:
            keywords = json.loads(keywords)
        except:
            keywords = []

    return {
        "name": pool.get("name", ""),
        "lokasyon": pool.get("lokasyon", ""),
        "gerekli_deneyim_yil": pool.get("gerekli_deneyim_yil", 0),
        "gerekli_egitim": pool.get("gerekli_egitim", ""),
        "keywords": keywords,
        "aranan_nitelikler": pool.get("aranan_nitelikler", ""),
        "is_tanimi": pool.get("is_tanimi", ""),
        "gorev_tanimi_raw_text": pool.get("gorev_tanimi_raw_text", "")
    }


def _save_v3_evaluation(
    candidate_id: int,
    position_id: int,
    result: CandidateEvaluationResponse
) -> bool:
    """V3 değerlendirme sonucunu veritabanına kaydeder."""
    try:
        evaluation_data = {
            "version": "v3",
            "eligible": result.eligible,
            "total_score": result.total_score,
            "gemini_score": result.gemini_score,
            "hermes_score": result.hermes_score,
            "score_difference": result.score_difference,
            "claude_used": result.claude_used,
            "consensus_method": result.consensus_method,
            "scores": result.scores,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "notes_for_hr": result.notes_for_hr,
            "interview_questions": result.interview_questions,
            "overall_assessment": result.overall_assessment,
            "elimination_reason": result.elimination_reason,
            "evaluated_at": datetime.now().isoformat()
        }

        evaluation_text = json.dumps(evaluation_data, ensure_ascii=False)

        return save_ai_evaluation(
            candidate_id=candidate_id,
            position_id=position_id,
            evaluation_text=evaluation_text,
            v2_score=result.total_score,
            eval_prompt=""
        )
    except Exception as e:
        logger.error(f"V3 değerlendirme kayıt hatası: {e}")
        return False


def _get_v3_evaluation(candidate_id: int, position_id: int) -> Optional[dict]:
    """V3 değerlendirme sonucunu veritabanından getirir."""
    try:
        result = get_ai_evaluation(candidate_id, position_id)
        if not result:
            return None

        try:
            data = json.loads(result["evaluation_text"])
            if data.get("version") == "v3":
                data["created_at"] = result["created_at"]
                return data
        except:
            pass

        return None
    except Exception as e:
        logger.error(f"V3 değerlendirme okuma hatası: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: TEK ADAY DEĞERLENDİRMESİ
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/evaluate")
async def evaluate_single(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Tek aday-pozisyon değerlendirmesi yapar.

    Body:
        candidate_id: int
        position_id: int
        force_refresh: bool (optional)
    """
    start_time = time.time()
    company_id = current_user["company_id"]

    try:
        candidate_id = body.get("candidate_id")
        position_id = body.get("position_id")
        force_refresh = body.get("force_refresh", False)

        if not candidate_id or not position_id:
            raise HTTPException(
                status_code=400,
                detail="candidate_id ve position_id zorunludur"
            )

        # Günlük limit kontrolü
        can_evaluate, limit_message, remaining = check_ai_daily_limit(company_id)
        if not can_evaluate:
            raise HTTPException(status_code=429, detail=limit_message)

        # Aday kontrolü (company_id güvenlik kontrolü dahil)
        candidate = get_candidate(candidate_id, company_id=company_id)
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="Aday bulunamadı veya erişim yetkiniz yok"
            )

        # Pozisyon kontrolü
        pool = get_department_pool(position_id)
        if not pool:
            raise HTTPException(status_code=404, detail="Pozisyon bulunamadı")

        if not verify_department_pool_ownership(position_id, company_id):
            raise HTTPException(
                status_code=403,
                detail="Bu pozisyona erişim yetkiniz yok"
            )

        # Cache kontrolü
        if not force_refresh:
            cached = _get_v3_evaluation(candidate_id, position_id)
            if cached:
                elapsed = time.time() - start_time
                logger.info(f"Cache'den döndürüldü: candidate={candidate_id}, position={position_id}")
                return {
                    "success": True,
                    "data": {
                        "total_score": cached["total_score"],
                        "eligible": cached["eligible"],
                        "evaluation_method": cached["consensus_method"],
                        "gemini_score": cached["gemini_score"],
                        "hermes_score": cached["hermes_score"],
                        "claude_used": cached["claude_used"],
                        "layer_scores": cached["scores"],
                        "strengths": cached["strengths"],
                        "weaknesses": cached["weaknesses"],
                        "notes": " | ".join(cached["notes_for_hr"]) if cached["notes_for_hr"] else "",
                        "overall_assessment": cached["overall_assessment"],
                        "processing_time": elapsed,
                        "from_cache": True,
                        "evaluated_at": cached.get("created_at")
                    }
                }

        # AI değerlendirmesi yap
        candidate_data = _get_candidate_data(candidate)
        position_data = _get_position_data(pool)

        logger.info(f"AI değerlendirme başlatılıyor: candidate={candidate_id}, position={position_id}")

        result: CandidateEvaluationResponse = await evaluate_candidate(
            candidate_id=candidate_id,
            position_id=position_id,
            candidate_data=candidate_data,
            position_data=position_data
        )

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"AI değerlendirme hatası: {result.error_message}"
            )

        # Sonucu kaydet
        _save_v3_evaluation(candidate_id, position_id, result)

        elapsed = time.time() - start_time
        logger.info(f"Değerlendirme tamamlandı: candidate={candidate_id}, score={result.total_score}, süre={elapsed:.2f}s")

        return {
            "success": True,
            "data": {
                "total_score": result.total_score,
                "eligible": result.eligible,
                "evaluation_method": result.consensus_method,
                "gemini_score": result.gemini_score,
                "hermes_score": result.hermes_score,
                "claude_used": result.claude_used,
                "layer_scores": result.scores,
                "strengths": result.strengths,
                "weaknesses": result.weaknesses,
                "notes": " | ".join(result.notes_for_hr) if result.notes_for_hr else "",
                "overall_assessment": result.overall_assessment,
                "interview_questions": result.interview_questions,
                "elimination_reason": result.elimination_reason,
                "processing_time": elapsed,
                "from_cache": False,
                "remaining_daily_limit": remaining - 1 if remaining > 0 else remaining
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Değerlendirme hatası: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Değerlendirme sırasında bir hata oluştu: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: TOPLU DEĞERLENDİRME
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/evaluate-batch")
async def evaluate_batch(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Birden fazla adayı tek pozisyon için değerlendirir.

    Body:
        candidate_ids: List[int]
        position_id: int
        force_refresh: bool (optional)
    """
    start_time = time.time()
    company_id = current_user["company_id"]

    try:
        candidate_ids = body.get("candidate_ids", [])
        position_id = body.get("position_id")
        force_refresh = body.get("force_refresh", False)

        if not candidate_ids or not position_id:
            raise HTTPException(
                status_code=400,
                detail="candidate_ids ve position_id zorunludur"
            )

        if len(candidate_ids) > 50:
            raise HTTPException(
                status_code=400,
                detail="Tek seferde en fazla 50 aday değerlendirilebilir"
            )

        # Günlük limit kontrolü
        can_evaluate, limit_message, remaining = check_ai_daily_limit(company_id)
        if not can_evaluate:
            raise HTTPException(status_code=429, detail=limit_message)

        # Pozisyon kontrolü
        pool = get_department_pool(position_id)
        if not pool:
            raise HTTPException(status_code=404, detail="Pozisyon bulunamadı")

        if not verify_department_pool_ownership(position_id, company_id):
            raise HTTPException(
                status_code=403,
                detail="Bu pozisyona erişim yetkiniz yok"
            )

        position_data = _get_position_data(pool)
        results = []
        successful = 0
        failed = 0
        eligible_count = 0
        total_score = 0

        for candidate_id in candidate_ids:
            try:
                candidate = get_candidate(candidate_id, company_id=company_id)
                if not candidate:
                    results.append({
                        "candidate_id": candidate_id,
                        "success": False,
                        "error": "Aday bulunamadı veya erişim yetkiniz yok"
                    })
                    failed += 1
                    continue

                # Cache kontrolü
                if not force_refresh:
                    cached = _get_v3_evaluation(candidate_id, position_id)
                    if cached:
                        results.append({
                            "candidate_id": candidate_id,
                            "candidate_name": candidate.ad_soyad,
                            "success": True,
                            "total_score": cached["total_score"],
                            "eligible": cached["eligible"],
                            "evaluation_method": cached["consensus_method"],
                            "from_cache": True
                        })
                        successful += 1
                        total_score += cached["total_score"]
                        if cached["eligible"]:
                            eligible_count += 1
                        continue

                # AI değerlendirmesi
                candidate_data = _get_candidate_data(candidate)
                result = await evaluate_candidate(
                    candidate_id=candidate_id,
                    position_id=position_id,
                    candidate_data=candidate_data,
                    position_data=position_data
                )

                if result.success:
                    _save_v3_evaluation(candidate_id, position_id, result)
                    results.append({
                        "candidate_id": candidate_id,
                        "candidate_name": candidate.ad_soyad,
                        "success": True,
                        "total_score": result.total_score,
                        "eligible": result.eligible,
                        "evaluation_method": result.consensus_method,
                        "claude_used": result.claude_used,
                        "from_cache": False
                    })
                    successful += 1
                    total_score += result.total_score
                    if result.eligible:
                        eligible_count += 1
                else:
                    results.append({
                        "candidate_id": candidate_id,
                        "candidate_name": candidate.ad_soyad,
                        "success": False,
                        "error": result.error_message
                    })
                    failed += 1

            except Exception as e:
                logger.error(f"Batch değerlendirme hatası (candidate={candidate_id}): {e}")
                results.append({
                    "candidate_id": candidate_id,
                    "success": False,
                    "error": str(e)
                })
                failed += 1

        elapsed = time.time() - start_time
        average_score = total_score / successful if successful > 0 else 0

        logger.info(f"Toplu değerlendirme tamamlandı: {successful}/{len(candidate_ids)} başarılı, süre={elapsed:.2f}s")

        return {
            "success": True,
            "data": {
                "results": results,
                "summary": {
                    "total": len(candidate_ids),
                    "successful": successful,
                    "failed": failed,
                    "eligible_count": eligible_count,
                    "average_score": round(average_score, 1),
                    "processing_time": round(elapsed, 2)
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Toplu değerlendirme hatası: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Toplu değerlendirme sırasında bir hata oluştu: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: DEĞERLENDİRME DURUMU
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status/{candidate_id}/{position_id}")
async def get_evaluation_status(
    candidate_id: int,
    position_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mevcut değerlendirme durumunu sorgular."""
    company_id = current_user["company_id"]

    try:
        # Güvenlik kontrolleri
        candidate = get_candidate(candidate_id, company_id=company_id)
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="Aday bulunamadı veya erişim yetkiniz yok"
            )

        if not verify_department_pool_ownership(position_id, company_id):
            raise HTTPException(
                status_code=403,
                detail="Bu pozisyona erişim yetkiniz yok"
            )

        evaluation = _get_v3_evaluation(candidate_id, position_id)

        if evaluation:
            return {
                "success": True,
                "data": {
                    "exists": True,
                    "evaluation": {
                        "total_score": evaluation["total_score"],
                        "eligible": evaluation["eligible"],
                        "evaluation_method": evaluation["consensus_method"],
                        "gemini_score": evaluation["gemini_score"],
                        "hermes_score": evaluation["hermes_score"],
                        "claude_used": evaluation["claude_used"],
                        "evaluated_at": evaluation.get("created_at"),
                        "strengths": evaluation["strengths"],
                        "weaknesses": evaluation["weaknesses"],
                        "notes": evaluation["notes_for_hr"],
                        "interview_questions": evaluation.get("interview_questions", [])
                    }
                }
            }
        else:
            return {
                "success": True,
                "data": {
                    "exists": False,
                    "evaluation": None
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Değerlendirme durumu sorgulama hatası: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sorgulama sırasında bir hata oluştu: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT: GÜNLÜK LİMİT DURUMU
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/daily-limit")
async def get_daily_limit_status(
    current_user: dict = Depends(get_current_user)
):
    """Şirketin günlük AI değerlendirme limit durumunu döndürür."""
    company_id = current_user["company_id"]

    try:
        can_evaluate, message, remaining = check_ai_daily_limit(company_id)

        return {
            "success": True,
            "data": {
                "can_evaluate": can_evaluate,
                "remaining": remaining,
                "message": message if message else (
                    "Sınırsız" if remaining == -1 else f"{remaining} değerlendirme hakkınız kaldı"
                )
            }
        }

    except Exception as e:
        logger.exception(f"Limit sorgulama hatası: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Limit sorgulanırken bir hata oluştu: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CV INTELLIGENCE ENDPOINT'LERİ
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/intelligence/stats")
async def get_intelligence_statistics(
    current_user: dict = Depends(get_current_user)
):
    """Şirketin CV intelligence istatistiklerini döndürür."""
    company_id = current_user["company_id"]

    try:
        stats = get_intelligence_stats(company_id)
        return {"success": True, "data": stats}
    except Exception as e:
        logger.exception(f"Intelligence istatistik hatası: {e}")
        raise HTTPException(status_code=500, detail=f"İstatistikler getirilirken hata: {str(e)}")


@router.get("/intelligence/pending")
async def get_pending_intelligence(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Henüz intelligence analizi yapılmamış adayları listeler."""
    company_id = current_user["company_id"]

    try:
        if limit > 100:
            limit = 100
        pending = get_candidates_without_intelligence(company_id, limit=limit)
        return {"success": True, "data": {"candidates": pending, "count": len(pending)}}
    except Exception as e:
        logger.exception(f"Pending intelligence hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Liste getirilirken hata: {str(e)}")


@router.get("/intelligence/{candidate_id}")
async def get_intelligence(
    candidate_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Adayın mevcut intelligence verisini getirir."""
    company_id = current_user["company_id"]

    try:
        candidate = get_candidate(candidate_id, company_id=company_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Aday bulunamadı veya erişim yetkiniz yok")

        intelligence = get_candidate_intelligence(candidate_id)
        if not intelligence:
            return {"success": True, "data": None, "message": "Bu aday için henüz intelligence analizi yapılmamış"}
        return {"success": True, "data": intelligence}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Intelligence getirme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Veri getirilirken hata: {str(e)}")


@router.post("/intelligence/analyze")
async def analyze_single_intelligence(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Tek adayın CV'sini analiz eder ve intelligence verisini kaydeder."""
    start_time = time.time()
    company_id = current_user["company_id"]

    try:
        candidate_id = body.get("candidate_id")
        force_refresh = body.get("force_refresh", False)

        if not candidate_id:
            raise HTTPException(status_code=400, detail="candidate_id zorunludur")

        candidate = get_candidate(candidate_id, company_id=company_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Aday bulunamadı veya erişim yetkiniz yok")

        # Mevcut intelligence var mı?
        if not force_refresh:
            existing = get_candidate_intelligence(candidate_id)
            if existing:
                return {"success": True, "data": existing, "from_cache": True, "processing_time": 0}

        # Aday verilerini hazırla
        candidate_data = {
            "ad_soyad": candidate.ad_soyad,
            "mevcut_pozisyon": candidate.mevcut_pozisyon,
            "mevcut_sirket": candidate.mevcut_sirket,
            "toplam_deneyim_yil": candidate.toplam_deneyim_yil,
            "lokasyon": candidate.lokasyon,
            "egitim": candidate.egitim,
            "universite": candidate.universite,
            "bolum": candidate.bolum,
            "teknik_beceriler": candidate.teknik_beceriler,
            "sertifikalar": candidate.sertifikalar,
            "diller": candidate.diller,
            "deneyim_detay": candidate.deneyim_detay,
            "deneyim_aciklama": candidate.deneyim_aciklama
        }

        logger.info(f"CV Intelligence analizi başlıyor: candidate_id={candidate_id}")
        result = await analyze_candidate_intelligence(candidate_id, company_id, candidate_data)
        elapsed = time.time() - start_time

        if not result.success:
            raise HTTPException(status_code=500, detail=f"CV analizi başarısız: {result.error_message}")

        # Veritabanına kaydet
        saved = save_candidate_intelligence(candidate_id, company_id, result.to_dict())
        if not saved:
            logger.error(f"Intelligence kaydetme hatası: candidate_id={candidate_id}")

        return {
            "success": True,
            "data": {
                "candidate_id": candidate_id,
                "career_path": result.career_path,
                "level": result.level,
                "experience_years": result.experience_years,
                "sectors": result.sectors,
                "suitable_positions": result.suitable_positions,
                "education_level": result.education_level,
                "education_field": result.education_field,
                "current_location": result.current_location,
                "key_skills": result.key_skills
            },
            "from_cache": False,
            "processing_time": round(elapsed, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Intelligence analiz hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Analiz sırasında hata: {str(e)}")


@router.post("/intelligence/analyze-batch")
async def analyze_batch_intelligence(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Birden fazla adayın CV'sini analiz eder (max 20)."""
    start_time = time.time()
    company_id = current_user["company_id"]

    try:
        candidate_ids = body.get("candidate_ids", [])
        force_refresh = body.get("force_refresh", False)

        if not candidate_ids:
            raise HTTPException(status_code=400, detail="candidate_ids zorunludur")

        if len(candidate_ids) > 20:
            raise HTTPException(status_code=400, detail="Tek seferde en fazla 20 aday analiz edilebilir")

        results = []
        candidates_to_analyze = []

        for cid in candidate_ids:
            candidate = get_candidate(cid, company_id=company_id)
            if not candidate:
                results.append({"candidate_id": cid, "success": False, "error": "Aday bulunamadı"})
                continue

            if not force_refresh:
                existing = get_candidate_intelligence(cid)
                if existing:
                    results.append({
                        "candidate_id": cid,
                        "candidate_name": candidate.ad_soyad,
                        "success": True,
                        "career_path": existing.get("career_path"),
                        "level": existing.get("level"),
                        "from_cache": True
                    })
                    continue

            candidates_to_analyze.append({
                "id": cid,
                "ad_soyad": candidate.ad_soyad,
                "mevcut_pozisyon": candidate.mevcut_pozisyon,
                "mevcut_sirket": candidate.mevcut_sirket,
                "toplam_deneyim_yil": candidate.toplam_deneyim_yil,
                "lokasyon": candidate.lokasyon,
                "egitim": candidate.egitim,
                "universite": candidate.universite,
                "bolum": candidate.bolum,
                "teknik_beceriler": candidate.teknik_beceriler,
                "sertifikalar": candidate.sertifikalar,
                "diller": candidate.diller,
                "deneyim_detay": candidate.deneyim_detay,
                "deneyim_aciklama": candidate.deneyim_aciklama
            })

        if candidates_to_analyze:
            batch_results = await analyze_intelligence_batch(candidates_to_analyze, company_id, max_concurrent=5)

            for result in batch_results:
                if result.success:
                    save_candidate_intelligence(result.candidate_id, company_id, result.to_dict())
                    results.append({
                        "candidate_id": result.candidate_id,
                        "success": True,
                        "career_path": result.career_path,
                        "level": result.level,
                        "suitable_positions": result.suitable_positions[:3] if result.suitable_positions else [],
                        "from_cache": False,
                        "processing_time": result.processing_time
                    })
                else:
                    results.append({
                        "candidate_id": result.candidate_id,
                        "success": False,
                        "error": result.error_message
                    })

        elapsed = time.time() - start_time
        successful = sum(1 for r in results if r.get("success"))

        return {
            "success": True,
            "data": {
                "results": results,
                "summary": {
                    "total": len(candidate_ids),
                    "successful": successful,
                    "failed": len(candidate_ids) - successful,
                    "from_cache": sum(1 for r in results if r.get("from_cache")),
                    "processing_time": round(elapsed, 2)
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Batch intelligence hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Toplu analiz sırasında hata: {str(e)}")
