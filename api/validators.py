# -*- coding: utf-8 -*-
"""
TalentFlow - Input Validation Module
Kullanici girdilerini dogrulama ve temizleme fonksiyonlari
"""

import re
import html
from typing import Optional, Tuple

# ============ SABITLER ============

# Dosya limitleri
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 10MB

# Izin verilen dosya tipleri
ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}

# Email regex (RFC 5322 basitleştirilmiş)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Telefon regex (Turkiye formatlari)
# +90 5XX XXX XX XX, 0 5XX XXX XX XX, 5XX XXX XX XX
PHONE_REGEX = re.compile(
    r"^(?:\+90|0)?[\s.-]?[1-9][0-9]{2}[\s.-]?[0-9]{3}[\s.-]?[0-9]{2}[\s.-]?[0-9]{2}$"
)

# Tehlikeli HTML/JS patternleri
DANGEROUS_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onclick, onerror, etc.
    re.compile(r"<iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<object[^>]*>", re.IGNORECASE),
    re.compile(r"<embed[^>]*>", re.IGNORECASE),
]


# ============ EMAIL DOGRULAMA ============

def validate_email(email: str) -> Tuple[bool, str]:
    """
    Email formatini dogrula

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    if not email:
        return False, "Email adresi boş olamaz"

    email = email.strip().lower()

    if len(email) > 254:
        return False, "Email adresi çok uzun (max 254 karakter)"

    if not EMAIL_REGEX.match(email):
        return False, "Geçersiz email formatı"

    # Basit domain kontrolu
    domain = email.split("@")[1]
    if ".." in domain or domain.startswith(".") or domain.endswith("."):
        return False, "Geçersiz email domain"

    return True, ""


def normalize_email(email: str) -> str:
    """Email adresini normalize et (lowercase, trim)"""
    if not email:
        return ""
    return email.strip().lower()


# ============ TELEFON DOGRULAMA ============

def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    Telefon numarasini dogrula (Turkiye formatlari)

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    if not phone:
        return True, ""  # Telefon opsiyonel olabilir

    # Sadece rakam ve izin verilen karakterler
    cleaned = re.sub(r"[\s.\-\(\)]", "", phone.strip())

    # Cok kisa veya cok uzun
    if len(cleaned) < 10:
        return False, "Telefon numarası çok kısa"
    if len(cleaned) > 13:
        return False, "Telefon numarası çok uzun"

    if not PHONE_REGEX.match(phone.strip()):
        return False, "Geçersiz telefon formatı"

    return True, ""


def normalize_phone(phone: str) -> str:
    """
    Telefon numarasini normalize et
    Format: +90 5XX XXX XX XX
    """
    if not phone:
        return ""

    # Sadece rakamlari al
    digits = re.sub(r"[^\d]", "", phone)

    # Basa 0 veya 90 ekle
    if len(digits) == 10:
        digits = "90" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "9" + digits

    # Format: +90 5XX XXX XX XX
    if len(digits) == 12 and digits.startswith("90"):
        return f"+{digits[:2]} {digits[2:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"

    return phone.strip()


# ============ DOSYA DOGRULAMA ============

def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """
    Dosya uzantisini dogrula (sadece PDF/DOCX)

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    if not filename:
        return False, "Dosya adı boş olamaz"

    # Uzantiyi al
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_FILE_EXTENSIONS:
        return False, f"Desteklenmeyen dosya tipi. Sadece PDF ve DOCX kabul edilir."

    return True, ""


def validate_file_size(size_bytes: int) -> Tuple[bool, str]:
    """
    Dosya boyutunu dogrula (max 10MB)

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    if size_bytes <= 0:
        return False, "Dosya boş"

    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"Dosya çok büyük ({size_mb:.1f}MB). Maksimum {MAX_FILE_SIZE_MB}MB"

    return True, ""


def validate_file(filename: str, size_bytes: int, content: bytes = None) -> Tuple[bool, str]:
    """
    Dosyayi tam dogrula (uzanti + boyut + magic bytes)

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    # Uzanti kontrolu
    valid, msg = validate_file_extension(filename)
    if not valid:
        return False, msg

    # Boyut kontrolu
    valid, msg = validate_file_size(size_bytes)
    if not valid:
        return False, msg

    # Magic bytes kontrolu (dosya icerigi varsa)
    if content:
        valid, msg = validate_file_magic_bytes(content, filename)
        if not valid:
            return False, msg

    return True, ""


def validate_file_magic_bytes(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    Dosya magic bytes kontrolu - gercek dosya tipini dogrula

    Returns:
        Tuple[bool, str]: (gecerli_mi, hata_mesaji)
    """
    if len(content) < 4:
        return False, "Dosya içeriği çok kısa"

    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    # PDF magic bytes: %PDF
    if ext == ".pdf":
        if not content[:4] == b"%PDF":
            return False, "Geçersiz PDF dosyası"

    # DOCX magic bytes: PK (ZIP archive)
    elif ext == ".docx":
        if not content[:2] == b"PK":
            return False, "Geçersiz DOCX dosyası"

    return True, ""


def get_file_extension(filename: str) -> str:
    """Dosya uzantisini al (lowercase)"""
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


# ============ XSS TEMIZLIGI ============

def sanitize_html(text: str) -> str:
    """
    HTML karakterlerini escape et (XSS koruması)
    """
    if not text:
        return ""
    return html.escape(str(text))


def sanitize_input(text: str) -> str:
    """
    Kullanici girdisini temizle:
    - HTML escape
    - Tehlikeli patternleri kaldir
    - Whitespace normalize
    """
    if not text:
        return ""

    text = str(text)

    # Tehlikeli patternleri kaldir
    for pattern in DANGEROUS_PATTERNS:
        text = pattern.sub("", text)

    # HTML escape
    text = html.escape(text)

    # Whitespace normalize (fazla bosluklari tek bosluga indir)
    text = " ".join(text.split())

    return text.strip()


def sanitize_dict(data: dict, exclude_keys: set = None) -> dict:
    """
    Dictionary'deki tum string degerleri temizle

    Args:
        data: Temizlenecek dictionary
        exclude_keys: Temizlenmeyecek key'ler (ornegin password)
    """
    if not data:
        return {}

    exclude_keys = exclude_keys or set()
    result = {}

    for key, value in data.items():
        if key in exclude_keys:
            result[key] = value
        elif isinstance(value, str):
            result[key] = sanitize_input(value)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, exclude_keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_input(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


# ============ GENEL DOGRULAMALAR ============

def validate_required(value: str, field_name: str) -> Tuple[bool, str]:
    """Zorunlu alan kontrolu"""
    if not value or not str(value).strip():
        return False, f"{field_name} alanı zorunludur"
    return True, ""


def validate_length(value: str, field_name: str, min_len: int = 0, max_len: int = 1000) -> Tuple[bool, str]:
    """Uzunluk kontrolu"""
    if not value:
        return True, ""

    length = len(str(value))

    if length < min_len:
        return False, f"{field_name} en az {min_len} karakter olmalı"

    if length > max_len:
        return False, f"{field_name} en fazla {max_len} karakter olabilir"

    return True, ""


def validate_url(url: str) -> Tuple[bool, str]:
    """URL formatini dogrula"""
    if not url:
        return True, ""  # Opsiyonel

    url = url.strip()

    # Basit URL regex
    url_pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$", re.IGNORECASE
    )

    if not url_pattern.match(url):
        return False, "Geçersiz URL formatı"

    return True, ""


# ============ ADAY BILGILERI DOGRULAMA ============

def validate_candidate_data(data: dict) -> Tuple[bool, list]:
    """
    Aday verilerini toplu dogrula

    Returns:
        Tuple[bool, list]: (gecerli_mi, hata_listesi)
    """
    errors = []

    # Email kontrolu
    if "email" in data and data["email"]:
        valid, msg = validate_email(data["email"])
        if not valid:
            errors.append(msg)

    # Telefon kontrolu
    if "telefon" in data and data["telefon"]:
        valid, msg = validate_phone(data["telefon"])
        if not valid:
            errors.append(msg)

    # LinkedIn URL kontrolu
    if "linkedin" in data and data["linkedin"]:
        valid, msg = validate_url(data["linkedin"])
        if not valid:
            errors.append("Geçersiz LinkedIn URL")

    # GitHub URL kontrolu
    if "github" in data and data["github"]:
        valid, msg = validate_url(data["github"])
        if not valid:
            errors.append("Geçersiz GitHub URL")

    # Ad soyad uzunluk kontrolu
    if "ad_soyad" in data:
        valid, msg = validate_length(data["ad_soyad"], "Ad Soyad", min_len=2, max_len=100)
        if not valid:
            errors.append(msg)

    return len(errors) == 0, errors


# ============ KULLANICI BILGILERI DOGRULAMA ============

def validate_user_data(data: dict) -> Tuple[bool, list]:
    """
    Kullanici verilerini toplu dogrula

    Returns:
        Tuple[bool, list]: (gecerli_mi, hata_listesi)
    """
    errors = []

    # Email kontrolu (zorunlu)
    if "email" in data:
        valid, msg = validate_email(data["email"])
        if not valid:
            errors.append(msg)

    # Ad soyad kontrolu
    if "ad_soyad" in data:
        valid, msg = validate_length(data["ad_soyad"], "Ad Soyad", min_len=2, max_len=100)
        if not valid:
            errors.append(msg)

    # Sifre kontrolu
    if "password" in data:
        valid, msg = validate_password_strength(data["password"])
        if not valid:
            errors.append(msg)

    return len(errors) == 0, errors


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Sifre gucunu kontrol et"""
    if not password:
        return False, "Şifre boş olamaz"

    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalı"

    if len(password) > 128:
        return False, "Şifre çok uzun"

    # En az bir rakam
    if not re.search(r"\d", password):
        return False, "Şifre en az bir rakam içermeli"

    # En az bir harf
    if not re.search(r"[a-zA-Z]", password):
        return False, "Şifre en az bir harf içermeli"

    return True, ""
