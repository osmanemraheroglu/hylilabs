"""
HyliLabs - Email CV Toplama Fonksiyonlari
scheduler.py tarafindan saat basi cagrilir
"""

import logging
from datetime import datetime

from database import (
    get_all_email_accounts, is_email_processed, mark_email_processed,
    find_duplicate_candidate, create_candidate, create_application,
    get_all_positions, log_email, auto_assign_candidate_to_pool,
    log_email_collection, update_email_collection_log
)
from email_reader import EmailReader
from core.cv_parser import parse_cv, save_cv_file
from core.candidate_matcher import match_candidate_to_positions_ai
from models import Application, EmailLog
from events import trigger_event

# Logging ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Konfigürasyon
EMAIL_LIMIT_PER_ACCOUNT = 50  # Hesap basina max email


def check_emails_for_account(account: dict) -> dict:
    """Tek bir email hesabini kontrol et"""
    stats = {"processed": 0, "success": 0, "duplicate": 0, "error": 0}

    # Progress tracking için log_id
    log_id = None
    try:
        log_id = log_email_collection(
            account_id=account.get("id"),
            account_email=account.get("email", ""),
            klasor="INBOX",
            taranan_email=0,
            bulunan_cv=0,
            basarili_cv=0,
            mevcut_aday=0,
            hatali_cv=0,
            durum="devam_ediyor",
            company_id=account.get("company_id"),
            user_id=None
        )
        logger.info(f"Email tarama başladı, log_id: {log_id}")
    except Exception as log_start_err:
        logger.warning(f"Başlangıç log hatası: {log_start_err}")

    try:
        logger.info(f"Hesap kontrol ediliyor: {account['email']}")
        reader = EmailReader.from_account(account)

        for email_msg in reader.fetch_emails_with_attachments(unseen_only=True, limit=EMAIL_LIMIT_PER_ACCOUNT):
            stats["processed"] += 1

            # Daha once islendi mi?
            if is_email_processed(email_msg.message_id):
                logger.debug(f"Atlandi (islenmis): {email_msg.message_id}")
                continue

            # P2 Security: company_id email hesabından alınıyor
            company_id = account.get("company_id", 1)

            # Email logla
            email_log = EmailLog(
                email_id=email_msg.message_id,
                gonderen=email_msg.sender,
                konu=email_msg.subject,
                tarih=email_msg.date,
                ek_sayisi=len(email_msg.attachments),
                company_id=company_id  # P2 Security: multi-tenancy izolasyonu
            )
            log_email(email_log)

            # Aynı email'den gelen ekler için aday ID'sini takip et
            # İlk ek aday oluşturur, sonraki ekler mevcut adaya eklenir veya atlanır
            email_candidate_id = None

            # Ekleri isle
            for attachment in email_msg.attachments:
                try:
                    # CV parse
                    result = parse_cv(attachment.content, attachment.filename)

                    if not result.basarili:
                        logger.warning(f"Parse hatasi: {attachment.filename} - {result.hata_mesaji}")
                        stats["error"] += 1
                        continue

                    candidate = result.candidate

                    # Duplicate kontrolu
                    existing = find_duplicate_candidate(candidate.email, candidate.telefon)

                    # Eğer aynı email mesajından daha önce bir aday oluşturulduysa, onu kullan
                    if email_candidate_id:
                        logger.info(f"Aday zaten mevcut (aynı email'den), ek atlandı: {attachment.filename} - Aday ID: {email_candidate_id}")
                        stats["duplicate"] += 1
                        continue

                    if existing:
                        # Mevcut adayı kullan
                        email_candidate_id = existing['id']
                        logger.info(f"Duplicate aday bulundu, mevcut adaya ek atlandı: {candidate.ad_soyad} (ID: {email_candidate_id}) - Ek: {attachment.filename}")
                        stats["duplicate"] += 1
                        continue

                    # CV dosyasini kaydet (firma bazli klasore)
                    cv_path = save_cv_file(attachment.content, attachment.filename, company_id, candidate.email)
                    if cv_path:
                        candidate.cv_dosya_yolu = cv_path

                    # Aday olustur
                    candidate_id = create_candidate(candidate, company_id=company_id)
                    email_candidate_id = candidate_id  # Bu email için aday ID'sini kaydet

                    # v2 scoring sistemi ile pozisyonlara eşleştir (fallback ile)
                    try:
                        try:
                            from candidate_matcher import match_candidate_to_positions_keyword
                        except ImportError:
                            from core.candidate_matcher import match_candidate_to_positions_keyword
                        from database import get_approved_titles, get_pool_by_name, assign_candidate_to_department_pool, create_system_pools
                        from scoring_v2 import turkish_lower
                        try:
                            from thefuzz import fuzz
                        except ImportError:
                            fuzz = None

                        # Sistem havuzlarını oluştur (yoksa)
                        create_system_pools(company_id)

                        # v2 scoring ile pozisyonlara eşleştir
                        match_result = match_candidate_to_positions_keyword(candidate_id, company_id)

                        # approved_title_mappings kontrolü - adayın mevcut_pozisyon/deneyim ile eşleşen pozisyonlar
                        candidate_pos_text = (candidate.mevcut_pozisyon or '') + ' ' + (getattr(candidate, 'deneyim_detay', '') or '')
                        candidate_pos_lower = turkish_lower(candidate_pos_text) if candidate_pos_text.strip() else ''

                        if candidate_pos_lower:
                            # Tüm pozisyonlar için approved_title_mappings kontrolü
                            from database import get_department_pools
                            all_positions = get_department_pools(company_id, include_inactive=False, pool_type='position')

                            for pos in all_positions:
                                approved_titles = get_approved_titles(pos['id'])
                                if not approved_titles:
                                    continue

                                # Adayın pozisyon bilgileri ile approved başlıkları karşılaştır
                                matched = False
                                for title_info in approved_titles:
                                    title_lower = turkish_lower(title_info['title'])

                                    # Fuzzy matching veya substring kontrolü
                                    if fuzz:
                                        ratio = fuzz.partial_ratio(candidate_pos_lower, title_lower)
                                        if ratio >= 70:  # %70 eşleşme eşiği
                                            matched = True
                                            break
                                    elif title_lower in candidate_pos_lower or candidate_pos_lower in title_lower:
                                        matched = True
                                        break

                                if matched:
                                    # Bu pozisyona ekle (eğer zaten eklenmemişse ve limit dolmamışsa)
                                    from database import add_candidate_to_position, get_candidate_position_count, get_candidate
                                    from scoring_v2 import calculate_match_score_v2

                                    current_count = get_candidate_position_count(candidate_id)
                                    if current_count >= 5:  # MAX 5 pozisyon limiti
                                        continue

                                    # Aday bilgilerini veritabanından al (tam bilgiler için)
                                    candidate_db = get_candidate(candidate_id, company_id=company_id)
                                    if not candidate_db:
                                        continue

                                    # Candidate'i dict'e çevir
                                    if isinstance(candidate_db, dict):
                                        candidate_dict = candidate_db
                                    elif hasattr(candidate_db, 'model_dump'):
                                        candidate_dict = candidate_db.model_dump()
                                    elif hasattr(candidate_db, 'dict'):
                                        candidate_dict = candidate_db.dict()
                                    else:
                                        candidate_dict = {
                                            'id': getattr(candidate_db, 'id', candidate_id),
                                            'ad_soyad': getattr(candidate_db, 'ad_soyad', candidate.ad_soyad) or '',
                                            'mevcut_pozisyon': getattr(candidate_db, 'mevcut_pozisyon', '') or '',
                                            'deneyim_detay': getattr(candidate_db, 'deneyim_detay', '') or '',
                                            'toplam_deneyim_yil': getattr(candidate_db, 'toplam_deneyim_yil', 0) or 0,
                                            'egitim': getattr(candidate_db, 'egitim', '') or '',
                                            'lokasyon': getattr(candidate_db, 'lokasyon', '') or '',
                                            'teknik_beceriler': getattr(candidate_db, 'teknik_beceriler', '') or '',
                                            'cv_raw_text': getattr(candidate_db, 'cv_raw_text', '') or '',
                                            'mevcut_sirket': getattr(candidate_db, 'mevcut_sirket', '') or ''
                                        }

                                    # Pozisyon bilgilerini dict formatına çevir
                                    pos_dict = {
                                        'id': pos['id'],
                                        'name': pos.get('name', '') or pos.get('baslik', ''),
                                        'keywords': pos.get('keywords', ''),
                                        'gerekli_deneyim_yil': pos.get('gerekli_deneyim_yil', 0) or 0,
                                        'gerekli_egitim': pos.get('gerekli_egitim', '') or '',
                                        'lokasyon': pos.get('lokasyon', '') or ''
                                    }

                                    # v2 scoring ile skor hesapla
                                    try:
                                        v2_score = calculate_match_score_v2(candidate_dict, pos_dict)
                                        if v2_score and v2_score.get('position_score', 0) > 0:
                                            score = v2_score.get('total', 0)
                                            if add_candidate_to_position(candidate_id, pos['id'], score):
                                                logger.info(f"Aday approved_title_mappings ile eşleşti: {candidate.ad_soyad} → {pos.get('name', '')} (skor: {score})")
                                                match_result['added'] = match_result.get('added', 0) + 1
                                    except Exception as e:
                                        logger.warning(f"approved_title_mappings eşleşmesi için v2 scoring hatası: {e}")
                                        continue

                        # Hiçbir pozisyona eşleşmediyse Genel Havuz'a at
                        if match_result.get('added', 0) == 0:
                            from database import get_pool_by_name, assign_candidate_to_department_pool
                            general_pool = get_pool_by_name(company_id, 'Genel Havuz')
                            if general_pool:
                                assign_candidate_to_department_pool(
                                    candidate_id, general_pool['id'], company_id, 'auto', 0, 'Yeni aday - değerlendirme bekliyor'
                                )
                                logger.info(f"Aday Genel Havuz'a atandı (pozisyon eşleşmesi yok): {candidate.ad_soyad}")
                        else:
                            logger.info(f"Aday {match_result.get('added', 0)} pozisyona atandı: {candidate.ad_soyad}")

                    except Exception as e:
                        # v2 başarısız, fallback kullanıldı
                        logger.warning(f"v2 scoring başarısız, fallback kullanılıyor: {e}")
                        assignments = auto_assign_candidate_to_pool(candidate_id, company_id)
                        if assignments:
                            logger.info(f"Aday havuza atandı (fallback): {candidate.ad_soyad} - {assignments}")

                    # Basvuru kaydi (sadece ilk ek için)
                    try:
                        application = Application(
                            candidate_id=candidate_id,
                            kaynak="email",
                            email_id=email_msg.message_id
                        )
                        create_application(application)
                    except Exception as app_error:
                        # FOREIGN KEY constraint hatası veya duplicate application hatası
                        if "FOREIGN KEY" in str(app_error) or "UNIQUE constraint" in str(app_error) or "constraint" in str(app_error).lower():
                            logger.warning(f"Application kaydı zaten mevcut veya constraint hatası, atlandı: {app_error}")
                        else:
                            raise  # Diğer hataları yukarı fırlat

                    # Pozisyonlarla eslestir
                    positions = get_all_positions(only_active=True, company_id=company_id)
                    if positions:
                        candidate.id = candidate_id
                        match_candidate_to_positions_ai(candidate, positions)

                    # Event trigger
                    trigger_event("candidate_created", {
                        "candidate_id": candidate_id,
                        "ad_soyad": candidate.ad_soyad,
                        "kaynak": "email_worker"
                    })

                    logger.info(f"Yeni aday eklendi: {candidate.ad_soyad} (ID: {candidate_id})")
                    stats["success"] += 1

                except Exception as e:
                    # FOREIGN KEY constraint hatası kontrolü
                    error_str = str(e).lower()
                    if "foreign key" in error_str or "constraint" in error_str:
                        if email_candidate_id:
                            logger.info(f"Aday zaten mevcut (aynı email'den), ek atlandı: {attachment.filename} - Aday ID: {email_candidate_id}")
                            stats["duplicate"] += 1
                        else:
                            logger.error(f"Ek isleme hatasi (constraint): {attachment.filename} - {e}")
                            stats["error"] += 1
                    else:
                        logger.error(f"Ek isleme hatasi: {attachment.filename} - {e}")
                        stats["error"] += 1

                # Progress update (her 25 CV'de bir)
                total_processed = stats["success"] + stats["duplicate"] + stats["error"]
                if log_id and total_processed > 0 and total_processed % 25 == 0:
                    try:
                        update_email_collection_log(
                            log_id=log_id,
                            bulunan_cv=total_processed,
                            basarili_cv=stats["success"],
                            mevcut_aday=stats["duplicate"],
                            hatali_cv=stats["error"]
                        )
                        logger.debug(f"Progress update: {total_processed} CV işlendi")
                    except Exception as progress_err:
                        logger.warning(f"Progress update hatası: {progress_err}")

            # Email'i islendi isaretle
            mark_email_processed(email_msg.message_id)

    except Exception as e:
        logger.error(f"Hesap hatasi ({account['email']}): {e}")

    # Email toplama islemini GÜNCELLE (başlangıçta oluşturuldu)
    try:
        bulunan_cv = stats["success"] + stats["duplicate"] + stats["error"]
        if stats["error"] == 0 and stats["success"] > 0:
            durum = "tamamlandi"
        elif stats["success"] > 0:
            durum = "kismi_basarili"
        elif stats["processed"] == 0:
            durum = "bos"
        else:
            durum = "basarisiz"

        if log_id:
            update_email_collection_log(
                log_id=log_id,
                taranan_email=stats["processed"],
                bulunan_cv=bulunan_cv,
                basarili_cv=stats["success"],
                mevcut_aday=stats["duplicate"],
                hatali_cv=stats["error"],
                durum=durum
            )
            logger.info(f"Email tarama tamamlandı: {durum}, {bulunan_cv} CV, log_id: {log_id}")
        else:
            # log_id yoksa yeni kayıt oluştur (fallback)
            log_email_collection(
                account_id=account.get("id"),
                account_email=account.get("email", ""),
                klasor="INBOX",
                taranan_email=stats["processed"],
                bulunan_cv=bulunan_cv,
                basarili_cv=stats["success"],
                mevcut_aday=stats["duplicate"],
                hatali_cv=stats["error"],
                durum=durum,
                company_id=account.get("company_id"),
                user_id=None
            )
            logger.info(f"Email collection log yazildi (fallback): {durum}, {bulunan_cv} CV")
    except Exception as log_err:
        logger.warning(f"Email collection log hatası: {log_err}")

    return stats


def check_all_emails():
    """Tum email hesaplarini kontrol et"""
    logger.info("="*50)
    logger.info(f"Email kontrolu basladi: {datetime.now()}")

    accounts = get_all_email_accounts(only_active=True)

    if not accounts:
        logger.warning("Aktif email hesabi bulunamadi")
        return

    total_stats = {"processed": 0, "success": 0, "duplicate": 0, "error": 0}

    for account in accounts:
        stats = check_emails_for_account(account)
        for key in total_stats:
            total_stats[key] += stats[key]

    logger.info(f"Toplam sonuc: {total_stats}")
    logger.info(f"Email kontrolu bitti: {datetime.now()}")
    logger.info("="*50)
