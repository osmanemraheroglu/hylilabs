# -*- coding: utf-8 -*-
"""
TalentFlow - Rate Limiting Module
Istek sinirlama sistemi
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Tuple
from contextlib import contextmanager
import threading

# Thread-safe lock
_lock = threading.Lock()

# Veritabani yolu
DB_PATH = "data/talentflow.db"


# ============ RATE LIMIT SABITLERI ============

class RateLimitConfig:
    """Rate limit konfigurasyonlari"""

    # Login: 5 deneme / 15 dakika
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_WINDOW_MINUTES = 15

    # CV Yukleme: 20 dosya / saat
    CV_UPLOAD_MAX = 20
    CV_UPLOAD_WINDOW_MINUTES = 60

    # API Cagrisi: 100 istek / dakika
    API_MAX_REQUESTS = 100
    API_WINDOW_MINUTES = 1

    # Genel istek limiti: 1000 / saat
    GENERAL_MAX_REQUESTS = 1000
    GENERAL_WINDOW_MINUTES = 60

    # === PUBLIC ENDPOINT LIMITLERI (Kariyer Sayfası) ===
    # Public başvuru: 10 istek / saat / IP (spam önleme)
    PUBLIC_APPLY_MAX = 10
    PUBLIC_APPLY_WINDOW_MINUTES = 60

    # Public pozisyon listesi: 60 istek / dakika / IP
    PUBLIC_POSITIONS_MAX = 60
    PUBLIC_POSITIONS_WINDOW_MINUTES = 1

    # Public genel: 120 istek / dakika / IP
    PUBLIC_GENERAL_MAX = 120
    PUBLIC_GENERAL_WINDOW_MINUTES = 1


# ============ VERITABANI ============

@contextmanager
def get_connection():
    """Thread-safe veritabani baglantisi"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_rate_limit_table():
    """Rate limit tablosunu olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                action_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)

        # Index olustur (performans icin)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup
            ON rate_limits (identifier, action_type, timestamp)
        """)


def cleanup_old_records():
    """Eski rate limit kayitlarini temizle (24 saatten eski)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor.execute(
            "DELETE FROM rate_limits WHERE timestamp < ?",
            (cutoff,)
        )


# ============ RATE LIMIT FONKSIYONLARI ============

def record_action(identifier: str, action_type: str, metadata: str = None):
    """
    Bir aksiyonu kaydet

    Args:
        identifier: Kullanici identifier (email, IP, user_id)
        action_type: Aksiyon tipi (login, cv_upload, api_call)
        metadata: Ek bilgi (opsiyonel)
    """
    with _lock:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rate_limits (identifier, action_type, timestamp, metadata)
                VALUES (?, ?, ?, ?)
            """, (identifier, action_type, datetime.now().isoformat(), metadata))


def get_action_count(identifier: str, action_type: str, window_minutes: int) -> int:
    """
    Belirli bir zaman penceresi icindeki aksiyon sayisini getir

    Args:
        identifier: Kullanici identifier
        action_type: Aksiyon tipi
        window_minutes: Zaman penceresi (dakika)

    Returns:
        Aksiyon sayisi
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM rate_limits
            WHERE identifier = ? AND action_type = ? AND timestamp > ?
        """, (identifier, action_type, cutoff))
        row = cursor.fetchone()
        return row["count"] if row else 0


def check_rate_limit(identifier: str, action_type: str,
                     max_attempts: int, window_minutes: int) -> Tuple[bool, int, int]:
    """
    Rate limit kontrolu yap

    Args:
        identifier: Kullanici identifier
        action_type: Aksiyon tipi
        max_attempts: Maksimum deneme sayisi
        window_minutes: Zaman penceresi (dakika)

    Returns:
        Tuple[bool, int, int]: (izin_var_mi, mevcut_sayi, kalan_deneme)
    """
    current_count = get_action_count(identifier, action_type, window_minutes)
    remaining = max(0, max_attempts - current_count)
    allowed = current_count < max_attempts

    return allowed, current_count, remaining


def get_wait_time(identifier: str, action_type: str, window_minutes: int) -> int:
    """
    Rate limit sifirlanana kadar bekleme suresini hesapla (saniye)

    Returns:
        Bekleme suresi (saniye), 0 eger limit yok
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()

        # En eski kaydi bul
        cursor.execute("""
            SELECT MIN(timestamp) as oldest
            FROM rate_limits
            WHERE identifier = ? AND action_type = ? AND timestamp > ?
        """, (identifier, action_type, cutoff))

        row = cursor.fetchone()
        if not row or not row["oldest"]:
            return 0

        oldest = datetime.fromisoformat(row["oldest"])
        reset_time = oldest + timedelta(minutes=window_minutes)
        wait_seconds = (reset_time - datetime.now()).total_seconds()

        return max(0, int(wait_seconds))


# ============ OZEL RATE LIMIT FONKSIYONLARI ============

def check_login_limit(identifier: str) -> Tuple[bool, str]:
    """
    Login rate limit kontrolu

    Args:
        identifier: Email veya IP adresi

    Returns:
        Tuple[bool, str]: (izin_var_mi, mesaj)
    """
    allowed, count, remaining = check_rate_limit(
        identifier,
        "login",
        RateLimitConfig.LOGIN_MAX_ATTEMPTS,
        RateLimitConfig.LOGIN_WINDOW_MINUTES
    )

    if not allowed:
        wait_time = get_wait_time(identifier, "login", RateLimitConfig.LOGIN_WINDOW_MINUTES)
        wait_minutes = max(1, wait_time // 60)
        return False, f"Cok fazla basarisiz giris denemesi. {wait_minutes} dakika sonra tekrar deneyin."

    return True, f"Kalan deneme: {remaining}"


def record_login_attempt(identifier: str, success: bool = False):
    """Login denemesini kaydet (sadece basarisiz denemeleri sayar)"""
    if not success:
        record_action(identifier, "login", "failed")


def clear_login_attempts(identifier: str):
    """Basarili giris sonrasi login denemelerini temizle"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM rate_limits
            WHERE identifier = ? AND action_type = 'login'
        """, (identifier,))


def check_cv_upload_limit(identifier: str) -> Tuple[bool, str]:
    """
    CV yukleme rate limit kontrolu

    Args:
        identifier: User ID veya IP

    Returns:
        Tuple[bool, str]: (izin_var_mi, mesaj)
    """
    allowed, count, remaining = check_rate_limit(
        identifier,
        "cv_upload",
        RateLimitConfig.CV_UPLOAD_MAX,
        RateLimitConfig.CV_UPLOAD_WINDOW_MINUTES
    )

    if not allowed:
        wait_time = get_wait_time(identifier, "cv_upload", RateLimitConfig.CV_UPLOAD_WINDOW_MINUTES)
        wait_minutes = max(1, wait_time // 60)
        return False, f"Saatlik CV yukleme limitine ulastiniz ({RateLimitConfig.CV_UPLOAD_MAX}). {wait_minutes} dakika sonra tekrar deneyin."

    return True, f"Kalan yukleme hakki: {remaining}/{RateLimitConfig.CV_UPLOAD_MAX}"


def record_cv_upload(identifier: str):
    """CV yukleme aksiyonunu kaydet"""
    record_action(identifier, "cv_upload")


def check_api_limit(identifier: str) -> Tuple[bool, str]:
    """
    API cagrisi rate limit kontrolu

    Args:
        identifier: User ID veya API key

    Returns:
        Tuple[bool, str]: (izin_var_mi, mesaj)
    """
    allowed, count, remaining = check_rate_limit(
        identifier,
        "api_call",
        RateLimitConfig.API_MAX_REQUESTS,
        RateLimitConfig.API_WINDOW_MINUTES
    )

    if not allowed:
        wait_time = get_wait_time(identifier, "api_call", RateLimitConfig.API_WINDOW_MINUTES)
        return False, f"API istek limitine ulastiniz. {wait_time} saniye sonra tekrar deneyin."

    return True, ""


def record_api_call(identifier: str):
    """API cagrisini kaydet"""
    record_action(identifier, "api_call")


# ============ PUBLIC ENDPOINT FONKSIYONLARI (Kariyer Sayfası) ============

def check_public_apply_limit(ip_address: str) -> Tuple[bool, str]:
    """
    Public başvuru rate limit kontrolu (spam önleme)

    Args:
        ip_address: İstemci IP adresi

    Returns:
        Tuple[bool, str]: (izin_var_mi, mesaj)
    """
    allowed, count, remaining = check_rate_limit(
        ip_address,
        "public_apply",
        RateLimitConfig.PUBLIC_APPLY_MAX,
        RateLimitConfig.PUBLIC_APPLY_WINDOW_MINUTES
    )

    if not allowed:
        wait_time = get_wait_time(ip_address, "public_apply", RateLimitConfig.PUBLIC_APPLY_WINDOW_MINUTES)
        wait_minutes = max(1, wait_time // 60)
        return False, f"Çok fazla başvuru gönderdiniz. {wait_minutes} dakika sonra tekrar deneyin."

    return True, f"Kalan başvuru hakkı: {remaining}"


def record_public_apply(ip_address: str):
    """Public başvuru aksiyonunu kaydet"""
    record_action(ip_address, "public_apply")


def check_public_positions_limit(ip_address: str) -> Tuple[bool, str]:
    """
    Public pozisyon listesi rate limit kontrolu

    Args:
        ip_address: İstemci IP adresi

    Returns:
        Tuple[bool, str]: (izin_var_mi, mesaj)
    """
    allowed, count, remaining = check_rate_limit(
        ip_address,
        "public_positions",
        RateLimitConfig.PUBLIC_POSITIONS_MAX,
        RateLimitConfig.PUBLIC_POSITIONS_WINDOW_MINUTES
    )

    if not allowed:
        wait_time = get_wait_time(ip_address, "public_positions", RateLimitConfig.PUBLIC_POSITIONS_WINDOW_MINUTES)
        return False, f"Çok fazla istek gönderdiniz. {wait_time} saniye sonra tekrar deneyin."

    return True, ""


def record_public_positions(ip_address: str):
    """Public pozisyon listesi aksiyonunu kaydet"""
    record_action(ip_address, "public_positions")


# ============ DEKORATOR ============

def rate_limit_decorator(action_type: str, max_attempts: int, window_minutes: int):
    """
    Rate limit dekoratoru

    Kullanim:
        @rate_limit_decorator("api_call", 100, 1)
        def my_api_function(user_id, ...):
            ...
    """
    def decorator(func):
        def wrapper(identifier, *args, **kwargs):
            allowed, count, remaining = check_rate_limit(
                str(identifier), action_type, max_attempts, window_minutes
            )

            if not allowed:
                wait_time = get_wait_time(str(identifier), action_type, window_minutes)
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {action_type}. "
                    f"Wait {wait_time} seconds."
                )

            # Aksiyonu kaydet
            record_action(str(identifier), action_type)

            return func(identifier, *args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Rate limit asildi hatasi"""
    pass


# ============ ISTATISTIKLER ============

def get_rate_limit_stats(identifier: str = None) -> dict:
    """
    Rate limit istatistiklerini getir

    Args:
        identifier: Belirli bir kullanici icin (None = tum sistem)

    Returns:
        Istatistik dictionary
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # Son 1 saat
        hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        if identifier:
            cursor.execute("""
                SELECT action_type, COUNT(*) as count
                FROM rate_limits
                WHERE identifier = ? AND timestamp > ?
                GROUP BY action_type
            """, (identifier, hour_ago))
        else:
            cursor.execute("""
                SELECT action_type, COUNT(*) as count
                FROM rate_limits
                WHERE timestamp > ?
                GROUP BY action_type
            """, (hour_ago,))

        for row in cursor.fetchall():
            stats[row["action_type"]] = row["count"]

        return stats


# Modul yuklendiginde tabloyu olustur
init_rate_limit_table()
