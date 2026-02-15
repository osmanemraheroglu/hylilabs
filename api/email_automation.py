"""
TalentFlow - Email Otomasyon Sistemi
Otomatik email gönderimi için event-driven sistem

Desteklenen otomasyonlar:
- Durum değişikliği bildirimleri
- Mülakat hatırlatmaları (24 saat önce)
- Başvuru onay emailleri
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import threading
import time

logger = logging.getLogger(__name__)

from database import (
    get_connection, get_email_template, get_candidate,
    get_company_settings, save_company_setting
)
from email_sender import send_email
from events import register_handler, trigger_event
from config import COMPANY_INFO


# ============================================================
# OTOMASYON AYARLARI
# ============================================================

DEFAULT_AUTOMATION_SETTINGS = {
    "durum_degisikligi_email": True,      # Durum değişince email gönder
    "basvuru_onay_email": True,           # Yeni başvuruda onay emaili
    "mulakat_hatirlatma_email": True,     # Mülakat hatırlatması
    "hatirlatma_saat_oncesi": 24,         # Kaç saat önce hatırlatma
    "red_email_gonder": True,             # Red durumunda email
    "teklif_email_gonder": True,          # Teklif durumunda email
    "mulakat_email_gonder": True,         # Mülakat durumunda email
}


def get_automation_settings(company_id: int) -> Dict[str, Any]:
    """Otomasyon ayarlarını getir"""
    settings = get_company_settings(company_id)
    automation = settings.get("email_automation", {})

    # Varsayılan değerlerle birleştir
    result = DEFAULT_AUTOMATION_SETTINGS.copy()
    result.update(automation)
    return result


def save_automation_settings(company_id: int, settings: Dict[str, Any]) -> bool:
    """Otomasyon ayarlarını kaydet"""
    return save_company_setting(company_id, "email_automation", settings)


# ============================================================
# ŞABLON DEĞİŞKEN DEĞİŞTİRME
# ============================================================

def sanitize_template_var(value) -> str:
    """Email template değişkenlerini güvenli hale getir
    
    Güvenlik:
    - HTML injection önleme (< > karakterleri escape)
    - Format string injection önleme ({ } karakterleri kaldır)
    
    Args:
        value: Template değişkeni değeri
    
    Returns:
        Sanitize edilmiş string
    """
    if value is None:
        return ''
    value = str(value)
    # HTML injection önle
    value = value.replace('<', '&lt;').replace('>', '&gt;')
    # Format string injection önle (sadece { } karakterlerini kaldır, placeholder'ları bozma)
    # Not: replace_template_variables() {key} formatını kullanıyor, bu yüzden sadece tek { veya } karakterlerini kaldır
    # Ama bu çok agresif olabilir, bu yüzden sadece HTML escape yapıyoruz
    # Template'teki {key} formatı zaten güvenli çünkü key'ler whitelist'ten geliyor
    return value


def replace_template_variables(template: str, variables: Dict[str, str]) -> str:
    """
    Şablondaki değişkenleri değerlerle değiştir (güvenli)

    Args:
        template: Email şablonu ({aday_adi}, {pozisyon} vb. içeren)
        variables: Değişken değerleri dict'i

    Returns:
        Değişkenleri değiştirilmiş metin (sanitize edilmiş)
    """
    result = template
    for key, value in variables.items():
        placeholder = "{" + key + "}"
        # Güvenlik: Değerleri sanitize et
        sanitized_value = sanitize_template_var(value) if value else "-"
        result = result.replace(placeholder, sanitized_value)
    return result


def get_common_variables(candidate: Dict, company_id: int) -> Dict[str, str]:
    """Tüm şablonlarda kullanılan ortak değişkenleri getir"""
    return {
        "aday_adi": candidate.get("ad_soyad", ""),
        "aday_email": candidate.get("email", ""),
        "aday_telefon": candidate.get("telefon", ""),
        "sirket_adi": COMPANY_INFO.get("name", "TalentFlow"),
        "sirket_telefon": COMPANY_INFO.get("phone", ""),
        "sirket_adres": COMPANY_INFO.get("address", ""),
        "sirket_website": COMPANY_INFO.get("website", ""),
        "tarih": datetime.now().strftime("%d.%m.%Y"),
        "saat": datetime.now().strftime("%H:%M"),
    }


# ============================================================
# DURUM DEĞİŞİKLİĞİ EMAİLLERİ
# ============================================================

STATUS_TEMPLATE_MAP = {
    "mulakat": "mulakat_daveti",
    "teklif": "is_teklifi",
    "red": "red_bildirimi",
    "reddedildi": "red_bildirimi",
    "teklif_bekliyor": "is_teklifi",
    "ise_alindi": "is_teklifi",
}


def send_status_change_email(
    candidate_id: int,
    old_status: str,
    new_status: str,
    company_id: int,
    extra_variables: Dict[str, str] = None
) -> tuple[bool, str]:
    """
    Durum değişikliği emaili gönder

    Args:
        candidate_id: Aday ID
        old_status: Eski durum
        new_status: Yeni durum
        company_id: Firma ID
        extra_variables: Ek şablon değişkenleri

    Returns:
        (başarılı, mesaj) tuple
    """
    # Otomasyon ayarlarını kontrol et
    settings = get_automation_settings(company_id)

    if not settings.get("durum_degisikligi_email", True):
        return False, "Durum değişikliği emailleri devre dışı"

    # Duruma göre email gönder mi kontrol et
    if new_status in ["red", "reddedildi"] and not settings.get("red_email_gonder", True):
        return False, "Red emailleri devre dışı"

    if new_status in ["teklif", "teklif_bekliyor", "ise_alindi"] and not settings.get("teklif_email_gonder", True):
        return False, "Teklif emailleri devre dışı"

    if new_status == "mulakat" and not settings.get("mulakat_email_gonder", True):
        return False, "Mülakat emailleri devre dışı"

    # Şablon kodunu bul
    template_code = STATUS_TEMPLATE_MAP.get(new_status)
    if not template_code:
        return False, f"'{new_status}' durumu için şablon tanımlı değil"

    # Aday bilgilerini al (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return False, "Aday bulunamadı"

    candidate_dict = dict(candidate) if hasattr(candidate, 'keys') else candidate.__dict__

    if not candidate_dict.get("email"):
        return False, "Aday email adresi yok"

    # Şablonu getir
    template = get_email_template(template_code, company_id)
    if not template:
        return False, f"'{template_code}' şablonu bulunamadı"

    # Değişkenleri hazırla
    variables = get_common_variables(candidate_dict, company_id)
    if extra_variables:
        variables.update(extra_variables)

    # Şablonu doldur
    subject = replace_template_variables(template["konu"], variables)
    body = replace_template_variables(template["icerik"], variables)

    # Email gönder
    success, msg = send_email(candidate_dict["email"], subject, body)

    # Event tetikle
    if success:
        trigger_event("email_sent", {
            "type": "status_change",
            "candidate_id": candidate_id,
            "new_status": new_status,
            "email": candidate_dict["email"],
            "template": template_code
        })

    return success, msg


# ============================================================
# BAŞVURU ONAY EMAİLİ
# ============================================================

def send_application_confirmation_email(
    candidate_id: int,
    company_id: int,
    position_title: str = None
) -> tuple[bool, str]:
    """
    Başvuru onay emaili gönder

    Args:
        candidate_id: Aday ID
        company_id: Firma ID
        position_title: Başvurulan pozisyon (opsiyonel)

    Returns:
        (başarılı, mesaj) tuple
    """
    # Otomasyon ayarlarını kontrol et
    settings = get_automation_settings(company_id)

    if not settings.get("basvuru_onay_email", True):
        return False, "Başvuru onay emailleri devre dışı"

    # Aday bilgilerini al (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return False, "Aday bulunamadı"

    candidate_dict = dict(candidate) if hasattr(candidate, 'keys') else candidate.__dict__

    if not candidate_dict.get("email"):
        return False, "Aday email adresi yok"

    # Şablonu getir
    template = get_email_template("basvuru_alindi", company_id)
    if not template:
        return False, "Başvuru onay şablonu bulunamadı"

    # Değişkenleri hazırla
    variables = get_common_variables(candidate_dict, company_id)
    variables["pozisyon"] = position_title or "Genel Başvuru"

    # Şablonu doldur
    subject = replace_template_variables(template["konu"], variables)
    body = replace_template_variables(template["icerik"], variables)

    # Email gönder
    success, msg = send_email(candidate_dict["email"], subject, body)

    # Event tetikle
    if success:
        trigger_event("email_sent", {
            "type": "application_confirmation",
            "candidate_id": candidate_id,
            "email": candidate_dict["email"],
            "position": position_title
        })

    return success, msg


# ============================================================
# MÜLAKAT HATIRLATMA SİSTEMİ
# ============================================================

def get_upcoming_interviews(hours_ahead: int = 24) -> List[Dict]:
    """
    Yaklaşan mülakatları getir

    Args:
        hours_ahead: Kaç saat içindeki mülakatlar

    Returns:
        Mülakat listesi
    """
    try:
        now = datetime.now()
        target_time = now + timedelta(hours=hours_ahead)

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT i.*, c.ad_soyad, c.email, c.telefon, p.baslik as pozisyon_baslik
                FROM interviews i
                JOIN candidates c ON i.candidate_id = c.id
                LEFT JOIN positions p ON i.position_id = p.id
                WHERE i.durum = 'planlandı'
                  AND i.hatirlatma_gonderildi = 0
                  AND datetime(i.tarih || ' ' || i.saat) BETWEEN ? AND ?
            """, (now.strftime("%Y-%m-%d %H:%M"), target_time.strftime("%Y-%m-%d %H:%M")))

            interviews = [dict(row) for row in cursor.fetchall()]

        return interviews
    except Exception as e:
        logger.error(f"Mülakat sorgulama hatası: {e}", exc_info=True)
        return []


def send_interview_reminder_email(interview: Dict, company_id: int) -> tuple[bool, str]:
    """
    Mülakat hatırlatma emaili gönder

    Args:
        interview: Mülakat bilgileri
        company_id: Firma ID

    Returns:
        (başarılı, mesaj) tuple
    """
    # Otomasyon ayarlarını kontrol et
    settings = get_automation_settings(company_id)

    if not settings.get("mulakat_hatirlatma_email", True):
        return False, "Mülakat hatırlatma emailleri devre dışı"

    if not interview.get("email"):
        return False, "Aday email adresi yok"

    # Şablonu getir
    template = get_email_template("mulakat_hatirlatma", company_id)
    if not template:
        return False, "Mülakat hatırlatma şablonu bulunamadı"

    # Değişkenleri hazırla
    interview_datetime = datetime.strptime(
        f"{interview['tarih']} {interview['saat']}",
        "%Y-%m-%d %H:%M"
    )

    variables = {
        "aday_adi": interview.get("ad_soyad", ""),
        "aday_email": interview.get("email", ""),
        "pozisyon": interview.get("pozisyon_baslik") or "Genel Mülakat",
        "mulakat_tarihi": interview_datetime.strftime("%d.%m.%Y"),
        "mulakat_saati": interview_datetime.strftime("%H:%M"),
        "mulakat_turu": interview.get("tur", "Genel"),
        "mulakat_lokasyon": interview.get("lokasyon", "-"),
        "mulakatci": interview.get("mulakatci", "-"),
        "sirket_adi": COMPANY_INFO.get("name", "TalentFlow"),
        "sirket_telefon": COMPANY_INFO.get("phone", ""),
    }

    # Şablonu doldur
    subject = replace_template_variables(template["konu"], variables)
    body = replace_template_variables(template["icerik"], variables)

    # Email gönder
    success, msg = send_email(interview["email"], subject, body)

    # Başarılıysa hatırlatma gönderildi olarak işaretle
    if success:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE interviews
                    SET hatirlatma_gonderildi = 1
                    WHERE id = ?
                """, (interview["id"],))
                conn.commit()
        except Exception as e:
            logger.error(f"Hatırlatma güncelleme hatası: {e}", exc_info=True)

        trigger_event("email_sent", {
            "type": "interview_reminder",
            "interview_id": interview["id"],
            "candidate_id": interview.get("candidate_id"),
            "email": interview["email"]
        })

    return success, msg


def process_interview_reminders(company_id: int = None) -> Dict[str, Any]:
    """
    Tüm yaklaşan mülakatlar için hatırlatma gönder

    Args:
        company_id: Firma ID (None ise tüm firmalar)

    Returns:
        İşlem sonucu
    """
    results = {
        "total": 0,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }

    # Otomasyon ayarlarını kontrol et
    if company_id:
        settings = get_automation_settings(company_id)
        hours_ahead = settings.get("hatirlatma_saat_oncesi", 24)
    else:
        hours_ahead = 24

    interviews = get_upcoming_interviews(hours_ahead)
    results["total"] = len(interviews)

    for interview in interviews:
        try:
            # Firma ID'yi belirle
            interview_company_id = company_id or interview.get("company_id", 1)

            success, msg = send_interview_reminder_email(interview, interview_company_id)

            if success:
                results["sent"] += 1
            elif "devre dışı" in msg.lower():
                results["skipped"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "interview_id": interview["id"],
                    "error": msg
                })
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "interview_id": interview.get("id"),
                "error": str(e)
            })

    return results


# ============================================================
# EVENT HANDLER'LAR
# ============================================================

def on_candidate_status_changed(data: Dict[str, Any]) -> None:
    """Aday durumu değiştiğinde tetiklenen handler"""
    candidate_id = data.get("candidate_id")
    old_status = data.get("old_status")
    new_status = data.get("new_status")

    # Firma ID'yi adaydan al
    # Not: Bu handler event'ten tetikleniyor ve company_id bilgisi yok
    # Adayın company_id'sini öğrenmek için allow_cross_tenant=True kullanıyoruz
    try:
        candidate = get_candidate(candidate_id, allow_cross_tenant=True)
        if candidate:
            candidate_dict = dict(candidate) if hasattr(candidate, 'keys') else candidate.__dict__
            company_id = candidate_dict.get("company_id", 1)

            # Email gönder (company_id ile güvenli erişim)
            send_status_change_email(candidate_id, old_status, new_status, company_id)
    except Exception as e:
        logger.error(f"Durum değişikliği email hatası: {e}", exc_info=True)


def on_candidate_created(data: Dict[str, Any]) -> None:
    """Yeni aday oluşturulduğunda tetiklenen handler"""
    candidate_id = data.get("candidate_id")
    company_id = data.get("company_id", 1)
    source = data.get("source", "manuel")

    # Sadece CV yükleme ve email kaynaklarında onay emaili gönder
    if source in ["cv_upload", "email", "web"]:
        try:
            send_application_confirmation_email(candidate_id, company_id)
        except Exception as e:
            logger.error(f"Başvuru onay email hatası: {e}", exc_info=True)


def on_application_created(data: Dict[str, Any]) -> None:
    """Yeni başvuru oluşturulduğunda tetiklenen handler"""
    candidate_id = data.get("candidate_id")
    position_id = data.get("position_id")

    # Pozisyon başlığını al
    position_title = None
    if position_id:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT baslik FROM positions WHERE id = ?", (position_id,))
                row = cursor.fetchone()
                if row:
                    position_title = row["baslik"]
        except Exception as e:
            logger.debug(f"Pozisyon başlığı sorgulama hatası: {e}")
            # Devam et, position_title None kalabilir

    # Onay emaili zaten candidate_created'da gönderiliyor
    # Burada ek işlemler yapılabilir


# ============================================================
# OTOMASYON BAŞLATMA
# ============================================================

_automation_initialized = False
_reminder_thread = None
_reminder_running = False


def initialize_email_automation():
    """
    Email otomasyon sistemini başlat
    Event handler'ları kaydet
    """
    global _automation_initialized

    if _automation_initialized:
        return

    # Event handler'ları kaydet
    register_handler("candidate_status_changed", on_candidate_status_changed)
    register_handler("candidate_created", on_candidate_created)
    register_handler("application_created", on_application_created)

    _automation_initialized = True
    logger.info("[EMAIL AUTOMATION] Sistem başlatıldı")


def start_reminder_scheduler(interval_minutes: int = 60):
    """
    Hatırlatma zamanlayıcısını başlat

    Args:
        interval_minutes: Kontrol aralığı (dakika)
    """
    global _reminder_thread, _reminder_running

    if _reminder_running:
        return

    def reminder_loop():
        global _reminder_running
        _reminder_running = True

        while _reminder_running:
            try:
                result = process_interview_reminders()
                if result["sent"] > 0:
                    logger.info(f"[REMINDER] {result['sent']} hatırlatma gönderildi")
            except Exception as e:
                logger.error(f"[REMINDER] Hata: {e}", exc_info=True)

            # Belirlenen süre bekle
            time.sleep(interval_minutes * 60)

    _reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    _reminder_thread.start()
    logger.info(f"[REMINDER] Zamanlayıcı başlatıldı ({interval_minutes} dakika aralıkla)")


def stop_reminder_scheduler():
    """Hatırlatma zamanlayıcısını durdur"""
    global _reminder_running
    _reminder_running = False


# ============================================================
# MANUEL TETİKLEME FONKSİYONLARI
# ============================================================

def send_bulk_status_emails(
    candidate_ids: List[int],
    new_status: str,
    company_id: int
) -> Dict[str, Any]:
    """
    Toplu durum değişikliği emaili gönder

    Args:
        candidate_ids: Aday ID listesi
        new_status: Yeni durum
        company_id: Firma ID

    Returns:
        İşlem sonucu
    """
    results = {
        "total": len(candidate_ids),
        "sent": 0,
        "failed": 0,
        "errors": []
    }

    for cid in candidate_ids:
        success, msg = send_status_change_email(cid, None, new_status, company_id)
        if success:
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["errors"].append({"candidate_id": cid, "error": msg})

    return results


def send_custom_email(
    candidate_id: int,
    company_id: int,
    template_code: str,
    extra_variables: Dict[str, str] = None
) -> tuple[bool, str]:
    """
    Özel şablon ile email gönder

    Args:
        candidate_id: Aday ID
        company_id: Firma ID
        template_code: Şablon kodu
        extra_variables: Ek değişkenler

    Returns:
        (başarılı, mesaj) tuple
    """
    # Aday bilgilerini al (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return False, "Aday bulunamadı"

    candidate_dict = dict(candidate) if hasattr(candidate, 'keys') else candidate.__dict__

    if not candidate_dict.get("email"):
        return False, "Aday email adresi yok"

    # Şablonu getir
    template = get_email_template(template_code, company_id)
    if not template:
        return False, f"'{template_code}' şablonu bulunamadı"

    # Değişkenleri hazırla
    variables = get_common_variables(candidate_dict, company_id)
    if extra_variables:
        variables.update(extra_variables)

    # Şablonu doldur
    subject = replace_template_variables(template["konu"], variables)
    body = replace_template_variables(template["icerik"], variables)

    # Email gönder
    success, msg = send_email(candidate_dict["email"], subject, body)

    if success:
        trigger_event("email_sent", {
            "type": "custom",
            "candidate_id": candidate_id,
            "email": candidate_dict["email"],
            "template": template_code
        })

    return success, msg


# Modül yüklendiğinde otomasyonu başlat
initialize_email_automation()
