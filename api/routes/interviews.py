from fastapi import APIRouter, Depends, HTTPException, Query
from routes.auth import get_current_user
from database import (
    create_interview, update_interview, get_interviews,
    delete_interview, get_all_positions
)
from models import Interview
from datetime import datetime
from typing import Optional
import traceback

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def require_company_user(current_user: dict):
    """Firma kullanicisi kontrolu - super_admin bu endpointe erisemez"""
    if current_user.get("company_id") is None:
        raise HTTPException(status_code=403, detail="Bu islem firma kullanicilarina ozeldir. Lutfen firma secin.")


@router.get("/dropdown-data")
def dropdown_data(current_user: dict = Depends(get_current_user)):
    """Mulakat formu icin aday ve pozisyon listeleri"""
    require_company_user(current_user)
    try:
        company_id = current_user["company_id"]

        # Pozisyonlari getir
        positions = get_all_positions(company_id, only_active=True)
        position_list = [{"id": p.id, "baslik": p.baslik} for p in positions]

        # Adaylari getir (basit liste)
        from database import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, ad_soyad, email FROM candidates WHERE company_id = ? ORDER BY ad_soyad",
                (company_id,)
            )
            candidates = [dict(row) for row in cursor.fetchall()]

        return {"success": True, "data": {"positions": position_list, "candidates": candidates}}
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

        interview = Interview(
            candidate_id=body["candidate_id"],
            position_id=body.get("position_id"),
            tarih=datetime.fromisoformat(body["tarih"]),
            sure_dakika=body.get("sure_dakika", 60),
            tur=body.get("tur", "teknik"),
            lokasyon=body.get("lokasyon", "online"),
            mulakatci=body.get("mulakatci"),
            durum=body.get("durum", "planlanmis"),
            notlar=body.get("notlar")
        )

        new_id = create_interview(interview, company_id=company_id)
        return {"success": True, "id": new_id, "message": "Mulakat olusturuldu"}
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
