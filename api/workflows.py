"""
TalentFlow - Workflow fonksiyonları
Tüm iş mantığı burada, app.py sadece UI içerecek

Bu modül agent sistemi için temel altyapıyı sağlar.
Tüm CV işleme, eşleştirme ve durum değişiklikleri bu modül üzerinden yapılmalıdır.
"""

import json
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from cv_parser import (
    parse_cv, parse_cv_with_agents, save_cv_file,
    validate_candidate_data, get_ai_scores_from_analysis,
    detect_cv_source, extract_text_from_file
)
from database import (
    get_connection, find_duplicate_candidate, create_candidate,
    process_candidate_with_dedup, create_application, add_candidate_to_pool,
    save_ai_analysis, log_api_usage, update_candidate
)
from candidate_matcher import (
    match_candidate_to_positions_ai, match_candidate_to_position_criteria,
    auto_match_candidate_to_all_positions, calculate_match_score
)
from models import Application
from events import trigger_event


# ============================================================
# CV İŞLEME WORKFLOW'LARI
# ============================================================

def workflow_parse_cv(file_content: bytes, filename: str, company_id: int,
                      user_id: str = "system", use_agents: bool = False) -> Dict[str, Any]:
    """
    CV dosyasını parse et - Temel workflow

    Args:
        file_content: CV dosya içeriği (bytes)
        filename: Dosya adı
        company_id: Firma ID
        user_id: Rate limiting için kullanıcı ID
        use_agents: AI agent modunu kullan

    Returns:
        dict: {"success": bool, "candidate": Candidate, "ai_analysis": dict,
               "warnings": list, "error": str, "processing_time_ms": int}
    """
    start_time = time.time()
    cv_source = "genel"  # Varsayılan

    try:
        # Event: CV yüklendi
        trigger_event("cv_uploaded", {
            "filename": filename,
            "company_id": company_id,
            "user_id": user_id,
            "use_agents": use_agents,
            "timestamp": datetime.now().isoformat()
        })

        # CV kaynağını tespit et (LinkedIn, Kariyer.net vs.)
        try:
            raw_text = extract_text_from_file(file_content, filename)
            cv_source = detect_cv_source(raw_text, filename)
        except Exception:
            cv_source = "genel"

        # CV'yi parse et
        if use_agents:
            result = parse_cv_with_agents(file_content, filename, user_id=user_id)

            if not result.get("success"):
                trigger_event("cv_parse_failed", {
                    "filename": filename,
                    "error": result.get("error", "Parse hatası"),
                    "use_agents": True
                })
                return {"success": False, "error": result.get("error", "Parse hatası")}

            candidate = result.get("candidate")
            ai_analysis = result.get("ai_analysis", {})
            scores = get_ai_scores_from_analysis(ai_analysis) if ai_analysis else None
        else:
            result = parse_cv(file_content, filename, user_id=user_id)

            if not result.basarili:
                trigger_event("cv_parse_failed", {
                    "filename": filename,
                    "error": result.hata_mesaji,
                    "use_agents": False
                })
                return {"success": False, "error": result.hata_mesaji}

            candidate = result.candidate
            ai_analysis = None
            scores = None

        if not candidate:
            return {"success": False, "error": "Aday bilgisi çıkarılamadı"}

        # Uyarıları kontrol et
        warnings = validate_candidate_data(candidate)

        processing_time = int((time.time() - start_time) * 1000)

        # Event: CV başarıyla parse edildi
        trigger_event("cv_parsed", {
            "filename": filename,
            "candidate_name": candidate.ad_soyad,
            "candidate_email": candidate.email,
            "use_agents": use_agents,
            "has_warnings": len(warnings) > 0,
            "processing_time_ms": processing_time
        })

        return {
            "success": True,
            "candidate": candidate,
            "ai_analysis": ai_analysis,
            "scores": scores,
            "warnings": warnings,
            "processing_time_ms": processing_time,
            "cv_source": cv_source  # linkedin, kariyernet, yenibiris, secretcv, genel
        }

    except Exception as e:
        trigger_event("cv_parse_error", {
            "filename": filename,
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


def workflow_process_cv(file_content: bytes, filename: str, company_id: int,
                        user_id: str = "system", use_agents: bool = False,
                        auto_save: bool = True) -> Dict[str, Any]:
    """
    CV'yi parse et ve kaydet - Tam işleme workflow'u

    Args:
        file_content: CV dosya içeriği
        filename: Dosya adı
        company_id: Firma ID
        user_id: Kullanıcı ID
        use_agents: AI agent modu
        auto_save: Otomatik kaydet

    Returns:
        dict: Detaylı sonuç
    """
    try:
        # 1. CV'yi parse et
        parse_result = workflow_parse_cv(
            file_content, filename, company_id, user_id, use_agents
        )

        if not parse_result.get("success"):
            return parse_result

        candidate = parse_result["candidate"]
        ai_analysis = parse_result.get("ai_analysis")
        scores = parse_result.get("scores")
        warnings = parse_result.get("warnings", [])

        # 2. CV dosyasını kaydet
        cv_path = save_cv_file(file_content, filename, candidate.email)
        if cv_path:
            candidate.cv_dosya_yolu = cv_path

        if not auto_save:
            return {
                "success": True,
                "candidate": candidate,
                "ai_analysis": ai_analysis,
                "scores": scores,
                "warnings": warnings,
                "saved": False
            }

        # 3. Duplicate kontrolü
        existing = find_duplicate_candidate(candidate.email or "", candidate.telefon)

        if existing:
            trigger_event("candidate_duplicate_found", {
                "new_candidate": candidate.ad_soyad,
                "existing_id": existing.id,
                "existing_name": existing.ad_soyad,
                "match_field": "email_or_phone"
            })

            return {
                "success": True,
                "candidate": candidate,
                "candidate_id": existing.id,
                "is_duplicate": True,
                "existing_candidate": existing,
                "ai_analysis": ai_analysis,
                "scores": scores,
                "warnings": warnings,
                "message": f"Mevcut aday bulundu: {existing.ad_soyad} (ID: {existing.id})"
            }

        # 4. Yeni aday kaydet
        candidate_id = create_candidate(candidate, company_id)

        trigger_event("candidate_created", {
            "candidate_id": candidate_id,
            "ad_soyad": candidate.ad_soyad,
            "email": candidate.email,
            "company_id": company_id,
            "source": "cv_upload"
        })

        # 5. AI analizi kaydet
        if ai_analysis and scores:
            save_ai_analysis(
                candidate_id=candidate_id,
                analysis_type="cv_parse",
                analysis_data=json.dumps(ai_analysis, ensure_ascii=False),
                skill_score=scores.get("skill_score"),
                experience_score=scores.get("experience_score"),
                overall_score=scores.get("overall_score"),
                career_level=scores.get("career_level"),
                strengths=", ".join(scores.get("strengths", [])[:5]),
                improvements=", ".join(scores.get("improvements", [])[:5]),
                processing_time_ms=parse_result.get("processing_time_ms")
            )

        return {
            "success": True,
            "candidate": candidate,
            "candidate_id": candidate_id,
            "is_duplicate": False,
            "ai_analysis": ai_analysis,
            "scores": scores,
            "warnings": warnings,
            "saved": True
        }

    except Exception as e:
        trigger_event("cv_process_error", {"error": str(e), "filename": filename})
        return {"success": False, "error": str(e)}


def workflow_full_application(file_content: bytes, filename: str, company_id: int,
                               position_id: int = None, user_id: str = "system",
                               use_agents: bool = False, auto_merge: bool = True,
                               kaynak: str = "manuel",
                               basvuru_tarihi: datetime = None) -> Dict[str, Any]:
    """
    Tam başvuru işleme: parse + deduplication + havuz ekleme + eşleştirme

    Args:
        file_content: CV dosya içeriği
        filename: Dosya adı
        company_id: Firma ID
        position_id: Pozisyon ID (opsiyonel)
        user_id: Kullanıcı ID
        use_agents: AI agent modu
        auto_merge: Otomatik birleştirme
        kaynak: Başvuru kaynağı (manuel, email, web vb.)
        basvuru_tarihi: Başvuru tarihi (email için email geliş tarihi, None ise datetime.now())

    Returns:
        dict: Detaylı sonuç
    """
    start_time = time.time()

    try:
        # Event: Başvuru alındı
        trigger_event("application_received", {
            "filename": filename,
            "company_id": company_id,
            "position_id": position_id,
            "kaynak": kaynak,
            "timestamp": datetime.now().isoformat()
        })

        # 1. CV'yi parse et
        parse_result = workflow_parse_cv(
            file_content, filename, company_id, user_id, use_agents
        )

        if not parse_result.get("success"):
            return parse_result

        candidate = parse_result["candidate"]
        ai_analysis = parse_result.get("ai_analysis")
        scores = parse_result.get("scores")

        # 2. CV dosyasını kaydet
        cv_path = save_cv_file(file_content, filename, candidate.email)
        if cv_path:
            candidate.cv_dosya_yolu = cv_path
            candidate.cv_dosya_adi = filename  # Duplicate kontrolü için

        # 3. Deduplication ile aday işle
        dedup_result = process_candidate_with_dedup(
            candidate=candidate,
            company_id=company_id,
            auto_merge=auto_merge
        )

        candidate_id = dedup_result["candidate_id"]
        is_duplicate = dedup_result["is_duplicate"]

        # Event
        if is_duplicate:
            trigger_event("candidate_duplicate_merged", {
                "candidate_id": candidate_id,
                "match_type": dedup_result.get("match_type"),
                "action": dedup_result.get("action")
            })
        else:
            trigger_event("candidate_created", {
                "candidate_id": candidate_id,
                "ad_soyad": candidate.ad_soyad,
                "company_id": company_id,
                "source": kaynak
            })

        # 4. AI analizi kaydet
        if ai_analysis and scores:
            save_ai_analysis(
                candidate_id=candidate_id,
                analysis_type="full_application",
                analysis_data=json.dumps(ai_analysis, ensure_ascii=False),
                skill_score=scores.get("skill_score"),
                experience_score=scores.get("experience_score"),
                overall_score=scores.get("overall_score"),
                career_level=scores.get("career_level"),
                strengths=", ".join(scores.get("strengths", [])[:5]),
                improvements=", ".join(scores.get("improvements", [])[:5]),
                processing_time_ms=parse_result.get("processing_time_ms")
            )

        # 5. Başvuru oluştur
        application = Application(
            candidate_id=candidate_id,
            position_id=position_id,
            kaynak=kaynak,
            basvuru_tarihi=basvuru_tarihi if basvuru_tarihi else datetime.now()
        )
        app_id = create_application(application)

        trigger_event("application_created", {
            "application_id": app_id,
            "candidate_id": candidate_id,
            "position_id": position_id,
            "kaynak": kaynak
        })

        # 6. Pozisyon havuzuna ekle
        pool_result = None
        if position_id:
            pool_result = workflow_add_to_pool(
                candidate_id=candidate_id,
                position_id=position_id,
                uyum_puani=scores.get("overall_score", 0) if scores else 0
            )

        # 7. Departman havuzuna otomatik ata
        dept_pool_result = None
        try:
            from database import auto_assign_candidate_to_pool
            dept_pool_result = auto_assign_candidate_to_pool(candidate_id, company_id, position_id)

            if dept_pool_result:
                trigger_event("candidate_pool_assigned", {
                    "candidate_id": candidate_id,
                    "assignments": dept_pool_result
                })
        except Exception as e:
            # Havuz ataması başarısız olsa da işlem devam etsin
            pass

        # 8. Otomatik pozisyon eşleştirme
        auto_match_result = None
        try:
            candidate_dict = {
                "id": candidate_id,
                "ad_soyad": candidate.ad_soyad if hasattr(candidate, 'ad_soyad') else "",
                "email": candidate.email if hasattr(candidate, 'email') else "",
                "teknik_beceriler": candidate.teknik_beceriler if hasattr(candidate, 'teknik_beceriler') else "",
                "toplam_deneyim_yil": candidate.toplam_deneyim_yil if hasattr(candidate, 'toplam_deneyim_yil') else 0,
                "egitim": candidate.egitim if hasattr(candidate, 'egitim') else "",
                "mevcut_pozisyon": candidate.mevcut_pozisyon if hasattr(candidate, 'mevcut_pozisyon') else "",
            }
            auto_match_result = auto_match_candidate_to_all_positions(candidate_dict, company_id)
        except Exception as e:
            # Otomatik eşleştirme başarısız olsa da işlem devam etsin
            pass

        processing_time = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "candidate": candidate,
            "candidate_id": candidate_id,
            "application_id": app_id,
            "is_duplicate": is_duplicate,
            "match_type": dedup_result.get("match_type"),
            "action": dedup_result.get("action"),
            "ai_analysis": ai_analysis,
            "scores": scores,
            "pool_result": pool_result,
            "dept_pool_result": dept_pool_result,
            "auto_match_result": auto_match_result,
            "processing_time_ms": processing_time
        }

    except Exception as e:
        trigger_event("application_error", {
            "filename": filename,
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


# ============================================================
# EŞLEŞTİRME WORKFLOW'LARI
# ============================================================

def workflow_match_candidate(candidate_id: int, company_id: int,
                              position_id: int = None) -> Dict[str, Any]:
    """
    Adayı pozisyonlarla eşleştir

    Args:
        candidate_id: Aday ID
        company_id: Firma ID
        position_id: Belirli pozisyon ID (None ise tüm açık pozisyonlar)

    Returns:
        dict: {"success": bool, "matches": list, "best_match": dict}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Aday bilgilerini al
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Aday bulunamadı"}

            candidate = dict(row)

            # Pozisyonları al
            if position_id:
                cursor.execute("""
                    SELECT * FROM positions WHERE id = ? AND company_id = ?
                """, (position_id, company_id))
            else:
                cursor.execute("""
                    SELECT * FROM positions
                    WHERE company_id = ? AND aktif = 1
                """, (company_id,))

            positions = [dict(row) for row in cursor.fetchall()]

        if not positions:
            return {"success": True, "matches": [], "best_match": None}

        # Event: Eşleştirme başladı
        trigger_event("matching_started", {
            "candidate_id": candidate_id,
            "candidate_name": candidate.get("ad_soyad"),
            "position_count": len(positions),
            "single_position": position_id is not None
        })

        # Eşleştirme yap
        matches = match_candidate_to_positions_ai(candidate, positions)

        # En iyi eşleşmeyi bul
        if matches:
            matches.sort(key=lambda x: x.get("toplam_puan", 0), reverse=True)
            best_match = matches[0]
        else:
            best_match = None

        # Event: Eşleştirme tamamlandı
        trigger_event("matching_completed", {
            "candidate_id": candidate_id,
            "match_count": len(matches),
            "best_match_score": best_match.get("toplam_puan") if best_match else 0,
            "best_match_position": best_match.get("position_id") if best_match else None
        })

        return {
            "success": True,
            "matches": matches,
            "best_match": best_match,
            "candidate": candidate
        }

    except Exception as e:
        trigger_event("matching_error", {
            "candidate_id": candidate_id,
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


def workflow_auto_match_all_positions(candidate_data: Dict, company_id: int,
                                       min_score: int = 0) -> Dict[str, Any]:
    """
    Adayı tüm açık pozisyonlarla otomatik eşleştir ve havuzlara ekle

    Args:
        candidate_data: Aday bilgileri dict
        company_id: Firma ID
        min_score: Minimum eşleşme puanı

    Returns:
        dict: {"success": bool, "matches": list, "pools_added": int}
    """
    try:
        candidate_id = candidate_data.get("id")

        trigger_event("auto_matching_started", {
            "candidate_id": candidate_id,
            "candidate_name": candidate_data.get("ad_soyad"),
            "company_id": company_id
        })

        # Eşleştirme yap
        matches = auto_match_candidate_to_all_positions(candidate_data, company_id)

        pools_added = 0
        for match in matches:
            if match.get("toplam_puan", 0) >= min_score:
                pool_result = workflow_add_to_pool(
                    candidate_id=candidate_id,
                    position_id=match.get("position_id"),
                    uyum_puani=match.get("toplam_puan", 0)
                )
                if pool_result.get("success"):
                    pools_added += 1

        trigger_event("auto_matching_completed", {
            "candidate_id": candidate_id,
            "total_matches": len(matches),
            "pools_added": pools_added
        })

        return {
            "success": True,
            "matches": matches,
            "pools_added": pools_added
        }

    except Exception as e:
        trigger_event("auto_matching_error", {
            "candidate_id": candidate_data.get("id"),
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


def workflow_match_to_position_criteria(candidate_data: Dict,
                                         position_data: Dict) -> Dict[str, Any]:
    """
    Adayı belirli pozisyon kriterleriyle detaylı eşleştir

    Args:
        candidate_data: Aday bilgileri
        position_data: Pozisyon bilgileri

    Returns:
        dict: Detaylı eşleştirme sonucu
    """
    try:
        trigger_event("criteria_matching_started", {
            "candidate_id": candidate_data.get("id"),
            "position_id": position_data.get("id")
        })

        result = match_candidate_to_position_criteria(candidate_data, position_data)

        trigger_event("criteria_matching_completed", {
            "candidate_id": candidate_data.get("id"),
            "position_id": position_data.get("id"),
            "total_score": result.get("toplam_puan", 0),
            "skill_match": result.get("beceri_uyumu", 0),
            "experience_match": result.get("deneyim_uyumu", 0)
        })

        return {
            "success": True,
            "result": result
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# HAVUZ WORKFLOW'LARI
# ============================================================

def workflow_add_to_pool(candidate_id: int, position_id: int,
                          uyum_puani: float = 0, durum: str = "beklemede") -> Dict[str, Any]:
    """
    Adayı pozisyon havuzuna ekle

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        uyum_puani: Uyum puanı
        durum: Havuz durumu

    Returns:
        dict: {"success": bool, "pool_id": int}
    """
    try:
        pool_id = add_candidate_to_pool(
            position_id=position_id,
            candidate_id=candidate_id,
            uyum_puani=uyum_puani,
            durum=durum
        )

        trigger_event("pool_candidate_added", {
            "candidate_id": candidate_id,
            "position_id": position_id,
            "uyum_puani": uyum_puani,
            "durum": durum,
            "pool_id": pool_id
        })

        return {
            "success": True,
            "pool_id": pool_id
        }

    except Exception as e:
        # Zaten havuzda olabilir
        if "UNIQUE constraint" in str(e):
            return {"success": True, "already_exists": True}
        return {"success": False, "error": str(e)}


def workflow_update_pool_status(candidate_id: int, position_id: int,
                                 new_status: str, notes: str = None) -> Dict[str, Any]:
    """
    Havuzdaki aday durumunu güncelle

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        new_status: Yeni durum
        notes: Notlar

    Returns:
        dict: {"success": bool}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Mevcut durumu al
            cursor.execute("""
                SELECT durum FROM position_pools
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, position_id))
            row = cursor.fetchone()
            old_status = row["durum"] if row else None

            # Güncelle
            cursor.execute("""
                UPDATE position_pools
                SET durum = ?, guncelleme_tarihi = CURRENT_TIMESTAMP
                WHERE candidate_id = ? AND position_id = ?
            """, (new_status, candidate_id, position_id))

            conn.commit()

        trigger_event("pool_status_changed", {
            "candidate_id": candidate_id,
            "position_id": position_id,
            "old_status": old_status,
            "new_status": new_status
        })

        return {"success": True, "old_status": old_status, "new_status": new_status}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# DURUM DEĞİŞTİRME WORKFLOW'LARI
# ============================================================

def workflow_change_candidate_status(candidate_id: int, new_status: str,
                                      hr_notes: str = None, user_id: int = None,
                                      reason: str = None) -> Dict[str, Any]:
    """
    Aday durumunu değiştir ve logla

    Args:
        candidate_id: Aday ID
        new_status: Yeni durum
        hr_notes: HR notları
        user_id: İşlemi yapan kullanıcı
        reason: Değişiklik nedeni

    Returns:
        dict: {"success": bool, "old_status": str, "new_status": str}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Mevcut durumu al
            cursor.execute("SELECT durum, ad_soyad FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Aday bulunamadı"}

            old_status = row["durum"]
            candidate_name = row["ad_soyad"]

            # Güncelle
            if hr_notes:
                cursor.execute("""
                    UPDATE candidates
                    SET durum = ?, notlar = ?, guncelleme_tarihi = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_status, hr_notes, candidate_id))
            else:
                cursor.execute("""
                    UPDATE candidates
                    SET durum = ?, guncelleme_tarihi = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_status, candidate_id))

            conn.commit()

        # Event: Durum değişti
        trigger_event("candidate_status_changed", {
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "old_status": old_status,
            "new_status": new_status,
            "user_id": user_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "success": True,
            "old_status": old_status,
            "new_status": new_status,
            "candidate_name": candidate_name
        }

    except Exception as e:
        trigger_event("status_change_error", {
            "candidate_id": candidate_id,
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


def workflow_bulk_status_change(candidate_ids: List[int], new_status: str,
                                 user_id: int = None, reason: str = None) -> Dict[str, Any]:
    """
    Toplu durum değişikliği

    Args:
        candidate_ids: Aday ID listesi
        new_status: Yeni durum
        user_id: İşlemi yapan kullanıcı
        reason: Değişiklik nedeni

    Returns:
        dict: {"success": bool, "updated_count": int, "failed": list}
    """
    updated = []
    failed = []

    trigger_event("bulk_status_change_started", {
        "candidate_count": len(candidate_ids),
        "new_status": new_status,
        "user_id": user_id
    })

    for cid in candidate_ids:
        result = workflow_change_candidate_status(
            candidate_id=cid,
            new_status=new_status,
            user_id=user_id,
            reason=reason
        )
        if result.get("success"):
            updated.append(cid)
        else:
            failed.append({"id": cid, "error": result.get("error")})

    trigger_event("bulk_status_change_completed", {
        "updated_count": len(updated),
        "failed_count": len(failed),
        "new_status": new_status
    })

    return {
        "success": len(failed) == 0,
        "updated_count": len(updated),
        "updated_ids": updated,
        "failed": failed
    }


# ============================================================
# POZİSYON WORKFLOW'LARI
# ============================================================

def workflow_create_position(position_data: Dict, company_id: int,
                              user_id: int = None) -> Dict[str, Any]:
    """
    Yeni pozisyon oluştur

    Args:
        position_data: Pozisyon bilgileri
        company_id: Firma ID
        user_id: Oluşturan kullanıcı

    Returns:
        dict: {"success": bool, "position_id": int}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO positions (
                    company_id, baslik, departman, lokasyon,
                    aciklama, gereksinimler, min_deneyim, max_deneyim,
                    min_maas, max_maas, aktif
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_id,
                position_data.get("baslik"),
                position_data.get("departman"),
                position_data.get("lokasyon"),
                position_data.get("aciklama"),
                position_data.get("gereksinimler"),
                position_data.get("min_deneyim"),
                position_data.get("max_deneyim"),
                position_data.get("min_maas"),
                position_data.get("max_maas"),
                position_data.get("aktif", True)
            ))

            position_id = cursor.lastrowid
            conn.commit()

        trigger_event("position_created", {
            "position_id": position_id,
            "baslik": position_data.get("baslik"),
            "company_id": company_id,
            "user_id": user_id
        })

        return {"success": True, "position_id": position_id}

    except Exception as e:
        return {"success": False, "error": str(e)}


def workflow_update_position(position_id: int, updates: Dict,
                              user_id: int = None) -> Dict[str, Any]:
    """
    Pozisyon güncelle

    Args:
        position_id: Pozisyon ID
        updates: Güncellenecek alanlar
        user_id: Güncelleyen kullanıcı

    Returns:
        dict: {"success": bool}
    """
    try:
        allowed_fields = [
            "baslik", "departman", "lokasyon", "aciklama",
            "gereksinimler", "min_deneyim", "max_deneyim",
            "min_maas", "max_maas", "aktif"
        ]

        set_clauses = []
        values = []

        for field, value in updates.items():
            if field in allowed_fields:
                set_clauses.append(f"{field} = ?")
                values.append(value)

        if not set_clauses:
            return {"success": False, "error": "Güncellenecek alan yok"}

        values.append(position_id)

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                UPDATE positions
                SET {', '.join(set_clauses)}, guncelleme_tarihi = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)

            conn.commit()

        trigger_event("position_updated", {
            "position_id": position_id,
            "updated_fields": list(updates.keys()),
            "user_id": user_id
        })

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# MÜLAKAT WORKFLOW'LARI
# ============================================================

def workflow_schedule_interview(candidate_id: int, position_id: int,
                                 interview_data: Dict, user_id: int = None) -> Dict[str, Any]:
    """
    Mülakat planla

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        interview_data: Mülakat bilgileri
        user_id: Planlayan kullanıcı

    Returns:
        dict: {"success": bool, "interview_id": int}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO interviews (
                    candidate_id, position_id, interview_date, interview_time,
                    interview_type, location, interviewer_ids, notes, durum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id,
                position_id,
                interview_data.get("date"),
                interview_data.get("time"),
                interview_data.get("type", "yuz_yuze"),
                interview_data.get("location"),
                json.dumps(interview_data.get("interviewers", [])),
                interview_data.get("notes"),
                "planlandı"
            ))

            interview_id = cursor.lastrowid
            conn.commit()

        # Aday durumunu güncelle
        workflow_change_candidate_status(
            candidate_id=candidate_id,
            new_status="mulakat",
            user_id=user_id,
            reason="Mülakat planlandı"
        )

        trigger_event("interview_scheduled", {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "position_id": position_id,
            "date": interview_data.get("date"),
            "time": interview_data.get("time"),
            "type": interview_data.get("type")
        })

        return {"success": True, "interview_id": interview_id}

    except Exception as e:
        return {"success": False, "error": str(e)}


def workflow_complete_interview(interview_id: int, result: str,
                                 feedback: str = None, score: int = None,
                                 user_id: int = None) -> Dict[str, Any]:
    """
    Mülakat tamamla

    Args:
        interview_id: Mülakat ID
        result: Sonuç (olumlu, olumsuz, beklemede)
        feedback: Geri bildirim
        score: Puan
        user_id: Tamamlayan kullanıcı

    Returns:
        dict: {"success": bool}
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Mülakat bilgilerini al
            cursor.execute("""
                SELECT candidate_id, position_id FROM interviews WHERE id = ?
            """, (interview_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Mülakat bulunamadı"}

            candidate_id = row["candidate_id"]
            position_id = row["position_id"]

            # Mülakatı güncelle
            cursor.execute("""
                UPDATE interviews
                SET durum = 'tamamlandı', sonuc = ?, geri_bildirim = ?,
                    puan = ?, guncelleme_tarihi = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (result, feedback, score, interview_id))

            conn.commit()

        # Sonuca göre aday durumunu güncelle
        if result == "olumlu":
            new_status = "teklif_bekliyor"
        elif result == "olumsuz":
            new_status = "reddedildi"
        else:
            new_status = "mulakat"

        workflow_change_candidate_status(
            candidate_id=candidate_id,
            new_status=new_status,
            user_id=user_id,
            reason=f"Mülakat sonucu: {result}"
        )

        trigger_event("interview_completed", {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "position_id": position_id,
            "result": result,
            "score": score
        })

        return {"success": True, "new_candidate_status": new_status}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# LEGACY UYUMLULUK (Eski fonksiyon isimleri)
# ============================================================

# Eski isimleri destekle
process_new_cv = workflow_process_cv
process_full_application = workflow_full_application
match_candidate = workflow_match_candidate
change_candidate_status = workflow_change_candidate_status
get_position_candidates = workflow_match_candidate  # Farklı parametre ama benzer işlev


# ============================================================
# WORKFLOW KAYIT SİSTEMİ (Agent için)
# ============================================================

WORKFLOW_REGISTRY = {
    "parse_cv": workflow_parse_cv,
    "process_cv": workflow_process_cv,
    "full_application": workflow_full_application,
    "match_candidate": workflow_match_candidate,
    "auto_match": workflow_auto_match_all_positions,
    "match_criteria": workflow_match_to_position_criteria,
    "add_to_pool": workflow_add_to_pool,
    "update_pool_status": workflow_update_pool_status,
    "change_status": workflow_change_candidate_status,
    "bulk_status": workflow_bulk_status_change,
    "create_position": workflow_create_position,
    "update_position": workflow_update_position,
    "schedule_interview": workflow_schedule_interview,
    "complete_interview": workflow_complete_interview,
}


def execute_workflow(workflow_name: str, **kwargs) -> Dict[str, Any]:
    """
    Workflow'u isimle çalıştır (Agent sistemi için)

    Args:
        workflow_name: Workflow adı
        **kwargs: Workflow parametreleri

    Returns:
        dict: Workflow sonucu
    """
    if workflow_name not in WORKFLOW_REGISTRY:
        return {"success": False, "error": f"Bilinmeyen workflow: {workflow_name}"}

    try:
        trigger_event("workflow_started", {
            "workflow_name": workflow_name,
            "params": str(kwargs)[:200]  # İlk 200 karakter
        })

        result = WORKFLOW_REGISTRY[workflow_name](**kwargs)

        trigger_event("workflow_completed", {
            "workflow_name": workflow_name,
            "success": result.get("success", False)
        })

        return result
    except Exception as e:
        trigger_event("workflow_error", {
            "workflow_name": workflow_name,
            "error": str(e)
        })
        return {"success": False, "error": str(e)}


def get_available_workflows() -> List[str]:
    """Kullanılabilir workflow listesi"""
    return list(WORKFLOW_REGISTRY.keys())
