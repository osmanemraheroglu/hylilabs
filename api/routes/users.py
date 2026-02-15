from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import sys
sys.path.append("/var/www/hylilabs/api")
from database import (
    get_company_users_detailed,
    get_company_user_stats,
    create_user_with_temp_password,
    update_user_by_company_admin,
    delete_user_by_company_admin,
    toggle_user_status,
    reset_user_password
)
from routes.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: str
    ad_soyad: str
    rol: str = "user"


class UpdateUserRequest(BaseModel):
    ad_soyad: Optional[str] = None
    email: Optional[str] = None
    rol: Optional[str] = None


@router.get("")
def list_users(current_user: dict = Depends(get_current_user)):
    """Firma kullanıcılarını listele"""
    company_id = current_user["company_id"]
    try:
        users_raw = get_company_users_detailed(company_id)
        users = [{k: v for k, v in u.items() if k != "password_hash"} for u in users_raw]
        stats = get_company_user_stats(company_id)
        return {"success": True, "data": {"users": users, "stats": stats}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_user(request: CreateUserRequest, current_user: dict = Depends(get_current_user)):
    """Yeni kullanıcı oluştur (geçici şifre ile)"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        result = create_user_with_temp_password(
            company_id=company_id,
            email=request.email,
            ad_soyad=request.ad_soyad,
            rol=request.rol,
            created_by=current_user["id"]
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{user_id}")
def update_user(user_id: int, request: UpdateUserRequest, current_user: dict = Depends(get_current_user)):
    """Kullanıcı bilgilerini güncelle"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")

    try:
        success = update_user_by_company_admin(
            user_id=user_id,
            company_id=company_id,
            current_user_id=current_user["id"],
            **fields
        )
        if not success:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
        return {"success": True, "message": "Kullanıcı güncellendi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}")
def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    """Kullanıcı sil"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        success = delete_user_by_company_admin(
            user_id=user_id,
            company_id=company_id,
            current_user_id=current_user["id"]
        )
        if not success:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
        return {"success": True, "message": "Kullanıcı silindi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/toggle-status")
def toggle_status(user_id: int, current_user: dict = Depends(get_current_user)):
    """Kullanıcı aktif/pasif durumunu değiştir"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        success, message = toggle_user_status(
            user_id=user_id,
            company_id=company_id,
            current_user_id=current_user["id"]
        )
        return {"success": success, "message": message}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, current_user: dict = Depends(get_current_user)):
    """Kullanıcı şifresini sıfırla"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        temp_password = reset_user_password(
            user_id=user_id,
            company_id=company_id,
            current_user_id=current_user["id"]
        )
        return {"success": True, "data": {"temp_password": temp_password}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
