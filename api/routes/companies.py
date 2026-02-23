"""
Companies API - Super Admin Only
Firma CRUD islemleri
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from routes.auth import get_current_user
from database import (
    get_connection, get_all_companies_admin, create_company,
    update_company, update_company_status, delete_company_soft,
    create_company_user, hash_password, hard_delete_company
)
from email_sender import send_email
from audit_logger import log_audit, AuditAction, EntityType
import traceback
import secrets
import string

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/me")
def get_my_company(current_user: dict = Depends(get_current_user)):
    """Kullanicinin kendi firmasini getir"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Firma bulunamadi")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, ad, max_aday, max_kullanici FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Firma bulunamadi")

            return {
                "success": True,
                "company": {
                    "id": row["id"],
                    "ad": row["ad"],
                    "max_aday": row["max_aday"],
                    "max_kullanici": row["max_kullanici"]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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
def create_company_endpoint(body: dict, request: Request, current_user: dict = Depends(get_current_user)):
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

        # Audit log: Firma oluşturma
        log_audit(
            user_id=current_user["id"],
            user_email=current_user["email"],
            company_id=None,  # Super admin, firma bağımsız
            action=AuditAction.COMPANY_CREATE.value,
            entity_type=EntityType.COMPANY.value,
            entity_id=company_id,
            entity_name=ad,
            details={"slug": slug, "plan": body.get("plan", "basic")},
            ip_address=request.client.host if request.client else None
        )

        # Yetkili email varsa otomatik kullanici olustur ve email gonder
        yetkili_email = body.get("yetkili_email")
        yetkili_adi = body.get("yetkili_adi") or "Yetkili"
        email_sent = False

        if yetkili_email:
            try:
                # Gecici sifre uret (8 karakter: buyuk+kucuk+rakam)
                chars = string.ascii_letters + string.digits
                gecici_sifre = ''.join(secrets.choice(chars) for _ in range(8))

                # Kullaniciyi DB'ye kaydet
                with get_connection() as conn:
                    cursor = conn.cursor()
                    hashed = hash_password(gecici_sifre)
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, ad_soyad, rol, company_id, aktif)
                        VALUES (?, ?, ?, 'company_admin', ?, 1)
                    """, (yetkili_email, hashed, yetkili_adi, company_id))
                    conn.commit()

                # System email hesabini al (company_id=1 veya varsayilan)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM email_accounts
                        WHERE aktif = 1 AND (company_id = 1 OR varsayilan_gonderim = 1)
                        ORDER BY varsayilan_gonderim DESC, company_id ASC
                        LIMIT 1
                    """)
                    email_account = cursor.fetchone()
                    email_account = dict(email_account) if email_account else None

                # Email gonder
                if email_account:
                    email_body = f"""Sayın {yetkili_adi},

{ad} için HyliLabs hesabınız oluşturuldu.

Giriş Bilgileri:
URL: http://***REMOVED***:3000
Email: {yetkili_email}
Şifre: {gecici_sifre}

İlk girişte şifrenizi değiştirmenizi öneririz.

Saygılarımızla,
HyliLabs Ekibi"""

                    success, msg = send_email(
                        to_email=yetkili_email,
                        subject="HyliLabs - Hesabınız Oluşturuldu",
                        body=email_body,
                        account=email_account,
                        sirket_adi="HyliLabs"
                    )
                    email_sent = success
            except Exception as e:
                # Kullanici/email hatasi firma olusturmayi engellemez
                traceback.print_exc()

        return {"success": True, "company_id": company_id, "email_sent": email_sent}
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


@router.patch("/{company_id}/toggle-status")
def toggle_company_status(company_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    """Firma aktif/pasif toggle - aktif ise pasif, pasif ise aktif yap"""
    require_super_admin(current_user)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Mevcut durumu ve firma adını al
            cursor.execute("SELECT ad, aktif FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Firma bulunamadi")

            firma_adi = row[0]
            current_status = row[1]
            new_status = 0 if current_status else 1

            # Firma durumunu guncelle
            cursor.execute("UPDATE companies SET aktif = ? WHERE id = ?", (new_status, company_id))

            # Eger pasife aliniyorsa kullanicilari da pasif yap
            if new_status == 0:
                cursor.execute("UPDATE users SET aktif = 0 WHERE company_id = ?", (company_id,))
            else:
                # Aktif ediliyorsa kullanicilari da aktif yap
                cursor.execute("UPDATE users SET aktif = 1 WHERE company_id = ?", (company_id,))

            conn.commit()

        # Audit log: Firma durum değişikliği
        log_audit(
            user_id=current_user["id"],
            user_email=current_user["email"],
            company_id=None,
            action=AuditAction.COMPANY_STATUS_CHANGE.value,
            entity_type=EntityType.COMPANY.value,
            entity_id=company_id,
            entity_name=firma_adi,
            old_values={"aktif": current_status},
            new_values={"aktif": new_status},
            ip_address=request.client.host if request.client else None
        )

        return {"success": True, "aktif": new_status}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{company_id}")
def delete_company_endpoint(company_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    """Firma kalici sil (hard delete) - TUM veriler silinir"""
    require_super_admin(current_user)

    try:
        # Silmeden önce firma adını al (audit log için)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ad FROM companies WHERE id = ?", (company_id,))
            row = cursor.fetchone()
            firma_adi = row[0] if row else f"Firma #{company_id}"

        success = hard_delete_company(company_id)

        if not success:
            raise HTTPException(status_code=404, detail="Firma bulunamadi")

        # Audit log: Firma silme
        log_audit(
            user_id=current_user["id"],
            user_email=current_user["email"],
            company_id=None,
            action=AuditAction.COMPANY_DELETE.value,
            entity_type=EntityType.COMPANY.value,
            entity_id=company_id,
            entity_name=firma_adi,
            details={"hard_delete": True},
            ip_address=request.client.host if request.client else None
        )

        return {"success": True, "message": "Firma ve tum verileri kalici olarak silindi"}
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
