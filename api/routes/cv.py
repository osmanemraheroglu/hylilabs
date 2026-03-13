from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
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
from rate_limiter import check_cv_upload_limit, record_cv_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cv", tags=["cv"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg'}
BULK_ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
BULK_MAX_FILES = 20


class ScanEmailsRequest(BaseModel):
    account_id: int
    folder: str = "INBOX"
    unseen_only: bool = True
    limit: int = 50


@router.post("/upload")
async def upload_cv(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Manuel CV yukleme - dosya parse et ve aday olustur"""
    # === CV UPLOAD RATE LIMIT KONTROLÜ (27.02.2026) ===
    user_id = str(current_user.get("id", "unknown"))
    allowed, msg = check_cv_upload_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Saatlik CV yükleme limitine ulaştınız (20 dosya/saat). Lütfen daha sonra tekrar deneyin."
        )
    # === KONTROL SONU ===

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

        # Blacklist kontrolu
        if isinstance(candidate_result, dict) and candidate_result.get("blacklisted"):
            return {
                "success": False,
                "message": candidate_result["message"],
                "data": {"blacklisted": True, "cv_attempt_count": candidate_result.get("cv_attempt_count", 1)}
            }

        candidate_id = candidate_result

        # Application kaydı oluştur (sadece yeni aday için)
        try:
            app = Application(candidate_id=candidate_id, kaynak="cv_yukleme")
            create_application(app, company_id)
        except Exception as e:
            logger.warning(f"Application kaydi olusturulamadi: {e}")

        # Başarılı upload'ı rate limit sayacına kaydet
        record_cv_upload(user_id)


        # === FAZ 9.1.3: Otomatik pozisyon eşleştirmesi ===
        try:
            from database import match_single_candidate_to_positions
            match_result = match_single_candidate_to_positions(candidate_id, company_id)
            if match_result.get('transferred', 0) > 0:
                logger.info(f"CV upload: Aday {candidate_id} otomatik {match_result['transferred']} pozisyona eşleştirildi")
        except Exception as match_err:
            logger.warning(f"Otomatik eşleştirme hatası (devam ediliyor): {match_err}")
        # === FAZ 9.1.3 SONU ===

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


@router.post("/bulk-upload")
async def bulk_upload_cv(files: List[UploadFile] = File(...), current_user: dict = Depends(get_current_user)):
    """Toplu CV yükleme — tek seferde max 20 CV, sıralı işleme (13.03.2026)"""
    company_id = current_user["company_id"]
    user_id = str(current_user.get("id", "unknown"))

    if not company_id:
        raise HTTPException(status_code=400, detail="Firma seçilmeli")

    # Max dosya sayısı kontrolü
    if len(files) > BULK_MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"En fazla {BULK_MAX_FILES} CV yükleyebilirsiniz. {len(files)} dosya seçildi."
        )

    if len(files) == 0:
        raise HTTPException(status_code=400, detail="Dosya seçilmedi")

    # Rate limit kontrolü
    allowed, msg = check_cv_upload_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Saatlik CV yükleme limitine ulaştınız (20 dosya/saat). Lütfen daha sonra tekrar deneyin."
        )

    # Firma aday limitini ön kontrol
    max_aday_limit = -1
    current_candidate_count = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT max_aday FROM companies WHERE id = ?", (company_id,))
        company_row = cursor.fetchone()
        if company_row:
            max_aday_limit = company_row['max_aday']

        cursor.execute("SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,))
        current_candidate_count = cursor.fetchone()[0]

    # KVKK audit log
    logger.info(f"[KVKK-AUDIT] Toplu CV yükleme başlatıldı: user_id={user_id}, company_id={company_id}, dosya_sayisi={len(files)}")

    results = []
    success_count = 0
    error_count = 0
    duplicate_count = 0
    blacklist_count = 0

    for file in files:
        filename = file.filename or "bilinmeyen_dosya"
        file_result = {
            "filename": filename,
            "status": "error",
            "message": "",
            "candidate_id": None
        }

        try:
            # Format kontrolü (toplu yüklemede sadece PDF ve DOCX)
            ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext not in BULK_ALLOWED_EXTENSIONS:
                file_result["message"] = f"Desteklenmeyen dosya tipi: {ext}. Toplu yüklemede sadece PDF ve DOCX desteklenir."
                error_count += 1
                results.append(file_result)
                continue

            # Dosya içeriğini oku
            content = await file.read()
            if not content:
                file_result["message"] = "Dosya boş"
                error_count += 1
                results.append(file_result)
                continue

            # Aday limiti kontrolü (her dosya için güncel kontrol)
            if max_aday_limit != -1 and (current_candidate_count + success_count) >= max_aday_limit:
                file_result["message"] = f"Aday limitine ulaşıldı ({max_aday_limit}). Kalan CV'ler işlenemedi."
                file_result["status"] = "limit"
                error_count += 1
                results.append(file_result)
                continue

            # CV parse et (KİLİTLİ — dokunulmadı)
            result = parse_cv(content, filename, user_id)

            if not result.basarili or not result.candidate:
                file_result["message"] = result.hata_mesaji or "CV parse edilemedi"
                error_count += 1
                results.append(file_result)
                continue

            # CV dosyasını kaydet (KİLİTLİ — dokunulmadı)
            cv_path = save_cv_file(content, filename, company_id, result.candidate.email)
            if cv_path:
                result.candidate.cv_dosya_yolu = cv_path
                result.candidate.cv_dosya_adi = filename

            # Adayı veritabanına kaydet (KİLİTLİ — dokunulmadı, duplicate kontrolü dahil)
            candidate_result = create_candidate(result.candidate, company_id)

            # Duplicate kontrolü
            if isinstance(candidate_result, dict) and candidate_result.get("duplicate"):
                file_result["status"] = "duplicate"
                file_result["message"] = candidate_result["message"]
                file_result["candidate_id"] = candidate_result.get("candidate_id")
                duplicate_count += 1
                results.append(file_result)
                continue

            # Blacklist kontrolü
            if isinstance(candidate_result, dict) and candidate_result.get("blacklisted"):
                file_result["status"] = "blacklisted"
                file_result["message"] = candidate_result["message"]
                blacklist_count += 1
                results.append(file_result)
                continue

            candidate_id = candidate_result

            # Application kaydı
            try:
                app = Application(candidate_id=candidate_id, kaynak="toplu_cv_yukleme")
                create_application(app, company_id)
            except Exception as e:
                logger.warning(f"Toplu yükleme application kaydı hatası: {e}")

            # Rate limit kaydı
            record_cv_upload(user_id)

            # Otomatik pozisyon eşleştirmesi
            try:
                from database import match_single_candidate_to_positions
                match_result = match_single_candidate_to_positions(candidate_id, company_id)
                if match_result.get('transferred', 0) > 0:
                    logger.info(f"Toplu CV: Aday {candidate_id} otomatik {match_result['transferred']} pozisyona eşleştirildi")
            except Exception as match_err:
                logger.warning(f"Toplu yükleme eşleştirme hatası (devam ediliyor): {match_err}")

            file_result["status"] = "success"
            file_result["message"] = "CV başarıyla yüklendi"
            file_result["candidate_id"] = candidate_id
            success_count += 1

        except Exception as e:
            file_result["message"] = str(e)
            error_count += 1
            logger.error(f"Toplu CV yükleme hatası ({filename}): {e}")

        results.append(file_result)

    # KVKK audit log - sonuç
    logger.info(
        f"[KVKK-AUDIT] Toplu CV yükleme tamamlandı: user_id={user_id}, company_id={company_id}, "
        f"toplam={len(files)}, basarili={success_count}, hata={error_count}, "
        f"duplicate={duplicate_count}, kara_liste={blacklist_count}"
    )

    return {
        "success": True,
        "message": f"Toplu yükleme tamamlandı: {success_count} başarılı, {duplicate_count} mevcut, {error_count} hata",
        "data": {
            "total": len(files),
            "success": success_count,
            "error": error_count,
            "duplicate": duplicate_count,
            "blacklisted": blacklist_count,
            "results": results
        }
    }


@router.get("/stats")
def cv_stats(current_user: dict = Depends(get_current_user)):
    """CV toplama istatistikleri - gerçek aday sayıları ve dosya istatistikleri"""
    company_id = current_user["company_id"]
    try:
        collection_stats = get_email_collection_stats(company_id=company_id)
        storage_stats = get_cv_storage_stats(company_id=company_id)
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


@router.get("/processing-status")
def get_processing_status(current_user = Depends(get_current_user)):
    """
    Firma için aktif ve son CV işlemlerini döndür.
    Progress UI için polling endpoint.
    """
    company_id = current_user["company_id"]

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Aktif işlemler (devam_ediyor)
            cursor.execute("""
                SELECT
                    id, account_email, klasor, taranan_email, bulunan_cv,
                    basarili_cv, mevcut_aday, hatali_cv, durum, tarih
                FROM email_collection_logs
                WHERE company_id = ? AND durum = 'devam_ediyor'
                ORDER BY tarih DESC
                LIMIT 5
            """, (company_id,))

            active_columns = ['id', 'account_email', 'klasor', 'taranan_email', 'bulunan_cv',
                             'basarili_cv', 'mevcut_aday', 'hatali_cv', 'durum', 'created_at']
            active = [dict(zip(active_columns, row)) for row in cursor.fetchall()]

            # Son 5 tamamlanan
            cursor.execute("""
                SELECT
                    id, account_email, klasor, taranan_email, bulunan_cv,
                    basarili_cv, mevcut_aday, hatali_cv, durum, tarih
                FROM email_collection_logs
                WHERE company_id = ? AND durum != 'devam_ediyor'
                ORDER BY tarih DESC
                LIMIT 5
            """, (company_id,))

            recent = [dict(zip(active_columns, row)) for row in cursor.fetchall()]

        return {
            "success": True,
            "data": {
                "active": active,
                "recent": recent,
                "has_active": len(active) > 0
            }
        }
    except Exception as e:
        logger.error(f"processing-status hatası: {e}")
        return {
            "success": False,
            "detail": "İşlem durumu alınamadı"
        }
