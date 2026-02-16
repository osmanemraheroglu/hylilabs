"""
Admin API - Super Admin Only
Sistem yonetimi ve istatistikler
"""

from fastapi import APIRouter, HTTPException, Depends
from routes.auth import get_current_user
from database import get_connection, get_super_admin_stats, get_company_wise_stats
import traceback

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_super_admin(current_user: dict):
    """Super admin yetkisi kontrolu"""
    if current_user["rol"] != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin yetkisi gerekli")


@router.get("/stats")
def get_system_stats(current_user: dict = Depends(get_current_user)):
    """Genel sistem istatistikleri"""
    require_super_admin(current_user)

    try:
        stats = get_super_admin_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company-stats")
def get_company_statistics(current_user: dict = Depends(get_current_user)):
    """Firma bazli istatistikler"""
    require_super_admin(current_user)

    try:
        stats = get_company_wise_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
def get_all_users(current_user: dict = Depends(get_current_user)):
    """Tum kullanicilar (tum firmalar)"""
    require_super_admin(current_user)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.id, u.email, u.ad_soyad, u.rol, u.aktif, u.company_id,
                       u.son_giris, u.olusturma_tarihi,
                       c.ad as firma_adi
                FROM users u
                LEFT JOIN companies c ON u.company_id = c.id
                ORDER BY u.id
            """)

            users = []
            cols = [d[0] for d in cursor.description]
            for row in cursor.fetchall():
                users.append(dict(zip(cols, row)))

        return {"success": True, "users": users}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Kullanici aktif/pasif"""
    require_super_admin(current_user)

    try:
        aktif = body.get("aktif")
        if aktif is None:
            raise HTTPException(status_code=400, detail="aktif alani zorunlu")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Super admin kontrolu
            cursor.execute("SELECT rol FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="Kullanici bulunamadi")

            if user[0] == "super_admin":
                raise HTTPException(status_code=403, detail="Super admin durumu degistirilemez")

            cursor.execute("UPDATE users SET aktif = ? WHERE id = ?", (1 if aktif else 0, user_id))
            conn.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Kullanici rol degistir"""
    require_super_admin(current_user)

    try:
        rol = body.get("rol")
        if not rol:
            raise HTTPException(status_code=400, detail="rol alani zorunlu")

        if rol == "super_admin":
            raise HTTPException(status_code=403, detail="Super admin rolu atanamaz")

        if rol not in ["company_admin", "user"]:
            raise HTTPException(status_code=400, detail="Gecersiz rol. Izin verilen: company_admin, user")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Mevcut rolu kontrol et
            cursor.execute("SELECT rol FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="Kullanici bulunamadi")

            if user[0] == "super_admin":
                raise HTTPException(status_code=403, detail="Super admin rolu degistirilemez")

            cursor.execute("UPDATE users SET rol = ? WHERE id = ?", (rol, user_id))
            conn.commit()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
