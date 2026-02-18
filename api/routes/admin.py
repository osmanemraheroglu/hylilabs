"""
Admin API - Super Admin Only
Sistem yonetimi ve istatistikler
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from routes.auth import get_current_user
from database import get_connection, get_super_admin_stats, get_company_wise_stats, verify_password, toggle_company_status
import traceback
import os

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

@router.post("/reset-data")
async def reset_data(request: Request, current_user: dict = Depends(get_current_user)):
    """Kademeli veri sıfırlama - silme öncesi otomatik backup alır"""
    import shutil
    from datetime import datetime
    
    body = await request.json()
    level = body.get("level")
    password = body.get("password", "")
    confirmation = body.get("confirmation", "")
    
    if level not in ["candidates", "pools", "full"]:
        raise HTTPException(400, "Gecersiz seviye. candidates, pools veya full olmali")
    if confirmation != "SIFIRLA":
        raise HTTPException(400, "Onay metni SIFIRLA olmali")
    if level == "full" and current_user.get("rol") != "super_admin":
        raise HTTPException(403, "Tam sifirlama sadece super_admin yapabilir")
    if current_user.get("rol") not in ["super_admin", "company_admin"]:
        raise HTTPException(403, "Bu islem icin yetkiniz yok")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (current_user["id"],))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(404, "Kullanici bulunamadi")
        
        if not verify_password(password, user[0]):
            raise HTTPException(403, "Sifre yanlis")
        
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "talentflow.db")
        backup_path = db_path.replace(".db", f"_backup_{datetime.now().strftime(chr(37)+chr(89)+chr(37)+chr(109)+chr(37)+chr(100)+chr(95)+chr(37)+chr(72)+chr(37)+chr(77)+chr(37)+chr(83))}.db")
        shutil.copy2(db_path, backup_path)
        
        company_id = current_user.get("company_id")
        
        try:
            if level == "candidates":
                if company_id:
                    cursor.execute("DELETE FROM ai_evaluations WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM ai_analyses WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM matches WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM candidate_pool_assignments WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM candidate_positions WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM candidates WHERE company_id = ?", (company_id,))
                else:
                    cursor.execute("DELETE FROM ai_evaluations")
                    cursor.execute("DELETE FROM ai_analyses")
                    cursor.execute("DELETE FROM matches")
                    cursor.execute("DELETE FROM candidate_pool_assignments")
                    cursor.execute("DELETE FROM candidate_positions")
                    cursor.execute("DELETE FROM candidates")
            
            elif level == "pools":
                if company_id:
                    cursor.execute("DELETE FROM candidate_pool_assignments WHERE department_pool_id IN (SELECT id FROM department_pools WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM position_pools WHERE position_id IN (SELECT id FROM department_pools WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM department_pools WHERE company_id = ?", (company_id,))
                else:
                    cursor.execute("DELETE FROM candidate_pool_assignments")
                    cursor.execute("DELETE FROM position_pools")
                    cursor.execute("DELETE FROM department_pools")
            
            elif level == "full":
                if company_id:
                    cursor.execute("DELETE FROM ai_evaluations WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM ai_analyses WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM matches WHERE company_id = ?", (company_id,))
                    cursor.execute("DELETE FROM candidate_pool_assignments WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM candidate_positions WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM candidates WHERE company_id = ?", (company_id,))
                    cursor.execute("DELETE FROM position_pools WHERE position_id IN (SELECT id FROM department_pools WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM department_pools WHERE company_id = ?", (company_id,))
                    cursor.execute("DELETE FROM position_keywords_v2 WHERE position_id IN (SELECT id FROM positions WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM position_criteria WHERE position_id IN (SELECT id FROM positions WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM position_requirements WHERE position_id IN (SELECT id FROM positions WHERE company_id = ?)", (company_id,))
                    cursor.execute("DELETE FROM positions WHERE company_id = ?", (company_id,))
                else:
                    cursor.execute("DELETE FROM ai_evaluations")
                    cursor.execute("DELETE FROM ai_analyses")
                    cursor.execute("DELETE FROM matches")
                    cursor.execute("DELETE FROM candidate_pool_assignments")
                    cursor.execute("DELETE FROM candidate_positions")
                    cursor.execute("DELETE FROM candidates")
                    cursor.execute("DELETE FROM position_pools")
                    cursor.execute("DELETE FROM department_pools")
                    cursor.execute("DELETE FROM position_keywords_v2")
                    cursor.execute("DELETE FROM position_criteria")
                    cursor.execute("DELETE FROM position_requirements")
                    cursor.execute("DELETE FROM positions")
                    cursor.execute("DELETE FROM email_collection_logs")
                    cursor.execute("DELETE FROM email_logs")
            
            conn.commit()
            return {"success": True, "message": f"{level} verileri sifirlandi", "backup": backup_path}
        
        except Exception as e:
            conn.rollback()
            raise HTTPException(500, f"Sifirlama hatasi: {str(e)}")

@router.put("/companies/{company_id}/toggle-status")
def toggle_company_active_status(company_id: int, current_user: dict = Depends(get_current_user)):
    """Firma aktiflik durumunu degistir"""
    require_super_admin(current_user)
    
    try:
        result = toggle_company_status(company_id)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
