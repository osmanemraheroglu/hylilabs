from fastapi import APIRouter, Depends, HTTPException, Query
from routes.auth import get_current_user
from database import (
    create_interview, update_interview, get_interviews,
    delete_interview, get_connection
)
from models import Interview
from datetime import datetime
from typing import Optional
import traceback
import logging

from email_sender import send_interview_invite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def require_company_user(current_user: dict):
    """Firma kullanicisi kontrolu - super_admin bu endpointe erisemez"""
    if current_user.get("company_id") is None:
        raise HTTPException(status_code=403, detail="Bu islem firma kullanicilarina ozeldir. Lutfen firma secin.")


@router.get("/dropdown-data")
def dropdown_data(current_user: dict = Depends(get_current_user)):
    """Mülakat formu için aday ve pozisyon listeleri"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        with get_connection() as conn:
            cursor = conn.cursor()

            # Pozisyonları department_pools tablosundan getir (pool_type='position')
            cursor.execute(
                """SELECT id, name as baslik
                   FROM department_pools
                   WHERE company_id = ? AND pool_type = 'position' AND is_active = 1
                   ORDER BY name""",
                (company_id,)
            )
            positions = [dict(row) for row in cursor.fetchall()]

            # Adayları getir (basit liste)
            cursor.execute(
                "SELECT id, ad_soyad, email FROM candidates WHERE company_id = ? ORDER BY ad_soyad",
                (company_id,)
            )
            candidates = [dict(row) for row in cursor.fetchall()]

            # Pozisyon bazlı aday eşleştirmesi (pozisyon seçilince filtreleme için)
            position_candidates = {}
            for pos in positions:
                cursor.execute(
                    """SELECT c.id, c.ad_soyad, c.email
                       FROM candidates c
                       JOIN candidate_pool_assignments cpa ON cpa.candidate_id = c.id
                       WHERE cpa.department_pool_id = ? AND c.company_id = ?
                       ORDER BY c.ad_soyad""",
                    (pos["id"], company_id)
                )
                pos_candidates = [dict(row) for row in cursor.fetchall()]
                position_candidates[str(pos["id"])] = pos_candidates

        return {"success": True, "data": {"positions": positions, "candidates": candidates, "positionCandidates": position_candidates}}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_interviews(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    candidate_id: Optional[int] = Query(None),
    durum: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Mulakatlari listele"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]
        sd = datetime.fromisoformat(start_date) if start_date else None
        ed = datetime.fromisoformat(end_date) if end_date else None

        results = get_interviews(
            start_date=sd, end_date=ed,
            candidate_id=candidate_id, durum=durum,
            company_id=company_id
        )

        # datetime nesnelerini string yap
        for r in results:
            if isinstance(r.get("tarih"), datetime):
                r["tarih"] = r["tarih"].isoformat()
            if isinstance(r.get("olusturma_tarihi"), datetime):
                r["olusturma_tarihi"] = r["olusturma_tarihi"].isoformat()

        return {"success": True, "data": results, "total": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_new_interview(
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Yeni mulakat olustur"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]
        send_email = body.get("send_email", True)

        interview_date = datetime.fromisoformat(body["tarih"])
        interview = Interview(
            candidate_id=body["candidate_id"],
            position_id=body.get("position_id"),
            tarih=interview_date,
            sure_dakika=body.get("sure_dakika", 60),
            tur=body.get("tur", "teknik"),
            lokasyon=body.get("lokasyon", "online"),
            mulakatci=body.get("mulakatci"),
            durum=body.get("durum", "planlanmis"),
            notlar=body.get("notlar")
        )

        new_id = create_interview(interview, company_id=company_id)

        # Email gönder
        email_sent = False
        if send_email:
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    # Aday bilgisini al
                    cursor.execute(
                        "SELECT ad_soyad, email FROM candidates WHERE id = ? AND company_id = ?",
                        (body["candidate_id"], company_id)
                    )
                    candidate = cursor.fetchone()

                    # Pozisyon bilgisini al
                    position_title = None
                    if body.get("position_id"):
                        cursor.execute(
                            "SELECT name FROM department_pools WHERE id = ? AND company_id = ?",
                            (body["position_id"], company_id)
                        )
                        pos_row = cursor.fetchone()
                        if pos_row:
                            position_title = pos_row["name"]

                if candidate and candidate["email"]:
                    success, msg = send_interview_invite(
                        candidate_name=candidate["ad_soyad"],
                        candidate_email=candidate["email"],
                        interview_date=interview_date,
                        duration=body.get("sure_dakika", 60),
                        interview_type=body.get("tur", "teknik"),
                        location=body.get("lokasyon", "online"),
                        position_title=position_title or "Genel Başvuru",
                        interviewer=body.get("mulakatci"),
                        notes=body.get("notlar")
                    )
                    email_sent = success
                    if not success:
                        logger.warning(f"Email gonderilemedi: {msg}")
            except Exception as e:
                logger.error(f"Email gonderme hatasi: {e}")
                email_sent = False

        return {
            "success": True,
            "id": new_id,
            "message": "Mulakat olusturuldu",
            "email_sent": email_sent
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{interview_id}")
def update_existing_interview(
    interview_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user)
):
    """Mulakat guncelle"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        # tarih string ise datetime yap
        if "tarih" in body and isinstance(body["tarih"], str):
            body["tarih"] = datetime.fromisoformat(body["tarih"])

        success = update_interview(interview_id, company_id=company_id, **body)
        if not success:
            raise HTTPException(status_code=404, detail="Mulakat bulunamadi veya degisiklik yok")
        return {"success": True, "message": "Mulakat guncellendi"}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{interview_id}")
def delete_existing_interview(
    interview_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mulakat sil"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]
        success = delete_interview(interview_id, company_id=company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Mulakat bulunamadi")
        return {"success": True, "message": "Mulakat silindi"}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
