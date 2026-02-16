from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
import sys
sys.path.append("/var/www/hylilabs/api")
from database import (
    create_candidate,
    get_email_collection_history,
    get_email_collection_stats
)
from core.cv_parser import parse_cv, save_cv_file, get_cv_storage_stats
from routes.auth import get_current_user

router = APIRouter(prefix="/api/cv", tags=["cv"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg'}


@router.post("/upload")
async def upload_cv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Manuel CV yukleme - dosya parse et ve aday olustur"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dosya adi bos")

    ext = '.' + file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen dosya tipi: {ext}. Desteklenen: {', '.join(ALLOWED_EXTENSIONS)}")

    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Dosya bos")

        # CV parse et (KORUNAN: cv_parser.py DEGISTIRILMEDI)
        result = parse_cv(content, file.filename, str(current_user["id"]))

        if not result.basarili or not result.candidate:
            return {
                "success": False,
                "message": result.hata_mesaji or "CV parse edilemedi",
                "data": None
            }

        # CV dosyasini kaydet
        cv_path = save_cv_file(content, file.filename, result.candidate.email)
        if cv_path:
            result.candidate.cv_dosya_yolu = cv_path
            result.candidate.cv_dosya_adi = file.filename

        # Adayi veritabanina kaydet (KORUNAN: database.py DEGISTIRILMEDI)
        company_id = current_user["company_id"]
        candidate_id = create_candidate(result.candidate, company_id)

        return {
            "success": True,
            "message": "CV basariyla yuklendi ve parse edildi",
            "data": {
                "candidate_id": candidate_id,
                "ad_soyad": result.candidate.ad_soyad,
                "email": result.candidate.email,
                "telefon": result.candidate.telefon,
                "lokasyon": result.candidate.lokasyon,
                "mevcut_pozisyon": result.candidate.mevcut_pozisyon,
                "toplam_deneyim_yil": result.candidate.toplam_deneyim_yil,
                "cv_source": result.cv_source
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def cv_stats(current_user: dict = Depends(get_current_user)):
    """CV toplama istatistikleri"""
    company_id = current_user["company_id"]
    try:
        collection_stats = get_email_collection_stats(company_id=company_id)
        storage_stats = get_cv_storage_stats()
        return {
            "success": True,
            "data": {
                "collection": collection_stats,
                "storage": storage_stats
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
def cv_history(days: int = 30, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Email toplama gecmisi"""
    company_id = current_user["company_id"]
    try:
        history = get_email_collection_history(company_id=company_id, days=days, limit=limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
