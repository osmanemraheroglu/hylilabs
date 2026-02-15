from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sys
sys.path.append("/var/www/hylilabs/api")
from database import get_company_settings, save_company_setting
from routes.auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SaveSettingRequest(BaseModel):
    key: str
    value: str


@router.get("")
def get_settings(current_user: dict = Depends(get_current_user)):
    """Firma ayarlarini getir"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        settings = get_company_settings(company_id)
        return {"success": True, "data": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
def update_setting(request: SaveSettingRequest, current_user: dict = Depends(get_current_user)):
    """Firma ayarini kaydet/guncelle"""
    if current_user["rol"] not in ["super_admin", "company_admin"]:
        raise HTTPException(status_code=403, detail="Yetkiniz yok")

    company_id = current_user["company_id"]
    try:
        success = save_company_setting(company_id, request.key, request.value)
        if not success:
            raise HTTPException(status_code=500, detail="Ayar kaydedilemedi")
        return {"success": True, "message": "Ayar kaydedildi"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
