from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
import sys
sys.path.append("/var/www/hylilabs/api")
from database import (
    get_all_candidates,
    get_candidates_count,
    get_candidate_full_data,
    update_candidate,
    delete_candidate_cv_file,
    get_candidate_positions
)
from routes.auth import get_current_user

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


def require_company_user(current_user: dict):
    """Firma kullanicisi kontrolu - super_admin bu endpointe erisemez"""
    if current_user.get("company_id") is None:
        raise HTTPException(status_code=403, detail="Bu islem firma kullanicilarina ozeldir. Lutfen firma secin.")


class UpdateCandidateRequest(BaseModel):
    ad_soyad: Optional[str] = None
    email: Optional[str] = None
    telefon: Optional[str] = None
    lokasyon: Optional[str] = None
    mevcut_pozisyon: Optional[str] = None
    durum: Optional[str] = None
    notlar: Optional[str] = None


@router.get("")
def list_candidates(
    havuz: Optional[str] = None,
    durum: Optional[str] = None,
    arama: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Aday listesi - filtreleme ve pagination destekli"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        candidates_raw = get_all_candidates(
            company_id=company_id,
            havuz=havuz,
            durum=durum,
            arama=arama,
            limit=limit,
            offset=offset
        )
        total = get_candidates_count(
            company_id=company_id,
            havuz=havuz,
            durum=durum,
            arama=arama
        )

        candidates = []
        for c in candidates_raw:
            d = c.model_dump() if hasattr(c, "model_dump") else c.__dict__
            d.pop("password_hash", None)
            d.pop("cv_raw_text", None)
            candidates.append(d)

        return {
            "success": True,
            "data": {
                "candidates": candidates,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{candidate_id}")
def get_candidate_detail(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Aday detay bilgileri"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        data = get_candidate_full_data(candidate_id=candidate_id, company_id=company_id)
        if not data:
            raise HTTPException(status_code=404, detail="Aday bulunamadi")

        data.pop("password_hash", None)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{candidate_id}")
def update_candidate_info(candidate_id: int, request: UpdateCandidateRequest, current_user: dict = Depends(get_current_user)):
    """Aday bilgilerini guncelle"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Guncellenecek alan yok")

    try:
        success = update_candidate(candidate_id=candidate_id, company_id=company_id, **fields)
        if not success:
            raise HTTPException(status_code=404, detail="Aday bulunamadi veya yetkiniz yok")
        return {"success": True, "message": "Aday guncellendi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Aday sil (CV dosyasi dahil)"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        from database import get_connection, verify_candidate_ownership
        if not verify_candidate_ownership(candidate_id, company_id):
            raise HTTPException(status_code=404, detail="Aday bulunamadi")

        delete_candidate_cv_file(candidate_id)

        with get_connection() as conn:
            cursor = conn.cursor()
            # CASCADE: Önce bağımlı tabloları temizle (orphan önleme)
            cursor.execute("DELETE FROM candidate_pool_assignments WHERE candidate_id = ?", (candidate_id,))
            cursor.execute("DELETE FROM matches WHERE candidate_id = ?", (candidate_id,))
            cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
            # Ana kaydı sil
            cursor.execute("DELETE FROM candidates WHERE id = ? AND company_id = ?", (candidate_id, company_id))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Aday silinemedi")

        return {"success": True, "message": "Aday silindi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{candidate_id}/positions")
def candidate_positions(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Adayin eslestigi pozisyonlar"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        from database import verify_candidate_ownership
        if not verify_candidate_ownership(candidate_id, company_id):
            raise HTTPException(status_code=404, detail="Aday bulunamadi")

        positions = get_candidate_positions(candidate_id)
        return {"success": True, "data": positions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
