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
from core.cv_parser import validate_cv_access

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


# ============================================================
# Durum Geçiş Endpoint'leri (Adım 3/4)
# ============================================================

@router.patch("/{candidate_id}/elen")
def elen_candidate(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Adayı elen - pozisyondan çıkar, havuza geri gönder"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        from database import get_connection, verify_candidate_ownership
        if not verify_candidate_ownership(candidate_id, company_id):
            raise HTTPException(status_code=404, detail="Aday bulunamadı")

        with get_connection() as conn:
            cursor = conn.cursor()
            # Pozisyon atamasını sil
            cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
            # Durumu güncelle
            cursor.execute("""
                UPDATE candidates
                SET durum = 'yeni', havuz = 'genel_havuz'
                WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            conn.commit()

        return {"success": True, "message": "Aday havuza geri gönderildi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{candidate_id}/arsivle")
def arsivle_candidate(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Adayı arşivle"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        from database import get_connection, verify_candidate_ownership
        if not verify_candidate_ownership(candidate_id, company_id):
            raise HTTPException(status_code=404, detail="Aday bulunamadı")

        with get_connection() as conn:
            cursor = conn.cursor()
            # Pozisyon atamasını sil
            cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ?", (candidate_id,))
            # Durumu güncelle
            cursor.execute("""
                UPDATE candidates
                SET durum = 'arsiv', havuz = 'arsiv'
                WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            conn.commit()

        return {"success": True, "message": "Aday arşivlendi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{candidate_id}/ise-al")
def ise_al_candidate(candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Adayı işe alındı olarak işaretle"""
    require_company_user(current_user)
    company_id = current_user["company_id"]
    try:
        from database import get_connection, verify_candidate_ownership
        if not verify_candidate_ownership(candidate_id, company_id):
            raise HTTPException(status_code=404, detail="Aday bulunamadı")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE candidates
                SET durum = 'ise_alindi'
                WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            conn.commit()

        return {"success": True, "message": "Aday işe alındı olarak işaretlendi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# CV ZIP Download Endpoint (appended - locked file policy)
# ============================================================

@router.get("/export/download-cvs")
def download_cvs(
    ids: str = Query(None, description="Comma separated candidate IDs"),
    pool_id: int = Query(None, description="Pool ID to filter"),
    havuz: str = Query(None, description="Havuz filter: genel_havuz, departman_havuzu, pozisyon_havuzu, arsiv"),
    all: bool = Query(False, description="Download all candidates"),
    current_user: dict = Depends(get_current_user)
):
    """CV dosyalarini ZIP olarak indir"""
    import os
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    from database import get_connection
    
    # Yetki kontrolu
    if current_user.get("rol") not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Bu islem icin yetkiniz yok")
    
    company_id = current_user.get("company_id")
    
    # Aday listesini olustur
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if ids:
            # Belirli IDler
            id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
            if not id_list:
                raise HTTPException(status_code=400, detail="Gecersiz ID listesi")
            placeholders = ",".join("?" * len(id_list))
            if company_id:
                cursor.execute(f"SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE id IN ({placeholders}) AND company_id = ?", id_list + [company_id])
            else:
                cursor.execute(f"SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE id IN ({placeholders})", id_list)
        
        elif pool_id:
            # Havuza gore
            if company_id:
                cursor.execute("""
                    SELECT c.id, c.ad_soyad, c.cv_dosya_yolu 
                    FROM candidates c
                    JOIN candidate_pool_assignments cpa ON c.id = cpa.candidate_id
                    WHERE cpa.department_pool_id = ? AND c.company_id = ?
                """, (pool_id, company_id))
            else:
                cursor.execute("""
                    SELECT c.id, c.ad_soyad, c.cv_dosya_yolu 
                    FROM candidates c
                    JOIN candidate_pool_assignments cpa ON c.id = cpa.candidate_id
                    WHERE cpa.department_pool_id = ?
                """, (pool_id,))
        
        elif havuz:
            # Havuz filtresine gore
            if havuz == "genel_havuz":
                if company_id:
                    cursor.execute("SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE company_id = ? AND havuz = 'genel_havuz' AND cv_dosya_yolu IS NOT NULL", (company_id,))
                else:
                    cursor.execute("SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE havuz = 'genel_havuz' AND cv_dosya_yolu IS NOT NULL")
            elif havuz == "departman_havuzu":
                if company_id:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.company_id = ? AND c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools pos ON cpa.department_pool_id = pos.id
                            JOIN department_pools dept ON pos.parent_id = dept.id
                            WHERE pos.pool_type = 'position' AND dept.pool_type = 'department' AND dept.is_system = 0
                        )
                    """, (company_id,))
                else:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools pos ON cpa.department_pool_id = pos.id
                            JOIN department_pools dept ON pos.parent_id = dept.id
                            WHERE pos.pool_type = 'position' AND dept.pool_type = 'department' AND dept.is_system = 0
                        )
                    """)
            elif havuz == "pozisyon_havuzu":
                if company_id:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.company_id = ? AND c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools dp ON cpa.department_pool_id = dp.id
                            WHERE dp.pool_type = 'position'
                        )
                    """, (company_id,))
                else:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools dp ON cpa.department_pool_id = dp.id
                            WHERE dp.pool_type = 'position'
                        )
                    """)
            elif havuz == "arsiv":
                if company_id:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.company_id = ? AND c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools dp ON cpa.department_pool_id = dp.id
                            WHERE dp.name = 'Arşiv' AND dp.is_system = 1
                        )
                    """, (company_id,))
                else:
                    cursor.execute("""
                        SELECT c.id, c.ad_soyad, c.cv_dosya_yolu FROM candidates c
                        WHERE c.cv_dosya_yolu IS NOT NULL AND c.id IN (
                            SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                            JOIN department_pools dp ON cpa.department_pool_id = dp.id
                            WHERE dp.name = 'Arşiv' AND dp.is_system = 1
                        )
                    """)
            else:
                raise HTTPException(status_code=400, detail=f"Gecersiz havuz: {havuz}")
        
        elif all:
            # Tum adaylar
            if company_id:
                cursor.execute("SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE company_id = ? AND cv_dosya_yolu IS NOT NULL", (company_id,))
            else:
                cursor.execute("SELECT id, ad_soyad, cv_dosya_yolu FROM candidates WHERE cv_dosya_yolu IS NOT NULL")
        
        else:
            raise HTTPException(status_code=400, detail="ids, pool_id veya all parametresi gerekli")
        
        candidates = cursor.fetchall()
    
    if not candidates:
        raise HTTPException(status_code=404, detail="Aday bulunamadi")
    
    # ZIP olustur
    zip_buffer = io.BytesIO()
    total_size = 0
    max_size = 100 * 1024 * 1024  # 100MB limit
    file_count = 0
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for cand_id, ad_soyad, cv_path in candidates:
            if not cv_path or not os.path.exists(cv_path):
                continue
            
            # Guvenlik: CV erisim kontrolu
            if not validate_cv_access(cv_path, company_id):
                continue
            
            file_size = os.path.getsize(cv_path)
            if total_size + file_size > max_size:
                break
            
            # Dosya adini temizle
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in (ad_soyad or "unknown"))
            ext = os.path.splitext(cv_path)[1] or ".pdf"
            zip_filename = f"{cand_id}_{safe_name}{ext}"
            
            zf.write(cv_path, zip_filename)
            total_size += file_size
            file_count += 1
    
    if file_count == 0:
        raise HTTPException(status_code=404, detail="Indirilecek CV dosyasi bulunamadi")
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=cv_export_{file_count}_dosya.zip"
        }
    )
