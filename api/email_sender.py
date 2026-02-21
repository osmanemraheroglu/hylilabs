"""
TalentFlow Email Gonderici
SMTP ile mulakat bildirimleri gonderir
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

from config import SMTP_CONFIG, COMPANY_INFO


# Email sablonlari
INTERVIEW_INVITE_TEMPLATE = """
Sayın {candidate_name},

{company_name} olarak başvurunuzu değerlendirdik ve sizinle bir mülakat gerçekleştirmek istiyoruz.

MÜLAKAT DETAYLARI
-----------------
Tarih: {interview_date}
Saat: {interview_time}
Süre: {duration} dakika
Tür: {interview_type}
Lokasyon: {location}
{location_details}

{interviewer_info}

POZİSYON
--------
{position_title}
{notes_section}
Lütfen bu mülakat davetini onaylamak veya değişiklik talep etmek için bizimle iletişime geçin.

Saygılarımızla,
{company_name} İK Ekibi
{company_contact}
"""

INTERVIEW_REMINDER_TEMPLATE = """
Sayin {candidate_name},

Bu email, yarin gerceklesecek mulakatiniz icin bir hatirlatmadir.

MULAKAT DETAYLARI
-----------------
Tarih: {interview_date}
Saat: {interview_time}
Sure: {duration} dakika
Lokasyon: {location}
{location_details}

{interviewer_info}

Herhangi bir sorunuz varsa lutfen bizimle iletisime gecin.

Basarilar dileriz!

{company_name} IK Ekibi
"""

INTERVIEW_CANCELLED_TEMPLATE = """
Sayin {candidate_name},

Maalesef {interview_date} tarihinde planlanmis olan mulakatinizin iptal edildigini bildirmek isteriz.

{cancellation_reason}

En kisa surede sizinle yeni bir mulakat planlamak icin iletisime gececegiz.

Anladiginiz icin tesekkur ederiz.

Saygilarimizla,
{company_name} IK Ekibi
"""

INTERVIEWER_NOTIFICATION_TEMPLATE = """
Yeni Mulakat Planlandi

MULAKAT DETAYLARI
-----------------
Aday: {candidate_name}
Email: {candidate_email}
Telefon: {candidate_phone}
Mevcut Pozisyon: {current_position}

Tarih: {interview_date}
Saat: {interview_time}
Sure: {duration} dakika
Tur: {interview_type}
Lokasyon: {location}

Pozisyon: {position_title}

Notlar: {notes}
"""

INTERVIEW_UPDATE_TEMPLATE = """
Sayin {candidate_name},

Sizinle planlanmis olan mulakat tarihinde degisiklik yapilmistir.

ONCEKI TARIH:
{old_date}

YENI MULAKAT DETAYLARI:
-----------------------
Tarih: {new_date}
Saat: {new_time}
Sure: {duration} dakika
Tur: {interview_type}
Lokasyon: {location}
{position_info}
{notes_info}

Yeni tarih ve saat uygun degilse, lutfen bizimle iletisime geciniz.

Saygilarimizla,
{company_name} IK Ekibi
"""


def send_email(
    to_email: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    account: Optional[dict] = None,
    sirket_adi: Optional[str] = None
) -> tuple[bool, str]:
    """
    Email gonder

    Args:
        to_email: Alici email adresi
        subject: Konu
        body: Email icerigi
        cc: CC adresi (opsiyonel)
        account: Kullanilacak email hesabi (veritabanindan). None ise varsayilan SMTP_CONFIG kullanilir.
        sirket_adi: Sirket adi (opsiyonel). Oncelikli olarak sender_name icin kullanilir.

    Returns:
        (basarili, mesaj) tuple
    """
    # Hesap ayarlarini belirle
    if account:
        smtp_server = account["smtp_server"]
        smtp_port = account.get("smtp_port", 587)
        email_addr = account["email"]
        password = account["sifre"]
        # Oncelik: sirket_adi > account.sender_name > account.ad > 'HyliLabs'
        sender_name = sirket_adi if sirket_adi else (account.get("sender_name") or account.get("ad") or "HyliLabs")
    else:
        if not SMTP_CONFIG["email"] or not SMTP_CONFIG["password"]:
            return False, "SMTP ayarlari yapilandirilmamis"
        smtp_server = SMTP_CONFIG["smtp_server"]
        smtp_port = SMTP_CONFIG["smtp_port"]
        email_addr = SMTP_CONFIG["email"]
        password = SMTP_CONFIG["password"]
        # Oncelik: sirket_adi > SMTP_CONFIG.sender_name > 'HyliLabs'
        sender_name = sirket_adi if sirket_adi else (SMTP_CONFIG.get("sender_name") or "HyliLabs")

    try:
        # Email olustur
        msg = MIMEMultipart()
        msg["From"] = f"{sender_name} <{email_addr}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = cc

        msg.attach(MIMEText(body, "plain", "utf-8"))

        # SMTP baglantisi
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_addr, password)

        # Gonder
        recipients = [to_email]
        if cc:
            recipients.append(cc)

        server.sendmail(email_addr, recipients, msg.as_string())
        server.quit()

        return True, "Email basariyla gonderildi"

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP kimlik dogrulama hatasi - email/sifre kontrol edin"
    except smtplib.SMTPException as e:
        return False, f"SMTP hatasi: {str(e)}"
    except Exception as e:
        return False, f"Beklenmeyen hata: {str(e)}"


# Türkçe ay isimleri
TURKCE_AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
    5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
    9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}


def format_turkish_date(dt: datetime) -> str:
    """Tarihi Türkçe formatta döndür (22 Şubat 2026)"""
    return f"{dt.day} {TURKCE_AYLAR[dt.month]} {dt.year}"


def get_location_details(location: str) -> str:
    """Lokasyon detaylarını oluştur"""
    if location == "online":
        return "Online mülakat linki ayrı olarak gönderilecektir."
    elif location == "ofis":
        if COMPANY_INFO["address"]:
            return f"Adres: {COMPANY_INFO['address']}"
        return "Ofis adresi ayrı olarak bildirilecektir."
    elif location == "telefon":
        return "Belirtilen saatte sizi arayacağız."
    return ""


def get_interview_type_label(tur: str) -> str:
    """Mülakat türü etiketi"""
    labels = {
        "teknik": "Teknik Mülakat",
        "hr": "İK Mülakatı",
        "yonetici": "Yönetici Mülakatı",
        "genel": "Genel Değerlendirme"
    }
    return labels.get(tur, tur.title())


def generate_interview_invite_content(
    candidate_name: str,
    interview_date: datetime,
    duration: int,
    interview_type: str,
    location: str,
    position_title: str,
    interviewer: Optional[str] = None,
    notes: Optional[str] = None,
    confirm_url: Optional[str] = None,
    onay_suresi: int = 3,
    sirket_adi: Optional[str] = None,
    is_reminder: bool = False
) -> dict:
    """
    Mülakat davet emaili içeriği oluştur (göndermeden)

    Args:
        confirm_url: Mülakat onay linki (opsiyonel)
        sirket_adi: Şirket adı (opsiyonel, yoksa COMPANY_INFO kullanılır)
        is_reminder: Hatırlatma emaili mi?

    Returns:
        {"konu": str, "icerik": str}
    """
    # Şirket adı
    company_name = sirket_adi or COMPANY_INFO["name"]

    # Mülakatçı bilgisi
    interviewer_info = ""
    if interviewer:
        interviewer_info = f"Mülakatçı: {interviewer}"

    # Şirket iletişim
    company_contact = ""
    if COMPANY_INFO["phone"]:
        company_contact += f"Tel: {COMPANY_INFO['phone']}\n"
    if COMPANY_INFO["website"]:
        company_contact += f"Web: {COMPANY_INFO['website']}"

    # Notlar bölümü (koşullu)
    notes_section = ""
    if notes:
        notes_section = f"\nNOTLAR\n------\n{notes}\n"

    # Hatırlatma için özel giriş metni
    if is_reminder:
        intro_text = f"Mülakat davetinizi henüz onaylamadığınızı fark ettik. Son gün hatırlatması olarak tekrar gönderiyoruz."
    else:
        intro_text = f"{company_name} olarak başvurunuzu değerlendirdik ve sizinle bir mülakat gerçekleştirmek istiyoruz."

    # Template yerine manuel oluştur (hatırlatma için farklı giriş)
    body = f"""
Sayın {candidate_name},

{intro_text}

MÜLAKAT DETAYLARI
-----------------
Tarih: {format_turkish_date(interview_date)}
Saat: {interview_date.strftime("%H:%M")}
Süre: {duration} dakika
Tür: {get_interview_type_label(interview_type)}
Lokasyon: {location.title()}
{get_location_details(location)}

{interviewer_info}

POZİSYON
--------
{position_title or "Genel Başvuru"}
{notes_section}
Lütfen bu mülakat davetini onaylamak veya değişiklik talep etmek için bizimle iletişime geçin.

Saygılarımızla,
{company_name} İK Ekibi
{company_contact}
"""

    # Onay linki ekle
    if confirm_url:
        body += "\n\nMÜLAKATI ONAYLA\n"
        body += "---------------\n"
        body += "Mülakata katılacağınızı onaylamak için aşağıdaki linke tıklayın:\n"
        body += f"{confirm_url}\n"
        body += f"(Link {onay_suresi} gün geçerlidir)\n"

    # Konu satırı
    if is_reminder:
        subject = f"HATIRLATMA: Mülakat Daveti - {company_name} - {position_title or 'Genel Başvuru'}"
    else:
        subject = f"Mülakat Daveti - {company_name} - {position_title or 'Genel Başvuru'}"

    return {"konu": subject, "icerik": body}


def send_interview_invite(
    candidate_name: str,
    candidate_email: str,
    interview_date: datetime,
    duration: int,
    interview_type: str,
    location: str,
    position_title: str,
    interviewer: Optional[str] = None,
    notes: Optional[str] = None,
    cc_interviewer: Optional[str] = None,
    account: Optional[dict] = None,
    confirm_url: Optional[str] = None,
    onay_suresi: int = 3,
    sirket_adi: Optional[str] = None,
    is_reminder: bool = False
) -> tuple[bool, str]:
    """
    Mülakat davet emaili gönder

    Args:
        account: Email hesabı (veritabanından). None ise SMTP_CONFIG kullanılır.
        confirm_url: Mülakat onay linki (opsiyonel)
        sirket_adi: Şirket adı (opsiyonel)
        is_reminder: Hatırlatma emaili mi?

    Returns:
        (basarili, mesaj) tuple
    """
    content = generate_interview_invite_content(
        candidate_name=candidate_name,
        interview_date=interview_date,
        duration=duration,
        interview_type=interview_type,
        location=location,
        position_title=position_title,
        interviewer=interviewer,
        notes=notes,
        confirm_url=confirm_url,
        onay_suresi=onay_suresi,
        sirket_adi=sirket_adi,
        is_reminder=is_reminder
    )

    return send_email(candidate_email, content["konu"], content["icerik"], cc=cc_interviewer, account=account, sirket_adi=sirket_adi)


def send_interview_reminder(
    candidate_name: str,
    candidate_email: str,
    interview_date: datetime,
    duration: int,
    location: str,
    interviewer: Optional[str] = None
) -> tuple[bool, str]:
    """
    Mulakat hatirlatma emaili gonder
    """
    interviewer_info = ""
    if interviewer:
        interviewer_info = f"Mulakatci: {interviewer}"

    body = INTERVIEW_REMINDER_TEMPLATE.format(
        candidate_name=candidate_name,
        company_name=COMPANY_INFO["name"],
        interview_date=interview_date.strftime("%d %B %Y"),
        interview_time=interview_date.strftime("%H:%M"),
        duration=duration,
        location=location.title(),
        location_details=get_location_details(location),
        interviewer_info=interviewer_info
    )

    subject = f"Mulakat Hatirlatmasi - Yarin {interview_date.strftime('%H:%M')}"

    return send_email(candidate_email, subject, body)


def send_interview_cancellation(
    candidate_name: str,
    candidate_email: str,
    interview_date: datetime,
    reason: Optional[str] = None
) -> tuple[bool, str]:
    """
    Mulakat iptal emaili gonder
    """
    cancellation_reason = ""
    if reason:
        cancellation_reason = f"Iptal sebebi: {reason}"

    body = INTERVIEW_CANCELLED_TEMPLATE.format(
        candidate_name=candidate_name,
        company_name=COMPANY_INFO["name"],
        interview_date=interview_date.strftime("%d %B %Y %H:%M"),
        cancellation_reason=cancellation_reason
    )

    subject = f"Mulakat Iptali - {COMPANY_INFO['name']}"

    return send_email(candidate_email, subject, body)


def send_interviewer_notification(
    interviewer_email: str,
    candidate_name: str,
    candidate_email: str,
    candidate_phone: str,
    current_position: str,
    interview_date: datetime,
    duration: int,
    interview_type: str,
    location: str,
    position_title: str,
    notes: Optional[str] = None
) -> tuple[bool, str]:
    """
    Mulakatciya bildirim emaili gonder
    """
    body = INTERVIEWER_NOTIFICATION_TEMPLATE.format(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone or "-",
        current_position=current_position or "-",
        interview_date=interview_date.strftime("%d %B %Y"),
        interview_time=interview_date.strftime("%H:%M"),
        duration=duration,
        interview_type=get_interview_type_label(interview_type),
        location=location.title(),
        position_title=position_title or "Genel Basvuru",
        notes=notes or "-"
    )

    subject = f"Yeni Mulakat: {candidate_name} - {interview_date.strftime('%d/%m %H:%M')}"

    return send_email(interviewer_email, subject, body)


def send_interview_update_notification(
    candidate_name: str,
    candidate_email: str,
    old_date: datetime,
    new_date: datetime,
    duration: int,
    interview_type: str,
    location: str,
    position_title: Optional[str] = None,
    notes: Optional[str] = None
) -> tuple[bool, str]:
    """
    Mulakat degisiklik bildirimi gonder

    Args:
        candidate_name: Aday adi
        candidate_email: Aday email adresi
        old_date: Eski mulakat tarihi
        new_date: Yeni mulakat tarihi
        duration: Sure (dakika)
        interview_type: Mulakat turu
        location: Lokasyon
        position_title: Pozisyon basligi (opsiyonel)
        notes: Notlar (opsiyonel)

    Returns:
        (basarili, mesaj) tuple
    """
    position_info = f"Pozisyon: {position_title}" if position_title else ""
    notes_info = f"Notlar: {notes}" if notes else ""

    body = INTERVIEW_UPDATE_TEMPLATE.format(
        candidate_name=candidate_name,
        company_name=COMPANY_INFO["name"],
        old_date=old_date.strftime("%d %B %Y %H:%M"),
        new_date=new_date.strftime("%d %B %Y"),
        new_time=new_date.strftime("%H:%M"),
        duration=duration,
        interview_type=interview_type,
        location=location,
        position_info=position_info,
        notes_info=notes_info
    )

    subject = f"Mulakat Tarihi Degisikligi - {COMPANY_INFO['name']}"

    return send_email(candidate_email, subject, body)


def test_smtp_connection(account: Optional[dict] = None) -> tuple[bool, str]:
    """SMTP baglanti testi"""
    if account:
        smtp_server = account["smtp_server"]
        smtp_port = account.get("smtp_port", 587)
        email_addr = account["email"]
        password = account["sifre"]
    else:
        if not SMTP_CONFIG["email"] or not SMTP_CONFIG["password"]:
            return False, "SMTP ayarlari yapilandirilmamis"
        smtp_server = SMTP_CONFIG["smtp_server"]
        smtp_port = SMTP_CONFIG["smtp_port"]
        email_addr = SMTP_CONFIG["email"]
        password = SMTP_CONFIG["password"]

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_addr, password)
        server.quit()
        return True, "SMTP baglantisi basarili"
    except smtplib.SMTPAuthenticationError:
        return False, "Kimlik dogrulama hatasi"
    except Exception as e:
        return False, f"Baglanti hatasi: {str(e)}"


def test_smtp_with_params(
    smtp_server: str,
    smtp_port: int,
    email_addr: str,
    password: str
) -> tuple[bool, str]:
    """Belirli ayarlarla SMTP baglanti testi yap"""
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_addr, password)
        server.quit()
        return True, "SMTP baglantisi basarili"
    except smtplib.SMTPAuthenticationError:
        return False, "Kimlik dogrulama hatasi - email/sifre kontrol edin"
    except Exception as e:
        return False, f"Baglanti hatasi: {str(e)}"


# ============ SIFRE SIFIRLAMA EMAIL SABLONU ============

PASSWORD_RESET_TEMPLATE = """
Merhaba,

TalentFlow hesabiniz icin sifre sifirlama talebi alindi.

SIFIRLAMA KODUNUZ
-----------------
{reset_code}

Bu kod 15 dakika gecerlidir.

Eger bu talebi siz yapmadiysiniz, bu emaili gormezden gelebilirsiniz.
Hesabiniza erisim saglayamadiginizi dusunuyorsaniz, lutfen sistem yoneticisi ile iletisime gecin.

Guvenliginiz icin:
- Bu kodu kimseyle paylasmayiniz
- TalentFlow ekibi sizden asla sifrenizi istemez

Saygilarimizla,
{company_name} IK Ekibi
"""


def send_password_reset_email(
    to_email: str,
    reset_code: str,
    account: Optional[dict] = None
) -> tuple[bool, str]:
    """
    Sifre sifirlama kodu emaili gonder

    Args:
        to_email: Kullanici email adresi
        reset_code: 6 haneli sifirlama kodu
        account: Kullanilacak email hesabi (opsiyonel)

    Returns:
        (basarili, mesaj) tuple
    """
    body = PASSWORD_RESET_TEMPLATE.format(
        reset_code=reset_code,
        company_name=COMPANY_INFO.get("name", "TalentFlow")
    )

    subject = f"Sifre Sifirlama - {COMPANY_INFO.get('name', 'TalentFlow')}"

    return send_email(to_email, subject, body, account=account)
