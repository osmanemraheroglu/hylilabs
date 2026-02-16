"""
Companies API - Super Admin Only
Firma CRUD islemleri
"""

from fastapi import APIRouter, HTTPException, Depends
from routes.auth import get_current_user
from database import (
    get_connection, get_all_companies_admin, create_company,
    update_company, update_company_status, delete_company_soft,
    create_company_user
)
import traceback

router = APIRouter(prefix="/api/companies", tags=["companies"])


def require_super_admin(current_user: dict):
    """Super admin yetkisi kontrolu"""
    if current_user["rol"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin yetkisi gerekli")


@router.get("")
def list_companies(current_user: dict = Depends(get_current_user)):
    """Tum firmalari listele"""
    require_super_admin(current_user)

    try:
        companies = get_all_companies_admin()
        return {"success": True, "companies": companies}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{company_id}")
def get_company(company_id: int, current_user: dict = Depends(get_current_user)):
    """Firma detay"""
    require_super_admin(current_user)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Firma bulunamadi")

            cols = [d[0] for d in cursor.description]
            company = dict(zip(cols, row))

        return {"success": True, "company": company}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_company_endpoint(body: dict, current_user: dict = Depends(get_current_user)):
    """Yeni firma olustur"""
    require_super_admin(current_user)

    try:
        ad = body.get("ad")
        if not ad:
            raise HTTPException(status_code=400, detail="Firma adi zorunlu")

        # Slug olustur
        slug = body.get("slug") or ad.lower().replace(" ", "-").replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")

        company_id = create_company(
            ad=ad,
            slug=slug,
            email=body.get("email"),
            telefon=body.get("telefon"),
            adres=body.get("adres"),
            website=body.get("website"),
            yetkili_adi=body.get("yetkili_adi"),
            yetkili_email=body.get("yetkili_email"),
            yetkili_telefon=body.get("yetkili_telefon"),
            plan=body.get("plan", "basic"),
            max_kullanici=body.get("max_kullanici", 5),
            max_aday=body.get("max_aday", 1000)
        )

        return {"success": True, "company_id": company_id}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail="Bu slug zaten kullaniliyor")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{company_id}")
def update_company_endpoint(company_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Firma guncelle"""
    require_super_admin(current_user)

    try:
        # Izin verilen alanlar
        allowed_fields = [
            "ad", "slug", "email", "telefon", "adres", "website",
            "yetkili_adi", "yetkili_email", "yetkili_telefon",
            "plan", "max_kullanici", "max_aday", "notlar",
            "sozlesme_baslangic", "sozlesme_bitis"
        ]

        update_data = {k: v for k, v in body.items() if k in allowed_fields}

        if not update_data:
            raise HTTPException(status_code=400, detail="Guncellenecek alan yok")

        success = update_company(company_id, **update_data)

        if not success:
            raise HTTPException(status_code=404, detail="Firma bulunamadi")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{company_id}/status")
def toggle_company_status(company_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Firma aktif/pasif toggle"""
    require_super_admin(current_user)

    try:
        aktif = body.get("aktif")
        if aktif is None:
            raise HTTPException(status_code=400, detail="aktif alani zorunlu")

        # update_company_status uses "durum" field, we need to use update_company for "aktif"
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE companies SET aktif = ? WHERE id = ?", (1 if aktif else 0, company_id))
            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Firma bulunamadi")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{company_id}")
def delete_company_endpoint(company_id: int, current_user: dict = Depends(get_current_user)):
    """Firma sil (soft delete)"""
    require_super_admin(current_user)

    try:
        success = delete_company_soft(company_id)

        if not success:
            raise HTTPException(status_code=404, detail="Firma bulunamadi")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{company_id}/users")
def add_company_user(company_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Firmaya kullanici ekle"""
    require_super_admin(current_user)

    try:
        email = body.get("email")
        ad_soyad = body.get("ad_soyad")
        sifre = body.get("sifre")
        rol = body.get("rol", "user")

        if not email or not ad_soyad or not sifre:
            raise HTTPException(status_code=400, detail="email, ad_soyad ve sifre zorunlu")

        if rol == "super_admin":
            raise HTTPException(status_code=403, detail="Super admin rolu atanamaz")

        user_id = create_company_user(
            company_id=company_id,
            email=email,
            ad_soyad=ad_soyad,
            sifre=sifre,
            rol=rol
        )

        return {"success": True, "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail="Bu email zaten kullaniliyor")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{company_id}/stats")
def get_company_stats(company_id: int, current_user: dict = Depends(get_current_user)):
    """Firma istatistikleri"""
    require_super_admin(current_user)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Firma kontrol
            cursor.execute("SELECT id FROM companies WHERE id = ?", (company_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Firma bulunamadi")

            # Toplam aday
            cursor.execute("SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,))
            toplam_aday = cursor.fetchone()[0]

            # Toplam pozisyon
            cursor.execute("SELECT COUNT(*) FROM department_pools WHERE company_id = ? AND pool_type = 'position'", (company_id,))
            toplam_pozisyon = cursor.fetchone()[0]

            # Toplam kullanici
            cursor.execute("SELECT COUNT(*) FROM users WHERE company_id = ?", (company_id,))
            toplam_kullanici = cursor.fetchone()[0]

        return {
            "success": True,
            "stats": {
                "toplam_aday": toplam_aday,
                "toplam_pozisyon": toplam_pozisyon,
                "toplam_kullanici": toplam_kullanici
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
