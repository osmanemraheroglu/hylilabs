# -*- coding: utf-8 -*-
"""
TalentFlow - Audit Trail System
Kullanici aktivitelerini loglama ve izleme
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import contextmanager
from enum import Enum

# Veritabani yolu
DB_PATH = "data/talentflow.db"


# ============ AKSIYON TIPLERI ============

class AuditAction(str, Enum):
    """Loglanacak aksiyon tipleri"""
    # Auth
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"

    # CV Operations
    CV_UPLOAD = "CV_UPLOAD"
    CV_DELETE = "CV_DELETE"
    CV_DOWNLOAD = "CV_DOWNLOAD"

    # Candidate Operations
    CANDIDATE_CREATE = "CANDIDATE_CREATE"
    CANDIDATE_UPDATE = "CANDIDATE_UPDATE"
    CANDIDATE_DELETE = "CANDIDATE_DELETE"
    CANDIDATE_VIEW = "CANDIDATE_VIEW"
    CANDIDATE_ANONYMIZE = "CANDIDATE_ANONYMIZE"

    # Position Operations
    POSITION_CREATE = "POSITION_CREATE"
    POSITION_UPDATE = "POSITION_UPDATE"
    POSITION_DELETE = "POSITION_DELETE"

    # User Operations
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_DELETE = "USER_DELETE"

    # Evaluation
    EVALUATION_CREATE = "EVALUATION_CREATE"
    EVALUATION_UPDATE = "EVALUATION_UPDATE"

    # Pool Operations
    POOL_TRANSFER = "POOL_TRANSFER"
    POOL_ADD = "POOL_ADD"
    POOL_REMOVE = "POOL_REMOVE"

    # Data Operations
    DATA_EXPORT = "DATA_EXPORT"
    DATA_IMPORT = "DATA_IMPORT"

    # Settings
    SETTINGS_CHANGE = "SETTINGS_CHANGE"

    # KVKK
    KVKK_CONSENT = "KVKK_CONSENT"
    KVKK_DATA_REQUEST = "KVKK_DATA_REQUEST"
    KVKK_DELETE_REQUEST = "KVKK_DELETE_REQUEST"

    # Email
    EMAIL_ACCOUNT_CREATE = "EMAIL_ACCOUNT_CREATE"
    EMAIL_ACCOUNT_DELETE = "EMAIL_ACCOUNT_DELETE"
    EMAIL_FETCH = "EMAIL_FETCH"

    # Company Operations (Super Admin)
    COMPANY_CREATE = "COMPANY_CREATE"
    COMPANY_DELETE = "COMPANY_DELETE"
    COMPANY_STATUS_CHANGE = "COMPANY_STATUS_CHANGE"

    # Synonym Operations (FAZ 3)
    SYNONYM_APPROVE = "SYNONYM_APPROVE"
    SYNONYM_CREATE = "SYNONYM_CREATE"
    SYNONYM_UPDATE = "SYNONYM_UPDATE"
    SYNONYM_DELETE = "SYNONYM_DELETE"

    # Generic Data Operations (FAZ 3.2)
    DATA_UPDATE = "DATA_UPDATE"
    DATA_DELETE = "DATA_DELETE"


class EntityType(str, Enum):
    """Entity tipleri"""
    CANDIDATE = "candidate"
    POSITION = "position"
    USER = "user"
    COMPANY = "company"
    APPLICATION = "application"
    INTERVIEW = "interview"
    EVALUATION = "evaluation"
    EMAIL_ACCOUNT = "email_account"
    POOL = "pool"
    SYSTEM = "system"
    SYNONYM = "synonym"


class KVKKCategory(str, Enum):
    """KVKK Veri İşleme Kategorileri (Madde 12 uyumlu)"""
    VERI_ISLEME = "veri_isleme"           # Kişisel Veri İşleme
    VERI_ERISIM = "veri_erisim"           # Kişisel Veriye Erişim
    VERI_SILME = "veri_silme"             # Kişisel Veri Silme/İmha
    VERI_AKTARIM = "veri_aktarim"         # Kişisel Veri Aktarımı
    VERI_GUNCELLEME = "veri_guncelleme"   # Kişisel Veri Güncelleme
    KULLANICI_YONETIMI = "kullanici_yonetimi"  # Kullanıcı Yönetimi
    SISTEM_ERISIMI = "sistem_erisimi"     # Sistem Erişimi
    GUVENLIK = "guvenlik"                 # Güvenlik Olayı


# KVKK Kategori Açıklamaları
KVKK_CATEGORY_LABELS = {
    KVKKCategory.VERI_ISLEME.value: "Kişisel Veri İşleme",
    KVKKCategory.VERI_ERISIM.value: "Kişisel Veriye Erişim",
    KVKKCategory.VERI_SILME.value: "Kişisel Veri Silme/İmha",
    KVKKCategory.VERI_AKTARIM.value: "Kişisel Veri Aktarımı",
    KVKKCategory.VERI_GUNCELLEME.value: "Kişisel Veri Güncelleme",
    KVKKCategory.KULLANICI_YONETIMI.value: "Kullanıcı Yönetimi",
    KVKKCategory.SISTEM_ERISIMI.value: "Sistem Erişimi",
    KVKKCategory.GUVENLIK.value: "Güvenlik Olayı"
}


# Aksiyon -> KVKK Kategorisi Eşleştirmesi
ACTION_KVKK_MAPPING = {
    # Sistem Erişimi
    AuditAction.LOGIN_SUCCESS.value: KVKKCategory.SISTEM_ERISIMI.value,
    AuditAction.LOGOUT.value: KVKKCategory.SISTEM_ERISIMI.value,

    # Güvenlik
    AuditAction.LOGIN_FAILED.value: KVKKCategory.GUVENLIK.value,

    # CV/Aday İşlemleri - Kişisel Veri
    AuditAction.CV_UPLOAD.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.CV_DELETE.value: KVKKCategory.VERI_SILME.value,
    AuditAction.CV_DOWNLOAD.value: KVKKCategory.VERI_AKTARIM.value,
    AuditAction.CANDIDATE_CREATE.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.CANDIDATE_UPDATE.value: KVKKCategory.VERI_GUNCELLEME.value,
    AuditAction.CANDIDATE_DELETE.value: KVKKCategory.VERI_SILME.value,
    AuditAction.CANDIDATE_VIEW.value: KVKKCategory.VERI_ERISIM.value,
    AuditAction.CANDIDATE_ANONYMIZE.value: KVKKCategory.VERI_SILME.value,

    # Pozisyon İşlemleri
    AuditAction.POSITION_CREATE.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.POSITION_UPDATE.value: KVKKCategory.VERI_GUNCELLEME.value,
    AuditAction.POSITION_DELETE.value: KVKKCategory.VERI_SILME.value,

    # Kullanıcı Yönetimi
    AuditAction.USER_CREATE.value: KVKKCategory.KULLANICI_YONETIMI.value,
    AuditAction.USER_UPDATE.value: KVKKCategory.KULLANICI_YONETIMI.value,
    AuditAction.USER_DELETE.value: KVKKCategory.KULLANICI_YONETIMI.value,

    # Değerlendirme
    AuditAction.EVALUATION_CREATE.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.EVALUATION_UPDATE.value: KVKKCategory.VERI_GUNCELLEME.value,

    # Havuz İşlemleri
    AuditAction.POOL_TRANSFER.value: KVKKCategory.VERI_GUNCELLEME.value,
    AuditAction.POOL_ADD.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.POOL_REMOVE.value: KVKKCategory.VERI_GUNCELLEME.value,

    # Veri Aktarım
    AuditAction.DATA_EXPORT.value: KVKKCategory.VERI_AKTARIM.value,
    AuditAction.DATA_IMPORT.value: KVKKCategory.VERI_ISLEME.value,

    # Ayarlar
    AuditAction.SETTINGS_CHANGE.value: KVKKCategory.KULLANICI_YONETIMI.value,

    # KVKK Özel
    AuditAction.KVKK_CONSENT.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.KVKK_DATA_REQUEST.value: KVKKCategory.VERI_ERISIM.value,
    AuditAction.KVKK_DELETE_REQUEST.value: KVKKCategory.VERI_SILME.value,

    # Email
    AuditAction.EMAIL_ACCOUNT_CREATE.value: KVKKCategory.KULLANICI_YONETIMI.value,
    AuditAction.EMAIL_ACCOUNT_DELETE.value: KVKKCategory.KULLANICI_YONETIMI.value,
    AuditAction.EMAIL_FETCH.value: KVKKCategory.VERI_ISLEME.value,

    # Company Operations (Super Admin)
    AuditAction.COMPANY_CREATE.value: KVKKCategory.KULLANICI_YONETIMI.value,
    AuditAction.COMPANY_DELETE.value: KVKKCategory.VERI_SILME.value,
    AuditAction.COMPANY_STATUS_CHANGE.value: KVKKCategory.KULLANICI_YONETIMI.value,

    # Synonym Operations (FAZ 3)
    AuditAction.SYNONYM_APPROVE.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.SYNONYM_CREATE.value: KVKKCategory.VERI_ISLEME.value,
    AuditAction.SYNONYM_UPDATE.value: KVKKCategory.VERI_GUNCELLEME.value,
    AuditAction.SYNONYM_DELETE.value: KVKKCategory.VERI_SILME.value,

    # Generic Data Operations (FAZ 3.2)
    AuditAction.DATA_UPDATE.value: KVKKCategory.VERI_GUNCELLEME.value,
    AuditAction.DATA_DELETE.value: KVKKCategory.VERI_SILME.value
}


# ============ VERITABANI ============

@contextmanager
def get_connection():
    """Veritabani baglantisi"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_audit_table():
    """Audit logs tablosunu olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                user_email TEXT,
                company_id INTEGER,
                action TEXT NOT NULL,
                action_label TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                entity_name TEXT,
                details TEXT,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                kvkk_category TEXT
            )
        """)

        # kvkk_category kolonu yoksa ekle (migration)
        try:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN kvkk_category TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN action_label TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN entity_name TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN old_values TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN new_values TEXT")
        except:
            pass

        # Indexler
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_logs (timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_logs (user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action
            ON audit_logs (action)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_entity
            ON audit_logs (entity_type, entity_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_kvkk
            ON audit_logs (kvkk_category)
        """)


# ============ LOGLAMA FONKSIYONLARI ============

def log_action(
    action: str,
    user_id: int = None,
    user_email: str = None,
    company_id: int = None,
    entity_type: str = None,
    entity_id: int = None,
    entity_name: str = None,
    details: dict = None,
    old_values: dict = None,
    new_values: dict = None,
    ip_address: str = None,
    user_agent: str = None
) -> int:
    """
    KVKK uyumlu aksiyon logu oluştur

    Args:
        action: Aksiyon tipi (AuditAction enum)
        user_id: Kullanici ID
        user_email: Kullanici email
        company_id: Firma ID
        entity_type: Entity tipi (EntityType enum)
        entity_id: Entity ID
        entity_name: Entity adı (örn: aday adı, pozisyon adı)
        details: Ek detaylar (dict -> JSON)
        old_values: Değişiklik öncesi değerler (KVKK için)
        new_values: Değişiklik sonrası değerler (KVKK için)
        ip_address: IP adresi
        user_agent: Tarayici bilgisi

    Returns:
        Oluşturulan log ID
    """
    # KVKK kategorisini otomatik belirle
    kvkk_category = ACTION_KVKK_MAPPING.get(action, None)

    # Aksiyon etiketini belirle
    action_label = None
    for audit_action in AuditAction:
        if audit_action.value == action:
            action_label = action.replace("_", " ").title()
            break

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_logs (
                timestamp, user_id, user_email, company_id,
                action, action_label, entity_type, entity_id, entity_name,
                details, old_values, new_values,
                ip_address, user_agent, kvkk_category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            user_id,
            user_email,
            company_id,
            action,
            action_label,
            entity_type,
            entity_id,
            entity_name,
            json.dumps(details, ensure_ascii=False) if details else None,
            json.dumps(old_values, ensure_ascii=False) if old_values else None,
            json.dumps(new_values, ensure_ascii=False) if new_values else None,
            ip_address,
            user_agent,
            kvkk_category
        ))

        return cursor.lastrowid


def log_from_session(
    action: str,
    session_state,
    entity_type: str = None,
    entity_id: int = None,
    entity_name: str = None,
    details: dict = None,
    old_values: dict = None,
    new_values: dict = None
) -> int:
    """
    Session bilgilerinden otomatik KVKK uyumlu log olustur

    Args:
        action: Aksiyon tipi
        session_state: Streamlit session_state
        entity_type: Entity tipi
        entity_id: Entity ID
        entity_name: Entity adı
        details: Ek detaylar
        old_values: Önceki değerler
        new_values: Yeni değerler
    """
    user = session_state.get("user") if hasattr(session_state, "get") else None

    if user:
        return log_action(
            action=action,
            user_id=user.get("id"),
            user_email=user.get("email"),
            company_id=user.get("company_id"),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            details=details,
            old_values=old_values,
            new_values=new_values
        )
    else:
        return log_action(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            details=details,
            old_values=old_values,
            new_values=new_values
        )


# ============ SORGULAMA FONKSIYONLARI ============

def get_audit_logs(
    start_date: str = None,
    end_date: str = None,
    user_id: int = None,
    company_id: int = None,
    action: str = None,
    entity_type: str = None,
    entity_id: int = None,
    kvkk_category: str = None,
    limit: int = 100,
    offset: int = 0
) -> List[dict]:
    """
    Audit loglarini filtrele ve getir

    Args:
        start_date: Baslangic tarihi (ISO format)
        end_date: Bitis tarihi (ISO format)
        user_id: Kullanici filtresi
        company_id: Firma filtresi
        action: Aksiyon filtresi
        entity_type: Entity tipi filtresi
        entity_id: Entity ID filtresi
        kvkk_category: KVKK kategorisi filtresi
        limit: Maksimum kayit sayisi
        offset: Atlama sayisi

    Returns:
        Log listesi
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if company_id:
            conditions.append("company_id = ?")
            params.append(company_id)

        if action:
            conditions.append("action = ?")
            params.append(action)

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)

        if kvkk_category:
            conditions.append("kvkk_category = ?")
            params.append(kvkk_category)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT * FROM audit_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))

        logs = []
        for row in cursor.fetchall():
            log = dict(row)
            # JSON alanlarını parse et
            for field in ["details", "old_values", "new_values"]:
                if log.get(field):
                    try:
                        log[field] = json.loads(log[field])
                    except:
                        pass
            logs.append(log)

        return logs


def get_audit_log_count(
    start_date: str = None,
    end_date: str = None,
    user_id: int = None,
    company_id: int = None,
    action: str = None,
    entity_type: str = None
) -> int:
    """Filtreli log sayisini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)

        if company_id:
            conditions.append("company_id = ?")
            params.append(company_id)

        if action:
            conditions.append("action = ?")
            params.append(action)

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(f"""
            SELECT COUNT(*) as count FROM audit_logs
            WHERE {where_clause}
        """, params)

        return cursor.fetchone()["count"]


def get_user_activity(user_id: int, limit: int = 50) -> List[dict]:
    """Belirli bir kullanicinin aktivitelerini getir"""
    return get_audit_logs(user_id=user_id, limit=limit)


def get_entity_history(entity_type: str, entity_id: int, limit: int = 50) -> List[dict]:
    """Belirli bir entity uzerindeki islemleri getir"""
    return get_audit_logs(entity_type=entity_type, entity_id=entity_id, limit=limit)


def get_candidate_history(candidate_id: int, limit: int = 50) -> List[dict]:
    """Aday uzerindeki islemleri getir"""
    return get_entity_history(EntityType.CANDIDATE.value, candidate_id, limit)


def get_recent_activity(company_id: int = None, hours: int = 24, limit: int = 100) -> List[dict]:
    """Son X saatteki aktiviteleri getir"""
    start_date = (datetime.now() - timedelta(hours=hours)).isoformat()
    return get_audit_logs(start_date=start_date, company_id=company_id, limit=limit)


# ============ ISTATISTIKLER ============

def get_audit_stats(company_id: int = None, days: int = 7) -> dict:
    """Audit istatistiklerini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        company_filter = "AND company_id = ?" if company_id else ""
        params = [start_date]
        if company_id:
            params.append(company_id)

        # Aksiyon dagilimi
        cursor.execute(f"""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ? {company_filter}
            GROUP BY action
            ORDER BY count DESC
        """, params)
        action_stats = {row["action"]: row["count"] for row in cursor.fetchall()}

        # Gunluk aktivite
        cursor.execute(f"""
            SELECT date(timestamp) as tarih, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ? {company_filter}
            GROUP BY tarih
            ORDER BY tarih ASC
        """, params)
        daily_stats = [{"tarih": row["tarih"], "count": row["count"]} for row in cursor.fetchall()]

        # En aktif kullanicilar
        cursor.execute(f"""
            SELECT user_email, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ? AND user_email IS NOT NULL {company_filter}
            GROUP BY user_email
            ORDER BY count DESC
            LIMIT 10
        """, params)
        top_users = [{"email": row["user_email"], "count": row["count"]} for row in cursor.fetchall()]

        return {
            "action_stats": action_stats,
            "daily_stats": daily_stats,
            "top_users": top_users,
            "total_logs": sum(action_stats.values())
        }


def get_action_types() -> List[str]:
    """Tum aksiyon tiplerini getir"""
    return [action.value for action in AuditAction]


def get_entity_types() -> List[str]:
    """Tum entity tiplerini getir"""
    return [entity.value for entity in EntityType]


def get_kvkk_categories() -> List[str]:
    """Tüm KVKK kategorilerini getir"""
    return [cat.value for cat in KVKKCategory]


# ============ KVKK RAPORLARI ============

def get_kvkk_report(
    company_id: int = None,
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    KVKK Denetim Raporu (Madde 12 uyumlu)

    Returns:
        {
            'veri_isleme': [...],
            'veri_erisim': [...],
            'veri_silme': [...],
            'veri_aktarim': [...],
            'veri_guncelleme': [...],
            'kullanici_yonetimi': [...],
            'sistem_erisimi': [...],
            'guvenlik': [...],
            'summary': {category: count}
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        conditions = ["kvkk_category IS NOT NULL"]
        params = []

        if company_id:
            conditions.append("company_id = ?")
            params.append(company_id)

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions)

        # Kategori bazında logları getir
        report = {}
        summary = {}

        for category in KVKKCategory:
            cursor.execute(f"""
                SELECT * FROM audit_logs
                WHERE {where_clause} AND kvkk_category = ?
                ORDER BY timestamp DESC
                LIMIT 100
            """, (*params, category.value))

            logs = []
            for row in cursor.fetchall():
                log = dict(row)
                for field in ["details", "old_values", "new_values"]:
                    if log.get(field):
                        try:
                            log[field] = json.loads(log[field])
                        except:
                            pass
                logs.append(log)

            report[category.value] = logs

            # Özet için sayım
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM audit_logs
                WHERE {where_clause} AND kvkk_category = ?
            """, (*params, category.value))
            summary[category.value] = cursor.fetchone()["count"]

        report["summary"] = summary
        report["category_labels"] = KVKK_CATEGORY_LABELS

        return report


def get_kvkk_stats(company_id: int = None, days: int = 30) -> dict:
    """KVKK kategori istatistikleri"""
    with get_connection() as conn:
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        company_filter = "AND company_id = ?" if company_id else ""
        params = [start_date]
        if company_id:
            params.append(company_id)

        # Kategori dağılımı
        cursor.execute(f"""
            SELECT kvkk_category, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp >= ? AND kvkk_category IS NOT NULL {company_filter}
            GROUP BY kvkk_category
            ORDER BY count DESC
        """, params)
        category_stats = {row["kvkk_category"]: row["count"] for row in cursor.fetchall()}

        # Kişisel veri erişim sayısı
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM audit_logs
            WHERE timestamp >= ? AND kvkk_category = 'veri_erisim' {company_filter}
        """, params)
        veri_erisim = cursor.fetchone()["count"]

        # Kişisel veri silme sayısı
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM audit_logs
            WHERE timestamp >= ? AND kvkk_category = 'veri_silme' {company_filter}
        """, params)
        veri_silme = cursor.fetchone()["count"]

        # Kişisel veri aktarım sayısı
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM audit_logs
            WHERE timestamp >= ? AND kvkk_category = 'veri_aktarim' {company_filter}
        """, params)
        veri_aktarim = cursor.fetchone()["count"]

        # Güvenlik olayları
        cursor.execute(f"""
            SELECT COUNT(*) as count FROM audit_logs
            WHERE timestamp >= ? AND kvkk_category = 'guvenlik' {company_filter}
        """, params)
        guvenlik = cursor.fetchone()["count"]

        return {
            "category_stats": category_stats,
            "category_labels": KVKK_CATEGORY_LABELS,
            "veri_erisim": veri_erisim,
            "veri_silme": veri_silme,
            "veri_aktarim": veri_aktarim,
            "guvenlik_olaylari": guvenlik,
            "days": days
        }


def get_user_kvkk_activity(user_id: int, days: int = 30) -> List[dict]:
    """Kullanıcının KVKK kapsamındaki aktiviteleri"""
    start_date = (datetime.now() - timedelta(days=days)).isoformat()
    return get_audit_logs(
        start_date=start_date,
        user_id=user_id,
        limit=500
    )


def get_entity_kvkk_history(entity_type: str, entity_id: int) -> List[dict]:
    """Bir entity üzerindeki tüm KVKK işlemleri"""
    return get_audit_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        limit=500
    )


# ============ TEMIZLIK ============

def cleanup_old_audit_logs(days: int = 365):
    """Eski audit loglarini temizle (varsayilan 1 yil)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute(
            "DELETE FROM audit_logs WHERE timestamp < ?",
            (cutoff,)
        )
        return cursor.rowcount


def export_audit_logs_csv(
    start_date: str = None,
    end_date: str = None,
    company_id: int = None
) -> str:
    """Audit loglarini CSV formatinda export et"""
    import csv
    import io

    logs = get_audit_logs(
        start_date=start_date,
        end_date=end_date,
        company_id=company_id,
        limit=10000  # Max 10k kayit
    )

    output = io.StringIO()
    if logs:
        fieldnames = ["timestamp", "user_email", "action", "entity_type", "entity_id", "details"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for log in logs:
            log["details"] = json.dumps(log.get("details", {}), ensure_ascii=False) if log.get("details") else ""
            writer.writerow(log)

    return output.getvalue()


# Modul yuklendiginde tabloyu olustur
init_audit_table()
