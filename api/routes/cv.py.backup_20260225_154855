from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import sys
import logging

sys.path.append("/var/www/hylilabs/api")
from database import (
    create_candidate,
    create_application,
    get_email_collection_history,
    get_email_collection_stats,
    get_connection
)
from models import Application
from core.cv_parser import parse_cv, save_cv_file, get_cv_storage_stats
from routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cv", tags=["cv"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg'}


class ScanEmailsRequest(BaseModel):
    account_id: int
    folder: str = "INBOX"
    unseen_only: bool = True
    limit: int = 50


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

        # CV parse et
        result = parse_cv(content, file.filename, str(current_user["id"]))

        if not result.basarili or not result.candidate:
            return {
                "success": False,
                "message": result.hata_mesaji or "CV parse edilemedi",
                "data": None
            }

        # Firma ID al
        company_id = current_user["company_id"]
        if not company_id:
            raise HTTPException(status_code=400, detail="Firma secilmeli")

        # Firma aday limitini kontrol et
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT max_aday FROM companies WHERE id = ?", (company_id,))
            company = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,))
            current_count = cursor.fetchone()[0]

            if company and company['max_aday'] != -1 and current_count >= company['max_aday']:
                raise HTTPException(
                    status_code=403,
                    detail=f"Aday limitinize ulaştınız! Maksimum {company['max_aday']} aday ekleyebilirsiniz. Limitinizi artırmak için yöneticinizle iletişime geçin."
                )

        # CV dosyasini kaydet (firma bazli klasore)
        cv_path = save_cv_file(content, file.filename, company_id, result.candidate.email)
        if cv_path:
            result.candidate.cv_dosya_yolu = cv_path
            result.candidate.cv_dosya_adi = file.filename

        # Adayi veritabanina kaydet
        candidate_result = create_candidate(result.candidate, company_id)

        # Duplicate kontrolu
        if isinstance(candidate_result, dict) and candidate_result.get("duplicate"):
            return {
                "success": False,
                "message": candidate_result["message"],
                "data": {"existing_id": candidate_result["candidate_id"]}
            }

        candidate_id = candidate_result

        # Application kaydı oluştur (sadece yeni aday için)
        try:
            app = Application(candidate_id=candidate_id, kaynak="cv_yukleme")
            create_application(app, company_id)
        except Exception as e:
            logger.warning(f"Application kaydi olusturulamadi: {e}")

        return {
            "success": True,
            "message": "CV başarıyla yüklendi ve parse edildi",
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


@router.post("/scan-emails")
def scan_emails_for_cv(body: ScanEmailsRequest, current_user: dict = Depends(get_current_user)):
    """Email hesabindan CV tara ve topla - TalentFlow mantigi ile birebir"""
    from email_reader import EmailReader
    from database import (
        get_all_email_accounts, is_email_processed, mark_email_processed,
        find_duplicate_candidate, log_email, log_email_collection,
        increment_email_account_cv_count, verify_email_account_ownership
    )
    from models import EmailLog

    company_id = current_user["company_id"]
    user_id = current_user["id"]

    # Hesap kontrolu
    if not verify_email_account_ownership(body.account_id, company_id):
        raise HTTPException(status_code=403, detail="Bu hesaba erisim yetkiniz yok")

    # Hesap bilgilerini al
    accounts = get_all_email_accounts(only_active=False, company_id=company_id)
    account = next((a for a in accounts if a["id"] == body.account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="Email hesabı bulunamadı")

    # Sonuc istatistikleri
    results = {
        "processed": 0,
        "cv_found": 0,
        "success": 0,
        "duplicate": 0,
        "error": 0,
        "candidates": [],
        "errors": []
    }

    collection_start = datetime.now()

    try:
        # EmailReader olustur ve baglan
        reader = EmailReader.from_account(account)
        if not reader.connect():
            raise HTTPException(status_code=500, detail="Email sunucusuna baglanilamadi")

        # Emailleri tara
        for email_msg in reader.fetch_emails_with_attachments(
            folder=body.folder,
            unseen_only=body.unseen_only,
            limit=body.limit
        ):
            results["processed"] += 1

            # Email logla
            email_log = EmailLog(
                email_id=email_msg.message_id,
                gonderen=email_msg.sender,
                konu=email_msg.subject,
                tarih=email_msg.date,
                ek_sayisi=len(email_msg.attachments)
            )
            log_email(email_log)

            # Daha once islendi mi?
            if is_email_processed(email_msg.message_id):
                continue

            # Ekleri isle
            for attachment in email_msg.attachments:
                results["cv_found"] += 1

                try:
                    # CV parse et
                    result = parse_cv(attachment.content, attachment.filename, str(user_id))

                    if not result.basarili or not result.candidate:
                        results["error"] += 1
                        results["errors"].append({
                            "file": attachment.filename,
                            "error": result.hata_mesaji or "Parse hatasi"
                        })
                        continue

                    candidate = result.candidate

                    # Duplicate kontrolu (email/telefon ile)
                    existing = find_duplicate_candidate(candidate.email, candidate.telefon)
                    if existing:
                        results["duplicate"] += 1
                        continue

                    # CV dosyasini kaydet (firma bazli klasore)
                    cv_path = save_cv_file(attachment.content, attachment.filename, company_id, candidate.email)
                    if cv_path:
                        candidate.cv_dosya_yolu = cv_path
                        candidate.cv_dosya_adi = attachment.filename

                    # Adayi kaydet
                    candidate_result = create_candidate(candidate, company_id)

                    # Duplicate kontrolü (create_candidate dict döndü mü?)
                    if isinstance(candidate_result, dict) and candidate_result.get("duplicate"):
                        results["duplicate"] += 1
                        continue

                    candidate_id = candidate_result

                    # Application kaydı oluştur (email tarama için)
                    try:
                        app = Application(
                            candidate_id=candidate_id,
                            kaynak="email",
                            email_id=email_msg.message_id
                        )
                        create_application(app, company_id)
                    except Exception as e:
                        logger.warning(f"Application kaydi olusturulamadi: {e}")

                    results["success"] += 1
                    results["candidates"].append({
                        "id": candidate_id,
                        "ad_soyad": candidate.ad_soyad,
                        "email": candidate.email
                    })

                except Exception as e:
                    results["error"] += 1
                    results["errors"].append({
                        "file": attachment.filename,
                        "error": str(e)
                    })

            # Email'i islendi olarak isaretle
            mark_email_processed(email_msg.message_id)

        reader.disconnect()

        # Hesabin CV sayacini guncelle
        if results["success"] > 0:
            increment_email_account_cv_count(body.account_id, results["success"])

        # Toplama islemini logla
        collection_end = datetime.now()
        durum = "tamamlandi" if results["error"] == 0 else ("kismi_basarili" if results["success"] > 0 else "basarisiz")

        try:
            log_email_collection(
                account_id=body.account_id,
                account_email=account["email"],
                klasor=body.folder,
                taranan_email=results["processed"],
                bulunan_cv=results["cv_found"],
                basarili_cv=results["success"],
                mevcut_aday=results["duplicate"],
                hatali_cv=results["error"],
                durum=durum,
                hata_detaylari=json.dumps(results["errors"], ensure_ascii=False) if results["errors"] else None,
                baslangic_zamani=collection_start,
                bitis_zamani=collection_end,
                company_id=company_id,
                user_id=user_id
            )
        except Exception:
            pass  # Loglama hatasi ana islemi etkilemesin

        # AUTO-MATCH: Yeni CV'ler parse edildikten sonra eslestirmeyi tetikle
        if results["success"] > 0:
            try:
                from database import sync_candidates_to_all_positions
                sync_candidates_to_all_positions(company_id)
            except Exception:
                pass  # Eslestirme hatasi CV islemini bozmamali

        return {
            "success": True,
            "message": f"Tarama tamamlandı: {results['success']} yeni aday, {results['duplicate']} mevcut, {results['error']} hata",
            "data": results
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tarama hatasi: {str(e)}")
