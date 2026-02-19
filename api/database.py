"""
TalentFlow Veritabani Islemleri
SQLite ile CRUD operasyonlari
"""

import sqlite3
import os
import json
import re
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from contextlib import contextmanager

from config import CACHE_TTL

logger = logging.getLogger(__name__)

# ============ CACHE MEKANİZMASI ============

_cache = {}
# CACHE_TTL config.py'den import ediliyor


def cached_get(key: str, fetch_func, ttl: int = CACHE_TTL):
    """Basit TTL cache - sık okunan ve nadiren değişen veriler için
    
    Args:
        key: Cache anahtarı
        fetch_func: Veriyi getiren fonksiyon (parametresiz)
        ttl: Time-to-live (saniye, default: 300)
    
    Returns:
        Cache'den veya fetch_func'tan gelen veri
    """
    now = time.time()
    if key in _cache and (now - _cache[key]['time']) < ttl:
        return _cache[key]['data']
    data = fetch_func()
    _cache[key] = {'data': data, 'time': now}
    return data


def invalidate_cache(key_prefix: str = None):
    """Cache temizle
    
    Args:
        key_prefix: Belirli bir prefix ile başlayan cache'leri temizle (None ise tümünü temizle)
    """
    global _cache
    if key_prefix:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(key_prefix)}
    else:
        _cache = {}

try:
    import streamlit as st
except ImportError:
    # Streamlit yoksa (test ortamı gibi) st = None
    st = None

from config import DATABASE_PATH, DATA_DIR, EMAIL_ENCRYPTION_KEY
from models import Candidate, Position, Application, Match, EmailLog, Interview
from cryptography.fernet import Fernet


def ensure_data_dir():
    """Data dizininin var oldugundan emin ol"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri doğru şekilde küçük harfe çevir.
    Python'da 'İ'.lower() → 'i̇' (combining dot) sorunu var, bu fonksiyon düzeltir."""
    return text.replace('İ', 'i').replace('I', 'ı').lower()


def _parse_keywords(keywords: list) -> list:
    """Keyword listesindeki virgülle ayrılmış elemanları ayrı keyword'lere böl."""
    result = []
    for kw in keywords:
        if ',' in kw:
            result.extend([k.strip() for k in kw.split(',') if k.strip()])
        else:
            result.append(kw.strip())
    return [k for k in result if k]


def _keyword_match(kw: str, search_text: str) -> bool:
    """Keyword eşleştirme: kısa keyword'ler (<=3 kar) word boundary, uzunlar substring.
    Böylece 'ik' sadece 'ik ' veya ' ik' olarak eşleşir, 'teknik' içinde eşleşmez.
    Ama 'mühendis' substring olarak 'mühendislik' içinde eşleşir."""
    if len(kw) <= 3:
        pattern = r'(?<![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])' + re.escape(kw) + r'(?![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])'
        return bool(re.search(pattern, search_text))
    return kw in search_text


# ============ EMAIL SIFRE SIFRELEME ============

def get_fernet():
    """Fernet instance döndür"""
    return Fernet(EMAIL_ENCRYPTION_KEY.encode())


def encrypt_email_password(password: str) -> str:
    """Email şifresini şifrele"""
    if not password:
        return password
    f = get_fernet()
    return f.encrypt(password.encode()).decode()


def decrypt_email_password(encrypted: str) -> str:
    """Email şifresini çöz"""
    if not encrypted:
        return encrypted
    try:
        f = get_fernet()
        return f.decrypt(encrypted.encode()).decode()
    except Exception as e:
        # Eski düz metin şifre olabilir
        logger.debug(f"Şifre decrypt hatası (düz metin olabilir): {e}")
        return encrypted


@contextmanager
def get_connection():
    """Veritabani baglantisi context manager
    
    Performans iyileştirmeleri:
    - WAL mode: Concurrent read/write performansını artırır
    - Timeout: Database locked hatalarını önler
    """
    ensure_data_dir()
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL mode: Write-Ahead Logging - concurrent read/write performansı için
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_database():
    """Veritabani tablolarini olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Firmalar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                email TEXT,
                telefon TEXT,
                adres TEXT,
                website TEXT,
                logo_url TEXT,
                aktif INTEGER DEFAULT 1,
                max_kullanici INTEGER DEFAULT 5,
                max_aday INTEGER DEFAULT 1000,
                plan TEXT DEFAULT 'basic',
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Kullanicilar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                ad_soyad TEXT NOT NULL,
                rol TEXT DEFAULT 'user',
                aktif INTEGER DEFAULT 1,
                son_giris TIMESTAMP,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Adaylar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                ad_soyad TEXT NOT NULL,
                email TEXT NOT NULL,
                telefon TEXT,
                lokasyon TEXT,
                linkedin TEXT,
                egitim TEXT,
                universite TEXT,
                bolum TEXT,
                toplam_deneyim_yil REAL,
                mevcut_pozisyon TEXT,
                mevcut_sirket TEXT,
                deneyim_detay TEXT,
                teknik_beceriler TEXT,
                diller TEXT,
                sertifikalar TEXT,
                cv_raw_text TEXT,
                cv_dosya_adi TEXT,
                cv_dosya_yolu TEXT,
                havuz TEXT DEFAULT 'genel_havuz',
                durum TEXT DEFAULT 'yeni',
                notlar TEXT,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                guncelleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Pozisyonlar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                baslik TEXT NOT NULL,
                departman TEXT,
                lokasyon TEXT,
                aciklama TEXT,
                gerekli_deneyim_yil REAL,
                gerekli_egitim TEXT,
                gerekli_beceriler TEXT,
                tercih_edilen_beceriler TEXT,
                aktif INTEGER DEFAULT 1,
                acilis_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                kapanis_tarihi TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)

        # Pozisyon kriterleri tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                kriter_tipi TEXT NOT NULL,
                deger TEXT NOT NULL,
                min_deger TEXT,
                max_deger TEXT,
                seviye TEXT,
                zorunlu INTEGER DEFAULT 0,
                agirlik REAL DEFAULT 1.0,
                FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
            )
        """)

        # Pozisyon havuzlari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                uyum_puani REAL DEFAULT 0,
                durum TEXT DEFAULT 'beklemede',
                ekleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notlar TEXT,
                FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
                UNIQUE(position_id, candidate_id)
            )
        """)

        # Basvurular tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER,
                kaynak TEXT DEFAULT 'email',
                email_id TEXT,
                basvuru_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)

        # Eslesmeler tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                uyum_puani REAL DEFAULT 0,
                detayli_analiz TEXT,
                deneyim_puani REAL,
                egitim_puani REAL,
                beceri_puani REAL,
                hesaplama_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)

        # Email loglari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT UNIQUE NOT NULL,
                gonderen TEXT,
                konu TEXT,
                tarih TIMESTAMP,
                ek_sayisi INTEGER DEFAULT 0,
                islendi INTEGER DEFAULT 0,
                hata TEXT,
                islem_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Mulakatlar tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER,
                tarih TIMESTAMP NOT NULL,
                sure_dakika INTEGER DEFAULT 60,
                tur TEXT DEFAULT 'teknik',
                lokasyon TEXT DEFAULT 'online',
                mulakatci TEXT,
                durum TEXT DEFAULT 'planlanmis',
                notlar TEXT,
                degerlendirme TEXT,
                puan INTEGER,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
        """)

        # AI Analiz tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                analysis_data TEXT,
                skill_score REAL,
                experience_score REAL,
                education_score REAL,
                overall_score REAL,
                career_level TEXT,
                strengths TEXT,
                improvements TEXT,
                processing_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            )
        """)

        # Aday birlestirme loglari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_merge_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_candidate_id INTEGER NOT NULL,
                merged_candidate_id INTEGER,
                eslesme_tipi TEXT NOT NULL,
                eslesme_degeri TEXT,
                islem_tipi TEXT NOT NULL,
                detay TEXT,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (master_candidate_id) REFERENCES candidates(id)
            )
        """)

        # Email hesaplari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL DEFAULT 1 REFERENCES companies(id),
                ad TEXT NOT NULL,
                saglayici TEXT NOT NULL,
                email TEXT NOT NULL,
                sifre TEXT NOT NULL,
                imap_server TEXT NOT NULL,
                imap_port INTEGER DEFAULT 993,
                smtp_server TEXT NOT NULL,
                smtp_port INTEGER DEFAULT 587,
                sender_name TEXT,
                aktif INTEGER DEFAULT 1,
                varsayilan_okuma INTEGER DEFAULT 0,
                varsayilan_gonderim INTEGER DEFAULT 0,
                son_kontrol TIMESTAMP,
                toplam_cv INTEGER DEFAULT 0,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(company_id, email)
            )
        """)

        # IK degerlendirme tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                position_id INTEGER REFERENCES positions(id),
                evaluator_id INTEGER REFERENCES users(id),
                ik_puani INTEGER CHECK(ik_puani >= 1 AND ik_puani <= 5),
                ik_notlari TEXT,
                durum TEXT DEFAULT 'beklemede',
                onceki_durum TEXT,
                degerlendirme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                guncelleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(candidate_id, position_id)
            )
        """)

        # AI değerlendirmeleri tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                position_id INTEGER NOT NULL REFERENCES department_pools(id) ON DELETE CASCADE,
                evaluation_text TEXT NOT NULL,
                v2_score INTEGER DEFAULT 0,
                eval_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(candidate_id, position_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_eval_candidate ON ai_evaluations(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_eval_position ON ai_evaluations(position_id)")

        # Sifre sifirlama tokenlari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Pozisyon Sablonlari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT NOT NULL,
                ikon TEXT DEFAULT '📋',
                renk TEXT DEFAULT 'blue',
                departman TEXT,
                lokasyon TEXT,
                aciklama TEXT,
                gerekli_deneyim_yil REAL,
                gerekli_egitim TEXT,
                kriterler TEXT,
                aktif INTEGER DEFAULT 1,
                siralama INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Meslek Unvanlari tablosu (Akilli Oneri Sistemi)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unvan TEXT NOT NULL,
                kategori TEXT,
                sektor TEXT DEFAULT 'Genel',
                departman TEXT,
                varsayilan_egitim TEXT,
                varsayilan_deneyim REAL,
                kullanim_sayisi INTEGER DEFAULT 0,
                son_kullanan_firma_id INTEGER,
                varsayilan INTEGER DEFAULT 0,
                aktif INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Departman Havuzları tablosu (hiyerarşik: departman -> pozisyon)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                parent_id INTEGER,
                pool_type TEXT DEFAULT 'department',
                name TEXT NOT NULL,
                icon TEXT DEFAULT '📁',
                keywords TEXT,
                description TEXT,
                is_system INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (parent_id) REFERENCES department_pools(id) ON DELETE CASCADE,
                UNIQUE(company_id, name, parent_id)
            )
        """)

        # Aday-Havuz Atamaları tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_pool_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                department_pool_id INTEGER,
                position_id INTEGER,
                assignment_type TEXT DEFAULT 'auto',
                match_score INTEGER DEFAULT 0,
                match_reason TEXT,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
                FOREIGN KEY (department_pool_id) REFERENCES department_pools(id) ON DELETE CASCADE,
                FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
            )
        """)

        # Aday-Pozisyon İlişkileri tablosu (adayların hangi department_pools pozisyonlarında olduğu)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidate_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                match_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'aktif',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
                FOREIGN KEY (position_id) REFERENCES department_pools(id) ON DELETE CASCADE,
                UNIQUE(candidate_id, position_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_candidate ON candidate_positions(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_position ON candidate_positions(position_id)")

        # Indeksler
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_email ON password_reset_tokens(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_telefon ON candidates(telefon)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_havuz ON candidates(havuz)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_tarih ON interviews(tarih)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_candidate ON interviews(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_accounts_aktif ON email_accounts(aktif)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_candidate ON ai_analyses(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_titles_unvan ON job_titles(unvan)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_titles_kategori ON job_titles(kategori)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_titles_sektor ON job_titles(sektor)")

        # Migration: company_id kolonunu mevcut tablolara ekle (varsa atla)
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN company_id INTEGER REFERENCES companies(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN company_id INTEGER REFERENCES companies(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_company ON candidates(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_company ON positions(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_criteria_position ON position_criteria(position_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_pools_position ON position_pools(position_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_position_pools_candidate ON position_pools(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_merge_logs_master ON candidate_merge_logs(master_candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_department_pools_company ON department_pools(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_assignments_candidate ON candidate_pool_assignments(candidate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_assignments_pool ON candidate_pool_assignments(department_pool_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_assignments_position ON candidate_pool_assignments(position_id)")

        # KVKK Migration: candidates tablosuna yeni alanlar
        kvkk_migrations = [
            ("candidates", "expires_at", "TEXT"),  # Veri saklama suresi sonu
            ("candidates", "is_anonymized", "INTEGER DEFAULT 0"),  # Anonimlestirildi mi
            ("candidates", "anonymized_at", "TEXT"),  # Anonimlestirilme tarihi
            ("applications", "kvkk_consent", "INTEGER DEFAULT 0"),  # KVKK onay
            ("applications", "consent_date", "TEXT"),  # Onay tarihi
        ]

        for table, column, col_type in kvkk_migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            except sqlite3.OperationalError:
                pass  # Kolon zaten var

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_expires ON candidates(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_anonymized ON candidates(is_anonymized)")

        # AI Analyses Migration: position_id kolonu ekle
        try:
            cursor.execute("ALTER TABLE ai_analyses ADD COLUMN position_id INTEGER REFERENCES positions(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_position ON ai_analyses(position_id)")

        # Department Pools Migration: hiyerarşik yapı için yeni kolonlar
        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN parent_id INTEGER REFERENCES department_pools(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN pool_type TEXT DEFAULT 'department'")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_department_pools_parent ON department_pools(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_department_pools_type ON department_pools(pool_type)")
        
        # Department pools migration: deneyim, eğitim, lokasyon kolonları ekle
        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN gerekli_deneyim_yil REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var
        
        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN gerekli_egitim TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var
        
        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN lokasyon TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Department pools migration: aranan_nitelikler ve is_tanimi kolonları ekle
        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN aranan_nitelikler TEXT")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        try:
            cursor.execute("ALTER TABLE department_pools ADD COLUMN is_tanimi TEXT")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Keyword Dictionary tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_dictionary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'genel',
                usage_count INTEGER DEFAULT 0,
                source TEXT DEFAULT 'seed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keyword_dict_keyword ON keyword_dictionary(keyword)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keyword_dict_category ON keyword_dictionary(category)")

        # Keyword seed data - tablo boşsa doldur
        cursor.execute("SELECT COUNT(*) FROM keyword_dictionary")
        if cursor.fetchone()[0] == 0:
            seed_keywords = [
                # Yazılım / IT
                ('python', 'yazilim'), ('java', 'yazilim'), ('javascript', 'yazilim'), ('react', 'yazilim'),
                ('angular', 'yazilim'), ('vue', 'yazilim'), ('node.js', 'yazilim'), ('typescript', 'yazilim'),
                ('sql', 'yazilim'), ('postgresql', 'yazilim'), ('mysql', 'yazilim'), ('mongodb', 'yazilim'),
                ('aws', 'yazilim'), ('azure', 'yazilim'), ('docker', 'yazilim'), ('kubernetes', 'yazilim'),
                ('git', 'yazilim'), ('api', 'yazilim'), ('rest', 'yazilim'), ('microservices', 'yazilim'),
                ('agile', 'yazilim'), ('scrum', 'yazilim'), ('devops', 'yazilim'), ('ci/cd', 'yazilim'),
                ('linux', 'yazilim'), ('c#', 'yazilim'), ('c++', 'yazilim'), ('php', 'yazilim'),
                ('ruby', 'yazilim'), ('golang', 'yazilim'), ('swift', 'yazilim'), ('kotlin', 'yazilim'),
                ('flutter', 'yazilim'), ('react native', 'yazilim'), ('html', 'yazilim'), ('css', 'yazilim'),
                
                # İnşaat / Mühendislik
                ('autocad', 'insaat'), ('sap2000', 'insaat'), ('etabs', 'insaat'), ('tekla', 'insaat'),
                ('revit', 'insaat'), ('primavera', 'insaat'), ('ms project', 'insaat'), ('navisworks', 'insaat'),
                ('bim', 'insaat'), ('archicad', 'insaat'), ('sketchup', 'insaat'), ('solidworks', 'insaat'),
                ('catia', 'insaat'), ('inventor', 'insaat'), ('şantiye', 'insaat'), ('metraj', 'insaat'),
                ('keşif', 'insaat'), ('hakediş', 'insaat'), ('ihale', 'insaat'), ('yapı denetim', 'insaat'),
                ('statik', 'insaat'), ('betonarme', 'insaat'), ('çelik yapı', 'insaat'), ('proje yönetimi', 'insaat'),
                
                # Finans / Muhasebe
                ('sap', 'finans'), ('erp', 'finans'), ('muhasebe', 'finans'), ('bütçe', 'finans'),
                ('finans', 'finans'), ('ifrs', 'finans'), ('ufrs', 'finans'), ('vergi', 'finans'),
                ('kdv', 'finans'), ('e-fatura', 'finans'), ('logo', 'finans'), ('mikro', 'finans'),
                ('netsis', 'finans'), ('eta', 'finans'), ('luca', 'finans'), ('bordro', 'finans'),
                ('maliyet', 'finans'), ('nakit akış', 'finans'), ('denetim', 'finans'), ('konsolidasyon', 'finans'),
                
                # Satın Alma / Lojistik
                ('satın alma', 'satin_alma'), ('tedarik', 'satin_alma'), ('tedarikçi', 'satin_alma'),
                ('stok', 'satin_alma'), ('envanter', 'satin_alma'), ('lojistik', 'satin_alma'),
                ('depo', 'satin_alma'), ('sevkiyat', 'satin_alma'), ('ithalat', 'satin_alma'),
                ('ihracat', 'satin_alma'), ('gümrük', 'satin_alma'), ('sözleşme', 'satin_alma'),
                ('teklif', 'satin_alma'), ('sipariş', 'satin_alma'), ('fiyat analizi', 'satin_alma'),
                
                # Makine / Üretim
                ('makine parkı', 'makine'), ('iş makinesi', 'makine'), ('ekipman', 'makine'),
                ('bakım', 'makine'), ('onarım', 'makine'), ('arıza', 'makine'), ('önleyici bakım', 'makine'),
                ('periyodik bakım', 'makine'), ('yedek parça', 'makine'), ('üretim', 'makine'),
                ('kalite kontrol', 'makine'), ('iso', 'makine'), ('lean', 'makine'), ('kaizen', 'makine'),
                ('tpm', 'makine'), ('cnc', 'makine'), ('otomasyon', 'makine'), ('plc', 'makine'),
                
                # İnsan Kaynakları
                ('işe alım', 'ik'), ('mülakat', 'ik'), ('özlük', 'ik'), ('sgk', 'ik'),
                ('pdks', 'ik'), ('performans', 'ik'), ('eğitim', 'ik'), ('organizasyon', 'ik'),
                ('ücret', 'ik'), ('yan haklar', 'ik'), ('yetenek yönetimi', 'ik'), ('kariyer', 'ik'),
                
                # Satış / Pazarlama
                ('crm', 'satis'), ('salesforce', 'satis'), ('hubspot', 'satis'), ('seo', 'satis'),
                ('sem', 'satis'), ('dijital pazarlama', 'satis'), ('sosyal medya', 'satis'),
                ('google ads', 'satis'), ('meta ads', 'satis'), ('e-ticaret', 'satis'),
                ('b2b', 'satis'), ('b2c', 'satis'), ('müşteri ilişkileri', 'satis'),
                
                # Genel
                ('ms office', 'genel'), ('excel', 'genel'), ('word', 'genel'), ('powerpoint', 'genel'),
                ('outlook', 'genel'), ('teams', 'genel'), ('ingilizce', 'genel'), ('almanca', 'genel'),
                ('iletişim', 'genel'), ('problem çözme', 'genel'), ('analitik düşünme', 'genel'),
                ('takım çalışması', 'genel'), ('liderlik', 'genel'), ('sunum', 'genel'), ('raporlama', 'genel')
            ]
            
            cursor.executemany(
                "INSERT OR IGNORE INTO keyword_dictionary (keyword, category, source) VALUES (?, ?, 'seed')",
                seed_keywords
            )

        # Users Migration: notification_preferences kolonu ekle
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN notification_preferences TEXT")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Users Migration: created_by kolonu ekle (kim tarafından oluşturuldu)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Users Migration: Eski 'admin' rollerini yeni 3 seviyeli sisteme çevir
        # company_id olmayan admin -> super_admin
        cursor.execute("""
            UPDATE users SET rol = 'super_admin'
            WHERE rol = 'admin' AND company_id IS NULL
        """)
        # company_id olan admin -> company_admin
        cursor.execute("""
            UPDATE users SET rol = 'company_admin'
            WHERE rol = 'admin' AND company_id IS NOT NULL
        """)

        # Companies Migration: Super Admin paneli için yeni kolonlar
        company_columns = [
            ("durum", "TEXT DEFAULT 'aktif'"),  # aktif, askida, pasif
            ("yetkili_adi", "TEXT"),
            ("yetkili_email", "TEXT"),
            ("yetkili_telefon", "TEXT"),
            ("sozlesme_baslangic", "DATE"),
            ("sozlesme_bitis", "DATE"),
            ("notlar", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col_name, col_type in company_columns:
            try:
                cursor.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Kolon zaten var

        # Users Migration: must_change_password kolonu ekle (şifre sıfırlama için)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Email Accounts Migration: company_id kolonu ekle (multi-tenant icin)
        try:
            cursor.execute("ALTER TABLE email_accounts ADD COLUMN company_id INTEGER DEFAULT 1 REFERENCES companies(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Mevcut email hesaplarini varsayilan firmaya ata
        cursor.execute("UPDATE email_accounts SET company_id = 1 WHERE company_id IS NULL")

        # Candidates Migration: linkedin kolonu ekle
        try:
            cursor.execute("ALTER TABLE candidates ADD COLUMN linkedin TEXT")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Email sablonlari tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                sablon_kodu TEXT NOT NULL,
                sablon_adi TEXT NOT NULL,
                konu TEXT NOT NULL,
                icerik TEXT NOT NULL,
                degiskenler TEXT,
                aktif INTEGER DEFAULT 1,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                guncelleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                UNIQUE(company_id, sablon_kodu)
            )
        """)

        # Departman Şablonları tablosu (firma bazlı standart departmanlar)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '📁',
                description TEXT,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                UNIQUE(company_id, name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_templates_company ON department_templates(company_id)")

        # ========== PLAN VE LİMİT SİSTEMİ ==========

        # Plans tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                max_users INTEGER DEFAULT 2,
                max_cvs INTEGER DEFAULT 100,
                max_positions INTEGER DEFAULT 5,
                max_departments INTEGER DEFAULT 3,
                ai_analysis_enabled INTEGER DEFAULT 0,
                email_integration_enabled INTEGER DEFAULT 0,
                price_monthly INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Varsayılan planları ekle
        default_plans = [
            ('trial', 'Deneme', 2, 50, 3, 2, 0, 0, 0),
            ('starter', 'Başlangıç', 3, 200, 10, 5, 0, 1, 500),
            ('professional', 'Profesyonel', 10, 1000, 50, 15, 1, 1, 1500),
            ('enterprise', 'Kurumsal', -1, -1, -1, -1, 1, 1, 4000),  # -1 = sınırsız
        ]
        for plan in default_plans:
            cursor.execute("""
                INSERT OR IGNORE INTO plans
                (name, display_name, max_users, max_cvs, max_positions, max_departments,
                 ai_analysis_enabled, email_integration_enabled, price_monthly)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, plan)

        # Companies Migration: plan_id kolonu ekle
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN plan_id INTEGER DEFAULT 1 REFERENCES plans(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Companies Migration: trial_ends_at kolonu ekle
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN trial_ends_at DATE")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

        # Mevcut firmalara varsayılan plan ata (plan_id olmayanlara)
        cursor.execute("UPDATE companies SET plan_id = 1 WHERE plan_id IS NULL")

        # ========== AKILLI HAVUZ: EŞDEĞER POZİSYON ÖNERİLERİ ==========
        # approved_title_mappings tablosu - İK'nın onayladığı eşdeğer pozisyon başlıkları
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_title_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                is_approved INTEGER DEFAULT 0,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (position_id) REFERENCES department_pools(id) ON DELETE CASCADE,
                UNIQUE(position_id, title)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved_titles_position ON approved_title_mappings(position_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_approved_titles_approved ON approved_title_mappings(is_approved)")

        # Varsayilan email sablonlarini ekle (company_id NULL = global sablonlar)
        _init_default_email_templates(cursor)

    # Email şifrelerini migrate et (düz metin -> şifreli)
    migrate_email_passwords()


def _init_default_email_templates(cursor):
    """Varsayilan email sablonlarini olustur"""
    default_templates = [
        {
            "sablon_kodu": "basvuru_alindi",
            "sablon_adi": "Başvuru Alındı",
            "konu": "{sirket_adi} - Başvurunuz Alındı",
            "icerik": """Sayın {aday_adi},

{pozisyon} pozisyonu için yapmış olduğunuz başvuruyu aldık.

Başvurunuz değerlendirme sürecine alınmıştır. Değerlendirme sonucunda sizinle iletişime geçeceğiz.

Başvurunuz için teşekkür ederiz.

Saygılarımızla,
{sirket_adi} İnsan Kaynakları Ekibi
{sirket_telefon}
{sirket_website}""",
            "degiskenler": "aday_adi,pozisyon,sirket_adi,sirket_telefon,sirket_website"
        },
        {
            "sablon_kodu": "mulakat_daveti",
            "sablon_adi": "Mülakat Daveti",
            "konu": "{sirket_adi} - Mülakat Daveti",
            "icerik": """Sayın {aday_adi},

{sirket_adi} olarak başvurunuzu değerlendirdik ve sizinle bir mülakat gerçekleştirmek istiyoruz.

MÜLAKAT DETAYLARI
-----------------
Tarih: {mulakat_tarihi}
Saat: {mulakat_saati}
Süre: {mulakat_suresi} dakika
Tür: {mulakat_turu}
Lokasyon: {mulakat_lokasyon}

POZISYON
--------
{pozisyon}

NOTLAR
------
{notlar}

Lütfen bu mülakat davetini onaylamak veya değişiklik talep etmek için bizimle iletişime geçin.

Saygılarımızla,
{sirket_adi} İK Ekibi
{sirket_telefon}""",
            "degiskenler": "aday_adi,sirket_adi,mulakat_tarihi,mulakat_saati,mulakat_suresi,mulakat_turu,mulakat_lokasyon,pozisyon,notlar,sirket_telefon"
        },
        {
            "sablon_kodu": "red_bildirimi",
            "sablon_adi": "Red Bildirimi",
            "konu": "{sirket_adi} - Başvuru Sonucu",
            "icerik": """Sayın {aday_adi},

{pozisyon} pozisyonu için yapmış olduğunuz başvuru değerlendirilmiştir.

Yaptığımız değerlendirmeler sonucunda, maalesef bu pozisyon için başka bir aday ile devam etme kararı aldık.

Başvurunuz için gösterdiğiniz ilgiye teşekkür eder, kariyerinizde başarılar dileriz.

Gelecekte açılacak pozisyonlar için başvurularınızı bekliyoruz.

Saygılarımızla,
{sirket_adi} İnsan Kaynakları Ekibi""",
            "degiskenler": "aday_adi,pozisyon,sirket_adi"
        },
        {
            "sablon_kodu": "teklif",
            "sablon_adi": "İş Teklifi",
            "konu": "{sirket_adi} - İş Teklifi",
            "icerik": """Sayın {aday_adi},

Mülakat sürecimizi başarıyla tamamladığınızı memnuniyetle bildirmek isteriz.

{sirket_adi} olarak size {pozisyon} pozisyonu için iş teklifi sunmaktan mutluluk duyuyoruz.

TEKLİF DETAYLARI
----------------
Pozisyon: {pozisyon}
Departman: {departman}
Başlangıç Tarihi: {baslangic_tarihi}
Çalışma Şekli: {calisma_sekli}

{ek_detaylar}

Bu teklifi {son_cevap_tarihi} tarihine kadar değerlendirmenizi rica ederiz.

Herhangi bir sorunuz varsa lütfen bizimle iletişime geçmekten çekinmeyin.

Ekibimize katılmanızı dört gözle bekliyoruz!

Saygılarımızla,
{sirket_adi} İnsan Kaynakları Ekibi
{sirket_telefon}""",
            "degiskenler": "aday_adi,pozisyon,departman,baslangic_tarihi,calisma_sekli,ek_detaylar,son_cevap_tarihi,sirket_adi,sirket_telefon"
        },
        {
            "sablon_kodu": "mulakat_hatirlatma",
            "sablon_adi": "Mülakat Hatırlatma",
            "konu": "{sirket_adi} - Mülakat Hatırlatması",
            "icerik": """Sayın {aday_adi},

Bu email, yarın gerçekleşecek mülakatınız için bir hatırlatmadır.

MÜLAKAT DETAYLARI
-----------------
Tarih: {mulakat_tarihi}
Saat: {mulakat_saati}
Süre: {mulakat_suresi} dakika
Lokasyon: {mulakat_lokasyon}

Herhangi bir sorunuz varsa lütfen bizimle iletişime geçin.

Başarılar dileriz!

{sirket_adi} İK Ekibi""",
            "degiskenler": "aday_adi,mulakat_tarihi,mulakat_saati,mulakat_suresi,mulakat_lokasyon,sirket_adi"
        },
        {
            "sablon_kodu": "mulakat_iptal",
            "sablon_adi": "Mülakat İptali",
            "konu": "{sirket_adi} - Mülakat İptali",
            "icerik": """Sayın {aday_adi},

Maalesef {mulakat_tarihi} tarihinde planlanan mülakatınızın iptal edildiğini bildirmek isteriz.

{iptal_nedeni}

En kısa sürede sizinle yeni bir mülakat planlamak için iletişime geçeceğiz.

Anlayışınız için teşekkür ederiz.

Saygılarımızla,
{sirket_adi} İK Ekibi""",
            "degiskenler": "aday_adi,mulakat_tarihi,iptal_nedeni,sirket_adi"
        }
    ]

    for template in default_templates:
        # Global sablon olarak ekle (company_id = NULL)
        cursor.execute("""
            INSERT OR IGNORE INTO email_templates
            (company_id, sablon_kodu, sablon_adi, konu, icerik, degiskenler)
            VALUES (NULL, ?, ?, ?, ?, ?)
        """, (
            template["sablon_kodu"],
            template["sablon_adi"],
            template["konu"],
            template["icerik"],
            template["degiskenler"]
        ))


# ============ API KULLANIM LOGLAMA ============

def _init_api_usage_table():
    """API kullanim tablosunu olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                user_id INTEGER,
                islem_tipi TEXT NOT NULL,
                model TEXT DEFAULT 'claude-3-sonnet',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                toplam_tokens INTEGER DEFAULT 0,
                tahmini_maliyet REAL DEFAULT 0,
                basarili INTEGER DEFAULT 1,
                hata_mesaji TEXT,
                islem_suresi_ms INTEGER,
                detay TEXT,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_tarih ON api_usage_logs(tarih)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_company ON api_usage_logs(company_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_islem ON api_usage_logs(islem_tipi)")


# API fiyatlandirma (USD per 1M token) - Claude 3 Sonnet
API_PRICING = {
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
}

# Varsayilan aylik limit (USD)
DEFAULT_MONTHLY_LIMIT = 100.0


def log_api_usage(
    islem_tipi: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str = "claude-3-sonnet",
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
    basarili: bool = True,
    hata_mesaji: Optional[str] = None,
    islem_suresi_ms: Optional[int] = None,
    detay: Optional[str] = None
) -> int:
    """
    API kullanimini logla

    Args:
        islem_tipi: cv_parse, ai_analiz, eslestirme, ranking vb.
        input_tokens: Girdi token sayisi
        output_tokens: Cikti token sayisi
        model: Kullanilan model
        company_id: Firma ID
        user_id: Kullanici ID
        basarili: Islem basarili mi
        hata_mesaji: Hata varsa mesaji
        islem_suresi_ms: Islem suresi (ms)
        detay: Ek detaylar (JSON string)

    Returns:
        Eklenen log ID'si
    """
    toplam_tokens = input_tokens + output_tokens

    # Maliyet hesapla
    pricing = API_PRICING.get(model, API_PRICING["claude-3-sonnet"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    tahmini_maliyet = input_cost + output_cost

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO api_usage_logs
            (company_id, user_id, islem_tipi, model, input_tokens, output_tokens,
             toplam_tokens, tahmini_maliyet, basarili, hata_mesaji, islem_suresi_ms, detay)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id, user_id, islem_tipi, model, input_tokens, output_tokens,
            toplam_tokens, tahmini_maliyet, 1 if basarili else 0, hata_mesaji,
            islem_suresi_ms, detay
        ))
        return cursor.lastrowid


def get_api_usage_stats(
    company_id: Optional[int] = None,
    days: int = 30
) -> dict:
    """
    API kullanim istatistiklerini getir

    Returns:
        {
            "toplam_cagri": int,
            "toplam_token": int,
            "toplam_maliyet": float,
            "gunluk": [{tarih, cagri, token, maliyet}],
            "islem_bazli": {islem_tipi: {cagri, token, maliyet}},
            "basari_orani": float
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Tarih filtresi
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Temel istatistikler
        base_query = """
            SELECT
                COUNT(*) as toplam_cagri,
                COALESCE(SUM(toplam_tokens), 0) as toplam_token,
                COALESCE(SUM(tahmini_maliyet), 0) as toplam_maliyet,
                COALESCE(SUM(CASE WHEN basarili = 1 THEN 1 ELSE 0 END), 0) as basarili_cagri
            FROM api_usage_logs
            WHERE tarih >= ?
        """
        params = [start_date]

        if company_id:
            base_query += " AND company_id = ?"
            params.append(company_id)

        cursor.execute(base_query, params)
        row = cursor.fetchone()

        toplam_cagri = row["toplam_cagri"] or 0
        basari_orani = (row["basarili_cagri"] / toplam_cagri * 100) if toplam_cagri > 0 else 100

        stats = {
            "toplam_cagri": toplam_cagri,
            "toplam_token": row["toplam_token"] or 0,
            "toplam_maliyet": round(row["toplam_maliyet"] or 0, 4),
            "basari_orani": round(basari_orani, 1)
        }

        # Gunluk istatistikler
        daily_query = """
            SELECT
                DATE(tarih) as gun,
                COUNT(*) as cagri,
                COALESCE(SUM(toplam_tokens), 0) as token,
                COALESCE(SUM(tahmini_maliyet), 0) as maliyet
            FROM api_usage_logs
            WHERE tarih >= ?
        """
        daily_params = [start_date]

        if company_id:
            daily_query += " AND company_id = ?"
            daily_params.append(company_id)

        daily_query += " GROUP BY DATE(tarih) ORDER BY gun DESC"
        cursor.execute(daily_query, daily_params)

        stats["gunluk"] = [
            {
                "tarih": row["gun"],
                "cagri": row["cagri"],
                "token": row["token"],
                "maliyet": round(row["maliyet"], 4)
            }
            for row in cursor.fetchall()
        ]

        # Islem bazli istatistikler
        islem_query = """
            SELECT
                islem_tipi,
                COUNT(*) as cagri,
                COALESCE(SUM(toplam_tokens), 0) as token,
                COALESCE(SUM(tahmini_maliyet), 0) as maliyet
            FROM api_usage_logs
            WHERE tarih >= ?
        """
        islem_params = [start_date]

        if company_id:
            islem_query += " AND company_id = ?"
            islem_params.append(company_id)

        islem_query += " GROUP BY islem_tipi ORDER BY maliyet DESC"
        cursor.execute(islem_query, islem_params)

        stats["islem_bazli"] = {
            row["islem_tipi"]: {
                "cagri": row["cagri"],
                "token": row["token"],
                "maliyet": round(row["maliyet"], 4)
            }
            for row in cursor.fetchall()
        }

        return stats


def get_monthly_api_usage(company_id: Optional[int] = None) -> dict:
    """
    Aylik API kullanim ozeti

    Returns:
        {
            "ay": str,
            "toplam_cagri": int,
            "toplam_token": int,
            "toplam_maliyet": float,
            "limit": float,
            "kalan": float,
            "kullanim_yuzdesi": float
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Bu ayin baslangici
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = """
            SELECT
                COUNT(*) as toplam_cagri,
                COALESCE(SUM(toplam_tokens), 0) as toplam_token,
                COALESCE(SUM(tahmini_maliyet), 0) as toplam_maliyet
            FROM api_usage_logs
            WHERE tarih >= ?
        """
        params = [month_start.strftime("%Y-%m-%d")]

        if company_id:
            query += " AND company_id = ?"
            params.append(company_id)

        cursor.execute(query, params)
        row = cursor.fetchone()

        toplam_maliyet = row["toplam_maliyet"] or 0
        limit = DEFAULT_MONTHLY_LIMIT
        kalan = max(0, limit - toplam_maliyet)
        kullanim_yuzdesi = (toplam_maliyet / limit * 100) if limit > 0 else 0

        return {
            "ay": now.strftime("%Y-%m"),
            "toplam_cagri": row["toplam_cagri"] or 0,
            "toplam_token": row["toplam_token"] or 0,
            "toplam_maliyet": round(toplam_maliyet, 4),
            "limit": limit,
            "kalan": round(kalan, 4),
            "kullanim_yuzdesi": round(kullanim_yuzdesi, 1)
        }


def get_recent_api_calls(
    company_id: Optional[int] = None,
    limit: int = 50
) -> list[dict]:
    """Son API cagrilarini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                a.id, a.islem_tipi, a.model, a.input_tokens, a.output_tokens,
                a.toplam_tokens, a.tahmini_maliyet, a.basarili, a.hata_mesaji,
                a.islem_suresi_ms, a.tarih,
                u.email as kullanici_email
            FROM api_usage_logs a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE 1=1
        """
        params = []

        if company_id:
            query += " AND a.company_id = ?"
            params.append(company_id)

        query += " ORDER BY a.tarih DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# Tabloyu olustur
_init_api_usage_table()


# ============ EMAIL TOPLAMA LOGLARI ============

def _init_email_collection_table():
    """Email toplama log tablosunu olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_collection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                user_id INTEGER,
                account_id INTEGER,
                account_email TEXT,
                klasor TEXT DEFAULT 'INBOX',
                taranan_email INTEGER DEFAULT 0,
                bulunan_cv INTEGER DEFAULT 0,
                basarili_cv INTEGER DEFAULT 0,
                mevcut_aday INTEGER DEFAULT 0,
                hatali_cv INTEGER DEFAULT 0,
                durum TEXT DEFAULT 'basarili',
                hata_detaylari TEXT,
                baslangic_zamani TIMESTAMP,
                bitis_zamani TIMESTAMP,
                sure_saniye INTEGER,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (account_id) REFERENCES email_accounts(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_collection_tarih ON email_collection_logs(tarih)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_collection_account ON email_collection_logs(account_id)")

        # Firma ayarları tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS company_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                guncelleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                UNIQUE(company_id, setting_key)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_company_settings_company ON company_settings(company_id)")

        # Migration: interviews tablosuna kolonlar ekle (tablo varsa)
        try:
            cursor.execute("ALTER TABLE interviews ADD COLUMN hatirlatma_gonderildi INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var veya tablo yok

        try:
            cursor.execute("ALTER TABLE interviews ADD COLUMN saat TEXT DEFAULT '09:00'")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var veya tablo yok

        try:
            cursor.execute("ALTER TABLE interviews ADD COLUMN company_id INTEGER REFERENCES companies(id)")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var veya tablo yok

        # Migration: interviews tablosuna durum kolonu ekle
        try:
            cursor.execute("ALTER TABLE interviews ADD COLUMN durum TEXT DEFAULT 'planlanmis'")
        except sqlite3.OperationalError:
            pass  # Kolon zaten var veya tablo yok

        # Index'leri sadece interviews tablosu varsa olustur
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_hatirlatma ON interviews(hatirlatma_gonderildi)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interviews_company ON interviews(company_id)")
        except sqlite3.OperationalError:
            pass  # Tablo henuz olusturulmamis, index daha sonra olusturulacak

        # ========== PERFORMANS İYİLEŞTİRMELERİ: Eksik Index'ler ==========
        
        # matches tablosu composite index (candidate_id, position_id sorguları için)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_candidate_position ON matches(candidate_id, position_id)")
        
        # candidate_positions tablosu skor sıralaması için (position_id ve match_score DESC)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_score ON candidate_positions(position_id, match_score DESC)")
        
        # candidates tablosu email ile arama için (company_id + email)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(company_id, email)")
        
        # candidates tablosu ad_soyad ile arama için (company_id + ad_soyad)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_adsoyad ON candidates(company_id, ad_soyad)")
        
        # department_pools pool_type filtresi için (company_id + pool_type)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_department_pools_type_company ON department_pools(company_id, pool_type)")
        
        # audit_logs tarih sıralaması için (company_id + timestamp DESC)
        # Not: audit_logs tablosunda timestamp kolonu kullanılıyor (created_at değil)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_company_date ON audit_logs(company_id, timestamp DESC)")
        
        # ========== CRITICAL FIX: candidate_positions Foreign Key Migration ==========
        # Eski tablo yanlış foreign key'e sahip olabilir (position_id → positions yerine department_pools olmalı)
        # SQLite'da ALTER TABLE ile FK değiştirilemez, tabloyu yeniden oluşturmalıyız
        try:
            # Mevcut veriyi yedekle
            cursor.execute("SELECT COUNT(*) FROM candidate_positions")
            row_count = cursor.fetchone()[0]
            
            if row_count > 0:
                # Veriyi geçici tabloya kopyala
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS candidate_positions_backup AS
                    SELECT * FROM candidate_positions
                """)
                logger.info(f"candidate_positions tablosu yedeklendi: {row_count} kayıt")
            
            # Eski tabloyu sil
            cursor.execute("DROP TABLE IF EXISTS candidate_positions")
            logger.info("Eski candidate_positions tablosu silindi")
            
            # Yeni tabloyu doğru foreign key'lerle oluştur
            cursor.execute("""
                CREATE TABLE candidate_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER NOT NULL,
                    position_id INTEGER NOT NULL,
                    match_score INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'aktif',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
                    FOREIGN KEY (position_id) REFERENCES department_pools(id) ON DELETE CASCADE,
                    UNIQUE(candidate_id, position_id)
                )
            """)
            logger.info("Yeni candidate_positions tablosu oluşturuldu (doğru FK'lerle)")
            
            # Index'leri yeniden oluştur
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_candidate ON candidate_positions(candidate_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_position ON candidate_positions(position_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidate_positions_score ON candidate_positions(position_id, match_score DESC)")
            
            # Yedekten veriyi geri yükle (sadece geçerli foreign key'leri olanlar)
            if row_count > 0:
                cursor.execute("""
                    INSERT INTO candidate_positions (candidate_id, position_id, match_score, status, created_at)
                    SELECT cp.candidate_id, cp.position_id, cp.match_score, cp.status, cp.created_at
                    FROM candidate_positions_backup cp
                    WHERE EXISTS (SELECT 1 FROM candidates c WHERE c.id = cp.candidate_id)
                      AND EXISTS (SELECT 1 FROM department_pools dp WHERE dp.id = cp.position_id)
                """)
                restored_count = cursor.rowcount
                logger.info(f"Veri geri yüklendi: {restored_count}/{row_count} kayıt")
                
                # Yedek tabloyu sil
                cursor.execute("DROP TABLE IF EXISTS candidate_positions_backup")
                logger.info("Yedek tablo silindi")
        except Exception as e:
            logger.error(f"candidate_positions migration hatası: {e}", exc_info=True)
            # Hata durumunda yedekten geri yükle
            try:
                cursor.execute("SELECT COUNT(*) FROM candidate_positions_backup")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("DROP TABLE IF EXISTS candidate_positions")
                    cursor.execute("ALTER TABLE candidate_positions_backup RENAME TO candidate_positions")
                    logger.warning("Migration başarısız, yedekten geri yüklendi")
            except Exception as restore_error:
                logger.error(f"Yedekten geri yükleme hatası: {restore_error}", exc_info=True)


def log_email_collection(
    account_id: int,
    account_email: str,
    klasor: str = "INBOX",
    taranan_email: int = 0,
    bulunan_cv: int = 0,
    basarili_cv: int = 0,
    mevcut_aday: int = 0,
    hatali_cv: int = 0,
    durum: str = "basarili",
    hata_detaylari: Optional[str] = None,
    baslangic_zamani: Optional[datetime] = None,
    bitis_zamani: Optional[datetime] = None,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> int:
    """
    Email toplama islemini logla

    Args:
        account_id: Email hesap ID
        account_email: Email adresi
        klasor: Taranan klasör
        taranan_email: Taranan email sayısı
        bulunan_cv: Bulunan CV sayısı
        basarili_cv: Başarıyla eklenen CV sayısı
        mevcut_aday: Mevcut aday (duplicate) sayısı
        hatali_cv: Hatalı/parse edilemeyen CV sayısı
        durum: basarili, kismi_basarili, basarisiz
        hata_detaylari: Hata varsa JSON formatında detaylar
        baslangic_zamani: İşlem başlangıç zamanı
        bitis_zamani: İşlem bitiş zamanı

    Returns:
        Eklenen log ID'si
    """
    sure_saniye = None
    if baslangic_zamani and bitis_zamani:
        sure_saniye = int((bitis_zamani - baslangic_zamani).total_seconds())

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_collection_logs
            (company_id, user_id, account_id, account_email, klasor, taranan_email,
             bulunan_cv, basarili_cv, mevcut_aday, hatali_cv, durum, hata_detaylari,
             baslangic_zamani, bitis_zamani, sure_saniye)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id, user_id, account_id, account_email, klasor, taranan_email,
            bulunan_cv, basarili_cv, mevcut_aday, hatali_cv, durum, hata_detaylari,
            baslangic_zamani.isoformat() if baslangic_zamani else None,
            bitis_zamani.isoformat() if bitis_zamani else None,
            sure_saniye
        ))
        return cursor.lastrowid


def get_email_collection_history(
    company_id: Optional[int] = None,
    account_id: Optional[int] = None,
    days: int = 30,
    limit: int = 100
) -> list[dict]:
    """
    Email toplama geçmişini getir

    Returns:
        Liste of dict: Her toplama işlemi için detaylar
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = """
            SELECT
                e.id, e.account_id, e.account_email, e.klasor,
                e.taranan_email, e.bulunan_cv, e.basarili_cv,
                e.mevcut_aday, e.hatali_cv, e.durum, e.hata_detaylari,
                e.baslangic_zamani, e.bitis_zamani, e.sure_saniye, e.tarih,
                u.email as kullanici_email, u.ad_soyad as kullanici_adi,
                ea.ad as hesap_adi
            FROM email_collection_logs e
            LEFT JOIN users u ON e.user_id = u.id
            LEFT JOIN email_accounts ea ON e.account_id = ea.id
            WHERE e.tarih >= ?
        """
        params = [start_date]

        if company_id:
            query += " AND e.company_id = ?"
            params.append(company_id)

        if account_id:
            query += " AND e.account_id = ?"
            params.append(account_id)

        query += " ORDER BY e.tarih DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_email_collection_stats(
    company_id: Optional[int] = None,
    days: int = 30
) -> dict:
    """
    Email toplama istatistiklerini getir

    Returns:
        {
            "toplam_islem": int,
            "toplam_taranan": int,
            "toplam_cv": int,
            "toplam_basarili": int,
            "toplam_hatali": int,
            "basari_orani": float,
            "hesap_bazli": {hesap_email: {islem, cv, basarili}}
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Genel istatistikler
        base_query = """
            SELECT
                COUNT(*) as toplam_islem,
                COALESCE(SUM(taranan_email), 0) as toplam_taranan,
                COALESCE(SUM(bulunan_cv), 0) as toplam_cv,
                COALESCE(SUM(basarili_cv), 0) as toplam_basarili,
                COALESCE(SUM(hatali_cv), 0) as toplam_hatali,
                COALESCE(SUM(mevcut_aday), 0) as toplam_mevcut
            FROM email_collection_logs
            WHERE tarih >= ?
        """
        params = [start_date]

        if company_id:
            base_query += " AND company_id = ?"
            params.append(company_id)

        cursor.execute(base_query, params)
        row = cursor.fetchone()

        toplam_cv = row["toplam_cv"] or 0
        toplam_basarili = row["toplam_basarili"] or 0
        basari_orani = (toplam_basarili / toplam_cv * 100) if toplam_cv > 0 else 0

        stats = {
            "toplam_islem": row["toplam_islem"] or 0,
            "toplam_taranan": row["toplam_taranan"] or 0,
            "toplam_cv": toplam_cv,
            "toplam_basarili": toplam_basarili,
            "toplam_hatali": row["toplam_hatali"] or 0,
            "toplam_mevcut": row["toplam_mevcut"] or 0,
            "basari_orani": round(basari_orani, 1)
        }

        # Hesap bazlı istatistikler
        hesap_query = """
            SELECT
                account_email,
                COUNT(*) as islem_sayisi,
                COALESCE(SUM(bulunan_cv), 0) as cv_sayisi,
                COALESCE(SUM(basarili_cv), 0) as basarili_sayisi
            FROM email_collection_logs
            WHERE tarih >= ?
        """
        hesap_params = [start_date]

        if company_id:
            hesap_query += " AND company_id = ?"
            hesap_params.append(company_id)

        hesap_query += " GROUP BY account_email ORDER BY cv_sayisi DESC"
        cursor.execute(hesap_query, hesap_params)

        stats["hesap_bazli"] = {
            row["account_email"]: {
                "islem": row["islem_sayisi"],
                "cv": row["cv_sayisi"],
                "basarili": row["basarili_sayisi"]
            }
            for row in cursor.fetchall()
        }

        return stats


# ============================================================
# FİRMA AYARLARI FONKSİYONLARI
# ============================================================

def get_company_settings(company_id: int) -> dict:
    """
    Firma ayarlarını getir

    Args:
        company_id: Firma ID

    Returns:
        Ayarlar dict'i
    """
    settings = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT setting_key, setting_value FROM company_settings
            WHERE company_id = ?
        """, (company_id,))

        for row in cursor.fetchall():
            key = row["setting_key"]
            value = row["setting_value"]
            # JSON olarak parse etmeye çalış
            try:
                settings[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                settings[key] = value

    return settings


def save_company_setting(company_id: int, key: str, value) -> bool:
    """
    Firma ayarını kaydet (varsa güncelle)

    Args:
        company_id: Firma ID
        key: Ayar anahtarı
        value: Ayar değeri (dict/list otomatik JSON'a çevrilir)

    Returns:
        Başarılı mı
    """
    # Değeri JSON'a çevir (dict/list ise)
    if isinstance(value, (dict, list)):
        value_str = json.dumps(value, ensure_ascii=False)
    else:
        value_str = str(value) if value is not None else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO company_settings (company_id, setting_key, setting_value)
            VALUES (?, ?, ?)
            ON CONFLICT(company_id, setting_key)
            DO UPDATE SET setting_value = excluded.setting_value,
                          guncelleme_tarihi = CURRENT_TIMESTAMP
        """, (company_id, key, value_str))

        conn.commit()
        return True


# Email toplama tablosunu olustur
_init_email_collection_table()


# ============ SQL GUVENLIK YARDIMCILARI ============

# Izin verilen alan adlari (SQL Injection onleme)
ALLOWED_FIELDS = {
    "candidates": {
        "ad_soyad", "email", "telefon", "lokasyon", "egitim", "universite", "bolum",
        "toplam_deneyim_yil", "mevcut_pozisyon", "mevcut_sirket", "teknik_beceriler",
        "diller", "sertifikalar", "linkedin", "github", "cv_dosya_yolu", "cv_dosya_adi",
        "deneyim_detay", "egitim_detay", "kaynak", "havuz", "durum", "notlar",
        "guncelleme_tarihi", "company_id", "expires_at", "is_anonymized", "anonymized_at"
    },
    "applications": {
        "kvkk_consent", "consent_date"
    },
    "positions": {
        "baslik", "departman", "lokasyon", "aciklama", "gerekli_deneyim_yil",
        "gerekli_egitim", "gerekli_beceriler", "tercih_edilen_beceriler",
        "min_maas", "max_maas", "aktif", "company_id"
    },
    "position_criteria": {
        "kriter_tipi", "deger", "seviye", "min_deger", "max_deger", "zorunlu", "agirlik"
    },
    "position_pools": {
        "uyum_puani", "durum", "notlar"
    },
    "interviews": {
        "tarih", "saat", "sure_dakika", "tur", "lokasyon", "notlar", "durum",
        "interviewer_name", "interviewer_email"
    },
    "email_accounts": {
        "ad", "saglayici", "email", "sifre", "imap_server", "imap_port",
        "smtp_server", "smtp_port", "sender_name", "aktif", "varsayilan_okuma",
        "varsayilan_gonderim", "son_kontrol", "toplam_cv"
    },
    "companies": {
        "ad", "slug", "email", "telefon", "adres", "website", "logo_url",
        "plan", "aktif"
    },
    "users": {
        "email", "password_hash", "ad_soyad", "company_id", "rol", "aktif", "son_giris"
    }
}


def validate_field_names(table: str, fields: dict) -> dict:
    """Alan adlarini dogrula, izin verilmeyenleri filtrele"""
    allowed = ALLOWED_FIELDS.get(table, set())
    return {k: v for k, v in fields.items() if k in allowed}


def safe_set_clause(table: str, fields: dict) -> tuple:
    """Guvenli SET clause olustur, sadece izin verilen alanlar
    
    Güvenlik:
    - Alan adları whitelist kontrolünden geçer (kullanıcı inputu değil)
    - Değerler parametreli sorgu ile gönderilir (? placeholder)
    - f-string sadece whitelist'teki alan adları için kullanılır (güvenli)
    
    Args:
        table: Tablo adı (whitelist kontrolü için)
        fields: Güncellenecek alanlar dict'i
    
    Returns:
        (set_clause, values_tuple): SET clause string'i ve değerler tuple'ı
    """
    validated = validate_field_names(table, fields)
    if not validated:
        return "", ()

    # Güvenlik: Alan adları whitelist'ten geldiği için f-string güvenli
    # Değerler parametreli sorgu ile gönderilecek
    set_clause = ", ".join(f"{k} = ?" for k in validated.keys())
    return set_clause, tuple(validated.values())


# ============ OWNERSHIP KONTROLLERI ============

class PermissionError(Exception):
    """Yetki hatasi - kayda erisim izni yok"""
    pass


def verify_candidate_ownership(candidate_id: int, company_id: int) -> bool:
    """Adayin bu firmaya ait oldugunu dogrula"""
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT company_id FROM candidates WHERE id = ?",
            (candidate_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return row[0] == company_id


def verify_position_ownership(position_id: int, company_id: int) -> bool:
    """Pozisyonun bu firmaya ait oldugunu dogrula"""
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT company_id FROM positions WHERE id = ?",
            (position_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return row[0] == company_id


def verify_department_pool_ownership(pool_id: int, company_id: int) -> bool:
    """Department pool'un bu firmaya ait oldugunu dogrula"""
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT company_id FROM department_pools WHERE id = ?",
            (pool_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return row[0] == company_id


def verify_email_account_ownership(account_id: int, company_id: int) -> bool:
    """Email hesabinin bu firmaya ait oldugunu dogrula"""
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT company_id FROM email_accounts WHERE id = ?",
            (account_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        return row[0] == company_id


def verify_interview_ownership(interview_id: int, company_id: int) -> bool:
    """Mülakatın bu firmaya ait olduğunu doğrula (candidate üzerinden)"""
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.company_id FROM interviews i
            JOIN candidates c ON i.candidate_id = c.id
            WHERE i.id = ?
        """, (interview_id,))
        row = cursor.fetchone()
        if not row:
            return False
        return row[0] == company_id


# ============ ADAY ISLEMLERI ============

def check_duplicate_candidate(company_id: int, email: Optional[str] = None, 
                               telefon: Optional[str] = None, 
                               ad_soyad: Optional[str] = None) -> dict:
    """Çoklu kritere göre duplicate kontrolü (güçlendirilmiş)
    
    Args:
        company_id: Firma ID (zorunlu - veri izolasyonu için)
        email: Email adresi
        telefon: Telefon numarası
        ad_soyad: Ad soyad (opsiyonel, şu an kullanılmıyor ama gelecekte eklenebilir)
    
    Returns:
        dict: {
            'is_duplicate': bool,
            'candidate_id': int or None,
            'matched_by': str or None ('email' | 'telefon' | 'both'),
            'existing_name': str or None
        }
    """
    if not company_id:
        raise ValueError("company_id zorunludur")
    
    result = {
        'is_duplicate': False,
        'candidate_id': None,
        'matched_by': None,
        'existing_name': None
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Email ile kontrol (en güvenilir)
        if email and email.strip():
            cursor.execute(
                "SELECT id, ad_soyad FROM candidates WHERE company_id = ? AND LOWER(email) = LOWER(?)",
                (company_id, email.strip())
            )
            row = cursor.fetchone()
            if row:
                result['is_duplicate'] = True
                result['candidate_id'] = row['id']
                result['matched_by'] = 'email'
                result['existing_name'] = row['ad_soyad']
                return result
        
        # 2. Telefon ile kontrol
        if telefon and telefon.strip():
            # Telefon numarasını normalize et (sadece rakamlar)
            clean_tel = ''.join(c for c in telefon if c.isdigit())
            if len(clean_tel) >= 10:
                # Son 10 haneyi al (ülke kodu olmadan)
                last_10 = clean_tel[-10:]
                cursor.execute(
                    """SELECT id, ad_soyad FROM candidates 
                       WHERE company_id = ? 
                       AND REPLACE(REPLACE(REPLACE(telefon, ' ', ''), '-', ''), '+', '') LIKE ?""",
                    (company_id, f'%{last_10}')
                )
                row = cursor.fetchone()
                if row:
                    result['is_duplicate'] = True
                    result['candidate_id'] = row['id']
                    # Eğer email ile de eşleştiyse 'both' yap
                    if result['matched_by'] == 'email':
                        result['matched_by'] = 'both'
                    else:
                        result['matched_by'] = 'telefon'
                    result['existing_name'] = row['ad_soyad']
                    return result
    
    return result


def find_duplicate_candidate(email: str, telefon: Optional[str] = None) -> Optional[Candidate]:
    """Email veya telefon ile duplicate aday bul (geriye uyumluluk için)"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Oncelikle email ile ara
        if email:
            cursor.execute("SELECT * FROM candidates WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return Candidate(**dict(row))

        # Email bulunamazsa ve telefon varsa telefon ile ara
        if telefon:
            # Telefon numarasini normalize et (sadece rakamlar)
            normalized_phone = normalize_phone(telefon)
            if normalized_phone:
                cursor.execute("""
                    SELECT * FROM candidates
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(telefon, ' ', ''), '-', ''), '(', ''), ')', '') LIKE ?
                """, (f"%{normalized_phone[-10:]}%",))  # Son 10 rakam
                row = cursor.fetchone()
                if row:
                    return Candidate(**dict(row))

        return None


def normalize_phone(telefon: str) -> str:
    """Telefon numarasini normalize et (sadece rakamlar)"""
    if not telefon:
        return ""
    return "".join(c for c in telefon if c.isdigit())


def find_duplicate_candidates_detailed(email: str, telefon: Optional[str] = None,
                                       company_id: Optional[int] = None,
                                       cv_dosya_adi: Optional[str] = None) -> dict:
    """
    Detayli duplicate kontrolu - eslesmeler ve tipiyle birlikte dondur

    Returns:
        {
            "found": bool,
            "match_type": "email" | "telefon" | "cv_dosya" | "both" | None,
            "candidate": Candidate or None,
            "candidates": list[dict] - tum eslesmeler
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        result = {
            "found": False,
            "match_type": None,
            "candidate": None,
            "candidates": []
        }

        matches = []

        # Email ile ara (case-insensitive)
        if email:
            query = "SELECT *, 'email' as match_type FROM candidates WHERE LOWER(email) = LOWER(?)"
            params = [email]
            if company_id:
                query += " AND company_id = ?"
                params.append(company_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                matches.append(dict(row))

        # Telefon ile ara
        if telefon:
            normalized = normalize_phone(telefon)
            if normalized and len(normalized) >= 7:
                # Son 7+ rakam ile eslesme ara
                search_digits = normalized[-10:] if len(normalized) >= 10 else normalized[-7:]

                query = """
                    SELECT *, 'telefon' as match_type FROM candidates
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(telefon, ' ', ''), '-', ''), '(', ''), ')', '') LIKE ?
                """
                params = [f"%{search_digits}%"]
                if company_id:
                    query += " AND company_id = ?"
                    params.append(company_id)

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    # Ayni aday email ile de bulunmussa "both" yap
                    existing = next((m for m in matches if m["id"] == row_dict["id"]), None)
                    if existing:
                        existing["match_type"] = "both"
                    else:
                        matches.append(row_dict)

        # CV dosya adi ile ara
        if cv_dosya_adi:
            query = "SELECT *, 'cv_dosya' as match_type FROM candidates WHERE cv_dosya_adi = ?"
            params = [cv_dosya_adi]
            if company_id:
                query += " AND company_id = ?"
                params.append(company_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                row_dict = dict(row)
                # Ayni aday daha once bulunmussa ekleme
                existing = next((m for m in matches if m["id"] == row_dict["id"]), None)
                if not existing:
                    matches.append(row_dict)

        if matches:
            result["found"] = True
            result["candidates"] = matches
            # Ilk eslesen aday
            best_match = matches[0]
            result["candidate"] = Candidate(**{k: v for k, v in best_match.items() if k != "match_type"})
            result["match_type"] = best_match.get("match_type")

        return result


def log_candidate_merge(master_id: int, merged_id: Optional[int], eslesme_tipi: str,
                        eslesme_degeri: str, islem_tipi: str, detay: str = None) -> int:
    """Aday birlestirme/eslestirme logunu kaydet"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO candidate_merge_logs
            (master_candidate_id, merged_candidate_id, eslesme_tipi, eslesme_degeri, islem_tipi, detay)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (master_id, merged_id, eslesme_tipi, eslesme_degeri, islem_tipi, detay))
        return cursor.lastrowid


def process_candidate_with_dedup(candidate: Candidate, company_id: int = None,
                                 auto_merge: bool = True) -> dict:
    """
    Aday isle - duplicate kontrolu yap ve uygun islemi gerceklestir

    Args:
        candidate: Aday bilgileri
        company_id: Firma ID
        auto_merge: True ise mevcut adaya basvuru ekle, False ise yeni kayit olustur

    Returns:
        {
            "action": "created" | "linked" | "skipped",
            "candidate_id": int,
            "is_duplicate": bool,
            "match_type": str or None,
            "message": str
        }
    """
    result = {
        "action": None,
        "candidate_id": None,
        "is_duplicate": False,
        "match_type": None,
        "message": ""
    }

    # Duplicate kontrolu (email, telefon, CV dosya adi)
    dup_check = find_duplicate_candidates_detailed(
        email=candidate.email,
        telefon=candidate.telefon,
        company_id=company_id,
        cv_dosya_adi=getattr(candidate, 'cv_dosya_adi', None)
    )

    if dup_check["found"]:
        result["is_duplicate"] = True
        result["match_type"] = dup_check["match_type"]
        existing_candidate = dup_check["candidate"]

        if auto_merge:
            # Mevcut adaya bagla
            result["action"] = "linked"
            result["candidate_id"] = existing_candidate.id
            result["message"] = f"Mevcut aday bulundu ({dup_check['match_type']}): {existing_candidate.ad_soyad}"

            # Log kaydet
            eslesme_degeri = candidate.email if dup_check["match_type"] in ["email", "both"] else candidate.telefon
            log_candidate_merge(
                master_id=existing_candidate.id,
                merged_id=None,
                eslesme_tipi=dup_check["match_type"],
                eslesme_degeri=eslesme_degeri,
                islem_tipi="basvuru_baglandi",
                detay=f"Yeni basvuru mevcut adaya baglandi. Kaynak: CV yukleme"
            )
        else:
            result["action"] = "skipped"
            result["candidate_id"] = existing_candidate.id
            result["message"] = f"Duplicate bulundu, islem yapilmadi: {existing_candidate.ad_soyad}"
    else:
        # Yeni aday olustur
        candidate_id = create_candidate(candidate, company_id=company_id)
        result["action"] = "created"
        result["candidate_id"] = candidate_id
        result["message"] = f"Yeni aday olusturuldu: {candidate.ad_soyad}"

        # Log kaydet
        log_candidate_merge(
            master_id=candidate_id,
            merged_id=None,
            eslesme_tipi="yeni",
            eslesme_degeri=candidate.email or candidate.telefon,
            islem_tipi="yeni_aday",
            detay="Yeni aday kaydi olusturuldu"
        )

    return result


def create_candidate(candidate: Candidate, company_id: int) -> int:
    """Yeni aday olustur

    Args:
        candidate: Aday nesnesi
        company_id: Firma ID (zorunlu - veri izolasyonu için)

    Returns:
        int: Oluşturulan aday ID
        dict: Duplicate bulunursa {"duplicate": True, "candidate_id": int, "message": str}

    Raises:
        ValueError: company_id verilmezse
        LimitExceededError: CV limiti aşılmışsa
    """
    if not company_id:
        raise ValueError("company_id zorunludur - veri izolasyonu için firma ID gereklidir")

    # DUPLICATE KONTROL — Email veya telefon ile mevcut aday kontrolü
    email = getattr(candidate, 'email', None)
    telefon = getattr(candidate, 'telefon', None)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Email ile kontrol
        if email and email.strip():
            cursor.execute(
                "SELECT id, ad_soyad FROM candidates WHERE company_id = ? AND LOWER(TRIM(email)) = LOWER(TRIM(?))",
                (company_id, email.strip())
            )
            existing = cursor.fetchone()
            if existing:
                return {
                    "duplicate": True,
                    "candidate_id": existing[0],
                    "message": f"Bu aday zaten mevcut: {existing[1]} (ID: {existing[0]}). Email: {email}"
                }
        
        # Telefon ile kontrol
        if telefon and telefon.strip():
            clean_tel = ''.join(c for c in telefon if c.isdigit())
            if len(clean_tel) >= 10:
                cursor.execute(
                    "SELECT id, ad_soyad FROM candidates WHERE company_id = ? AND REPLACE(REPLACE(REPLACE(REPLACE(telefon, ' ', ''), '-', ''), '+', ''), '(', '') LIKE ?",
                    (company_id, f'%{clean_tel[-10:]}')
                )
                existing = cursor.fetchone()
                if existing:
                    return {
                        "duplicate": True,
                        "candidate_id": existing[0],
                        "message": f"Bu aday zaten mevcut: {existing[1]} (ID: {existing[0]}). Telefon eslesti."
                    }

    # Limit kontrolü
    check_and_raise_limit(company_id, 'cvs')

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO candidates (
                company_id, ad_soyad, email, telefon, lokasyon, linkedin,
                egitim, universite, bolum,
                toplam_deneyim_yil, mevcut_pozisyon, mevcut_sirket, deneyim_detay,
                teknik_beceriler, diller, sertifikalar,
                cv_raw_text, cv_dosya_adi, cv_dosya_yolu,
                havuz, durum, notlar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            candidate.ad_soyad, candidate.email, candidate.telefon, candidate.lokasyon,
            getattr(candidate, 'linkedin', None),
            candidate.egitim, candidate.universite, candidate.bolum,
            candidate.toplam_deneyim_yil, candidate.mevcut_pozisyon,
            candidate.mevcut_sirket, candidate.deneyim_detay,
            candidate.teknik_beceriler, candidate.diller, candidate.sertifikalar,
            candidate.cv_raw_text, candidate.cv_dosya_adi, candidate.cv_dosya_yolu,
            candidate.havuz, candidate.durum, candidate.notlar
        ))
        
        # AUTO-ASSIGN: Yeni adayı otomatik olarak Genel Havuz'a ata
        new_candidate_id = cursor.lastrowid
        genel_havuz = cursor.execute(
            "SELECT id FROM department_pools WHERE name = 'Genel Havuz' AND company_id = ?",
            (company_id,)
        ).fetchone()
        if genel_havuz:
            cursor.execute(
                "INSERT OR IGNORE INTO candidate_pool_assignments (candidate_id, department_pool_id, assignment_type, assigned_at, company_id) VALUES (?, ?, 'auto', datetime('now'), ?)",
                (new_candidate_id, genel_havuz[0], company_id)
            )
        
        return new_candidate_id


def update_candidate(candidate_id: int, company_id: int = None, **fields) -> bool:
    """Aday bilgilerini guncelle

    Args:
        candidate_id: Aday ID
        company_id: Firma ID (güvenlik için zorunlu önerilir)
        **fields: Güncellenecek alanlar

    Returns:
        bool: Güncelleme başarılı mı
    """
    if not fields:
        return False

    # Sahiplik kontrolu
    if company_id:
        if not verify_candidate_ownership(candidate_id, company_id):
            return False

    fields["guncelleme_tarihi"] = datetime.now().isoformat()

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("candidates", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                f"UPDATE candidates SET {set_clause} WHERE id = ? AND company_id = ?",
                (*values, candidate_id, company_id)
            )
        else:
            cursor.execute(
                f"UPDATE candidates SET {set_clause} WHERE id = ?",
                (*values, candidate_id)
            )
        return cursor.rowcount > 0


def get_candidate(candidate_id: int, company_id: int = None, allow_cross_tenant: bool = False) -> Optional[Candidate]:
    """ID ile aday getir

    Args:
        candidate_id: Aday ID
        company_id: Firma ID (güvenlik için zorunlu - multi-tenant veri izolasyonu)
        allow_cross_tenant: True ise company_id=None durumunda cross-tenant erişime izin ver
                          (Sadece super admin işlemleri için kullanılmalıdır)

    Returns:
        Candidate veya None (erişim yetkisi yoksa veya bulunamazsa)
    
    Raises:
        ValueError: company_id=None ve allow_cross_tenant=False durumunda
    
    Warning:
        allow_cross_tenant=True kullanımı cross-tenant data access riski taşır.
        Sadece super admin işlemleri için kullanılmalıdır.
    """
    # Güvenlik kontrolü: company_id=None ve allow_cross_tenant=False ise hata fırlat
    if company_id is None and not allow_cross_tenant:
        raise ValueError("company_id is required for tenant-safe access. Use allow_cross_tenant=True only for super admin operations.")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            # Güvenli: company_id ile filtreleme
            cursor.execute(
                "SELECT * FROM candidates WHERE id = ? AND company_id = ?",
                (candidate_id, company_id)
            )
        else:
            # ⚠️ UYARI: company_id=None kullanımı cross-tenant access riski taşır
            # Sadece allow_cross_tenant=True ile kullanılmalı (super admin işlemleri)
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        if row:
            return Candidate(**dict(row))
        return None


def get_candidates_by_ids(candidate_ids: list[int], company_id: int) -> dict[int, Candidate]:
    """Birden fazla adayı tek sorguda çek (N+1 query sorununu önlemek için)
    
    Args:
        candidate_ids: Aday ID listesi
        company_id: Firma ID (güvenlik için zorunlu)
    
    Returns:
        dict: {candidate_id: Candidate} mapping
    """
    if not candidate_ids:
        return {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # IN clause için placeholder'lar oluştur
        placeholders = ','.join(['?' for _ in candidate_ids])
        query = f"""
            SELECT * FROM candidates 
            WHERE id IN ({placeholders}) AND company_id = ?
        """
        params = candidate_ids + [company_id]
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Dict mapping oluştur: {candidate_id: Candidate}
        candidates_map = {}
        for row in rows:
            candidate = Candidate(**dict(row))
            candidates_map[candidate.id] = candidate
        
        return candidates_map


def get_all_candidates(
    company_id: int,
    havuz: Optional[str] = None,
    durum: Optional[str] = None,
    arama: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> list[Candidate]:
    """Tum adaylari getir (filtreleme ve pagination destekli)

    Args:
        company_id: Firma ID (zorunlu - veri izolasyonu için)
        havuz: Havuz filtresi
        durum: Durum filtresi
        arama: Arama terimi
        limit: Sayfa başına kayıt sayısı (default: 100)
        offset: Atlanacak kayıt sayısı (default: 0)

    Returns:
        list[Candidate]: Aday listesi

    Raises:
        ValueError: company_id verilmezse
    """
    if not company_id:
        raise ValueError("company_id zorunludur - veri izolasyonu için firma ID gereklidir")

    with get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM candidates WHERE company_id = ?"
        params = [company_id]

        if havuz:
            if havuz == "genel_havuz":
                query += " AND havuz = ?"
                params.append("genel_havuz")
            elif havuz == "departman_havuzu":
                # Departman altindaki pozisyonlara atanmis adaylar
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools pos ON cpa.department_pool_id = pos.id
                    JOIN department_pools dept ON pos.parent_id = dept.id
                    WHERE pos.pool_type = 'position' AND dept.pool_type = 'department' AND dept.is_system = 0
                )"""
            elif havuz == "pozisyon_havuzu":
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools dp ON cpa.department_pool_id = dp.id
                    WHERE dp.pool_type = 'position'
                )"""
            elif havuz == "arsiv":
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools dp ON cpa.department_pool_id = dp.id
                    WHERE dp.name = 'Arşiv' AND dp.is_system = 1
                )"""
            else:
                query += " AND havuz = ?"
                params.append(havuz)

        if durum:
            query += " AND durum = ?"
            params.append(durum)

        if arama:
            query += " AND (ad_soyad LIKE ? OR email LIKE ? OR teknik_beceriler LIKE ?)"
            search_term = f"%{arama}%"
            params.extend([search_term, search_term, search_term])

        query += " ORDER BY olusturma_tarihi DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [Candidate(**dict(row)) for row in cursor.fetchall()]


def get_candidates_count(
    company_id: int,
    havuz: Optional[str] = None,
    durum: Optional[str] = None,
    arama: Optional[str] = None
) -> int:
    """Toplam aday sayısını getir (filtreleme destekli)

    Args:
        company_id: Firma ID (zorunlu)
        havuz: Havuz filtresi
        durum: Durum filtresi
        arama: Arama terimi

    Returns:
        int: Toplam aday sayısı
    """
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM candidates WHERE company_id = ?"
        params = [company_id]

        if havuz:
            if havuz == "genel_havuz":
                query += " AND havuz = ?"
                params.append("genel_havuz")
            elif havuz == "departman_havuzu":
                # Departman altindaki pozisyonlara atanmis adaylar
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools pos ON cpa.department_pool_id = pos.id
                    JOIN department_pools dept ON pos.parent_id = dept.id
                    WHERE pos.pool_type = 'position' AND dept.pool_type = 'department' AND dept.is_system = 0
                )"""
            elif havuz == "pozisyon_havuzu":
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools dp ON cpa.department_pool_id = dp.id
                    WHERE dp.pool_type = 'position'
                )"""
            elif havuz == "arsiv":
                query += """ AND candidates.id IN (
                    SELECT cpa.candidate_id FROM candidate_pool_assignments cpa
                    JOIN department_pools dp ON cpa.department_pool_id = dp.id
                    WHERE dp.name = 'Arşiv' AND dp.is_system = 1
                )"""
            else:
                query += " AND havuz = ?"
                params.append(havuz)

        if durum:
            query += " AND durum = ?"
            params.append(durum)

        if arama:
            query += " AND (ad_soyad LIKE ? OR email LIKE ? OR teknik_beceriler LIKE ?)"
            search_term = f"%{arama}%"
            params.extend([search_term, search_term, search_term])

        cursor.execute(query, params)
        return cursor.fetchone()[0]


def get_admin_stats() -> dict:
    """ADMIN ONLY: Tüm sistem istatistiklerini getir

    Bu fonksiyon sadece sistem admini tarafından kullanılmalıdır.
    Veri izolasyonunu bypass eder.

    Returns:
        dict: Sistem istatistikleri
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM candidates")
        total_candidates = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM positions")
        total_positions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM applications")
        total_applications = cursor.fetchone()[0]

        return {
            "total_candidates": total_candidates,
            "total_positions": total_positions,
            "total_applications": total_applications
        }


# ============ FK CONSTRAINT YARDIMCI FONKSİYONLARI ============

def safe_delete_with_fk(cursor, table_name: str, where_clause: str, params: tuple, fk_column: str = None) -> dict:
    """
    FK bağımlılıkları olan tablodan güvenli silme.
    Önce bağımlı tabloları temizler, sonra ana tabloyu siler.
    
    Args:
        cursor: SQLite cursor
        table_name: Silinecek tablo (örn: 'department_pools', 'candidates')
        where_clause: WHERE koşulu (örn: 'id = ?')
        params: WHERE parametreleri (örn: (pool_id,))
        fk_column: Bağımlı tablolardaki FK kolon adı (örn: 'position_id', 'candidate_id')
                   None ise otomatik tespit eder (table_name'e göre)
    
    Returns:
        {
            'success': bool,
            'deleted_from_main': int,
            'deleted_from_dependent': dict,  # {table_name: count}
            'errors': list
        }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    result = {
        'success': False,
        'deleted_from_main': 0,
        'deleted_from_dependent': {},
        'errors': []
    }
    
    # FK kolon adını otomatik tespit et
    if fk_column is None:
        if table_name == 'department_pools':
            fk_column = 'position_id'
        elif table_name == 'candidates':
            fk_column = 'candidate_id'
        else:
            # Genel kural: table_name'in tekil hali + '_id'
            fk_column = table_name.rstrip('s') + '_id'
    
    try:
        # 1. PRAGMA foreign_keys=OFF
        cursor.execute("PRAGMA foreign_keys=OFF")
        
        # 2. Bağımlı tabloları dinamik bul
        # SQLite'da FK bilgisi sqlite_master'da saklanır
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND sql LIKE ?
            AND name != ?
        """, (f'%{fk_column}%', table_name))
        
        dependent_tables = [row[0] for row in cursor.fetchall()]
        
        # 3. Her bağımlı tablodan sil
        for dep_table in dependent_tables:
            # Güvenlik kontrolü: tablo adı sadece alfanumerik ve alt çizgi içermeli
            if not dep_table.replace('_', '').isalnum():
                logger.warning(f"safe_delete_with_fk: Güvensiz tablo adı atlandı: {dep_table}")
                continue
            
            try:
                # Önce kaç kayıt olduğunu say
                cursor.execute(f'SELECT COUNT(*) FROM "{dep_table}" WHERE {fk_column} IN (SELECT id FROM {table_name} WHERE {where_clause})', params)
                count_before = cursor.fetchone()[0]
                
                if count_before > 0:
                    # Bağımlı tablodan sil
                    cursor.execute(f'DELETE FROM "{dep_table}" WHERE {fk_column} IN (SELECT id FROM {table_name} WHERE {where_clause})', params)
                    result['deleted_from_dependent'][dep_table] = count_before
                    logger.info(f"safe_delete_with_fk: {dep_table} tablosundan {count_before} kayıt silindi")
            except Exception as e:
                error_msg = f"{dep_table} silme hatası: {e}"
                result['errors'].append(error_msg)
                logger.error(f"safe_delete_with_fk: {error_msg}")
        
        # 4. Ana tablodan sil
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}", params)
            count_before = cursor.fetchone()[0]
            
            cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}", params)
            result['deleted_from_main'] = cursor.rowcount
            result['success'] = True
            logger.info(f"safe_delete_with_fk: {table_name} tablosundan {result['deleted_from_main']} kayıt silindi")
        except Exception as e:
            error_msg = f"{table_name} silme hatası: {e}"
            result['errors'].append(error_msg)
            logger.error(f"safe_delete_with_fk: {error_msg}")
            result['success'] = False
        
        # 5. PRAGMA foreign_keys=ON
        cursor.execute("PRAGMA foreign_keys=ON")
        
    except Exception as e:
        error_msg = f"safe_delete_with_fk genel hata: {e}"
        result['errors'].append(error_msg)
        logger.error(f"safe_delete_with_fk: {error_msg}")
        # Foreign key constraint'leri tekrar aç
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        except:
            pass
    
    return result


# ============ POZISYON ISLEMLERI ============

def create_position(position: Position, company_id: int) -> int:
    """Yeni pozisyon olustur

    Args:
        position: Pozisyon nesnesi
        company_id: Firma ID (zorunlu - veri izolasyonu için)

    Returns:
        int: Oluşturulan pozisyon ID

    Raises:
        ValueError: company_id verilmezse
        LimitExceededError: Pozisyon limiti aşılmışsa
    """
    if not company_id:
        raise ValueError("company_id zorunludur - veri izolasyonu için firma ID gereklidir")

    # Limit kontrolü
    check_and_raise_limit(company_id, 'positions')

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO positions (
                company_id, baslik, departman, lokasyon, aciklama,
                gerekli_deneyim_yil, gerekli_egitim,
                gerekli_beceriler, tercih_edilen_beceriler,
                aktif
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            position.baslik, position.departman, position.lokasyon,
            position.aciklama, position.gerekli_deneyim_yil,
            position.gerekli_egitim, position.gerekli_beceriler,
            position.tercih_edilen_beceriler, position.aktif
        ))
        return cursor.lastrowid


def get_all_positions(company_id: int, only_active: bool = True, limit: int = 100, offset: int = 0) -> list[Position]:
    """Tum pozisyonlari getir (pagination destekli)

    Args:
        company_id: Firma ID (zorunlu - veri izolasyonu için)
        only_active: Sadece aktif pozisyonlar
        limit: Sayfa başına kayıt sayısı (default: 100)
        offset: Atlanacak kayıt sayısı (default: 0)

    Returns:
        list[Position]: Pozisyon listesi

    Raises:
        ValueError: company_id verilmezse
    """
    if not company_id:
        raise ValueError("company_id zorunludur - veri izolasyonu için firma ID gereklidir")

    with get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM positions WHERE company_id = ?"
        params = [company_id]

        if only_active:
            query += " AND aktif = 1"

        query += " ORDER BY acilis_tarihi DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        return [Position(**dict(row)) for row in cursor.fetchall()]


def get_positions_count(company_id: int, only_active: bool = True) -> int:
    """Toplam pozisyon sayısını getir

    Args:
        company_id: Firma ID (zorunlu)
        only_active: Sadece aktif pozisyonlar

    Returns:
        int: Toplam pozisyon sayısı
    """
    if not company_id:
        raise ValueError("company_id zorunludur")

    with get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM positions WHERE company_id = ?"
        params = [company_id]

        if only_active:
            query += " AND aktif = 1"

        cursor.execute(query, params)
        return cursor.fetchone()[0]


def get_position(position_id: int, company_id: int = None) -> Optional[Position]:
    """ID ile pozisyon getir

    Args:
        position_id: Pozisyon ID
        company_id: Firma ID (güvenlik için zorunlu önerilir)

    Returns:
        Position veya None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                "SELECT * FROM positions WHERE id = ? AND company_id = ?",
                (position_id, company_id)
            )
        else:
            # Geriye uyumluluk
            cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
        row = cursor.fetchone()
        if row:
            return Position(**dict(row))
        return None


def update_position(position_id: int, company_id: int = None, **fields) -> bool:
    """Pozisyon bilgilerini guncelle

    Args:
        position_id: Pozisyon ID
        company_id: Firma ID (güvenlik için zorunlu önerilir)
        **fields: Güncellenecek alanlar

    Returns:
        bool: Güncelleme başarılı mı
    """
    if not fields:
        return False

    # Sahiplik kontrolu
    if company_id:
        if not verify_position_ownership(position_id, company_id):
            return False

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("positions", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                f"UPDATE positions SET {set_clause} WHERE id = ? AND company_id = ?",
                (*values, position_id, company_id)
            )
        else:
            cursor.execute(
                f"UPDATE positions SET {set_clause} WHERE id = ?",
                (*values, position_id)
            )
        return cursor.rowcount > 0


def delete_position(position_id: int, company_id: int = None) -> bool:
    """Pozisyonu sil (kriterleri ve havuzu da silinir - CASCADE)

    Args:
        position_id: Pozisyon ID
        company_id: Firma ID (güvenlik için zorunlu önerilir)

    Returns:
        bool: Silme başarılı mı
    """
    # Sahiplik kontrolu
    if company_id:
        if not verify_position_ownership(position_id, company_id):
            return False

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                "DELETE FROM positions WHERE id = ? AND company_id = ?",
                (position_id, company_id)
            )
        else:
            cursor.execute("DELETE FROM positions WHERE id = ?", (position_id,))
        return cursor.rowcount > 0


# ============ POZISYON KRITER ISLEMLERI ============

def add_position_criteria(
    position_id: int,
    kriter_tipi: str,
    deger: str,
    min_deger: str = None,
    max_deger: str = None,
    seviye: str = None,
    zorunlu: bool = False,
    agirlik: float = 1.0
) -> int:
    """Pozisyona kriter ekle"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO position_criteria (
                position_id, kriter_tipi, deger, min_deger, max_deger, seviye, zorunlu, agirlik
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (position_id, kriter_tipi, deger, min_deger, max_deger, seviye, 1 if zorunlu else 0, agirlik))
        return cursor.lastrowid


def get_position_criteria(position_id: int) -> list[dict]:
    """Pozisyon kriterlerini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM position_criteria WHERE position_id = ? ORDER BY zorunlu DESC, kriter_tipi",
            (position_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_all_position_criteria(position_id: int) -> bool:
    """Pozisyonun tum kriterlerini sil"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM position_criteria WHERE position_id = ?", (position_id,))
        return True


# ============ POZISYON HAVUZ ISLEMLERI ============

def add_candidate_to_pool(
    position_id: int,
    candidate_id: int,
    uyum_puani: float = 0,
    durum: str = "beklemede",
    notlar: str = None
) -> int:
    """Adayi pozisyon havuzuna ekle"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO position_pools (
                position_id, candidate_id, uyum_puani, durum, notlar, ekleme_tarihi
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (position_id, candidate_id, uyum_puani, durum, notlar))
        return cursor.lastrowid


def get_position_pool(position_id: int, durum: str = None) -> list[dict]:
    """Pozisyon havuzundaki adayları getir (candidate_positions tablosundan)
    
    Args:
        position_id: Pozisyon ID (department_pools.id)
        durum: Durum filtresi (opsiyonel)
    
    Returns:
        Aday listesi (candidate_positions + candidates JOIN ile)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT cp.id, cp.candidate_id, cp.position_id, cp.match_score, cp.status, cp.created_at,
                   c.ad_soyad, c.email, c.telefon, c.mevcut_pozisyon, c.mevcut_sirket,
                   c.toplam_deneyim_yil, c.teknik_beceriler, c.lokasyon, c.egitim, c.universite,
                   c.bolum, c.cv_dosya_yolu, c.cv_dosya_adi, c.linkedin, c.diller, c.sertifikalar,
                   c.deneyim_detay, c.egitim_detay, c.notlar, c.durum as candidate_durum,
                   c.havuz, c.olusturma_tarihi,
                   -- Geriye uyumluluk için uyum_puani alias'ı ekle
                   cp.match_score as uyum_puani,
                   -- Durum için status kullan (candidate_pool_assignments'tan değil)
                   cp.status as durum
            FROM candidate_positions cp
            JOIN candidates c ON cp.candidate_id = c.id
            WHERE cp.position_id = ?
        """
        params = [position_id]

        if durum:
            query += " AND cp.status = ?"
            params.append(durum)

        query += " ORDER BY cp.match_score DESC, cp.created_at DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_candidate_pools(candidate_id: int) -> list[dict]:
    """Adayin dahil oldugu havuzlari getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pp.*, p.baslik as pozisyon_baslik, p.departman, p.lokasyon
            FROM position_pools pp
            JOIN positions p ON pp.position_id = p.id
            WHERE pp.candidate_id = ?
            ORDER BY pp.ekleme_tarihi DESC
        """, (candidate_id,))
        return [dict(row) for row in cursor.fetchall()]


def update_pool_candidate(position_id: int, candidate_id: int, company_id: int = None, **fields) -> bool:
    """Havuzdaki aday bilgisini guncelle (candidate_positions tablosunda)

    Args:
        position_id: Pozisyon ID (department_pools.id)
        candidate_id: Aday ID
        company_id: Firma ID (güvenlik için önerilir)
        **fields: Güncellenecek alanlar (status, match_score vb.)

    Raises:
        PermissionError: Pozisyon veya aday bu firmaya ait değilse
    """
    if not fields:
        return False

    # Sahiplik kontrolü
    if company_id:
        # Pozisyon sahipliği kontrolü (department_pools üzerinden)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company_id FROM department_pools WHERE id = ?
            """, (position_id,))
            pos_row = cursor.fetchone()
            if not pos_row or pos_row[0] != company_id:
                raise PermissionError("Bu pozisyona erişim yetkiniz yok")
        
        if not verify_candidate_ownership(candidate_id, company_id):
            raise PermissionError("Bu adaya erişim yetkiniz yok")

    # candidate_positions tablosu için izin verilen alanlar
    allowed_fields = {'status', 'match_score'}
    updates = {k: v for k, v in fields.items() if k in allowed_fields}
    
    if not updates:
        return False

    # Güvenli SET clause oluştur
    set_parts = [f"{field} = ?" for field in updates.keys()]
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [candidate_id, position_id]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE candidate_positions SET {set_clause} WHERE candidate_id = ? AND position_id = ?",
            values
        )
        updated = cursor.rowcount > 0
        
        # Geriye uyumluluk: candidate_pool_assignments tablosunu da güncelle (durum için)
        if updated and 'status' in updates:
            try:
                # durum → status mapping
                durum_map = {
                    'aktif': 'beklemede',
                    'beklemede': 'beklemede',
                    'inceleniyor': 'inceleniyor',
                    'mulakat': 'mulakat',
                    'teklif': 'teklif',
                    'red': 'red'
                }
                durum_value = durum_map.get(updates['status'], updates['status'])
                cursor.execute("""
                    UPDATE candidate_pool_assignments
                    SET match_reason = ?
                    WHERE candidate_id = ? AND department_pool_id = ?
                """, (f"Durum: {durum_value}", candidate_id, position_id))
            except Exception as e:
                logger.debug(f"candidate_pool_assignments güncelleme hatası (göz ardı edildi): {e}")
        
        return updated


def update_candidate_general_pool(candidate_id: int, havuz: str, company_id: int = None) -> bool:
    """Adayin genel havuzunu guncelle

    Args:
        candidate_id: Aday ID
        havuz: Yeni havuz adı
        company_id: Firma ID (güvenlik için önerilir)

    Raises:
        PermissionError: Aday bu firmaya ait değilse
    """
    # Sahiplik kontrolü
    if company_id:
        if not verify_candidate_ownership(candidate_id, company_id):
            raise PermissionError("Bu adaya erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                "UPDATE candidates SET havuz = ? WHERE id = ? AND company_id = ?",
                (havuz, candidate_id, company_id)
            )
        else:
            cursor.execute(
                "UPDATE candidates SET havuz = ? WHERE id = ?",
                (havuz, candidate_id)
            )
        return cursor.rowcount > 0


# ============ DEPARTMAN HAVUZ ISLEMLERI ============

SYSTEM_POOLS = [
    {'name': 'Genel Havuz', 'icon': '📥', 'description': 'Yeni gelen CV\'ler (30 gün saklanır)'},
    {'name': 'Arşiv', 'icon': '📦', 'description': '30 gün işlenmemiş CV\'ler (30 gün saklanır, sonra silinir)'},
]


def create_system_pools(company_id: int) -> list[int]:
    """Şirket için varsayılan sistem havuzlarını oluştur"""
    created_ids = []
    with get_connection() as conn:
        cursor = conn.cursor()
        for pool_data in SYSTEM_POOLS:
            cursor.execute("""
                INSERT OR IGNORE INTO department_pools (company_id, name, icon, description, is_system)
                VALUES (?, ?, ?, ?, 1)
            """, (company_id, pool_data['name'], pool_data['icon'], pool_data['description']))
            if cursor.rowcount > 0:
                created_ids.append(cursor.lastrowid)
    return created_ids


def get_department_pools(company_id: int, include_inactive: bool = False,
                         pool_type: str = None, parent_id: int = None, use_cache: bool = True) -> list[dict]:
    """Şirketin departman havuzlarını getir (cache destekli)

    Args:
        company_id: Şirket ID
        include_inactive: Pasif havuzları dahil et
        pool_type: 'department' veya 'position' filtresi (None=hepsi)
        parent_id: Belirli bir departmanın pozisyonlarını getir
        use_cache: Cache kullan (default: True)

    Returns:
        list[dict]: Departman havuzları listesi
    """
    # Cache key oluştur
    cache_key = f"dept_pools_{company_id}_{include_inactive}_{pool_type}_{parent_id}"
    
    def fetch():
        with get_connection() as conn:
            cursor = conn.cursor()
            active_filter = "" if include_inactive else "AND is_active = 1"
            type_filter = f"AND pool_type = '{pool_type}'" if pool_type else ""

            if parent_id is not None:
                parent_filter = f"AND parent_id = {parent_id}"
            else:
                parent_filter = ""

            cursor.execute(f"""
                SELECT * FROM department_pools
                WHERE company_id = ? {active_filter} {type_filter} {parent_filter}
                ORDER BY is_system DESC, name
            """, (company_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    if use_cache:
        return cached_get(cache_key, fetch)
    else:
        return fetch()


def get_pool_by_name(company_id: int, name: str, conn=None) -> Optional[dict]:
    """İsme göre havuz getir
    
    Args:
        company_id: Şirket ID
        name: Havuz adı
        conn: Mevcut veritabanı bağlantısı (isteğe bağlı). Verilmezse yeni bağlantı açılır.
    
    Returns:
        Havuz dict veya None
    """
    # Bağlantı yönetimi
    close_conn = False
    if conn is None:
        from config import DATABASE_PATH
        ensure_data_dir()
        conn = sqlite3.connect(DATABASE_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM department_pools
            WHERE company_id = ? AND name = ? AND is_active = 1
        """, (company_id, name))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        # Bağlantıyı kapat (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.close()


def assign_candidate_to_department_pool(candidate_id: int, pool_id: int, company_id: int,
                                        assignment_type: str = 'auto',
                                        match_score: int = 0, match_reason: str = '', conn=None) -> int:
    """Adayı departman/pozisyon havuzuna ata (çoklu atama destekli)

    Aynı aday birden fazla pozisyon havuzuna atanabilir.
    
    Args:
        candidate_id: Aday ID
        pool_id: Havuz ID
        assignment_type: Atama tipi ('auto' veya 'manual')
        match_score: Eşleşme skoru
        match_reason: Eşleşme nedeni
        conn: Mevcut veritabanı bağlantısı (isteğe bağlı). Verilmezse yeni bağlantı açılır.
    
    Returns:
        Atama ID'si
    """
    # Bağlantı yönetimi
    close_conn = False
    if conn is None:
        from config import DATABASE_PATH
        ensure_data_dir()
        conn = sqlite3.connect(DATABASE_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        close_conn = True

    try:
        cursor = conn.cursor()
        # Aynı havuza zaten atanmış mı kontrol et
        cursor.execute("""
            SELECT id FROM candidate_pool_assignments
            WHERE candidate_id = ? AND department_pool_id = ?
        """, (candidate_id, pool_id))
        existing = cursor.fetchone()

        if existing:
            # Varsa güncelle
            cursor.execute("""
                UPDATE candidate_pool_assignments
                SET match_score = ?, match_reason = ?, assignment_type = ?
                WHERE candidate_id = ? AND department_pool_id = ?
            """, (match_score, match_reason, assignment_type, candidate_id, pool_id))
            result = existing[0]
        else:
            # Yoksa ekle
            cursor.execute("""
                INSERT INTO candidate_pool_assignments
                (candidate_id, department_pool_id, assignment_type, match_score, match_reason, company_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (candidate_id, pool_id, assignment_type, match_score, match_reason, company_id))
            result = cursor.lastrowid
        
        # Commit işlemi (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.commit()
        
        return result
    finally:
        # Bağlantıyı kapat (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.close()


def find_matching_department(candidate_id: int, company_id: int) -> tuple:
    """CV içeriğine göre en uygun pozisyonu bul (hiyerarşik yapı)

    Önce pozisyon seviyesinde anahtar kelime eşleştirmesi yapar.
    Pozisyon eşleşirse o pozisyona atar (parent departman bilgisi de saklanır).

    Returns:
        (pool_id, score, reason) veya (None, 0, '') eğer eşleşme yoksa
    """
    # Aday bilgilerini al (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return None, 0, ""

    # Aranacak metin oluştur (Türkçe normalize)
    search_text = turkish_lower(' '.join(filter(None, [
        candidate.cv_raw_text or '',
        candidate.teknik_beceriler or '',
        candidate.mevcut_pozisyon or '',
        candidate.deneyim_detay or ''
    ])))

    if not search_text.strip():
        return None, 0, ""

    # Tüm havuzları getir (pozisyonlar dahil)
    pools = get_department_pools(company_id)

    # Sadece pozisyonları ara (pool_type='position' ve keywords var)
    # Departmanlar sadece gruplama için, anahtar kelime eşleştirmesi pozisyonlarda
    position_pools = [p for p in pools if p.get('pool_type') == 'position' and not p.get('is_system')]

    # Eski tip havuzları da dahil et (geriye uyumluluk)
    legacy_pools = [p for p in pools if not p.get('pool_type') and not p.get('is_system')]

    # Sadece pozisyonlarda anahtar kelime eşleştirmesi yap
    searchable_pools = position_pools + legacy_pools

    best_match = None
    best_score = 0
    matched_keywords = []

    for pool in searchable_pools:
        keywords_raw = pool.get('keywords')
        if not keywords_raw:
            continue

        # JSON parse
        try:
            keywords = json.loads(keywords_raw) if isinstance(keywords_raw, str) else keywords_raw
        except (json.JSONDecodeError, TypeError):
            continue

        if not keywords:
            continue

        keywords = _parse_keywords(keywords)
        score = 0
        current_matches = []

        for keyword in keywords:
            kw_lower = turkish_lower(keyword)
            if _keyword_match(kw_lower, search_text):
                score += 1
                current_matches.append(keyword)

        if score > best_score:
            best_score = score
            best_match = pool
            matched_keywords = current_matches

    if best_match and best_score > 0:
        reason = f"Eşleşen: {', '.join(matched_keywords[:5])}"
        return best_match['id'], best_score, reason

    return None, 0, ""


def find_all_matching_positions(candidate_id: int, company_id: int) -> list[dict]:
    """CV içeriğine göre TÜM eşleşen pozisyonları bul
    
    DEPRECATED: v2 sisteme geçildi. Sadece keyword eşleştirmesi yapıyor, title match kontrolü yok.
    Fallback olarak tutuluyor. Yeni kod için match_candidate_to_positions_keyword() kullanılmalı.

    Aday birden fazla pozisyonla eşleşebilir.

    Returns:
        [{'pool_id': X, 'pool_name': Y, 'score': Z, 'keywords': [...]}]
    """
    # Aday bilgilerini al (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return []

    # Aranacak metin oluştur (Türkçe normalize)
    search_text = turkish_lower(' '.join(filter(None, [
        candidate.cv_raw_text or '',
        candidate.teknik_beceriler or '',
        candidate.mevcut_pozisyon or '',
        candidate.deneyim_detay or ''
    ])))

    if not search_text.strip():
        return []

    pools = get_department_pools(company_id)
    position_pools = [p for p in pools if p.get('pool_type') == 'position' and not p.get('is_system')]

    matches = []

    for pool in position_pools:
        keywords_raw = pool.get('keywords')
        if not keywords_raw:
            continue

        try:
            keywords = json.loads(keywords_raw) if isinstance(keywords_raw, str) else keywords_raw
        except (json.JSONDecodeError, TypeError):
            continue

        if not keywords:
            continue

        keywords = _parse_keywords(keywords)
        matched_kw = []
        for keyword in keywords:
            kw_lower = turkish_lower(keyword)
            if _keyword_match(kw_lower, search_text):
                matched_kw.append(keyword)

        if matched_kw:
            matches.append({
                'pool_id': pool['id'],
                'pool_name': pool['name'],
                'score': len(matched_kw),
                'keywords': matched_kw
            })

    # Skora göre sırala
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def auto_assign_candidate_to_pool(candidate_id: int, company_id: int, position_id: int = None) -> list[dict]:
    """Adayı önce Genel Havuz'a at, eşleşme varsa pozisyona TAŞI
    
    DEPRECATED: v2 sisteme geçildi. Sadece fallback olarak tutuluyor.

    Akış:
    1. Önce Genel Havuz'a ata
    2. Eşleşen pozisyonları kontrol et
    3. Eşleşme varsa → Genel Havuz'dan kaldır, pozisyonlara ata
    4. Eşleşme yoksa → Genel Havuz'da kal
    """
    # company_id None ise varsayılan 1 kullan
    if company_id is None:
        company_id = 1

    assignments = []

    # Sistem havuzlarını oluştur (yoksa)
    create_system_pools(company_id)

    # Önce Genel Havuz'a ata
    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    if general_pool:
        assign_candidate_to_department_pool(
            candidate_id, general_pool['id'], company_id, 'auto', 0, 'Yeni aday - değerlendirme bekliyor'
        )

    # Eşleşen pozisyonları bul
    matches = find_all_matching_positions(candidate_id, company_id)

    if matches:
        # Genel Havuz'dan kaldır
        if general_pool:
            remove_candidate_from_department_pool(candidate_id, general_pool['id'])

        # Eşleşen pozisyonlara ata
        for match in matches:
            reason = f"{', '.join(match['keywords'][:3])} eslesti"
            assign_id = assign_candidate_to_department_pool(
                candidate_id, match['pool_id'], company_id, 'auto', match['score'], reason
            )
            assignments.append({
                'type': 'position',
                'id': assign_id,
                'pool_name': match['pool_name'],
                'score': match['score']
            })
    else:
        # Eşleşme yok - Genel Havuz'da kalır
        assignments.append({'type': 'general', 'pool_name': 'Genel Havuz'})

    return assignments


def remove_candidate_from_department_pool(candidate_id: int, pool_id: int) -> bool:
    """Adayı departman havuzundan çıkar"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM candidate_pool_assignments
            WHERE candidate_id = ? AND department_pool_id = ?
        """, (candidate_id, pool_id))
        return cursor.rowcount > 0


def auto_archive_old_candidates(company_id: int) -> dict:
    """30 günden eski Genel Havuz adaylarını Arşiv'e taşı

    Günlük cron job olarak çalıştırılmalı.

    Returns:
        {'archived': int, 'errors': int}
    """
    stats = {'archived': 0, 'errors': 0}

    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    archive_pool = get_pool_by_name(company_id, 'Arşiv')

    if not general_pool or not archive_pool:
        return stats

    with get_connection() as conn:
        cursor = conn.cursor()

        # 30 günden eski CV'ler (olusturma_tarihi'ne göre)
        cursor.execute("""
            SELECT cpa.candidate_id 
            FROM candidate_pool_assignments cpa
            JOIN candidates c ON cpa.candidate_id = c.id
            WHERE cpa.department_pool_id = ?
            AND julianday('now') - julianday(c.olusturma_tarihi) > 30
        """, (general_pool['id'],))

        old_candidates = [row[0] for row in cursor.fetchall()]

        for candidate_id in old_candidates:
            try:
                # Arşiv'e taşı
                cursor.execute("""
                    UPDATE candidate_pool_assignments
                    SET department_pool_id = ?,
                        match_reason = 'Otomatik arşivlendi (30 gün)'
                    WHERE candidate_id = ? AND department_pool_id = ?
                """, (archive_pool['id'], candidate_id, general_pool['id']))

                stats['archived'] += 1
            except Exception:
                stats['errors'] += 1

    return stats


def auto_delete_expired_candidates(company_id: int) -> dict:
    """30 günden eski Arşiv adaylarını sil

    FK Constraint Güvenliği:
    - delete_candidate() fonksiyonunu kullanarak tüm bağımlı tabloları güvenli şekilde temizler
    
    Günlük cron job olarak çalıştırılmalı.
    KVKK uyumluluğu için audit log tutulur.

    Returns:
        {'deleted': int, 'errors': int}
    """
    stats = {'deleted': 0, 'errors': 0}

    archive_pool = get_pool_by_name(company_id, 'Arşiv')
    if not archive_pool:
        return stats

    with get_connection() as conn:
        cursor = conn.cursor()

        # 30 günden eski adayları bul (olusturma_tarihi'ne göre)
        cursor.execute("""
            SELECT c.id, c.ad_soyad, c.email, c.olusturma_tarihi
            FROM candidate_pool_assignments cpa
            JOIN candidates c ON cpa.candidate_id = c.id
            WHERE cpa.department_pool_id = ?
            AND julianday('now') - julianday(c.olusturma_tarihi) > 30
        """, (archive_pool['id'],))

        expired_candidates = cursor.fetchall()

        for candidate in expired_candidates:
            try:
                candidate_id, name, email, olusturma_tarihi = candidate

                # Audit log (anonim)
                cursor.execute("""
                    INSERT INTO audit_logs (action, entity_type, entity_id, details, created_at)
                    VALUES ('AUTO_DELETE', 'candidate', ?, ?, datetime('now'))
                """, (candidate_id, f"Arşiv süresi doldu. Adı: {name[:3]}***, Email: ***@***"))

                # FK Constraint Güvenliği: delete_candidate() kullanarak tüm bağımlı tabloları temizle
                # Bu fonksiyon safe_delete_with_fk() kullanarak dinamik olarak tüm FK bağımlılıklarını temizler
                delete_result = delete_candidate(candidate_id, company_id)
                
                if delete_result.get('success'):
                    stats['deleted'] += 1
                else:
                    stats['errors'] += 1
                    logger.error(f"auto_delete_expired_candidates: Aday {candidate_id} silinemedi: {delete_result.get('error')}")

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"auto_delete_expired_candidates: Aday {candidate_id} silinirken hata: {e}")

        conn.commit()

    return stats


def get_candidates_expiring_soon(company_id: int, days: int = 7) -> list[dict]:
    """Yakında süresi dolacak adayları getir (uyarı için)

    Args:
        company_id: Şirket ID
        days: Kaç gün içinde dolacaklar

    Returns:
        [{'candidate_id': X, 'name': Y, 'pool': 'Genel Havuz'/'Arşiv', 'remaining_days': Z}]
    """
    results = []

    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    archive_pool = get_pool_by_name(company_id, 'Arşiv')

    with get_connection() as conn:
        cursor = conn.cursor()

        # Genel Havuz - 30 güne yaklaşanlar (olusturma_tarihi'ne göre)
        if general_pool:
            cursor.execute("""
                SELECT c.id, c.ad_soyad, 'Genel Havuz' as pool,
                       30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) as remaining_days
                FROM candidate_pool_assignments cpa
                JOIN candidates c ON cpa.candidate_id = c.id
                WHERE cpa.department_pool_id = ?
                AND 30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) <= ?
                AND 30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) > 0
            """, (general_pool['id'], days))
            results.extend([dict(row) for row in cursor.fetchall()])

        # Arşiv - 30 güne yaklaşanlar (olusturma_tarihi'ne göre)
        if archive_pool:
            cursor.execute("""
                SELECT c.id, c.ad_soyad, 'Arşiv' as pool,
                       30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) as remaining_days
                FROM candidate_pool_assignments cpa
                JOIN candidates c ON cpa.candidate_id = c.id
                WHERE cpa.department_pool_id = ?
                AND 30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) <= ?
                AND 30 - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) > 0
            """, (archive_pool['id'], days))
            results.extend([dict(row) for row in cursor.fetchall()])

    return sorted(results, key=lambda x: x['remaining_days'])


def pull_matching_candidates_to_position(position_pool_id: int, company_id: int) -> dict:
    """Pozisyonun onaylı başlıklarına uyan CV'leri Genel Havuz ve Arşiv'den çek (v2 Title Match)

    Kullanıcı "CV Çek" butonuna tıkladığında çağrılır.
    SADECE pozisyon başlığı eşleşmesi olan adayları pozisyona ekler.
    Keyword ve sektör eşleşmesi tek başına yetmez.

    Returns:
        {'total_scanned': int, 'matched': int, 'transferred': int, 'already_exists': int,
         'from_general': int, 'from_archive': int}
    """
    stats = {'total_scanned': 0, 'matched': 0, 'transferred': 0, 'already_exists': 0,
             'from_general': 0, 'from_archive': 0}

    # Pozisyon bilgilerini al
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, keywords, gerekli_deneyim_yil, gerekli_egitim, lokasyon FROM department_pools WHERE id = ?", (position_pool_id,))
        row = cursor.fetchone()
        if not row:
            return stats
        
        position_name = row[0] or ''
        position_keywords = row[1] or ''
        position_exp_years = row[2] or 0
        position_education = row[3] or ''
        position_location = row[4] or ''

    # approved_title_mappings tablosundan onaylı başlıkları al
    from scoring_v2 import get_title_mappings, turkish_lower
    try:
        from thefuzz import fuzz
    except ImportError:
        fuzz = None
    
    title_mappings = get_title_mappings(position_pool_id)
    
    # Pozisyon adını da ekle (exact match için)
    if position_name:
        if 'exact' not in title_mappings:
            title_mappings['exact'] = []
        if position_name not in title_mappings['exact']:
            title_mappings['exact'].append(position_name)
    
    # Eğer hiç onaylı başlık yoksa, pozisyona atama yapma
    if not any(title_mappings.values()):
        logger.warning(f"pull_matching_candidates_to_position({position_pool_id}): Onaylı başlık yok, atama yapılmıyor")
        return stats

    # Kaynak havuzları belirle (Genel Havuz, Arşiv için sayaç)
    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    archive_pool = get_pool_by_name(company_id, 'Arşiv')
    general_pool_id = general_pool['id'] if general_pool else None
    archive_pool_id = archive_pool['id'] if archive_pool else None

    with get_connection() as conn:
        cursor = conn.cursor()

        # TÜM firma adaylarını al (hangi havuzda olursa olsun)
        cursor.execute("""
            SELECT DISTINCT c.id, c.ad_soyad, c.cv_raw_text, c.teknik_beceriler, c.mevcut_pozisyon, 
                   c.deneyim_detay, c.toplam_deneyim_yil, c.egitim, c.lokasyon, c.mevcut_sirket
            FROM candidates c
            WHERE c.company_id = ?
        """, (company_id,))

        candidates = cursor.fetchall()
        stats['total_scanned'] = len(candidates)

        for cand in candidates:
            # sqlite3.Row objesi dict gibi erişilebilir
            candidate_id = cand['id']
            ad_soyad = cand['ad_soyad'] or ''
            cv_text = cand['cv_raw_text'] or ''
            skills = cand['teknik_beceriler'] or ''
            current_pos = cand['mevcut_pozisyon'] or ''
            experience = cand['deneyim_detay'] or ''
            exp_years = cand['toplam_deneyim_yil'] or 0
            education = cand['egitim'] or ''
            location = cand['lokasyon'] or ''
            company = cand['mevcut_sirket'] or ''

            # Adayın pozisyon başlıklarını bul
            candidate_titles = []
            if current_pos:
                candidate_titles.append(current_pos)
            
            # deneyim_detay'dan pozisyon başlıkları çıkar
            import re
            if experience:
                pos_patterns = re.findall(r'(?:Pozisyon|Unvan|Görev)[:\s]+([^,\n]+)', experience, re.IGNORECASE)
                candidate_titles.extend(pos_patterns)
            
            # Title eşleşmesi kontrolü
            title_match_found = False
            title_match_score = 0
            
            for title in candidate_titles:
                title_normalized = turkish_lower(title.strip())
                if not title_normalized:
                    continue
                
                # Exact match
                for exact_title in title_mappings.get('exact', []):
                    if turkish_lower(exact_title) == title_normalized:
                        title_match_found = True
                        title_match_score = 23
                        break
                
                if title_match_found:
                    break
                
                # Close match (fuzzy >= 85)
                if fuzz:
                    for close_title in title_mappings.get('close', []):
                        ratio = fuzz.ratio(title_normalized, turkish_lower(close_title))
                        if ratio >= 85:
                            if title_match_score < 14:
                                title_match_score = 14
                                title_match_found = True
                                break
                
                if title_match_found and title_match_score >= 14:
                    break
                
                # Partial match (fuzzy >= 70)
                if fuzz:
                    for partial_title in title_mappings.get('partial', []):
                        ratio = fuzz.ratio(title_normalized, turkish_lower(partial_title))
                        if ratio >= 70:
                            if title_match_score < 7:
                                title_match_score = 7
                                title_match_found = True
                                break
            
            # title_match_score == 0 ise skip et (pozisyon başlığı eşleşmesi yok)
            if not title_match_found or title_match_score == 0:
                continue
            
            stats['matched'] += 1

            # Aday max 5 pozisyonda olabilir - kontrol et
            current_pos_count = get_candidate_position_count(candidate_id)
            if current_pos_count >= 1:
                continue  # Limit dolmuş, atla

            # Zaten bu pozisyonda mı kontrol et (candidate_positions tablosu)
            cursor.execute("""
                SELECT 1 FROM candidate_positions
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, position_pool_id))

            if cursor.fetchone():
                stats['already_exists'] += 1
                continue

            # v2 scoring ile skor hesapla
            candidate_dict = {
                'id': candidate_id,
                'ad_soyad': ad_soyad or '',
                'teknik_beceriler': skills or '',
                'toplam_deneyim_yil': exp_years or 0,
                'egitim': education or '',
                'lokasyon': location or '',
                'cv_raw_text': cv_text or '',
                'deneyim_detay': experience or '',
                'mevcut_pozisyon': current_pos or '',
                'mevcut_sirket': company or ''
            }
            
            position_dict = {
                'id': position_pool_id,
                'name': position_name,
                'keywords': position_keywords,
                'gerekli_deneyim_yil': position_exp_years or 0,
                'gerekli_egitim': position_education or '',
                'lokasyon': position_location or ''
            }
            
            # v2 scoring ile skor hesapla
            try:
                from scoring_v2 import calculate_match_score_v2
                v2_result = calculate_match_score_v2(candidate_dict, position_dict)
                if v2_result:
                    match_score = v2_result.get('total', 0)
                else:
                    # v2 verisi yok, title_match_score'u kullan
                    match_score = title_match_score
            except Exception as e:
                logger.warning(f"v2 scoring hatası, title_match_score kullanılıyor: {e}")
                match_score = title_match_score

            # YENİ SİSTEM: candidate_positions tablosuna ekle
            try:
                # Foreign key kontrolü: candidate_id ve position_id geçerli mi?
                cursor.execute("SELECT 1 FROM candidates WHERE id = ?", (candidate_id,))
                if not cursor.fetchone():
                    logger.warning(f"candidate_id={candidate_id} bulunamadı, atlanıyor")
                    continue
                
                cursor.execute("SELECT 1 FROM department_pools WHERE id = ? AND pool_type = 'position'", (position_pool_id,))
                if not cursor.fetchone():
                    logger.warning(f"position_id={position_pool_id} bulunamadı veya pozisyon değil, atlanıyor")
                    continue
                
                cursor.execute("""
                    INSERT OR IGNORE INTO candidate_positions
                    (candidate_id, position_id, match_score, status, created_at)
                    VALUES (?, ?, ?, 'aktif', datetime('now'))
                """, (candidate_id, position_pool_id, match_score))
                inserted = cursor.rowcount > 0
                if not inserted:
                    logger.debug(f"candidate_positions INSERT başarısız (muhtemelen zaten mevcut): candidate_id={candidate_id}, position_id={position_pool_id}")
            except sqlite3.IntegrityError as e:
                # Foreign key constraint hatası
                logger.error(f"FOREIGN KEY constraint hatası: candidate_id={candidate_id}, position_id={position_pool_id}, hata={e}")
                inserted = False
            except Exception as e:
                logger.error(f"candidate_positions INSERT hatası: {e}", exc_info=True)
                inserted = False

            # ESKİ SİSTEM: candidate_pool_assignments tablosuna da ekle (uyumluluk için)
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO candidate_pool_assignments
                    (candidate_id, department_pool_id, assignment_type, match_score, match_reason, assigned_at)
                    VALUES (?, ?, 'auto', ?, 'Title eşleşmesi (v2)', datetime('now'))
                """, (candidate_id, position_pool_id, match_score))
            except Exception as e:
                logger.debug(f"[DEBUG] candidate_pool_assignments INSERT hatası: {e}")

            if inserted:
                stats['transferred'] += 1
                # Havuz alanını güncelle
                cursor.execute("UPDATE candidates SET havuz = 'pozisyona_aktarilan', durum = 'pozisyona_atandi' WHERE id = ?", (candidate_id,))

                # Hangi havuzdan geldi? (istatistik)
                cursor.execute("""
                    SELECT department_pool_id FROM candidate_pool_assignments
                    WHERE candidate_id = ? AND department_pool_id IN (?, ?)
                """, (candidate_id, general_pool_id or 0, archive_pool_id or 0))
                source_row = cursor.fetchone()
                if source_row:
                    if source_row[0] == general_pool_id:
                        stats['from_general'] += 1
                    elif source_row[0] == archive_pool_id:
                        stats['from_archive'] += 1

    return stats


# ============ HAVUZ YÖNETİM FONKSİYONLARI (RESTORE) ============

def move_candidate_to_pool(candidate_id: int, from_position_id: int, to_position_id: int) -> bool:
    """Adayi bir pozisyon havuzundan digerine tasi (candidate_positions tablosunda)
    
    Args:
        candidate_id: Aday ID
        from_position_id: Kaynak pozisyon ID (department_pools.id)
        to_position_id: Hedef pozisyon ID (department_pools.id)
    
    Returns:
        True: Başarılı, False: Kayıt bulunamadı
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Eski havuzdan bilgileri al (candidate_positions tablosundan)
        cursor.execute("""
            SELECT match_score, status FROM candidate_positions
            WHERE position_id = ? AND candidate_id = ?
        """, (from_position_id, candidate_id))
        old_pool = cursor.fetchone()

        if old_pool:
            match_score = old_pool[0] or 0
            status = old_pool[1] or 'aktif'
            
            # Yeni havuza ekle (candidate_positions)
            cursor.execute("""
                INSERT OR REPLACE INTO candidate_positions
                (candidate_id, position_id, match_score, status, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (candidate_id, to_position_id, match_score, status))

            # Eski havuzdan cikar (candidate_positions)
            cursor.execute("""
                DELETE FROM candidate_positions
                WHERE position_id = ? AND candidate_id = ?
            """, (from_position_id, candidate_id))

            # Geriye uyumluluk: candidate_pool_assignments tablosunu da güncelle
            try:
                # Eski kaydı sil
                cursor.execute("""
                    DELETE FROM candidate_pool_assignments
                    WHERE department_pool_id = ? AND candidate_id = ?
                """, (from_position_id, candidate_id))
                
                # Yeni kaydı ekle
                cursor.execute("""
                    INSERT OR REPLACE INTO candidate_pool_assignments
                    (candidate_id, department_pool_id, assignment_type, match_score, match_reason, assigned_at)
                    VALUES (?, ?, 'auto', ?, 'Pozisyon değişikliği', datetime('now'))
                """, (candidate_id, to_position_id, match_score))
            except Exception as e:
                logger.debug(f"candidate_pool_assignments move hatası (göz ardı edildi): {e}")

            return True
        return False


def batch_move_candidates_to_pool(candidate_ids: list, from_position_id: int, to_position_id: int) -> int:
    """Birden fazla adayi toplu olarak tasi"""
    moved_count = 0
    for candidate_id in candidate_ids:
        if move_candidate_to_pool(candidate_id, from_position_id, to_position_id):
            moved_count += 1
    return moved_count


def get_department_pool(pool_id: int) -> Optional[dict]:
    """Tek bir departman havuzunu getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM department_pools WHERE id = ?", (pool_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def create_department_pool(company_id: int, name: str, icon: str = '📁',
                           keywords: list = None, description: str = '',
                           parent_id: int = None, pool_type: str = 'department',
                           gerekli_deneyim_yil: float = 0, gerekli_egitim: str = '',
                           lokasyon: str = '', aranan_nitelikler: str = None,
                           is_tanimi: str = None) -> int:
    """Yeni departman veya pozisyon havuzu oluştur"""
    keywords_json = json.dumps(keywords or [], ensure_ascii=False)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO department_pools (company_id, parent_id, pool_type, name, icon, keywords, description, 
                                          gerekli_deneyim_yil, gerekli_egitim, lokasyon, aranan_nitelikler, is_tanimi, is_system)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (company_id, parent_id, pool_type, name, icon, keywords_json, description,
              gerekli_deneyim_yil, gerekli_egitim, lokasyon, aranan_nitelikler, is_tanimi))
        pool_id = cursor.lastrowid
    
    # Cache'i temizle
    invalidate_cache(f"dept_pools_{company_id}")
    return pool_id


def update_department_pool(pool_id: int, company_id: int = None, **fields) -> bool:
    """Departman havuzunu güncelle"""
    # Sahiplik kontrolü
    if company_id:
        if not verify_department_pool_ownership(pool_id, company_id):
            raise PermissionError("Bu havuza erişim yetkiniz yok")

    if 'keywords' in fields and isinstance(fields['keywords'], list):
        fields['keywords'] = json.dumps(fields['keywords'], ensure_ascii=False)

    allowed = ['name', 'icon', 'keywords', 'description', 'is_active', 'parent_id', 'pool_type',
               'gerekli_deneyim_yil', 'gerekli_egitim', 'lokasyon']
    updates = {k: v for k, v in fields.items() if k in allowed}

    if not updates:
        return False

    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [pool_id]

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(f"""
                UPDATE department_pools SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND is_system = 0 AND company_id = ?
            """, values + [company_id])
        else:
            cursor.execute(f"""
                UPDATE department_pools SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND is_system = 0
            """, values)
        success = cursor.rowcount > 0
    
    # Cache'i temizle
    if success and company_id:
        invalidate_cache(f"dept_pools_{company_id}")
    return success


def delete_department_pool(pool_id: int, company_id: int = None) -> bool:
    """Departman havuzunu tamamen sil (hard delete)
    
    FK Constraint Güvenliği:
    - Önce v2 tablolarını (position_keywords_v2, position_title_mappings, etc.) temizler
    - Sonra candidate_pool_assignments ve candidate_positions temizler
    - En son department_pools'tan siler
    """
    # Sahiplik kontrolü
    if company_id:
        if not verify_department_pool_ownership(pool_id, company_id):
            raise PermissionError("Bu havuza erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Sistem havuzu mu kontrol et
        cursor.execute("SELECT is_system, company_id FROM department_pools WHERE id = ?", (pool_id,))
        row = cursor.fetchone()
        if not row or row[0] == 1:  # Sistem havuzu silinemez
            return False

        pool_company_id = row[1]

        # Alt pozisyonları bul (önce alt pozisyonları silmeliyiz)
        cursor.execute("""
            SELECT id FROM department_pools WHERE parent_id = ?
        """, (pool_id,))
        child_pools = [row[0] for row in cursor.fetchall()]
        
        # Alt pozisyonları önce sil (recursive)
        for child_pool_id in child_pools:
            delete_department_pool(child_pool_id, pool_company_id)

        # Adayları CV yaşına göre Genel Havuz veya Arşiv'e taşı
        # handle_position_deletion() fonksiyonu candidate_positions tablosunu temizler
        # ve adayları uygun havuza taşır (30 günden yeni -> Genel Havuz, eski -> Arşiv)
        handle_position_deletion(pool_id, pool_company_id, conn=conn)

        # FK Constraint Güvenliği: v2 tablolarını ve diğer bağımlı tabloları temizle
        # safe_delete_with_fk() kullanarak dinamik olarak tüm bağımlı tabloları temizle
        delete_result = safe_delete_with_fk(
            cursor=cursor,
            table_name='department_pools',
            where_clause='id = ?',
            params=(pool_id,),
            fk_column='position_id'
        )
        
        if delete_result['errors']:
            logger.warning(f"delete_department_pool: Bazı bağımlı tablolar temizlenirken hata oluştu: {delete_result['errors']}")

        # candidate_pool_assignments tablosundan eski kayıtları temizle
        # (handle_position_deletion() yeni kayıt ekliyor, eski kayıtları kaldırmalıyız)
        cursor.execute("""
            DELETE FROM candidate_pool_assignments
            WHERE department_pool_id = ?
        """, (pool_id,))

        # safe_delete_with_fk zaten havuzu sildi, sonucunu dön
        return delete_result.get("success", False) and delete_result.get("deleted_from_main", 0) > 0


def get_department_pool_candidates(pool_id: int) -> list[dict]:
    """Departman havuzundaki adayları getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, cpa.assignment_type, cpa.match_score, cpa.match_reason, cpa.assigned_at
            FROM candidate_pool_assignments cpa
            JOIN candidates c ON cpa.candidate_id = c.id
            WHERE cpa.department_pool_id = ?
            ORDER BY cpa.match_score DESC, cpa.assigned_at DESC
        """, (pool_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_department_pool_stats(company_id: int) -> list[dict]:
    """Tüm departman havuzlarının istatistiklerini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dp.id, dp.name, dp.icon, dp.is_system, dp.keywords, dp.description,
                   dp.parent_id, dp.pool_type,
                   COUNT(DISTINCT CASE WHEN c.id IS NOT NULL THEN cpa.candidate_id END) as candidate_count
            FROM department_pools dp
            LEFT JOIN candidate_pool_assignments cpa ON dp.id = cpa.department_pool_id
            LEFT JOIN candidates c ON cpa.candidate_id = c.id
            WHERE dp.company_id = ? AND dp.is_active = 1
            GROUP BY dp.id
            ORDER BY dp.is_system DESC, dp.name
        """, (company_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_hierarchical_pool_stats(company_id: int) -> list[dict]:
    """Hiyerarşik havuz istatistikleri (departman -> pozisyon)
    
    PERFORMANS: Tek JOIN sorgusu ile tüm veriyi çeker (N+1 query sorununu önler)
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # PERFORMANS: Tüm departman ve pozisyonları tek sorguda çek
        cursor.execute("""
            SELECT 
                dept.id as dept_id,
                dept.name as dept_name,
                dept.icon as dept_icon,
                dept.is_system as dept_is_system,
                dept.keywords as dept_keywords,
                dept.description as dept_description,
                dept.parent_id as dept_parent_id,
                dept.pool_type as dept_pool_type,
                COUNT(DISTINCT CASE WHEN c_dept.id IS NOT NULL THEN cpa.candidate_id END) as dept_candidate_count,
                pos.id as pos_id,
                pos.name as pos_name,
                pos.icon as pos_icon,
                pos.keywords as pos_keywords,
                pos.description as pos_description,
                pos.parent_id as pos_parent_id,
                pos.pool_type as pos_pool_type,
                pos.gerekli_deneyim_yil as pos_gerekli_deneyim_yil,
                pos.gerekli_egitim as pos_gerekli_egitim,
                pos.lokasyon as pos_lokasyon,
                COUNT(DISTINCT CASE WHEN c_pos.id IS NOT NULL THEN cp.candidate_id END) as pos_candidate_count
            FROM department_pools dept
            LEFT JOIN candidate_pool_assignments cpa ON dept.id = cpa.department_pool_id
            LEFT JOIN candidates c_dept ON cpa.candidate_id = c_dept.id AND c_dept.company_id = ?
            LEFT JOIN department_pools pos ON pos.parent_id = dept.id AND pos.is_active = 1 AND pos.pool_type = 'position'
            LEFT JOIN candidate_positions cp ON pos.id = cp.position_id
            LEFT JOIN candidates c_pos ON cp.candidate_id = c_pos.id AND c_pos.company_id = ?
            WHERE dept.company_id = ? 
                AND dept.is_active = 1
                AND (dept.pool_type = 'department' OR dept.pool_type IS NULL)
                AND dept.parent_id IS NULL
                AND dept.is_system = 0
            GROUP BY dept.id, pos.id
            ORDER BY dept.name, pos.name
        """, (company_id, company_id, company_id))
        
        rows = cursor.fetchall()
        
        # Sonuçları departman bazında grupla
        departments_dict = {}
        for row in rows:
            row_dict = dict(row)
            dept_id = row_dict['dept_id']
            
            # Departman bilgilerini ilk kez görüyorsak ekle
            if dept_id not in departments_dict:
                departments_dict[dept_id] = {
                    'id': dept_id,
                    'name': row_dict['dept_name'],
                    'icon': row_dict['dept_icon'],
                    'is_system': row_dict['dept_is_system'],
                    'keywords': row_dict['dept_keywords'],
                    'description': row_dict['dept_description'],
                    'parent_id': row_dict['dept_parent_id'],
                    'pool_type': row_dict['dept_pool_type'],
                    'candidate_count': row_dict['dept_candidate_count'] or 0,
                    'positions': [],
                    'total_position_candidates': 0
                }
            
            # Pozisyon bilgisi varsa ekle
            if row_dict['pos_id']:
                pos_candidate_count = row_dict['pos_candidate_count'] or 0
                departments_dict[dept_id]['positions'].append({
                    'id': row_dict['pos_id'],
                    'name': row_dict['pos_name'],
                    'icon': row_dict['pos_icon'],
                    'keywords': row_dict['pos_keywords'],
                    'description': row_dict['pos_description'],
                    'parent_id': row_dict['pos_parent_id'],
                    'pool_type': row_dict['pos_pool_type'],
                    'gerekli_deneyim_yil': row_dict.get('pos_gerekli_deneyim_yil') or 0,
                    'gerekli_egitim': row_dict.get('pos_gerekli_egitim') or '',
                    'lokasyon': row_dict.get('pos_lokasyon') or '',
                    'candidate_count': pos_candidate_count
                })
                departments_dict[dept_id]['total_position_candidates'] += pos_candidate_count
        
        # Dict'i listeye çevir ve pozisyonları sırala
        departments = list(departments_dict.values())
        for dept in departments:
            dept['positions'].sort(key=lambda x: x['name'])
        
        return departments


def move_candidate_to_department_pool(candidate_id: int, target_pool_id: int, company_id: int, reason: str = 'Manuel taşıma') -> int:
    """Adayı başka bir departman havuzuna taşı"""
    return assign_candidate_to_department_pool(
        candidate_id, target_pool_id, company_id, 'manual', 0, reason
    )


def reassign_all_candidates_to_positions(company_id: int) -> dict:
    """Genel Havuz'daki adayları eşleşen pozisyonlara taşı"""
    stats = {'total': 0, 'matched': 0, 'assignments': 0}

    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    if not general_pool:
        return stats

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT candidate_id FROM candidate_pool_assignments
            WHERE department_pool_id = ?
        """, (general_pool['id'],))
        candidates = [row[0] for row in cursor.fetchall()]

    stats['total'] = len(candidates)

    for candidate_id in candidates:
        matches = find_all_matching_positions(candidate_id, company_id)

        if matches:
            stats['matched'] += 1

            for match in matches:
                reason = f"{', '.join(match['keywords'][:3])} eslesti"
                assign_candidate_to_department_pool(
                    candidate_id, match['pool_id'], company_id, 'auto', match['score'], reason
                )
                stats['assignments'] += 1

    return stats


def transfer_candidates_to_position(candidate_ids: list[int], target_pool_id: int,
                                    source_pool_id: int, user_id: int = None) -> dict:
    """Seçili adayları kaynak havuzdan hedef pozisyon havuzuna taşı"""
    stats = {'success': 0, 'failed': 0, 'already_exists': 0}

    with get_connection() as conn:
        cursor = conn.cursor()

        for candidate_id in candidate_ids:
            try:
                cursor.execute("""
                    SELECT 1 FROM candidate_pool_assignments
                    WHERE candidate_id = ? AND department_pool_id = ?
                """, (candidate_id, target_pool_id))

                if cursor.fetchone():
                    stats['already_exists'] += 1
                    continue

                cursor.execute("""
                    INSERT INTO candidate_pool_assignments
                    (candidate_id, department_pool_id, assignment_type, match_score, match_reason, assigned_at)
                    VALUES (?, ?, 'manual', 0, 'Manuel transfer', datetime('now'))
                """, (candidate_id, target_pool_id))

                cursor.execute("""
                    DELETE FROM candidate_pool_assignments
                    WHERE candidate_id = ? AND department_pool_id = ?
                """, (candidate_id, source_pool_id))

                stats['success'] += 1

            except Exception as e:
                stats['failed'] += 1

    return stats


def get_pool_candidates_with_days(pool_id: int, pool_type: str = 'general') -> list[dict]:
    """Havuzdaki adayları kalan gün bilgisiyle getir"""
    max_days = 30 if pool_type == 'general' else 30

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, c.olusturma_tarihi,
                   ? - CAST(julianday('now') - julianday(c.olusturma_tarihi) AS INTEGER) as remaining_days
            FROM candidate_pool_assignments cpa
            JOIN candidates c ON cpa.candidate_id = c.id
            WHERE cpa.department_pool_id = ?
            ORDER BY c.olusturma_tarihi DESC
        """, (max_days, pool_id))

        results = []
        for row in cursor.fetchall():
            candidate = dict(row)
            if candidate.get('remaining_days', 0) < 0:
                candidate['remaining_days'] = 0
            results.append(candidate)

        return results


def sync_candidates_to_all_positions(company_id: int) -> dict:
    """Tüm pozisyonlar için aday eşleştirmesi yap"""
    stats = {
        'positions_scanned': 0,
        'total_transferred': 0,
        'position_results': []
    }

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, keywords
            FROM department_pools
            WHERE company_id = ?
            AND pool_type = 'position'
            AND is_active = 1
            AND keywords IS NOT NULL
            AND keywords != '[]'
        """, (company_id,))

        positions = cursor.fetchall()
        stats['positions_scanned'] = len(positions)

        for pos in positions:
            pos_id, pos_name, _ = pos
            result = pull_matching_candidates_to_position(pos_id, company_id)

            stats['total_transferred'] += result.get('transferred', 0)
            stats['position_results'].append({
                'position_id': pos_id,
                'position_name': pos_name,
                'transferred': result.get('transferred', 0),
                'matched': result.get('matched', 0),
                'already_exists': result.get('already_exists', 0)
            })

    return stats


def remove_candidate_from_pool(position_id: int, candidate_id: int) -> bool:
    """Adayi havuzdan cikar (candidate_positions tablosundan)
    
    Args:
        position_id: Pozisyon ID (department_pools.id)
        candidate_id: Aday ID
    
    Returns:
        True: Başarılı, False: Kayıt bulunamadı
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # candidate_positions tablosundan sil
        cursor.execute(
            "DELETE FROM candidate_positions WHERE position_id = ? AND candidate_id = ?",
            (position_id, candidate_id)
        )
        deleted = cursor.rowcount > 0
        
        # Geriye uyumluluk: candidate_pool_assignments tablosundan da sil
        try:
            cursor.execute(
                "DELETE FROM candidate_pool_assignments WHERE department_pool_id = ? AND candidate_id = ?",
                (position_id, candidate_id)
            )
        except Exception as e:
            logger.debug(f"candidate_pool_assignments silme hatası (göz ardı edildi): {e}")
        
        return deleted


def get_candidates_by_general_pool(pool_type: str, company_id: int = None) -> list[dict]:
    """Genel havuza gore adaylari getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if pool_type == "yetenek_havuzu":
            query = """
                SELECT c.*,
                       (SELECT COUNT(*) FROM applications WHERE candidate_id = c.id) as basvuru_sayisi,
                       (SELECT MAX(basvuru_tarihi) FROM applications WHERE candidate_id = c.id) as son_basvuru
                FROM candidates c
                WHERE c.id NOT IN (SELECT DISTINCT candidate_id FROM position_pools)
            """
        elif pool_type == "bekleme_havuzu":
            query = """
                SELECT c.*,
                       (SELECT COUNT(*) FROM applications WHERE candidate_id = c.id) as basvuru_sayisi,
                       (SELECT MAX(basvuru_tarihi) FROM applications WHERE candidate_id = c.id) as son_basvuru
                FROM candidates c
                WHERE (c.email IS NULL OR c.email = '' OR c.telefon IS NULL OR c.telefon = '')
            """
        elif pool_type == "arsiv":
            query = """
                SELECT c.*,
                       (SELECT COUNT(*) FROM applications WHERE candidate_id = c.id) as basvuru_sayisi,
                       (SELECT MAX(basvuru_tarihi) FROM applications WHERE candidate_id = c.id) as son_basvuru
                FROM candidates c
                WHERE c.olusturma_tarihi < date('now', '-30 days')
                   OR c.id IN (SELECT DISTINCT candidate_id FROM position_pools WHERE durum = 'red')
            """
        else:
            query = """
                SELECT c.*,
                       (SELECT COUNT(*) FROM applications WHERE candidate_id = c.id) as basvuru_sayisi,
                       (SELECT MAX(basvuru_tarihi) FROM applications WHERE candidate_id = c.id) as son_basvuru
                FROM candidates c
                WHERE c.havuz = ?
            """

        params = []
        if pool_type not in ["yetenek_havuzu", "bekleme_havuzu", "arsiv"]:
            params.append(pool_type)

        if company_id:
            query += " AND c.company_id = ?" if "WHERE" in query else " WHERE c.company_id = ?"
            params.append(company_id)

        query += " ORDER BY c.olusturma_tarihi DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def batch_update_pool_status(position_id: int, candidate_ids: list, durum: str) -> int:
    """Birden fazla adayin havuz durumunu guncelle (candidate_positions tablosunda)
    
    Args:
        position_id: Pozisyon ID (department_pools.id)
        candidate_ids: Aday ID listesi
        durum: Yeni durum (beklemede, inceleniyor, mulakat, teklif, red)
    
    Returns:
        Güncellenen kayıt sayısı
    """
    if not candidate_ids:
        return 0
    
    # durum → status mapping
    status_map = {
        'beklemede': 'beklemede',
        'inceleniyor': 'inceleniyor',
        'mulakat': 'mulakat',
        'teklif': 'teklif',
        'red': 'red',
        'aktif': 'aktif'  # Geriye uyumluluk
    }
    status_value = status_map.get(durum, durum)
    
    updated = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in candidate_ids])
        cursor.execute(f"""
            UPDATE candidate_positions SET status = ?
            WHERE position_id = ? AND candidate_id IN ({placeholders})
        """, [status_value, position_id] + candidate_ids)
        updated = cursor.rowcount
        
        # Geriye uyumluluk: candidate_pool_assignments tablosunu da güncelle
        try:
            cursor.execute(f"""
                UPDATE candidate_pool_assignments
                SET match_reason = ?
                WHERE department_pool_id = ? AND candidate_id IN ({placeholders})
            """, [f"Durum: {durum}", position_id] + candidate_ids)
        except Exception as e:
            logger.debug(f"candidate_pool_assignments batch update hatası (göz ardı edildi): {e}")
    
    return updated


# ============ BASVURU ISLEMLERI ============

def create_application(application: Application, company_id: int = None) -> int:
    """Yeni basvuru olustur

    Args:
        application: Application nesnesi
        company_id: Firma ID (güvenlik için önerilir - adayın firmaya ait olduğu doğrulanır)

    Raises:
        PermissionError: Aday bu firmaya ait değilse
    """
    # Adayın bu firmaya ait olduğunu doğrula
    if company_id:
        if not verify_candidate_ownership(application.candidate_id, company_id):
            raise PermissionError("Bu adaya erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO applications (candidate_id, position_id, kaynak, email_id, basvuru_tarihi)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            application.candidate_id, application.position_id,
            application.kaynak, application.email_id,
            application.basvuru_tarihi.isoformat() if application.basvuru_tarihi else datetime.now().isoformat()
        ))
        return cursor.lastrowid


def get_all_applications(company_id: int = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """Tum basvurulari getir (aday ve pozisyon bilgileriyle, pagination destekli)

    Args:
        company_id: Firma ID (opsiyonel)
        limit: Sayfa başına kayıt sayısı (default: 100)
        offset: Atlanacak kayıt sayısı (default: 0)

    Returns:
        list[dict]: Başvuru listesi
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute("""
                SELECT a.*,
                       c.ad_soyad, c.email as aday_email, c.telefon, c.linkedin, c.mevcut_pozisyon,
                       c.toplam_deneyim_yil, c.cv_dosya_yolu,
                       p.baslik as pozisyon_baslik, p.departman, p.lokasyon
                FROM applications a
                JOIN candidates c ON a.candidate_id = c.id
                LEFT JOIN positions p ON a.position_id = p.id
                WHERE c.company_id = ?
                ORDER BY a.basvuru_tarihi DESC
                LIMIT ? OFFSET ?
            """, (company_id, limit, offset))
        else:
            cursor.execute("""
                SELECT a.*,
                       c.ad_soyad, c.email as aday_email, c.telefon, c.linkedin, c.mevcut_pozisyon,
                       c.toplam_deneyim_yil, c.cv_dosya_yolu,
                       p.baslik as pozisyon_baslik, p.departman, p.lokasyon
                FROM applications a
                JOIN candidates c ON a.candidate_id = c.id
                LEFT JOIN positions p ON a.position_id = p.id
                ORDER BY a.basvuru_tarihi DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]


def get_applications_count(company_id: int = None) -> int:
    """Toplam başvuru sayısını getir

    Args:
        company_id: Firma ID (opsiyonel)

    Returns:
        int: Toplam başvuru sayısı
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute("""
                SELECT COUNT(*) FROM applications a
                JOIN candidates c ON a.candidate_id = c.id
                WHERE c.company_id = ?
            """, (company_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM applications")
        return cursor.fetchone()[0]


def get_candidates_with_application_stats(company_id: int = None, havuz: str = None,
                                          durum: str = None, arama: str = None) -> list[dict]:
    """Adaylari basvuru istatistikleriyle birlikte getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT c.*,
                   COUNT(a.id) as basvuru_sayisi,
                   MAX(a.basvuru_tarihi) as son_basvuru_tarihi
            FROM candidates c
            LEFT JOIN applications a ON c.id = a.candidate_id
            WHERE 1=1
        """
        params = []

        if company_id:
            query += " AND c.company_id = ?"
            params.append(company_id)

        if havuz:
            query += " AND c.havuz = ?"
            params.append(havuz)

        if durum:
            query += " AND c.durum = ?"
            params.append(durum)

        if arama:
            # Türkçe karakterler için case-insensitive arama
            query += """ AND (LOWER(c.ad_soyad) LIKE LOWER(?) OR LOWER(c.email) LIKE LOWER(?)
                        OR LOWER(c.teknik_beceriler) LIKE LOWER(?) OR LOWER(c.telefon) LIKE LOWER(?)
                        OR LOWER(c.mevcut_pozisyon) LIKE LOWER(?) OR LOWER(c.lokasyon) LIKE LOWER(?))"""
            search_term = f"%{arama}%"
            params.extend([search_term, search_term, search_term, search_term, search_term, search_term])

        query += " GROUP BY c.id ORDER BY c.olusturma_tarihi DESC"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ============ ESLESTIRME ISLEMLERI ============

def save_match(match: Match) -> int:
    """Eslestirme sonucu kaydet"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Get company_id from candidate
        cursor.execute("SELECT company_id FROM candidates WHERE id = ?", (match.candidate_id,))
        row = cursor.fetchone()
        company_id = row[0] if row else None
        
        cursor.execute("""
            INSERT OR REPLACE INTO matches (
                candidate_id, position_id, uyum_puani, detayli_analiz,
                deneyim_puani, egitim_puani, beceri_puani, company_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match.candidate_id, match.position_id, match.uyum_puani,
            match.detayli_analiz, match.deneyim_puani,
            match.egitim_puani, match.beceri_puani, company_id
        ))
        return cursor.lastrowid


# ============ EMAIL LOG ISLEMLERI ============

def log_email(email_log: EmailLog) -> int:
    """Email logunu kaydet"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO email_logs (
                email_id, gonderen, konu, tarih, ek_sayisi, islendi, hata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            email_log.email_id, email_log.gonderen, email_log.konu,
            email_log.tarih, email_log.ek_sayisi, email_log.islendi,
            email_log.hata
        ))
        return cursor.lastrowid


def is_email_processed(email_id: str) -> bool:
    """Email daha once islendi mi?"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM email_logs WHERE email_id = ? AND islendi = 1",
            (email_id,)
        )
        return cursor.fetchone() is not None


def mark_email_processed(email_id: str, hata: Optional[str] = None):
    """Emaili islendi olarak isaretle"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_logs
            SET islendi = 1, hata = ?, islem_tarihi = ?
            WHERE email_id = ?
        """, (hata, datetime.now().isoformat(), email_id))


# ============ MULAKAT ISLEMLERI ============

def create_interview(interview: Interview, company_id: int = None) -> int:
    """Yeni mulakat olustur

    Args:
        interview: Interview nesnesi
        company_id: Firma ID (güvenlik için önerilir - adayın firmaya ait olduğu doğrulanır)

    Raises:
        PermissionError: Aday bu firmaya ait değilse
    """
    # Adayın bu firmaya ait olduğunu doğrula
    if company_id:
        if not verify_candidate_ownership(interview.candidate_id, company_id):
            raise PermissionError("Bu adaya erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interviews (
                candidate_id, position_id, tarih, sure_dakika, company_id,
                tur, lokasyon, mulakatci, durum, notlar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            interview.candidate_id, interview.position_id,
            interview.tarih.isoformat(), interview.sure_dakika, company_id,
            interview.tur, interview.lokasyon, interview.mulakatci,
            interview.durum, interview.notlar
        ))
        return cursor.lastrowid


def update_interview(interview_id: int, company_id: int = None, **fields) -> bool:
    """Mulakat bilgilerini guncelle

    Args:
        interview_id: Mülakat ID
        company_id: Firma ID (güvenlik için önerilir)
        **fields: Güncellenecek alanlar

    Raises:
        PermissionError: Mülakat bu firmaya ait değilse
    """
    if not fields:
        return False

    # Sahiplik kontrolü
    if company_id:
        if not verify_interview_ownership(interview_id, company_id):
            raise PermissionError("Bu mülakata erişim yetkiniz yok")

    # Tarih alanini ISO formatina cevir
    if "tarih" in fields and hasattr(fields["tarih"], "isoformat"):
        fields["tarih"] = fields["tarih"].isoformat()

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("interviews", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE interviews SET {set_clause} WHERE id = ?",
            (*values, interview_id)
        )
        return cursor.rowcount > 0


def get_interviews(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    candidate_id: Optional[int] = None,
    durum: Optional[str] = None,
    company_id: Optional[int] = None
) -> list[dict]:
    """Mulakatlari getir (aday bilgileriyle birlikte)"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT i.*, c.ad_soyad, c.email, c.telefon, c.mevcut_pozisyon,
                   p.baslik as pozisyon_baslik
            FROM interviews i
            JOIN candidates c ON i.candidate_id = c.id
            LEFT JOIN positions p ON i.position_id = p.id
            WHERE 1=1
        """
        params = []

        if company_id:
            query += " AND c.company_id = ?"
            params.append(company_id)

        if start_date:
            query += " AND i.tarih >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND i.tarih <= ?"
            params.append(end_date.isoformat())

        if candidate_id:
            query += " AND i.candidate_id = ?"
            params.append(candidate_id)

        if durum:
            query += " AND i.durum = ?"
            params.append(durum)

        query += " ORDER BY i.tarih ASC"

        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            data = dict(row)
            if data.get("tarih"):
                data["tarih"] = datetime.fromisoformat(data["tarih"])
            results.append(data)
        return results


def delete_interview(interview_id: int, company_id: int = None) -> bool:
    """Mulakati sil

    Args:
        interview_id: Mülakat ID
        company_id: Firma ID (güvenlik için önerilir)

    Raises:
        PermissionError: Mülakat bu firmaya ait değilse
    """
    # Sahiplik kontrolü
    if company_id:
        if not verify_interview_ownership(interview_id, company_id):
            raise PermissionError("Bu mülakata erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
        return cursor.rowcount > 0


# ============ EMAIL HESAP ISLEMLERI ============

def create_email_account(
    ad: str,
    saglayici: str,
    email: str,
    sifre: str,
    imap_server: str,
    smtp_server: str,
    imap_port: int = 993,
    smtp_port: int = 587,
    sender_name: str = None,
    company_id: int = None
) -> int:
    """Yeni email hesabi ekle

    Args:
        company_id: Firma ID (zorunlu - veri izolasyonu için)

    Raises:
        ValueError: company_id verilmezse
    """
    if not company_id:
        raise ValueError("company_id zorunludur - veri izolasyonu için firma ID gereklidir")

    # Şifreyi şifrele
    encrypted_password = encrypt_email_password(sifre)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_accounts (
                company_id, ad, saglayici, email, sifre,
                imap_server, imap_port, smtp_server, smtp_port,
                sender_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id, ad, saglayici, email, encrypted_password,
            imap_server, imap_port, smtp_server, smtp_port,
            sender_name or ad
        ))
        return cursor.lastrowid


def _process_email_account(row) -> dict:
    """Email hesap satırını işle ve şifreyi çöz"""
    account = dict(row)
    if account.get("sifre"):
        account["sifre"] = decrypt_email_password(account["sifre"])
    return account


def get_all_email_accounts(only_active: bool = True, company_id: int = None) -> list[dict]:
    """Tum email hesaplarini getir (firma bazli)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            if only_active:
                cursor.execute("SELECT * FROM email_accounts WHERE aktif = 1 AND company_id = ? ORDER BY ad", (company_id,))
            else:
                cursor.execute("SELECT * FROM email_accounts WHERE company_id = ? ORDER BY ad", (company_id,))
        else:
            if only_active:
                cursor.execute("SELECT * FROM email_accounts WHERE aktif = 1 ORDER BY ad")
            else:
                cursor.execute("SELECT * FROM email_accounts ORDER BY ad")
        return [_process_email_account(row) for row in cursor.fetchall()]


def update_email_account(account_id: int, company_id: int = None, **fields) -> bool:
    """Email hesabi guncelle

    Args:
        account_id: Email hesap ID
        company_id: Firma ID (güvenlik için önerilir)
        **fields: Güncellenecek alanlar

    Raises:
        PermissionError: Hesap bu firmaya ait değilse
    """
    if not fields:
        return False

    # Sahiplik kontrolü
    if company_id:
        if not verify_email_account_ownership(account_id, company_id):
            raise PermissionError("Bu email hesabına erişim yetkiniz yok")

    # Şifre güncelleniyorsa şifrele
    if "sifre" in fields and fields["sifre"]:
        fields["sifre"] = encrypt_email_password(fields["sifre"])

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("email_accounts", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute(
                f"UPDATE email_accounts SET {set_clause} WHERE id = ? AND company_id = ?",
                (*values, account_id, company_id)
            )
        else:
            cursor.execute(
                f"UPDATE email_accounts SET {set_clause} WHERE id = ?",
                (*values, account_id)
            )
        return cursor.rowcount > 0


def delete_email_account(account_id: int, company_id: int = None) -> bool:
    """Email hesabi sil

    Args:
        account_id: Email hesap ID
        company_id: Firma ID (güvenlik için önerilir)

    Raises:
        PermissionError: Hesap bu firmaya ait değilse
    """
    # Sahiplik kontrolü
    if company_id:
        if not verify_email_account_ownership(account_id, company_id):
            raise PermissionError("Bu email hesabına erişim yetkiniz yok")

    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute("DELETE FROM email_accounts WHERE id = ? AND company_id = ?", (account_id, company_id))
        else:
            cursor.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))
        return cursor.rowcount > 0


def set_default_email_account(account_id: int, for_reading: bool = False, for_sending: bool = False) -> bool:
    """Varsayilan email hesabini ayarla"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if for_reading:
            # Once tum hesaplarin okuma varsayilanini kaldir
            cursor.execute("UPDATE email_accounts SET varsayilan_okuma = 0")
            cursor.execute("UPDATE email_accounts SET varsayilan_okuma = 1 WHERE id = ?", (account_id,))

        if for_sending:
            # Once tum hesaplarin gonderim varsayilanini kaldir
            cursor.execute("UPDATE email_accounts SET varsayilan_gonderim = 0")
            cursor.execute("UPDATE email_accounts SET varsayilan_gonderim = 1 WHERE id = ?", (account_id,))

        return True


def increment_email_account_cv_count(account_id: int, count: int = 1) -> bool:
    """Email hesabinin CV sayacini artir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE email_accounts SET toplam_cv = toplam_cv + ?, son_kontrol = ? WHERE id = ?",
            (count, datetime.now().isoformat(), account_id)
        )
        return cursor.rowcount > 0


def migrate_email_passwords():
    """Mevcut düz metin şifreleri şifrele"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, sifre FROM email_accounts")
        rows = cursor.fetchall()
        for row in rows:
            try:
                # Zaten şifreli mi kontrol et
                decrypt_email_password(row['sifre'])
            except Exception:
                # Düz metin, şifrele
                encrypted = encrypt_email_password(row['sifre'])
                cursor.execute("UPDATE email_accounts SET sifre = ? WHERE id = ?", (encrypted, row['id']))
        logger.info(f"{len(rows)} email hesabı kontrol edildi")


# ============ AI ANALIZ ISLEMLERI ============

def save_ai_analysis(
    candidate_id: int,
    analysis_type: str,
    analysis_data: str,
    skill_score: float = None,
    experience_score: float = None,
    education_score: float = None,
    overall_score: float = None,
    career_level: str = None,
    strengths: str = None,
    improvements: str = None,
    processing_time_ms: int = None,
    position_id: int = None
) -> int:
    """AI analiz sonucunu kaydet"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_analyses (
                candidate_id, analysis_type, analysis_data,
                skill_score, experience_score, education_score, overall_score,
                career_level, strengths, improvements, processing_time_ms, position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_id, analysis_type, analysis_data,
            skill_score, experience_score, education_score, overall_score,
            career_level, strengths, improvements, processing_time_ms, position_id
        ))
        return cursor.lastrowid


def get_ai_analysis(candidate_id: int, analysis_type: str = None) -> Optional[dict]:
    """Aday icin AI analizini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if analysis_type:
            cursor.execute(
                "SELECT * FROM ai_analyses WHERE candidate_id = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1",
                (candidate_id, analysis_type)
            )
        else:
            cursor.execute(
                "SELECT * FROM ai_analyses WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
                (candidate_id,)
            )
        row = cursor.fetchone()
        return dict(row) if row else None


# ============ IK DEGERLENDIRME ISLEMLERI ============

def save_hr_evaluation(
    candidate_id: int,
    position_id: int = None,
    evaluator_id: int = None,
    ik_puani: int = None,
    ik_notlari: str = None,
    durum: str = "beklemede"
) -> int:
    """IK degerlendirmesi kaydet veya guncelle"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Mevcut degerlendirme var mi kontrol et
        if position_id:
            cursor.execute("""
                SELECT id, durum FROM hr_evaluations
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, position_id))
        else:
            cursor.execute("""
                SELECT id, durum FROM hr_evaluations
                WHERE candidate_id = ? AND position_id IS NULL
            """, (candidate_id,))

        existing = cursor.fetchone()

        if existing:
            # Guncelle
            onceki_durum = existing["durum"]
            cursor.execute("""
                UPDATE hr_evaluations
                SET ik_puani = COALESCE(?, ik_puani),
                    ik_notlari = COALESCE(?, ik_notlari),
                    durum = ?,
                    onceki_durum = ?,
                    evaluator_id = COALESCE(?, evaluator_id),
                    guncelleme_tarihi = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (ik_puani, ik_notlari, durum, onceki_durum, evaluator_id, existing["id"]))
            return existing["id"]
        else:
            # Yeni kayit
            cursor.execute("""
                INSERT INTO hr_evaluations
                (candidate_id, position_id, evaluator_id, ik_puani, ik_notlari, durum)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (candidate_id, position_id, evaluator_id, ik_puani, ik_notlari, durum))
            return cursor.lastrowid


def get_hr_evaluation(candidate_id: int, position_id: int = None) -> dict:
    """Aday icin IK degerlendirmesini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if position_id:
            cursor.execute("""
                SELECT e.*, u.ad_soyad as evaluator_name
                FROM hr_evaluations e
                LEFT JOIN users u ON e.evaluator_id = u.id
                WHERE e.candidate_id = ? AND e.position_id = ?
            """, (candidate_id, position_id))
        else:
            cursor.execute("""
                SELECT e.*, u.ad_soyad as evaluator_name
                FROM hr_evaluations e
                LEFT JOIN users u ON e.evaluator_id = u.id
                WHERE e.candidate_id = ? AND e.position_id IS NULL
            """, (candidate_id,))

        row = cursor.fetchone()
        return dict(row) if row else {}


def get_all_hr_evaluations(candidate_id: int) -> list[dict]:
    """Aday icin tum IK degerlendirmelerini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, p.baslik as position_title, u.ad_soyad as evaluator_name
            FROM hr_evaluations e
            LEFT JOIN positions p ON e.position_id = p.id
            LEFT JOIN users u ON e.evaluator_id = u.id
            WHERE e.candidate_id = ?
            ORDER BY e.guncelleme_tarihi DESC
        """, (candidate_id,))
        return [dict(row) for row in cursor.fetchall()]


# ============ DASHBOARD ISTATISTIKLERI ============

def get_dashboard_stats(company_id: int = None) -> dict:
    """Dashboard icin ozet istatistikler"""
    with get_connection() as conn:
        cursor = conn.cursor()
        company_filter = "WHERE company_id = ?" if company_id else ""
        company_and_c = "AND c.company_id = ?" if company_id else ""
        params = [company_id] if company_id else []

        # Bugun gelen basvuru
        cursor.execute(f"""
            SELECT COUNT(*) FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            WHERE date(a.basvuru_tarihi) = date('now')
            {company_and_c}
        """, params)
        bugun_basvuru = cursor.fetchone()[0]

        # Degerlendirme bekleyen (havuzda beklemede duranlar)
        cursor.execute(f"""
            SELECT COUNT(DISTINCT pp.candidate_id) FROM position_pools pp
            JOIN candidates c ON pp.candidate_id = c.id
            WHERE pp.durum = 'beklemede'
            {company_and_c}
        """, params)
        bekleyen = cursor.fetchone()[0]

        # Aktif pozisyon sayisi (department_pools tablosundan)
        company_and_dp = "AND department_pools.company_id = ?" if company_id else ""
        cursor.execute(f"""
            SELECT COUNT(*) FROM department_pools
            WHERE pool_type = 'position' AND is_active = 1
            {company_and_dp}
        """, params)
        aktif_pozisyon = cursor.fetchone()[0]

        # Bu ay ise alinan
        cursor.execute(f"""
            SELECT COUNT(*) FROM hr_evaluations e
            JOIN candidates c ON e.candidate_id = c.id
            WHERE e.durum = 'ise_alindi'
            AND strftime('%Y-%m', e.guncelleme_tarihi) = strftime('%Y-%m', 'now')
            {company_and_c}
        """, params)
        bu_ay_ise_alinan = cursor.fetchone()[0]

        # Toplam aday
        cursor.execute(f"SELECT COUNT(*) FROM candidates {company_filter}", params)
        toplam_aday = cursor.fetchone()[0]

        # Toplam basvuru
        cursor.execute(f"""
            SELECT COUNT(*) FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            WHERE 1=1 {company_and_c}
        """, params)
        toplam_basvuru = cursor.fetchone()[0]

        # Mulakat bekleyen (durum='mulakat' olan adaylar)
        company_and_cand = "AND candidates.company_id = ?" if company_id else ""
        cursor.execute(f"""
            SELECT COUNT(*) FROM candidates
            WHERE durum = 'mulakat'
            {company_and_cand}
        """, params)
        mulakat_bekleyen = cursor.fetchone()[0]

        return {
            "bugun_basvuru": bugun_basvuru,
            "bekleyen": bekleyen,
            "mulakat_bekleyen": mulakat_bekleyen,
            "aktif_pozisyon": aktif_pozisyon,
            "bu_ay_ise_alinan": bu_ay_ise_alinan,
            "toplam_aday": toplam_aday,
            "toplam_basvuru": toplam_basvuru
        }


def get_recent_applications(company_id: int = None, limit: int = 10) -> list[dict]:
    """Son basvurular"""
    with get_connection() as conn:
        cursor = conn.cursor()
        company_and = "AND c.company_id = ?" if company_id else ""
        params = [company_id] if company_id else []
        params.append(limit)

        cursor.execute(f"""
            SELECT
                a.id,
                a.basvuru_tarihi,
                a.kaynak,
                c.ad_soyad,
                c.email,
                p.baslik as pozisyon
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            LEFT JOIN positions p ON a.position_id = p.id
            WHERE 1=1 {company_and}
            ORDER BY a.basvuru_tarihi DESC
            LIMIT ?
        """, params)

        return [dict(row) for row in cursor.fetchall()]


def get_recent_evaluations(company_id: int = None, limit: int = 10) -> list[dict]:
    """Son degerlendirmeler"""
    with get_connection() as conn:
        cursor = conn.cursor()
        company_and = "AND c.company_id = ?" if company_id else ""
        params = [company_id] if company_id else []
        params.append(limit)

        cursor.execute(f"""
            SELECT
                e.id,
                e.ik_puani,
                e.durum,
                e.guncelleme_tarihi,
                c.ad_soyad,
                p.baslik as pozisyon,
                u.ad_soyad as degerlendiren
            FROM hr_evaluations e
            JOIN candidates c ON e.candidate_id = c.id
            LEFT JOIN positions p ON e.position_id = p.id
            LEFT JOIN users u ON e.evaluator_id = u.id
            WHERE 1=1 {company_and}
            ORDER BY e.guncelleme_tarihi DESC
            LIMIT ?
        """, params)

        return [dict(row) for row in cursor.fetchall()]


# ============ FIRMA ISLEMLERI ============

def create_company(ad: str, slug: str, email: str = None, telefon: str = None,
                   adres: str = None, website: str = None, plan: str = "basic") -> int:
    """Yeni firma olustur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO companies (ad, slug, email, telefon, adres, website, plan)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ad, slug, email, telefon, adres, website, plan))
        return cursor.lastrowid


def get_company(company_id: int) -> Optional[dict]:
    """ID ile firma getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_company_by_slug(slug: str) -> Optional[dict]:
    """Slug ile firma getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        return dict(row) if row else None


def toggle_company_status(company_id: int) -> dict:
    """Firma aktiflik durumunu degistir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Mevcut durumu al
        cursor.execute("SELECT aktif, ad FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "Firma bulunamadi"}
        
        current_status = row[0]
        company_name = row[1]
        new_status = 0 if current_status else 1
        
        # Durumu guncelle
        cursor.execute("UPDATE companies SET aktif = ? WHERE id = ?", (new_status, company_id))
        conn.commit()
        
        return {
            "success": True,
            "company_id": company_id,
            "company_name": company_name,
            "aktif": bool(new_status)
        }


def get_all_companies(only_active: bool = True) -> list[dict]:
    """Tum firmalari getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if only_active:
            cursor.execute("SELECT * FROM companies WHERE aktif = 1 ORDER BY ad")
        else:
            cursor.execute("SELECT * FROM companies ORDER BY ad")
        return [dict(row) for row in cursor.fetchall()]


def update_company(company_id: int, **fields) -> bool:
    """Firma bilgilerini guncelle"""
    if not fields:
        return False

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("companies", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE companies SET {set_clause} WHERE id = ?",
            (*values, company_id)
        )
        return cursor.rowcount > 0


# ============ SUPER ADMIN - FİRMA YÖNETİMİ ============

def get_all_companies_admin() -> list[dict]:
    """
    Super admin için tüm firmalar + istatistikler

    Returns:
        Liste of dict: Firma bilgileri + kullanıcı sayısı, CV sayısı, pozisyon sayısı
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.*,
                (SELECT COUNT(*) FROM users WHERE company_id = c.id) as kullanici_sayisi,
                (SELECT COUNT(*) FROM candidates WHERE company_id = c.id) as cv_sayisi,
                (SELECT COUNT(*) FROM positions WHERE company_id = c.id) as pozisyon_sayisi
            FROM companies c
            ORDER BY c.ad
        """)
        return [dict(row) for row in cursor.fetchall()]


def create_company_with_admin(
    firma_adi: str,
    yetkili_adi: str,
    yetkili_email: str,
    yetkili_telefon: str = None,
    adres: str = None,
    sozlesme_baslangic: str = None,
    sozlesme_bitis: str = None,
    notlar: str = None,
    plan_id: int = 1,
    trial_ends_at: str = None
) -> dict:
    """
    Firma ve company_admin kullanıcısı birlikte oluştur

    Args:
        firma_adi: Firma adı
        yetkili_adi: Yetkili kişi adı soyadı
        yetkili_email: Yetkili email (aynı zamanda login email)
        yetkili_telefon: Telefon
        adres: Adres
        sozlesme_baslangic: Sözleşme başlangıç tarihi
        sozlesme_bitis: Sözleşme bitiş tarihi
        notlar: Notlar
        plan_id: Plan ID (plans tablosundan)
        trial_ends_at: Deneme süresi bitiş tarihi

    Returns:
        dict: {'company_id': X, 'user_id': Y, 'temp_password': 'XXX'}
    """
    import secrets
    import re

    # Slug oluştur
    slug = re.sub(r'[^a-z0-9]+', '-', firma_adi.lower()).strip('-')

    # Benzersiz slug kontrolü
    base_slug = slug
    counter = 1
    while get_company_by_slug(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Geçici şifre oluştur (8 karakter)
    temp_password = secrets.token_urlsafe(6)  # ~8 karakter

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Firma oluştur
        cursor.execute("""
            INSERT INTO companies (
                ad, slug, email, telefon, adres, plan_id,
                aktif, durum,
                yetkili_adi, yetkili_email, yetkili_telefon,
                sozlesme_baslangic, sozlesme_bitis, notlar, trial_ends_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'aktif', ?, ?, ?, ?, ?, ?, ?)
        """, (
            firma_adi, slug, yetkili_email, yetkili_telefon, adres, plan_id,
            yetkili_adi, yetkili_email, yetkili_telefon,
            sozlesme_baslangic, sozlesme_bitis, notlar, trial_ends_at
        ))
        company_id = cursor.lastrowid

        # 2. Company admin kullanıcısı oluştur
        hashed_pw = hash_password(temp_password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, ad_soyad, company_id, rol, aktif)
            VALUES (?, ?, ?, ?, 'company_admin', 1)
        """, (yetkili_email, hashed_pw, yetkili_adi, company_id))
        user_id = cursor.lastrowid

        conn.commit()

        return {
            'company_id': company_id,
            'user_id': user_id,
            'temp_password': temp_password,
            'slug': slug
        }


def create_company_user(
    company_id: int,
    email: str,
    ad_soyad: str,
    rol: str = 'user'
) -> dict:
    """
    Mevcut firmaya yeni kullanıcı ekle

    Args:
        company_id: Firma ID
        email: Kullanıcı email adresi
        ad_soyad: Kullanıcı adı soyadı
        rol: Kullanıcı rolü ('user' veya 'company_admin')

    Returns:
        dict: {'user_id': X, 'temp_password': 'XXX'}
    """
    import secrets

    # Email kontrolü
    existing_user = get_user_by_email(email)
    if existing_user:
        raise ValueError(f"Bu email adresi zaten kayıtlı: {email}")

    # Firma kontrolü
    company = get_company(company_id)
    if not company:
        raise ValueError(f"Firma bulunamadı: {company_id}")

    # Rol kontrolü
    if rol not in ['user', 'company_admin']:
        rol = 'user'

    # Geçici şifre oluştur
    temp_password = secrets.token_urlsafe(6)

    with get_connection() as conn:
        cursor = conn.cursor()

        hashed_pw = hash_password(temp_password)
        cursor.execute("""
            INSERT INTO users (email, password_hash, ad_soyad, company_id, rol, aktif)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (email, hashed_pw, ad_soyad, company_id, rol))
        user_id = cursor.lastrowid

        conn.commit()

        return {
            'user_id': user_id,
            'temp_password': temp_password
        }


def update_company_status(company_id: int, durum: str) -> bool:
    """
    Firma durumunu güncelle

    Args:
        company_id: Firma ID
        durum: 'aktif', 'askida', 'pasif'

    Returns:
        bool: Güncelleme başarılı mı?
    """
    if durum not in ['aktif', 'askida', 'pasif']:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE companies SET durum = ?, aktif = ? WHERE id = ?",
            (durum, 1 if durum == 'aktif' else 0, company_id)
        )
        return cursor.rowcount > 0


def delete_company_soft(company_id: int) -> bool:
    """
    Firmayı soft delete yap (durum='silindi')

    Args:
        company_id: Firma ID

    Returns:
        bool: Silme başarılı mı?
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Firma durumunu güncelle
        cursor.execute(
            "UPDATE companies SET durum = 'silindi', aktif = 0 WHERE id = ?",
            (company_id,)
        )

        # Firma kullanıcılarını pasif yap
        cursor.execute(
            "UPDATE users SET aktif = 0 WHERE company_id = ?",
            (company_id,)
        )

        return cursor.rowcount > 0


def get_super_admin_stats() -> dict:
    """
    Super admin için genel istatistikler

    Returns:
        dict: {
            'toplam_firma': int,
            'aktif_firma': int,
            'askida_firma': int,
            'toplam_kullanici': int,
            'toplam_cv': int,
            'toplam_pozisyon': int,
            'son_30_gun_cv': int
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Firma sayıları
        cursor.execute("SELECT COUNT(*) FROM companies WHERE durum != 'silindi' OR durum IS NULL")
        toplam_firma = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM companies WHERE (durum = 'aktif' OR durum IS NULL) AND aktif = 1")
        aktif_firma = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM companies WHERE durum = 'askida'")
        askida_firma = cursor.fetchone()[0]

        # Kullanıcı sayısı
        cursor.execute("SELECT COUNT(*) FROM users WHERE aktif = 1")
        toplam_kullanici = cursor.fetchone()[0]

        # CV sayısı
        cursor.execute("SELECT COUNT(*) FROM candidates")
        toplam_cv = cursor.fetchone()[0]

        # Pozisyon sayısı
        cursor.execute("SELECT COUNT(*) FROM positions")
        toplam_pozisyon = cursor.fetchone()[0]

        # Son 30 gün CV
        cursor.execute("""
            SELECT COUNT(*) FROM candidates
            WHERE olusturma_tarihi >= date('now', '-30 days')
        """)
        son_30_gun_cv = cursor.fetchone()[0]

        return {
            'toplam_firma': toplam_firma,
            'aktif_firma': aktif_firma,
            'askida_firma': askida_firma,
            'toplam_kullanici': toplam_kullanici,
            'toplam_cv': toplam_cv,
            'toplam_pozisyon': toplam_pozisyon,
            'son_30_gun_cv': son_30_gun_cv
        }


def get_company_wise_stats() -> list[dict]:
    """
    Firma bazlı CV, pozisyon ve kullanıcı istatistikleri (Super Admin için)

    Returns:
        list[dict]: Her firma için istatistikler
            - company_id: Firma ID
            - company_name: Firma adı
            - cv_count: Toplam CV sayısı
            - position_count: Toplam pozisyon sayısı
            - user_count: Toplam kullanıcı sayısı
            - last_cv_date: Son CV yükleme tarihi
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                c.id as company_id,
                c.ad as company_name,
                c.plan,
                c.aktif,
                COALESCE(cv.cv_count, 0) as cv_count,
                COALESCE(p.position_count, 0) as position_count,
                COALESCE(u.user_count, 0) as user_count,
                cv.last_cv_date
            FROM companies c
            LEFT JOIN (
                SELECT company_id, COUNT(*) as cv_count, MAX(olusturma_tarihi) as last_cv_date
                FROM candidates
                GROUP BY company_id
            ) cv ON c.id = cv.company_id
            LEFT JOIN (
                SELECT company_id, COUNT(*) as position_count
                FROM positions
                GROUP BY company_id
            ) p ON c.id = p.company_id
            LEFT JOIN (
                SELECT company_id, COUNT(*) as user_count
                FROM users
                WHERE aktif = 1
                GROUP BY company_id
            ) u ON c.id = u.company_id
            WHERE c.durum != 'silindi' OR c.durum IS NULL
            ORDER BY cv.cv_count DESC NULLS LAST, c.ad
        """)
        return [dict(row) for row in cursor.fetchall()]


def is_company_active(company_id: int) -> bool:
    """
    Firma aktif mi kontrol et

    Args:
        company_id: Firma ID

    Returns:
        bool: Firma aktif mi? (durum='aktif' ve aktif=1)
    """
    if not company_id:
        return True  # company_id yoksa (super_admin) aktif kabul et

    company = get_company(company_id)
    if not company:
        return False

    durum = company.get('durum', 'aktif')
    aktif = company.get('aktif', 1)

    return durum == 'aktif' and aktif == 1


# ============ PLAN VE LİMİT YÖNETİMİ ============

class LimitExceededError(Exception):
    """Plan limiti aşıldığında fırlatılır"""
    pass


def get_all_plans(active_only: bool = True) -> list[dict]:
    """
    Tüm planları getir

    Args:
        active_only: Sadece aktif planları getir

    Returns:
        list[dict]: Plan listesi
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM plans WHERE is_active = 1 ORDER BY price_monthly ASC")
        else:
            cursor.execute("SELECT * FROM plans ORDER BY price_monthly ASC")
        return [dict(row) for row in cursor.fetchall()]


def get_plan(plan_id: int) -> Optional[dict]:
    """
    Plan detayları

    Args:
        plan_id: Plan ID

    Returns:
        dict: Plan bilgileri veya None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_plan_by_name(plan_name: str) -> Optional[dict]:
    """
    Plan adına göre plan getir

    Args:
        plan_name: Plan adı (trial, starter, professional, enterprise)

    Returns:
        dict: Plan bilgileri veya None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE name = ?", (plan_name,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_company_plan(company_id: int) -> Optional[dict]:
    """
    Firmanın planı ve limitleri

    Args:
        company_id: Firma ID

    Returns:
        dict: Plan bilgileri veya None (varsayılan plan dönülür)
    """
    if not company_id:
        # Super admin için enterprise plan
        return get_plan_by_name('enterprise')

    company = get_company(company_id)
    if not company:
        return None

    plan_id = company.get('plan_id', 1)
    plan = get_plan(plan_id)

    if not plan:
        # Varsayılan olarak trial planı dön
        plan = get_plan_by_name('trial')

    return plan


def set_company_plan(company_id: int, plan_id: int, trial_ends_at: str = None) -> bool:
    """
    Firmaya plan ata (super_admin yetkisi gerektirir)

    Args:
        company_id: Firma ID
        plan_id: Yeni plan ID
        trial_ends_at: Deneme süresi bitiş tarihi (YYYY-MM-DD)

    Returns:
        bool: Başarılı mı?
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if trial_ends_at:
            cursor.execute("""
                UPDATE companies SET plan_id = ?, trial_ends_at = ?
                WHERE id = ?
            """, (plan_id, trial_ends_at, company_id))
        else:
            cursor.execute("""
                UPDATE companies SET plan_id = ?
                WHERE id = ?
            """, (plan_id, company_id))
        return cursor.rowcount > 0


def check_limit(company_id: int, limit_type: str) -> dict:
    """
    Limit kontrolü

    Args:
        company_id: Firma ID
        limit_type: 'users', 'cvs', 'positions', 'departments'

    Returns:
        dict: {
            'allowed': True/False,
            'current': 5,
            'max': 10,
            'remaining': 5,
            'unlimited': False
        }
    """
    plan = get_company_plan(company_id)
    if not plan:
        # Plan yoksa varsayılan limitler
        plan = {'max_users': 2, 'max_cvs': 50, 'max_positions': 3, 'max_departments': 2}

    # Limit değerini al
    limit_map = {
        'users': 'max_users',
        'cvs': 'max_cvs',
        'positions': 'max_positions',
        'departments': 'max_departments'
    }

    max_value = plan.get(limit_map.get(limit_type, 'max_cvs'), 50)

    # -1 = sınırsız
    if max_value == -1:
        return {
            'allowed': True,
            'current': _get_current_count(company_id, limit_type),
            'max': -1,
            'remaining': -1,
            'unlimited': True
        }

    # Mevcut kullanım
    current = _get_current_count(company_id, limit_type)
    remaining = max(0, max_value - current)

    return {
        'allowed': current < max_value,
        'current': current,
        'max': max_value,
        'remaining': remaining,
        'unlimited': False
    }


def _get_current_count(company_id: int, limit_type: str) -> int:
    """Mevcut kullanım sayısını getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if limit_type == 'users':
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE company_id = ? AND aktif = 1
            """, (company_id,))
        elif limit_type == 'cvs':
            cursor.execute("""
                SELECT COUNT(*) FROM candidates
                WHERE company_id = ?
            """, (company_id,))
        elif limit_type == 'positions':
            cursor.execute("""
                SELECT COUNT(*) FROM positions
                WHERE company_id = ? AND aktif = 1
            """, (company_id,))
        elif limit_type == 'departments':
            cursor.execute("""
                SELECT COUNT(*) FROM department_pools
                WHERE company_id = ? AND pool_type = 'department'
            """, (company_id,))
        else:
            return 0

        return cursor.fetchone()[0]


if st is not None:
    @st.cache_data(ttl=60, show_spinner=False)
    def get_company_usage_cached(company_id: int) -> dict:
        """
        get_company_usage() için cache wrapper.
        60 saniye TTL ile cache'ler.
        """
        return get_company_usage(company_id)
else:
    def get_company_usage_cached(company_id: int) -> dict:
        """
        get_company_usage() için cache wrapper (Streamlit yoksa direkt çağır).
        """
        return get_company_usage(company_id)


def get_company_usage(company_id: int) -> dict:
    """
    Firma kullanım istatistikleri

    Args:
        company_id: Firma ID

    Returns:
        dict: {
            'users': {'current': 3, 'max': 10, 'percentage': 30, 'unlimited': False},
            'cvs': {'current': 150, 'max': 1000, 'percentage': 15, 'unlimited': False},
            'positions': {'current': 8, 'max': 50, 'percentage': 16, 'unlimited': False},
            'departments': {'current': 4, 'max': 15, 'percentage': 27, 'unlimited': False},
            'plan': {...}
        }
    """
    plan = get_company_plan(company_id)
    usage = {}

    for limit_type in ['users', 'cvs', 'positions', 'departments']:
        limit_info = check_limit(company_id, limit_type)

        if limit_info['unlimited']:
            percentage = 0
        elif limit_info['max'] > 0:
            percentage = int((limit_info['current'] / limit_info['max']) * 100)
        else:
            percentage = 100

        usage[limit_type] = {
            'current': limit_info['current'],
            'max': limit_info['max'],
            'percentage': min(percentage, 100),
            'unlimited': limit_info['unlimited']
        }

    usage['plan'] = plan
    return usage


def check_and_raise_limit(company_id: int, limit_type: str):
    """
    Limit kontrolü yap, aşılmışsa hata fırlat

    Args:
        company_id: Firma ID
        limit_type: 'users', 'cvs', 'positions', 'departments'

    Raises:
        LimitExceededError: Limit aşılmışsa
    """
    limit = check_limit(company_id, limit_type)
    if not limit['allowed']:
        label_map = {
            'users': 'Kullanıcı',
            'cvs': 'CV',
            'positions': 'Pozisyon',
            'departments': 'Departman'
        }
        label = label_map.get(limit_type, limit_type)
        raise LimitExceededError(
            f"{label} limitine ulaşıldı ({limit['current']}/{limit['max']}). "
            f"Limitinizi artırmak için planınızı yükseltin."
        )


# ============ KULLANICI ISLEMLERI ============

def validate_password(password: str) -> tuple[bool, list[str]]:
    """
    Şifre kurallarını kontrol et

    Kurallar:
    - Minimum 8 karakter
    - En az 1 büyük harf (A-Z)
    - En az 1 küçük harf (a-z)
    - En az 1 rakam (0-9)
    - En az 1 özel karakter (!@#$%^&*()_+-=)

    Args:
        password: Kontrol edilecek şifre

    Returns:
        tuple: (is_valid, error_messages)
    """
    errors = []

    if len(password) < 8:
        errors.append("Şifre en az 8 karakter olmalı")
    if not re.search(r'[A-Z]', password):
        errors.append("En az 1 büyük harf olmalı (A-Z)")
    if not re.search(r'[a-z]', password):
        errors.append("En az 1 küçük harf olmalı (a-z)")
    if not re.search(r'\d', password):
        errors.append("En az 1 rakam olmalı (0-9)")
    if not re.search(r'[!@#$%^&*()_+\-=]', password):
        errors.append("En az 1 özel karakter olmalı (!@#$%^&*()_+-=)")

    return len(errors) == 0, errors


def get_password_strength(password: str) -> dict:
    """
    Şifre gücünü hesapla

    Returns:
        dict: {
            'score': 0-100,
            'level': 'weak'|'medium'|'strong'|'very_strong',
            'label': 'Zayıf'|'Orta'|'Güçlü'|'Çok Güçlü',
            'color': 'red'|'orange'|'green'|'darkgreen',
            'checks': {...}
        }
    """
    score = 0
    checks = {
        'length_8': len(password) >= 8,
        'length_12': len(password) >= 12,
        'length_16': len(password) >= 16,
        'uppercase': bool(re.search(r'[A-Z]', password)),
        'lowercase': bool(re.search(r'[a-z]', password)),
        'digit': bool(re.search(r'\d', password)),
        'special': bool(re.search(r'[!@#$%^&*()_+\-=]', password)),
        'no_common': password.lower() not in ['password', '12345678', 'qwerty123', 'admin123']
    }

    # Puanlama
    if checks['length_8']:
        score += 20
    if checks['length_12']:
        score += 10
    if checks['length_16']:
        score += 10
    if checks['uppercase']:
        score += 15
    if checks['lowercase']:
        score += 15
    if checks['digit']:
        score += 15
    if checks['special']:
        score += 15
    if checks['no_common']:
        score += 0  # Bonus değil, zorunlu
    else:
        score = min(score, 20)  # Yaygın şifre ise düşür

    # Seviye belirleme
    if score >= 80:
        level, label, color = 'very_strong', 'Çok Güçlü', 'darkgreen'
    elif score >= 60:
        level, label, color = 'strong', 'Güçlü', 'green'
    elif score >= 40:
        level, label, color = 'medium', 'Orta', 'orange'
    else:
        level, label, color = 'weak', 'Zayıf', 'red'

    return {
        'score': score,
        'level': level,
        'label': label,
        'color': color,
        'checks': checks
    }


def hash_password(password: str) -> str:
    """Sifreyi bcrypt ile hashle"""
    import bcrypt
    # bcrypt hash oluştur ve string olarak döndür
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, stored_hash: str) -> bool:
    """Sifreyi dogrula (bcrypt veya eski SHA256)"""
    import bcrypt
    import hashlib

    try:
        # Önce bcrypt olarak dene
        if stored_hash.startswith('$2'):
            # bcrypt hash
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        else:
            # Eski SHA256 hash - geriye uyumluluk
            sha256_hash = hashlib.sha256(password.encode()).hexdigest()
            return stored_hash == sha256_hash
    except Exception:
        return False


def migrate_password_to_bcrypt(user_id: int, plain_password: str) -> bool:
    """Eski SHA256 sifresini bcrypt'e migrate et"""
    new_hash = hash_password(plain_password)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        return cursor.rowcount > 0


def is_bcrypt_hash(hash_str: str) -> bool:
    """Hash'in bcrypt formunda olup olmadigini kontrol et"""
    return hash_str.startswith('$2') if hash_str else False


def create_user(email: str, password: str, ad_soyad: str,
                company_id: int = None, rol: str = "user") -> int:
    """Yeni kullanici olustur

    Raises:
        LimitExceededError: Kullanıcı limiti aşılmışsa (company_id varsa)
    """
    # Limit kontrolü (company_id varsa)
    if company_id:
        check_and_raise_limit(company_id, 'users')

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (email, password_hash, ad_soyad, company_id, rol)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, hash_password(password), ad_soyad, company_id, rol))
        return cursor.lastrowid


def get_user_by_email(email: str) -> Optional[dict]:
    """Email ile kullanici getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user(user_id: int) -> Optional[dict]:
    """ID ile kullanici getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def verify_user(email: str, password: str) -> Optional[dict]:
    """Kullanici dogrula ve bilgilerini getir"""
    user = get_user_by_email(email)
    if user and user["aktif"]:
        # Firma aktiflik kontrolu (super_admin harici)
        if user.get("company_id"):
            company = get_company(user["company_id"])
            if not company or not company.get("aktif"):
                return None  # Firma pasif - login engelle
        
        stored_hash = user["password_hash"]

        # Sifre dogrulama
        if verify_password(password, stored_hash):
            # Eski SHA256 hash ise bcrypt'e migrate et
            if not stored_hash.startswith('$2'):
                migrate_password_to_bcrypt(user["id"], password)

            # Son giris tarihini guncelle
            update_user_last_login(user["id"])
            return user
    return None


def update_user_last_login(user_id: int):
    """Son giris tarihini guncelle"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET son_giris = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )


def get_users_by_company(company_id: int) -> list[dict]:
    """Firma kullanicilarini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE company_id = ? ORDER BY ad_soyad",
            (company_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def update_user(user_id: int, **fields) -> bool:
    """Kullanici bilgilerini guncelle"""
    if not fields:
        return False

    # Sifre varsa hashle
    if "password" in fields:
        fields["password_hash"] = hash_password(fields.pop("password"))

    # Guvenli alan adi dogrulama
    set_clause, values = safe_set_clause("users", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            (*values, user_id)
        )
        return cursor.rowcount > 0


def delete_user(user_id: int) -> bool:
    """Kullaniciyi sil"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


# ============ FİRMA ADMIN - KULLANICI YÖNETİMİ ============

def generate_temp_password() -> str:
    """
    Güvenli geçici şifre oluştur (tüm kurallara uygun)

    Oluşturulan şifre:
    - 12 karakter uzunluğunda
    - En az 1 büyük harf
    - En az 1 küçük harf
    - En az 1 rakam
    - En az 1 özel karakter

    Returns:
        str: Güvenli geçici şifre
    """
    import secrets
    import string

    # Zorunlu karakterler
    password = [
        secrets.choice(string.ascii_uppercase),  # 1 büyük harf
        secrets.choice(string.ascii_lowercase),  # 1 küçük harf
        secrets.choice(string.digits),           # 1 rakam
        secrets.choice("!@#$%^&*()_+-="),        # 1 özel karakter
    ]

    # Kalan karakterler (rastgele)
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
    password.extend(secrets.choice(all_chars) for _ in range(8))  # Toplam 12 karakter

    # Sırayı karıştır
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def get_company_users_detailed(company_id: int) -> list[dict]:
    """
    Firmaya ait tüm kullanıcıları detaylı getir

    Args:
        company_id: Firma ID

    Returns:
        Liste of dict: Kullanıcı bilgileri
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                u.*,
                (SELECT ad_soyad FROM users WHERE id = u.created_by) as created_by_name
            FROM users u
            WHERE u.company_id = ?
            ORDER BY u.ad_soyad
        """, (company_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_company_user_stats(company_id: int) -> dict:
    """
    Firma kullanıcı istatistikleri

    Returns:
        dict: {toplam, aktif, pasif, admin_sayisi}
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users WHERE company_id = ?", (company_id,))
        toplam = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE company_id = ? AND aktif = 1", (company_id,))
        aktif = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE company_id = ? AND rol = 'company_admin'", (company_id,))
        admin_sayisi = cursor.fetchone()[0]

        return {
            'toplam': toplam,
            'aktif': aktif,
            'pasif': toplam - aktif,
            'admin_sayisi': admin_sayisi
        }


def create_user_with_temp_password(
    company_id: int,
    email: str,
    ad_soyad: str,
    rol: str = 'user',
    created_by: int = None
) -> dict:
    """
    Geçici şifre ile yeni kullanıcı oluştur

    Args:
        company_id: Firma ID
        email: Email adresi
        ad_soyad: Ad soyad
        rol: Rol (user veya company_admin)
        created_by: Oluşturan kullanıcı ID

    Returns:
        dict: {'user_id': X, 'temp_password': 'XXX'}

    Raises:
        ValueError: Email zaten kullanılıyorsa
        LimitExceededError: Kullanıcı limiti aşılmışsa
    """
    # Limit kontrolü
    check_and_raise_limit(company_id, 'users')

    # Email kontrolü
    existing = get_user_by_email(email)
    if existing:
        raise ValueError(f"Bu email adresi zaten kullanılıyor: {email}")

    # Rol kontrolü (super_admin oluşturulamaz)
    if rol not in ['user', 'company_admin']:
        rol = 'user'

    # Geçici şifre oluştur
    temp_password = generate_temp_password()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (
                email, password_hash, ad_soyad, company_id, rol,
                aktif, must_change_password, created_by
            ) VALUES (?, ?, ?, ?, ?, 1, 1, ?)
        """, (
            email,
            hash_password(temp_password),
            ad_soyad,
            company_id,
            rol,
            created_by
        ))

        return {
            'user_id': cursor.lastrowid,
            'temp_password': temp_password
        }


def update_user_by_company_admin(
    user_id: int,
    company_id: int,
    current_user_id: int,
    **fields
) -> bool:
    """
    Company admin tarafından kullanıcı güncelleme

    Args:
        user_id: Güncellenecek kullanıcı ID
        company_id: İşlemi yapan adminin firma ID
        current_user_id: İşlemi yapan admin ID
        **fields: Güncellenecek alanlar

    Returns:
        bool: Güncelleme başarılı mı?

    Raises:
        PermissionError: Yetkisiz erişim
        ValueError: Geçersiz işlem
    """
    # Kullanıcıyı getir
    user = get_user(user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı")

    # Aynı firmadan olmalı
    if user.get('company_id') != company_id:
        raise PermissionError("Bu kullanıcıyı düzenleme yetkiniz yok")

    # super_admin düzenlenemez
    if user.get('rol') == 'super_admin':
        raise PermissionError("Super admin düzenlenemez")

    # Kendi rolünü düşüremez
    if user_id == current_user_id and 'rol' in fields:
        if fields['rol'] != user.get('rol'):
            raise ValueError("Kendi rolünüzü değiştiremezsiniz")

    # rol değeri kontrolü
    if 'rol' in fields and fields['rol'] not in ['user', 'company_admin']:
        raise ValueError("Geçersiz rol değeri")

    if not fields:
        return False

    # Şifre varsa hashle
    if "password" in fields:
        fields["password_hash"] = hash_password(fields.pop("password"))

    # Güvenli alan adı doğrulama
    set_clause, values = safe_set_clause("users", fields)
    if not set_clause:
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            (*values, user_id)
        )
        return cursor.rowcount > 0


def delete_user_by_company_admin(
    user_id: int,
    company_id: int,
    current_user_id: int
) -> bool:
    """
    Company admin tarafından kullanıcı silme

    Args:
        user_id: Silinecek kullanıcı ID
        company_id: İşlemi yapan adminin firma ID
        current_user_id: İşlemi yapan admin ID

    Returns:
        bool: Silme başarılı mı?

    Raises:
        PermissionError: Yetkisiz erişim
        ValueError: Geçersiz işlem
    """
    # Kendi kendini silemez
    if user_id == current_user_id:
        raise ValueError("Kendinizi silemezsiniz")

    # Kullanıcıyı getir
    user = get_user(user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı")

    # Aynı firmadan olmalı
    if user.get('company_id') != company_id:
        raise PermissionError("Bu kullanıcıyı silme yetkiniz yok")

    # super_admin silinemez
    if user.get('rol') == 'super_admin':
        raise PermissionError("Super admin silinemez")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0


def toggle_user_status(
    user_id: int,
    company_id: int,
    current_user_id: int
) -> tuple[bool, str]:
    """
    Kullanıcı aktif/pasif durumunu değiştir

    Args:
        user_id: Kullanıcı ID
        company_id: Firma ID
        current_user_id: İşlemi yapan kullanıcı ID

    Returns:
        tuple: (başarılı mı, yeni durum mesajı)
    """
    # Kendi kendini pasif yapamaz
    if user_id == current_user_id:
        raise ValueError("Kendi durumunuzu değiştiremezsiniz")

    user = get_user(user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı")

    if user.get('company_id') != company_id:
        raise PermissionError("Bu kullanıcıyı düzenleme yetkiniz yok")

    if user.get('rol') == 'super_admin':
        raise PermissionError("Super admin durumu değiştirilemez")

    new_status = 0 if user.get('aktif', 1) == 1 else 1

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET aktif = ? WHERE id = ?",
            (new_status, user_id)
        )

        status_text = "aktif" if new_status == 1 else "pasif"
        return cursor.rowcount > 0, status_text


def reset_user_password(
    user_id: int,
    company_id: int,
    current_user_id: int
) -> str:
    """
    Kullanıcı şifresini sıfırla ve geçici şifre oluştur

    Args:
        user_id: Kullanıcı ID
        company_id: Firma ID
        current_user_id: İşlemi yapan kullanıcı ID

    Returns:
        str: Yeni geçici şifre

    Raises:
        PermissionError/ValueError: Hata durumunda
    """
    user = get_user(user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı")

    if user.get('company_id') != company_id:
        raise PermissionError("Bu kullanıcının şifresini sıfırlama yetkiniz yok")

    if user.get('rol') == 'super_admin':
        raise PermissionError("Super admin şifresi sıfırlanamaz")

    # Yeni geçici şifre oluştur
    temp_password = generate_temp_password()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET password_hash = ?, must_change_password = 1
            WHERE id = ?
        """, (hash_password(temp_password), user_id))

    return temp_password


def check_must_change_password(user_id: int) -> bool:
    """Kullanıcının şifre değiştirmesi gerekiyor mu?"""
    user = get_user(user_id)
    return user.get('must_change_password', 0) == 1 if user else False


def clear_must_change_password(user_id: int) -> bool:
    """Şifre değiştirme zorunluluğunu kaldır"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET must_change_password = 0 WHERE id = ?",
            (user_id,)
        )
        return cursor.rowcount > 0


# ============ ROL VE YETKİ YÖNETİMİ ============

def get_user_role(user_id: int) -> Optional[str]:
    """Kullanıcının rolünü getir"""
    user = get_user(user_id)
    return user.get('rol', 'user') if user else None


def get_all_users(company_id: int = None) -> list[dict]:
    """
    Tüm kullanıcıları getir (super_admin için) veya firma bazlı

    Args:
        company_id: Firma ID (None ise tüm kullanıcılar - sadece super_admin için)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if company_id:
            cursor.execute("""
                SELECT u.*, c.ad as firma_adi
                FROM users u
                LEFT JOIN companies c ON u.company_id = c.id
                WHERE u.company_id = ?
                ORDER BY u.ad_soyad
            """, (company_id,))
        else:
            cursor.execute("""
                SELECT u.*, c.ad as firma_adi
                FROM users u
                LEFT JOIN companies c ON u.company_id = c.id
                ORDER BY c.ad, u.ad_soyad
            """)
        return [dict(row) for row in cursor.fetchall()]


def create_default_admin():
    """Varsayilan admin kullanicisi olustur (yoksa)"""
    admin = get_user_by_email("admin@talentflow.com")
    if not admin:
        create_user(
            email="admin@talentflow.com",
            password="admin123",
            ad_soyad="System Admin",
            company_id=None,
            rol="admin"
        )
        logger.info("Admin kullanicisi olusturuldu: admin@talentflow.com / admin123")


def create_demo_company_and_user():
    """Demo firma ve kullanici olustur"""
    # Demo firma
    company = get_company_by_slug("demo-sirket")
    if not company:
        company_id = create_company(
            ad="Demo Sirket",
            slug="demo-sirket",
            email="info@demo.com",
            telefon="+90 555 123 4567",
            plan="professional"
        )
    else:
        company_id = company["id"]

    # Demo kullanici
    user = get_user_by_email("demo@demo.com")
    if not user:
        create_user(
            email="demo@demo.com",
            password="demo123",
            ad_soyad="Demo Kullanici",
            company_id=company_id,
            rol="admin"  # Firma admini
        )
        logger.info("Demo kullanici olusturuldu: demo@demo.com / demo123")


# ============ SIFRE SIFIRLAMA ISLEMLERI ============

def create_password_reset_token(email: str) -> Optional[str]:
    """
    Sifre sifirlama tokeni olustur

    Args:
        email: Kullanici email adresi

    Returns:
        6 haneli token veya None (kullanici yoksa)
    """
    import random
    import string

    # Kullanici var mi kontrol et
    user = get_user_by_email(email)
    if not user:
        return None

    # 6 haneli rastgele kod olustur
    token = ''.join(random.choices(string.digits, k=6))

    # 15 dakika gecerli
    expires_at = (datetime.now() + timedelta(minutes=15)).isoformat()

    # Onceki kullanilmamis tokenleri gecersiz yap
    with get_connection() as conn:
        cursor = conn.cursor()

        # Eski tokenlari sil
        cursor.execute(
            "DELETE FROM password_reset_tokens WHERE email = ? AND used = 0",
            (email,)
        )

        # Yeni token ekle
        cursor.execute(
            """INSERT INTO password_reset_tokens (email, token, expires_at)
               VALUES (?, ?, ?)""",
            (email, token, expires_at)
        )

    return token


def verify_password_reset_token(email: str, token: str) -> tuple[bool, str]:
    """
    Sifre sifirlama tokenini dogrula

    Args:
        email: Kullanici email adresi
        token: 6 haneli kod

    Returns:
        (gecerli_mi, mesaj)
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """SELECT * FROM password_reset_tokens
               WHERE email = ? AND token = ? AND used = 0
               ORDER BY created_at DESC LIMIT 1""",
            (email, token)
        )
        row = cursor.fetchone()

        if not row:
            return False, "Gecersiz veya kullanilmis kod"

        # Sure kontrolu
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now() > expires_at:
            return False, "Kodun suresi dolmus. Lutfen yeni kod talep edin."

        return True, "Kod dogrulandi"


# ============ KVKK ISLEMLERI ============

def get_expiring_candidates(days: int = 30, company_id: int = None) -> list[dict]:
    """Suresi dolmak uzere olan adaylari getir"""
    future_date = (datetime.now() + timedelta(days=days)).isoformat()
    now = datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        company_filter = "AND company_id = ?" if company_id else ""
        params = [now, future_date]
        if company_id:
            params.append(company_id)

        cursor.execute(f"""
            SELECT * FROM candidates
            WHERE expires_at IS NOT NULL
            AND expires_at > ?
            AND expires_at <= ?
            AND is_anonymized = 0
            {company_filter}
            ORDER BY expires_at ASC
        """, params)
        return [dict(row) for row in cursor.fetchall()]


def get_expired_candidates(company_id: int = None) -> list[dict]:
    """Suresi dolmus adaylari getir"""
    now = datetime.now().isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        company_filter = "AND company_id = ?" if company_id else ""
        params = [now]
        if company_id:
            params.append(company_id)

        cursor.execute(f"""
            SELECT * FROM candidates
            WHERE expires_at IS NOT NULL
            AND expires_at <= ?
            AND is_anonymized = 0
            {company_filter}
            ORDER BY expires_at ASC
        """, params)
        return [dict(row) for row in cursor.fetchall()]


def extend_candidate_expiry(candidate_id: int, years: int = 1) -> bool:
    """Aday veri saklama suresini uzat"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT expires_at FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()

        if row and row["expires_at"]:
            current_expiry = datetime.fromisoformat(row["expires_at"])
            new_expiry = current_expiry + timedelta(days=years * 365)
        else:
            new_expiry = datetime.now() + timedelta(days=years * 365)

        cursor.execute(
            "UPDATE candidates SET expires_at = ? WHERE id = ?",
            (new_expiry.isoformat(), candidate_id)
        )
        return cursor.rowcount > 0


def anonymize_candidate(candidate_id: int) -> bool:
    """
    Aday verilerini anonimleştir (KVKK Unutulma Hakki)
    Kisisel bilgiler silinir, istatistiksel veriler korunur
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Aday bilgilerini anonimleştir
        cursor.execute("""
            UPDATE candidates SET
                ad_soyad = ?,
                email = ?,
                telefon = NULL,
                lokasyon = NULL,
                cv_raw_text = NULL,
                cv_dosya_yolu = NULL,
                cv_dosya_adi = NULL,
                linkedin = NULL,
                github = NULL,
                notlar = NULL,
                is_anonymized = 1,
                anonymized_at = ?
            WHERE id = ?
        """, (
            f"Silinmis Aday #{candidate_id}",
            f"deleted_{candidate_id}@anonymized.local",
            datetime.now().isoformat(),
            candidate_id
        ))

        return cursor.rowcount > 0


def delete_candidate_cv_file(candidate_id: int) -> bool:
    """Aday CV dosyasini sil"""
    import os

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cv_dosya_yolu FROM candidates WHERE id = ?",
            (candidate_id,)
        )
        row = cursor.fetchone()

        if row and row["cv_dosya_yolu"]:
            file_path = row["cv_dosya_yolu"]
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

            cursor.execute(
                "UPDATE candidates SET cv_dosya_yolu = NULL, cv_dosya_adi = NULL WHERE id = ?",
                (candidate_id,)
            )
            return True
    return False


def delete_candidate(candidate_id: int, company_id: int = None) -> dict:
    """
    Adayi ve iliskili tum verileri kalici olarak sil (KVKK Silme Hakki)
    
    FK Constraint Güvenliği:
    - safe_delete_with_fk() kullanarak dinamik olarak tüm bağımlı tabloları temizler
    - candidate_positions, matches, candidate_pool_assignments dahil

    Args:
        candidate_id: Aday ID
        company_id: Firma ID (güvenlik için zorunlu önerilir)

    Silinen veriler:
    - Aday kaydi
    - Basvurular
    - Havuz kayitlari
    - Mulakatlar
    - AI analizleri
    - IK degerlendirmeleri
    - KVKK onaylari
    - CV dosyasi
    - candidate_positions (FK güvenliği)
    - matches (FK güvenliği)
    - candidate_pool_assignments (FK güvenliği)

    Returns:
        dict: {"success": bool, "deleted_counts": {...}, "error": str or None}
    """
    import os

    deleted_counts = {
        "applications": 0,
        "pool_records": 0,
        "interviews": 0,
        "ai_analysis": 0,
        "hr_evaluations": 0,
        "merge_logs": 0,
        "email_logs": 0,
        "cv_file": False,
        "candidate_positions": 0,
        "matches": 0,
        "candidate_pool_assignments": 0
    }

    try:
        # Sahiplik kontrolu
        if company_id:
            if not verify_candidate_ownership(candidate_id, company_id):
                return {
                    "success": False,
                    "deleted_counts": deleted_counts,
                    "error": "Bu adaya erisim yetkiniz yok"
                }

        with get_connection() as conn:
            cursor = conn.cursor()

            # 1. CV dosyasini sil
            cursor.execute(
                "SELECT cv_dosya_yolu FROM candidates WHERE id = ?",
                (candidate_id,)
            )
            row = cursor.fetchone()
            if row and row["cv_dosya_yolu"]:
                file_path = row["cv_dosya_yolu"]
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_counts["cv_file"] = True
                    except OSError:
                        pass

            # 2. Önce email_id'leri al (applications'tan)
            cursor.execute(
                "SELECT email_id FROM applications WHERE candidate_id = ? AND email_id IS NOT NULL",
                (candidate_id,)
            )
            email_ids = [row["email_id"] for row in cursor.fetchall()]

            # 3. Basvurulari sil
            cursor.execute(
                "DELETE FROM applications WHERE candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["applications"] = cursor.rowcount

            # 4. Email loglarini sil (ayni CV tekrar import edilebilsin)
            for email_id in email_ids:
                cursor.execute(
                    "DELETE FROM email_logs WHERE email_id = ?",
                    (email_id,)
                )
                deleted_counts["email_logs"] += cursor.rowcount

            # 5. Havuz kayitlarini sil (eski sistem - position_pools)
            cursor.execute(
                "DELETE FROM position_pools WHERE candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["pool_records"] = cursor.rowcount

            # 6. Mulakatlari sil
            cursor.execute(
                "DELETE FROM interviews WHERE candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["interviews"] = cursor.rowcount

            # 7. AI analizlerini sil
            cursor.execute(
                "DELETE FROM ai_analyses WHERE candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["ai_analysis"] = cursor.rowcount

            # 8. IK degerlendirmelerini sil
            cursor.execute(
                "DELETE FROM hr_evaluations WHERE candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["hr_evaluations"] = cursor.rowcount

            # 9. Birlesme loglarini sil (master olarak)
            cursor.execute(
                "DELETE FROM candidate_merge_logs WHERE master_candidate_id = ?",
                (candidate_id,)
            )
            deleted_counts["merge_logs"] = cursor.rowcount

            # 10. FK Constraint Güvenliği: Dinamik olarak tüm bağımlı tabloları temizle
            # safe_delete_with_fk() candidate_positions, matches, candidate_pool_assignments dahil
            # tüm candidate_id FK'sı olan tabloları temizler
            delete_result = safe_delete_with_fk(
                cursor=cursor,
                table_name='candidates',
                where_clause='id = ?',
                params=(candidate_id,),
                fk_column='candidate_id'
            )
            
            # safe_delete_with_fk sonuçlarını deleted_counts'a ekle
            for table_name, count in delete_result['deleted_from_dependent'].items():
                if table_name in deleted_counts:
                    deleted_counts[table_name] = count
                else:
                    deleted_counts[table_name] = count
            
            if delete_result['errors']:
                logger.warning(f"delete_candidate: Bazı bağımlı tablolar temizlenirken hata oluştu: {delete_result['errors']}")

            # 11. Son olarak aday kaydini sil
            cursor.execute(
                "DELETE FROM candidates WHERE id = ?",
                (candidate_id,)
            )

            if cursor.rowcount == 0:
                return {
                    "success": False,
                    "deleted_counts": deleted_counts,
                    "error": "Aday bulunamadi"
                }

            conn.commit()

            return {
                "success": True,
                "deleted_counts": deleted_counts,
                "error": None
            }

    except Exception as e:
        import traceback
        logger.error(f"delete_candidate hatası: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "deleted_counts": deleted_counts,
            "error": str(e)
        }


def get_candidate_full_data(candidate_id: int, company_id: int = None, allow_cross_tenant: bool = False) -> dict:
    """
    KVKK Veri Tasinabilirlik Hakki icin tum aday verilerini getir
    
    Args:
        candidate_id: Aday ID
        company_id: Firma ID (güvenlik için zorunlu - multi-tenant veri izolasyonu)
        allow_cross_tenant: True ise company_id=None durumunda cross-tenant erişime izin ver
                          (Sadece super admin işlemleri için kullanılmalıdır)
    
    Returns:
        dict: Aday verileri veya boş dict (erişim yetkisi yoksa)
    
    Raises:
        ValueError: company_id=None ve allow_cross_tenant=False durumunda
    """
    # Güvenlik kontrolü: company_id=None ve allow_cross_tenant=False ise hata fırlat
    if company_id is None and not allow_cross_tenant:
        raise ValueError("company_id is required for tenant-safe access. Use allow_cross_tenant=True only for super admin operations.")
    
    # Güvenlik: company_id kontrolü
    if company_id:
        if not verify_candidate_ownership(candidate_id, company_id):
            return {}
    
    with get_connection() as conn:
        cursor = conn.cursor()

        # Aday bilgileri - company_id kontrolü ile
        if company_id:
            cursor.execute("SELECT * FROM candidates WHERE id = ? AND company_id = ?", 
                          (candidate_id, company_id))
        else:
            # ⚠️ UYARI: company_id=None kullanımı cross-tenant access riski taşır
            # Sadece allow_cross_tenant=True ile kullanılmalı (super admin işlemleri)
            cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
        
        candidate = cursor.fetchone()
        if not candidate:
            return {}

        candidate_data = dict(candidate)
        
        # company_id kontrolü: Eğer company_id verildiyse, tüm sorgularda filtreleme yap
        if company_id:
            # Sadece aynı firmaya ait verileri getir
            # Applications - company_id kontrolü (candidate üzerinden)
            cursor.execute("""
                SELECT a.*, p.baslik as pozisyon_baslik
                FROM applications a
                LEFT JOIN positions p ON a.position_id = p.id
                WHERE a.candidate_id = ? AND (p.company_id = ? OR a.position_id IS NULL)
            """, (candidate_id, company_id))
            applications = [dict(row) for row in cursor.fetchall()]

            # Mulakatlar - company_id kontrolü (candidate üzerinden)
            cursor.execute("""
                SELECT i.*, p.baslik as pozisyon_baslik
                FROM interviews i
                LEFT JOIN positions p ON i.position_id = p.id
                WHERE i.candidate_id = ? AND (p.company_id = ? OR i.position_id IS NULL)
            """, (candidate_id, company_id))
            interviews = [dict(row) for row in cursor.fetchall()]

            # Degerlendirmeler - company_id kontrolü
            cursor.execute("""
                SELECT he.*, p.baslik as pozisyon_baslik, u.ad_soyad as degerlendiren
                FROM hr_evaluations he
                LEFT JOIN positions p ON he.position_id = p.id
                LEFT JOIN users u ON he.evaluator_id = u.id
                WHERE he.candidate_id = ? AND (p.company_id = ? OR he.position_id IS NULL)
            """, (candidate_id, company_id))
            evaluations = [dict(row) for row in cursor.fetchall()]

            # Havuz bilgileri - company_id kontrolü
            cursor.execute("""
                SELECT pp.*, p.baslik as pozisyon_baslik
                FROM position_pools pp
                JOIN positions p ON pp.position_id = p.id
                WHERE pp.candidate_id = ? AND p.company_id = ?
            """, (candidate_id, company_id))
            pools = [dict(row) for row in cursor.fetchall()]
        else:
            # Geriye uyumluluk (super admin için)
            cursor.execute("""
                SELECT a.*, p.baslik as pozisyon_baslik
                FROM applications a
                LEFT JOIN positions p ON a.position_id = p.id
                WHERE a.candidate_id = ?
            """, (candidate_id,))
            applications = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT i.*, p.baslik as pozisyon_baslik
                FROM interviews i
                LEFT JOIN positions p ON i.position_id = p.id
                WHERE i.candidate_id = ?
            """, (candidate_id,))
            interviews = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT he.*, p.baslik as pozisyon_baslik, u.ad_soyad as degerlendiren
                FROM hr_evaluations he
                LEFT JOIN positions p ON he.position_id = p.id
                LEFT JOIN users u ON he.evaluator_id = u.id
                WHERE he.candidate_id = ?
            """, (candidate_id,))
            evaluations = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT pp.*, p.baslik as pozisyon_baslik
                FROM position_pools pp
                JOIN positions p ON pp.position_id = p.id
                WHERE pp.candidate_id = ?
            """, (candidate_id,))
            pools = [dict(row) for row in cursor.fetchall()]

        # Basvurular
        cursor.execute("""
            SELECT a.*, p.baslik as pozisyon_baslik
            FROM applications a
            LEFT JOIN positions p ON a.position_id = p.id
            WHERE a.candidate_id = ?
        """, (candidate_id,))
        applications = [dict(row) for row in cursor.fetchall()]

        # Mulakatlar
        cursor.execute("""
            SELECT i.*, p.baslik as pozisyon_baslik
            FROM interviews i
            LEFT JOIN positions p ON i.position_id = p.id
            WHERE i.candidate_id = ?
        """, (candidate_id,))
        interviews = [dict(row) for row in cursor.fetchall()]

        # Degerlendirmeler
        cursor.execute("""
            SELECT he.*, p.baslik as pozisyon_baslik, u.ad_soyad as degerlendiren
            FROM hr_evaluations he
            LEFT JOIN positions p ON he.position_id = p.id
            LEFT JOIN users u ON he.evaluator_id = u.id
            WHERE he.candidate_id = ?
        """, (candidate_id,))
        evaluations = [dict(row) for row in cursor.fetchall()]

        # Havuz bilgileri
        cursor.execute("""
            SELECT pp.*, p.baslik as pozisyon_baslik
            FROM position_pools pp
            JOIN positions p ON pp.position_id = p.id
            WHERE pp.candidate_id = ?
        """, (candidate_id,))
        pools = [dict(row) for row in cursor.fetchall()]

        # AI Analizleri
        cursor.execute(
            "SELECT * FROM ai_analyses WHERE candidate_id = ?",
            (candidate_id,)
        )
        ai_analyses = [dict(row) for row in cursor.fetchall()]

        return {
            "candidate": candidate_data,
            "applications": applications,
            "interviews": interviews,
            "evaluations": evaluations,
            "pools": pools,
            "ai_analyses": ai_analyses,
            "export_date": datetime.now().isoformat(),
            "export_note": "KVKK Madde 11 kapsaminda veri tasinabilirlik hakki"
        }


def get_kvkk_stats(company_id: int = None) -> dict:
    """KVKK istatistiklerini getir"""
    with get_connection() as conn:
        cursor = conn.cursor()

        company_filter = "WHERE company_id = ?" if company_id else ""
        params = [company_id] if company_id else []

        # Toplam aday
        cursor.execute(f"SELECT COUNT(*) as count FROM candidates {company_filter}", params)
        total = cursor.fetchone()["count"]

        # Anonimlestirilmis
        anon_filter = "WHERE is_anonymized = 1" + (" AND company_id = ?" if company_id else "")
        cursor.execute(f"SELECT COUNT(*) as count FROM candidates {anon_filter}", params)
        anonymized = cursor.fetchone()["count"]

        # Suresi dolmus
        now = datetime.now().isoformat()
        exp_filter = f"WHERE expires_at <= ? AND is_anonymized = 0" + (" AND company_id = ?" if company_id else "")
        exp_params = [now] + params
        cursor.execute(f"SELECT COUNT(*) as count FROM candidates {exp_filter}", exp_params)
        expired = cursor.fetchone()["count"]

        # 30 gun icinde dolacak
        future = (datetime.now() + timedelta(days=30)).isoformat()
        exp30_filter = f"WHERE expires_at > ? AND expires_at <= ? AND is_anonymized = 0" + (" AND company_id = ?" if company_id else "")
        exp30_params = [now, future] + params
        cursor.execute(f"SELECT COUNT(*) as count FROM candidates {exp30_filter}", exp30_params)
        expiring_soon = cursor.fetchone()["count"]

        return {
            "total_candidates": total,
            "anonymized": anonymized,
            "expired": expired,
            "expiring_soon": expiring_soon,
            "active": total - anonymized
        }


# ============ VERİ SIFIRLAMA İŞLEMLERİ ============

def reset_all_cv_data(company_id: int = None) -> dict:
    """
    Tüm CV verilerini sıfırla (email logs, applications, candidates, ai_analyses)
    
    Dinamik olarak candidates tablosuna FK ile bağlı TÜM tabloları bulur ve temizler.
    Bu sayede ileride yeni tablo eklense bile otomatik temizlenir.

    Returns:
        dict: Her tablo için silinen kayıt sayıları
    """
    import logging
    logger = logging.getLogger(__name__)
    
    results = {
        "email_logs": 0,
        "candidates": 0,
        "success": True,
        "error": None
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Foreign key constraint'leri geçici olarak kapat (ekstra güvenlik)
            cursor.execute("PRAGMA foreign_keys=OFF")

            # 1. Email loglarını sıfırla
            try:
                cursor.execute("UPDATE email_logs SET islendi = 0, hata = NULL, islem_tarihi = NULL")
                results["email_logs"] = cursor.rowcount
                logger.info(f"reset_all_cv_data: {results['email_logs']} email_log kaydı sıfırlandı")
            except Exception as e:
                logger.warning(f"reset_all_cv_data email_logs hatası: {e}")

            # 2. candidates tablosuna FK ile bağlı TÜM tabloları dinamik olarak bul
            try:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    AND sql LIKE '%candidate_id%'
                    AND name != 'candidates'
                    ORDER BY name
                """)
                dependent_tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"reset_all_cv_data: Bulunan bağımlı tablolar: {dependent_tables}")
            except Exception as e:
                logger.warning(f"reset_all_cv_data bağımlı tablo bulma hatası: {e}")
                # Fallback: Manuel liste (eğer dinamik bulma başarısız olursa)
                dependent_tables = [
                    'interviews',
                    'hr_evaluations',
                    'candidate_merge_logs',
                    'candidate_pool_assignments',
                    'position_pools',
                    'applications',
                    'ai_analyses',
                    'matches_backup',
                    'matches',
                    'candidate_positions'
                ]

            # 3. Tüm bağımlı tabloları temizle (child → parent sırası)
            for table_name in dependent_tables:
                try:
                    # Güvenlik: Tablo adını doğrula (sadece alfanumerik ve underscore)
                    if not table_name.replace('_', '').isalnum():
                        logger.warning(f"reset_all_cv_data: Geçersiz tablo adı atlandı: {table_name}")
                        continue
                    
                    # Önce kaç kayıt olduğunu say
                    if company_id:
                        # SQL injection koruması: Tablo adı sqlite_master'dan geldiği için güvenli
                        # Ama yine de parametreli sorgu kullanılamadığı için dikkatli olmalıyız
                        cursor.execute(f"""
                            SELECT COUNT(*) FROM "{table_name}"
                            WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)
                        """, (company_id,))
                        count_before = cursor.fetchone()[0]
                        
                        # Sonra sil
                        cursor.execute(f"""
                            DELETE FROM "{table_name}"
                            WHERE candidate_id IN (SELECT id FROM candidates WHERE company_id = ?)
                        """, (company_id,))
                    else:
                        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                        count_before = cursor.fetchone()[0]
                        cursor.execute(f'DELETE FROM "{table_name}"')
                    
                    results[table_name] = count_before
                    if count_before > 0:
                        logger.info(f"reset_all_cv_data: {table_name} tablosundan {count_before} kayıt silindi")
                except Exception as e:
                    # Tablo yoksa veya hata olursa devam et
                    logger.warning(f"reset_all_cv_data {table_name} silme hatası: {e}")
                    results[table_name] = 0

            # 4. Adayları sil (EN SON - tüm FK constraint'ler temizlendikten sonra)
            try:
                # Önce kaç aday olduğunu say
                if company_id:
                    cursor.execute("SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,))
                    count_before = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM candidates WHERE company_id = ?", (company_id,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM candidates")
                    count_before = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM candidates")
                results["candidates"] = count_before
                logger.info(f"reset_all_cv_data: {count_before} aday silindi")
            except Exception as e:
                logger.error(f"reset_all_cv_data candidates silme hatası: {e}")
                results["candidates"] = 0

            # Foreign key constraint'leri tekrar aç
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # Tüm değişiklikleri commit et
            conn.commit()
            
            logger.info(f"reset_all_cv_data tamamlandı: {results}")
            return results

    except Exception as e:
        import traceback
        logger.error(f"reset_all_cv_data genel hata: {e}\n{traceback.format_exc()}")
        results["success"] = False
        results["error"] = str(e)
        return results


def find_candidates_by_position_titles(company_id: int, title_list: list, pool_types: list = None) -> list:
    """
    Genel Havuz ve Arşiv'deki adayların mevcut_pozisyon ve deneyim_detay
    alanlarında verilen pozisyon başlıklarını ara.
    
    Args:
        company_id: Firma ID
        title_list: Aranacak pozisyon başlıkları listesi
        pool_types: Hangi havuz tiplerinde aransın (None ise sistem havuzları: Genel Havuz, Arşiv)
    
    Returns:
        [{
            'candidate_id': int,
            'ad_soyad': str,
            'mevcut_pozisyon': str,
            'matched_title': str,  # Hangi başlık eşleşti
            'match_source': str,   # 'mevcut_pozisyon' veya 'deneyim_detay'
            'match_level': str,    # 'exact', 'close', 'partial'
            'match_ratio': float   # Eşleşme oranı (0-100)
        }]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from scoring_v2 import turkish_lower
    try:
        from thefuzz import fuzz
    except ImportError:
        fuzz = None
        logger.warning("thefuzz modülü bulunamadı, basit substring matching kullanılacak")
    
    if not title_list:
        return []
    
    # Sistem havuzlarını bul (Genel Havuz, Arşiv)
    general_pool = get_pool_by_name(company_id, 'Genel Havuz')
    archive_pool = get_pool_by_name(company_id, 'Arşiv')
    
    if not general_pool and not archive_pool:
        logger.warning(f"find_candidates_by_position_titles: Sistem havuzları bulunamadı (company_id={company_id})")
        return []
    
    system_pool_ids = []
    if general_pool:
        system_pool_ids.append(general_pool['id'])
    if archive_pool:
        system_pool_ids.append(archive_pool['id'])
    
    if not system_pool_ids:
        return []
    
    # Genel Havuz ve Arşiv'deki adayları çek (candidate_pool_assignments üzerinden)
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT c.id, c.ad_soyad, c.mevcut_pozisyon, c.deneyim_detay
            FROM candidates c
            JOIN candidate_pool_assignments cpa ON cpa.candidate_id = c.id
            WHERE c.company_id = ?
            AND cpa.department_pool_id IN ({})
            AND c.is_anonymized = 0
        """.format(','.join('?' * len(system_pool_ids))), [company_id] + system_pool_ids)
        
        candidates = [dict(row) for row in cursor.fetchall()]
    
    if not candidates:
        return []
    
    results = []
    title_list_lower = [turkish_lower(t) for t in title_list if t]
    
    for cand in candidates:
        best_match = None
        best_ratio = 0
        best_source = None
        
        # 1. mevcut_pozisyon kontrol
        if cand.get('mevcut_pozisyon'):
            pos_lower = turkish_lower(cand['mevcut_pozisyon'])
            for title in title_list_lower:
                if fuzz:
                    ratio = fuzz.ratio(pos_lower, title)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = title
                        best_source = 'mevcut_pozisyon'
                elif title in pos_lower or pos_lower in title:
                    # Basit substring matching (thefuzz yoksa)
                    if best_ratio < 80:
                        best_ratio = 80
                        best_match = title
                        best_source = 'mevcut_pozisyon'
        
        # 2. deneyim_detay kontrol
        if cand.get('deneyim_detay'):
            exp_lower = turkish_lower(cand['deneyim_detay'])
            for title in title_list_lower:
                if fuzz:
                    # deneyim_detay uzun metin, partial_ratio kullan
                    ratio = fuzz.partial_ratio(exp_lower, title)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = title
                        best_source = 'deneyim_detay'
                elif title in exp_lower:
                    # Basit substring matching
                    if best_ratio < 70:
                        best_ratio = 70
                        best_match = title
                        best_source = 'deneyim_detay'
        
        # Eşik kontrolü (ratio >= 50)
        if best_ratio >= 50 and best_match:
            match_level = 'exact' if best_ratio >= 80 else 'close' if best_ratio >= 65 else 'partial'
            
            # Orijinal title'ı bul (lowercase değil)
            original_title = best_match
            for t in title_list:
                if turkish_lower(t) == best_match:
                    original_title = t
                    break
            
            results.append({
                'candidate_id': cand['id'],
                'ad_soyad': cand['ad_soyad'],
                'mevcut_pozisyon': cand.get('mevcut_pozisyon', ''),
                'matched_title': original_title,
                'match_source': best_source,
                'match_level': match_level,
                'match_ratio': best_ratio
            })
    
    # En iyi eşleşmeleri üste getir (ratio'ya göre)
    results.sort(key=lambda x: x['match_ratio'], reverse=True)
    
    logger.info(f"find_candidates_by_position_titles: {len(results)} aday bulundu (company_id={company_id}, title_count={len(title_list)})")
    return results


# ============ BACKUP ISLEMLERI ============

import shutil
import glob

BACKUP_RETENTION_DAYS = 7  # Son 7 günün yedeğini tut


def get_backup_dir():
    """Backup dizinini döndür"""
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup() -> tuple[bool, str, Optional[str]]:
    """
    Veritabanı yedeği oluştur

    Returns:
        (basarili, mesaj, dosya_yolu)
    """
    try:
        backup_dir = get_backup_dir()
        date_str = datetime.now().strftime("%Y-%m-%d")
        backup_filename = f"talentflow_backup_{date_str}.db"
        backup_path = backup_dir / backup_filename

        # Mevcut veritabanını kopyala
        shutil.copy2(DATABASE_PATH, backup_path)

        # Eski yedekleri temizle
        cleanup_count = cleanup_old_backups()

        return True, f"Yedek oluşturuldu: {backup_filename}", str(backup_path)

    except Exception as e:
        return False, f"Yedek oluşturulamadı: {str(e)}", None


def cleanup_old_backups() -> int:
    """
    BACKUP_RETENTION_DAYS'den eski yedekleri sil

    Returns:
        Silinen dosya sayısı
    """
    try:
        backup_dir = get_backup_dir()
        cutoff_date = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
        deleted_count = 0

        # Tüm backup dosyalarını bul
        backup_pattern = str(backup_dir / "talentflow_backup_*.db")
        backup_files = glob.glob(backup_pattern)

        for backup_file in backup_files:
            # Dosya adından tarihi çıkar
            filename = os.path.basename(backup_file)
            try:
                # talentflow_backup_2024-01-14.db formatından tarih çıkar
                date_str = filename.replace("talentflow_backup_", "").replace(".db", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff_date:
                    os.remove(backup_file)
                    deleted_count += 1
            except (ValueError, OSError):
                continue  # Geçersiz format, atla

        return deleted_count

    except Exception:
        return 0


def get_backup_list() -> list[dict]:
    """
    Mevcut yedeklerin listesini döndür

    Returns:
        [{"filename": "...", "date": "...", "size_mb": ..., "path": "..."}]
    """
    try:
        backup_dir = get_backup_dir()
        backup_pattern = str(backup_dir / "talentflow_backup_*.db")
        backup_files = glob.glob(backup_pattern)

        backups = []
        for backup_file in backup_files:
            filename = os.path.basename(backup_file)
            try:
                date_str = filename.replace("talentflow_backup_", "").replace(".db", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB

                backups.append({
                    "filename": filename,
                    "date": file_date.strftime("%Y-%m-%d"),
                    "size_mb": round(file_size, 2),
                    "path": backup_file
                })
            except (ValueError, OSError):
                continue

        # Tarihe göre sırala (en yeni önce)
        backups.sort(key=lambda x: x["date"], reverse=True)
        return backups

    except Exception:
        return []


def get_backup_file(filename: str) -> Optional[bytes]:
    """
    Yedek dosyasını oku

    Args:
        filename: Yedek dosya adı

    Returns:
        Dosya içeriği (bytes) veya None
    """
    try:
        backup_dir = get_backup_dir()
        backup_path = backup_dir / filename

        # Güvenlik: Sadece backup dizinindeki dosyalara izin ver
        if not str(backup_path).startswith(str(backup_dir)):
            return None

        if backup_path.exists():
            with open(backup_path, "rb") as f:
                return f.read()
        return None

    except Exception:
        return None


def delete_backup(filename: str) -> bool:
    """
    Belirli bir yedeği sil

    Args:
        filename: Silinecek yedek dosya adı

    Returns:
        Başarılı mı
    """
    try:
        backup_dir = get_backup_dir()
        backup_path = backup_dir / filename

        # Güvenlik: Sadece backup dizinindeki dosyalara izin ver
        if not str(backup_path).startswith(str(backup_dir)):
            return False

        if backup_path.exists():
            os.remove(backup_path)
            return True
        return False

    except Exception:
        return False


def restore_backup(filename: str) -> tuple[bool, str]:
    """
    Yedeği geri yükle

    Args:
        filename: Geri yüklenecek yedek dosya adı

    Returns:
        (basarili, mesaj)
    """
    try:
        backup_dir = get_backup_dir()
        backup_path = backup_dir / filename

        # Güvenlik: Sadece backup dizinindeki dosyalara izin ver
        if not str(backup_path).startswith(str(backup_dir)):
            return False, "Geçersiz dosya yolu!"

        if not backup_path.exists():
            return False, "Yedek dosyası bulunamadı!"

        # Geri yüklemeden önce mevcut veritabanının yedeğini al
        pre_restore_backup = backup_dir / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

        try:
            # Mevcut veritabanını kopyala (geri alma için)
            shutil.copy2(DATABASE_PATH, pre_restore_backup)
        except Exception as e:
            return False, f"Mevcut veritabanı yedeklenemedi: {str(e)}"

        # Tüm bağlantıları kapat
        try:
            # Global connection varsa kapat
            import sqlite3
            # Mevcut bağlantıları zorla kapat
            conn = sqlite3.connect(DATABASE_PATH)
            conn.close()
        except Exception as e:
            logger.debug(f"Veritabanı bağlantısı kapatma hatası (normal olabilir): {e}")

        try:
            # Yedeği geri yükle
            shutil.copy2(backup_path, DATABASE_PATH)
            return True, f"Yedek başarıyla geri yüklendi: {filename}. Önceki veritabanı şuraya kaydedildi: {pre_restore_backup.name}"

        except Exception as e:
            # Hata durumunda eski yedeği geri yükle
            try:
                shutil.copy2(pre_restore_backup, DATABASE_PATH)
                return False, f"Geri yükleme başarısız, önceki durum korundu: {str(e)}"
            except Exception as e2:
                logger.error(f"KRİTİK HATA: Geri yükleme ve geri alma başarısız: {e}, {e2}", exc_info=True)
                return False, f"KRİTİK HATA: Geri yükleme başarısız ve geri alma da başarısız: {str(e)}"

    except Exception as e:
        return False, f"Beklenmeyen hata: {str(e)}"


def get_backup_stats() -> dict:
    """
    Backup istatistiklerini döndür

    Returns:
        {"count": ..., "total_size_mb": ..., "oldest": "...", "newest": "..."}
    """
    backups = get_backup_list()

    if not backups:
        return {
            "count": 0,
            "total_size_mb": 0,
            "oldest": None,
            "newest": None
        }

    total_size = sum(b["size_mb"] for b in backups)

    return {
        "count": len(backups),
        "total_size_mb": round(total_size, 2),
        "oldest": backups[-1]["date"] if backups else None,
        "newest": backups[0]["date"] if backups else None
    }


# ============ POZİSYON ŞABLONLARI ============

def get_position_templates() -> list:
    """Tüm aktif pozisyon şablonlarını getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ad, ikon, renk, departman, lokasyon, aciklama,
                   gerekli_deneyim_yil, gerekli_egitim, kriterler, siralama
            FROM position_templates
            WHERE aktif = 1
            ORDER BY siralama, ad
        """)
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            templates.append({
                "id": row[0],
                "ad": row[1],
                "ikon": row[2],
                "renk": row[3],
                "departman": row[4],
                "lokasyon": row[5],
                "aciklama": row[6],
                "gerekli_deneyim_yil": row[7],
                "gerekli_egitim": row[8],
                "kriterler": json.loads(row[9]) if row[9] else [],
                "siralama": row[10]
            })
        return templates


def create_position_template(ad: str, ikon: str, renk: str, departman: str,
                            lokasyon: str, aciklama: str, gerekli_deneyim_yil: float,
                            gerekli_egitim: str, kriterler: list, siralama: int = 0) -> int:
    """Yeni pozisyon şablonu oluştur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO position_templates
            (ad, ikon, renk, departman, lokasyon, aciklama, gerekli_deneyim_yil, gerekli_egitim, kriterler, siralama)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ad, ikon, renk, departman, lokasyon, aciklama, gerekli_deneyim_yil,
              gerekli_egitim, json.dumps(kriterler, ensure_ascii=False), siralama))
        return cursor.lastrowid


def seed_default_templates():
    """Varsayılan inşaat sektörü şablonlarını oluştur"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Zaten şablon var mı kontrol et
        cursor.execute("SELECT COUNT(*) FROM position_templates")
        if cursor.fetchone()[0] > 0:
            return  # Şablonlar zaten mevcut

    templates = [
        {
            "ad": "Saha Mühendisi",
            "ikon": "👷",
            "renk": "orange",
            "departman": "Mühendislik",
            "lokasyon": "Şantiye",
            "aciklama": "İnşaat projelerinde saha koordinasyonu ve teknik denetim",
            "gerekli_deneyim_yil": 3,
            "gerekli_egitim": "Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İnşaat Mühendisliği, Mimarlık", "seviye": "Lisans", "zorunlu": True, "agirlik": 1.0},
                {"tip": "deneyim", "deger": "Saha deneyimi", "min_deger": "3", "max_deger": "10", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "AutoCAD", "zorunlu": True, "agirlik": 0.8},
                {"tip": "beceri", "deger": "MS Project", "zorunlu": False, "agirlik": 0.5},
                {"tip": "dil", "deger": "İngilizce", "seviye": "B1", "zorunlu": False, "agirlik": 0.3}
            ],
            "siralama": 1
        },
        {
            "ad": "Şantiye Şefi",
            "ikon": "🏗️",
            "renk": "red",
            "departman": "Yönetim",
            "lokasyon": "Şantiye",
            "aciklama": "Şantiye operasyonlarının yönetimi ve koordinasyonu",
            "gerekli_deneyim_yil": 7,
            "gerekli_egitim": "Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İnşaat Mühendisliği", "seviye": "Lisans", "zorunlu": True, "agirlik": 1.0},
                {"tip": "deneyim", "deger": "Şantiye yönetimi", "min_deger": "7", "max_deger": "20", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "Ekip yönetimi", "zorunlu": True, "agirlik": 0.9},
                {"tip": "beceri", "deger": "Bütçe yönetimi", "zorunlu": True, "agirlik": 0.8},
                {"tip": "dil", "deger": "İngilizce", "seviye": "B2", "zorunlu": False, "agirlik": 0.4}
            ],
            "siralama": 2
        },
        {
            "ad": "Teknik Eleman",
            "ikon": "🔧",
            "renk": "blue",
            "departman": "Teknik",
            "lokasyon": "Şantiye",
            "aciklama": "Teknik çizim, metraj ve saha desteği",
            "gerekli_deneyim_yil": 1,
            "gerekli_egitim": "Ön Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İnşaat, Harita, Teknik", "seviye": "Ön Lisans", "zorunlu": True, "agirlik": 1.0},
                {"tip": "deneyim", "deger": "Teknik destek", "min_deger": "1", "max_deger": "5", "zorunlu": False, "agirlik": 0.7},
                {"tip": "beceri", "deger": "AutoCAD", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "Metraj", "zorunlu": False, "agirlik": 0.6}
            ],
            "siralama": 3
        },
        {
            "ad": "Kalite Kontrol",
            "ikon": "✅",
            "renk": "green",
            "departman": "Kalite",
            "lokasyon": "Şantiye",
            "aciklama": "İnşaat kalite standartlarının denetimi ve raporlama",
            "gerekli_deneyim_yil": 3,
            "gerekli_egitim": "Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İnşaat Mühendisliği, Mimarlık", "seviye": "Lisans", "zorunlu": True, "agirlik": 1.0},
                {"tip": "deneyim", "deger": "Kalite kontrol", "min_deger": "3", "max_deger": "10", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "ISO standartları", "zorunlu": False, "agirlik": 0.7},
                {"tip": "beceri", "deger": "Raporlama", "zorunlu": True, "agirlik": 0.6}
            ],
            "siralama": 4
        },
        {
            "ad": "Lojistik Sorumlusu",
            "ikon": "🚛",
            "renk": "purple",
            "departman": "Lojistik",
            "lokasyon": "Ofis/Şantiye",
            "aciklama": "Malzeme tedarik ve lojistik operasyonları yönetimi",
            "gerekli_deneyim_yil": 2,
            "gerekli_egitim": "Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İşletme, Lojistik, Endüstri Mühendisliği", "seviye": "Lisans", "zorunlu": False, "agirlik": 0.8},
                {"tip": "deneyim", "deger": "Lojistik/tedarik", "min_deger": "2", "max_deger": "8", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "Excel", "zorunlu": True, "agirlik": 0.7},
                {"tip": "beceri", "deger": "ERP sistemleri", "zorunlu": False, "agirlik": 0.5}
            ],
            "siralama": 5
        },
        {
            "ad": "Satın Alma Uzmanı",
            "ikon": "💰",
            "renk": "yellow",
            "departman": "Satın Alma",
            "lokasyon": "Ofis",
            "aciklama": "Malzeme ve hizmet satın alma süreçlerinin yönetimi",
            "gerekli_deneyim_yil": 3,
            "gerekli_egitim": "Lisans",
            "kriterler": [
                {"tip": "egitim", "deger": "İşletme, İktisat, Mühendislik", "seviye": "Lisans", "zorunlu": True, "agirlik": 0.9},
                {"tip": "deneyim", "deger": "Satın alma", "min_deger": "3", "max_deger": "10", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "Tedarikçi yönetimi", "zorunlu": True, "agirlik": 0.8},
                {"tip": "beceri", "deger": "Pazarlık", "zorunlu": False, "agirlik": 0.6},
                {"tip": "dil", "deger": "İngilizce", "seviye": "B1", "zorunlu": False, "agirlik": 0.4}
            ],
            "siralama": 6
        },
        {
            "ad": "İdari Asistan",
            "ikon": "📝",
            "renk": "gray",
            "departman": "İdari İşler",
            "lokasyon": "Ofis",
            "aciklama": "Ofis yönetimi ve idari destek hizmetleri",
            "gerekli_deneyim_yil": 1,
            "gerekli_egitim": "Lise",
            "kriterler": [
                {"tip": "egitim", "deger": "Lise veya ön lisans", "seviye": "Lise", "zorunlu": True, "agirlik": 0.6},
                {"tip": "deneyim", "deger": "Ofis deneyimi", "min_deger": "1", "max_deger": "5", "zorunlu": False, "agirlik": 0.5},
                {"tip": "beceri", "deger": "MS Office", "zorunlu": True, "agirlik": 1.0},
                {"tip": "beceri", "deger": "İletişim", "zorunlu": True, "agirlik": 0.7}
            ],
            "siralama": 7
        },
        {
            "ad": "Boş Şablon",
            "ikon": "➕",
            "renk": "white",
            "departman": "",
            "lokasyon": "",
            "aciklama": "Sıfırdan yeni pozisyon oluşturun",
            "gerekli_deneyim_yil": 0,
            "gerekli_egitim": "",
            "kriterler": [],
            "siralama": 8
        }
    ]

    for t in templates:
        create_position_template(
            ad=t["ad"],
            ikon=t["ikon"],
            renk=t["renk"],
            departman=t["departman"],
            lokasyon=t["lokasyon"],
            aciklama=t["aciklama"],
            gerekli_deneyim_yil=t["gerekli_deneyim_yil"],
            gerekli_egitim=t["gerekli_egitim"],
            kriterler=t["kriterler"],
            siralama=t["siralama"]
        )


# ============ MESLEK UNVANLARI (AKILLI ÖNERİ SİSTEMİ) ============

def seed_job_titles():
    """İnşaat odaklı varsayılan meslek unvanlarını oluştur"""
    # Önce mevcut sayıyı kontrol et
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM job_titles")
        if cursor.fetchone()[0] > 0:
            return  # Unvanlar zaten mevcut

    # İnşaat odaklı meslek unvanları
    job_titles = [
        # ========== MÜHENDİSLİK ==========
        ("Saha Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 3),
        ("İnşaat Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Proje Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 3),
        ("Yapı Denetim Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 5),
        ("Statik Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 4),
        ("Harita Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Elektrik Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Makine Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Çevre Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Jeoloji Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Maden Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 2),
        ("Endüstri Mühendisi", "Mühendislik", "İnşaat", "Mühendislik", "Lisans", 1),

        # ========== MİMARLIK ==========
        ("Mimar", "Mimarlık", "İnşaat", "Mimarlık", "Lisans", 2),
        ("İç Mimar", "Mimarlık", "İnşaat", "Mimarlık", "Lisans", 2),
        ("Peyzaj Mimarı", "Mimarlık", "İnşaat", "Mimarlık", "Lisans", 2),
        ("Şehir Plancısı", "Mimarlık", "İnşaat", "Mimarlık", "Lisans", 3),

        # ========== ŞANTİYE YÖNETİM ==========
        ("Şantiye Şefi", "Yönetim", "İnşaat", "Yönetim", "Lisans", 7),
        ("Şantiye Müdürü", "Yönetim", "İnşaat", "Yönetim", "Lisans", 10),
        ("Proje Müdürü", "Yönetim", "İnşaat", "Yönetim", "Lisans", 8),
        ("Proje Koordinatörü", "Yönetim", "İnşaat", "Yönetim", "Lisans", 5),
        ("Yapı İşleri Müdürü", "Yönetim", "İnşaat", "Yönetim", "Lisans", 10),
        ("Teknik Ofis Şefi", "Yönetim", "İnşaat", "Teknik", "Lisans", 5),
        ("Planlama Şefi", "Yönetim", "İnşaat", "Planlama", "Lisans", 4),

        # ========== TEKNİK PERSONEL ==========
        ("Teknik Ressam", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("Teknik Eleman", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("Topoğraf", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 2),
        ("Harita Teknikeri", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("İnşaat Teknikeri", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("Elektrik Teknikeri", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("Makine Teknikeri", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("Laboratuvar Teknisyeni", "Teknik", "İnşaat", "Kalite", "Ön Lisans", 1),
        ("Metrajcı", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 2),
        ("Keşif Uzmanı", "Teknik", "İnşaat", "Teknik", "Lisans", 3),
        ("Hakediş Uzmanı", "Teknik", "İnşaat", "Teknik", "Lisans", 3),
        ("CAD Operatörü", "Teknik", "İnşaat", "Teknik", "Ön Lisans", 1),
        ("BIM Uzmanı", "Teknik", "İnşaat", "Teknik", "Lisans", 2),

        # ========== KALİTE & GÜVENLİK ==========
        ("Kalite Kontrol Mühendisi", "Kalite", "İnşaat", "Kalite", "Lisans", 3),
        ("Kalite Kontrol Sorumlusu", "Kalite", "İnşaat", "Kalite", "Ön Lisans", 2),
        ("İSG Uzmanı", "Güvenlik", "İnşaat", "İSG", "Lisans", 3),
        ("İş Güvenliği Uzmanı", "Güvenlik", "İnşaat", "İSG", "Lisans", 3),
        ("Çevre Sorumlusu", "Kalite", "İnşaat", "Çevre", "Lisans", 2),

        # ========== SATIN ALMA & LOJİSTİK ==========
        ("Satın Alma Müdürü", "Satın Alma", "İnşaat", "Satın Alma", "Lisans", 7),
        ("Satın Alma Uzmanı", "Satın Alma", "İnşaat", "Satın Alma", "Lisans", 3),
        ("Satın Alma Sorumlusu", "Satın Alma", "İnşaat", "Satın Alma", "Ön Lisans", 2),
        ("Tedarik Uzmanı", "Satın Alma", "İnşaat", "Satın Alma", "Lisans", 2),
        ("Lojistik Müdürü", "Lojistik", "İnşaat", "Lojistik", "Lisans", 5),
        ("Lojistik Sorumlusu", "Lojistik", "İnşaat", "Lojistik", "Ön Lisans", 2),
        ("Depo Sorumlusu", "Lojistik", "İnşaat", "Lojistik", "Lise", 2),
        ("Ambar Memuru", "Lojistik", "İnşaat", "Lojistik", "Lise", 1),
        ("Stok Kontrol Sorumlusu", "Lojistik", "İnşaat", "Lojistik", "Ön Lisans", 1),

        # ========== İDARİ & MUHASEBE ==========
        ("İdari İşler Müdürü", "İdari", "Genel", "İdari", "Lisans", 5),
        ("İdari Asistan", "İdari", "Genel", "İdari", "Lise", 1),
        ("Şantiye Sekreteri", "İdari", "İnşaat", "İdari", "Lise", 1),
        ("Ofis Memuru", "İdari", "Genel", "İdari", "Lise", 1),
        ("Muhasebe Müdürü", "Finans", "Genel", "Muhasebe", "Lisans", 7),
        ("Muhasebeci", "Finans", "Genel", "Muhasebe", "Ön Lisans", 2),
        ("Muhasebe Sorumlusu", "Finans", "Genel", "Muhasebe", "Ön Lisans", 3),
        ("Bordro Uzmanı", "Finans", "Genel", "İK", "Ön Lisans", 2),
        ("Mali İşler Uzmanı", "Finans", "Genel", "Finans", "Lisans", 3),

        # ========== İNSAN KAYNAKLARI ==========
        ("İK Müdürü", "İK", "Genel", "İK", "Lisans", 5),
        ("İK Uzmanı", "İK", "Genel", "İK", "Lisans", 2),
        ("İşe Alım Uzmanı", "İK", "Genel", "İK", "Lisans", 2),
        ("Personel Sorumlusu", "İK", "Genel", "İK", "Ön Lisans", 1),
        ("Puantör", "İK", "İnşaat", "İK", "Lise", 1),

        # ========== USTALAR & İŞÇİLER ==========
        ("Kalıpçı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 5),
        ("Demirci Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 5),
        ("Betoncu Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Duvarcı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Sıvacı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Boyacı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Fayans Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Alçı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Kaynakçı", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Elektrikçi", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Tesisatçı", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Su Tesisatçısı", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Doğalgaz Tesisatçısı", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("İzolasyoncu", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Çatı Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 3),
        ("Parke Ustası", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Marangoz", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Kalfa", "Üretim", "İnşaat", "Üretim", "Lise", 2),
        ("Vasıflı İşçi", "Üretim", "İnşaat", "Üretim", "İlkokul", 1),
        ("Vasıfsız İşçi", "Üretim", "İnşaat", "Üretim", "İlkokul", 0),
        ("Düz İşçi", "Üretim", "İnşaat", "Üretim", "İlkokul", 0),
        ("İnşaat İşçisi", "Üretim", "İnşaat", "Üretim", "İlkokul", 0),

        # ========== OPERATÖRLİK ==========
        ("Ekskavatör Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("Beko Loder Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("Vinç Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 3),
        ("Kule Vinç Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 3),
        ("Forklift Operatörü", "Operatör", "İnşaat", "Lojistik", "Lise", 1),
        ("Greyder Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("Silindir Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("Dozer Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("Transmikser Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 1),
        ("Beton Pompası Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),
        ("İş Makinesi Operatörü", "Operatör", "İnşaat", "Üretim", "Lise", 2),

        # ========== TAŞIMA & ULAŞIM ==========
        ("Şoför", "Ulaşım", "Genel", "Lojistik", "Lise", 1),
        ("Tır Şoförü", "Ulaşım", "Genel", "Lojistik", "Lise", 2),
        ("Kamyon Şoförü", "Ulaşım", "Genel", "Lojistik", "Lise", 1),
        ("Servis Şoförü", "Ulaşım", "Genel", "Lojistik", "Lise", 1),
        ("Makam Şoförü", "Ulaşım", "Genel", "İdari", "Lise", 2),
        ("Kurye", "Ulaşım", "Genel", "Lojistik", "Lise", 0),

        # ========== GÜVENLİK & HİZMET ==========
        ("Güvenlik Müdürü", "Güvenlik", "Genel", "Güvenlik", "Lisans", 5),
        ("Güvenlik Amiri", "Güvenlik", "Genel", "Güvenlik", "Lise", 3),
        ("Güvenlik Görevlisi", "Güvenlik", "Genel", "Güvenlik", "Lise", 0),
        ("Bekçi", "Güvenlik", "Genel", "Güvenlik", "İlkokul", 0),
        ("Temizlik Personeli", "Hizmet", "Genel", "Hizmet", "İlkokul", 0),
        ("Temizlik Görevlisi", "Hizmet", "Genel", "Hizmet", "İlkokul", 0),
        ("Aşçı", "Hizmet", "Genel", "Hizmet", "Lise", 2),
        ("Aşçı Yardımcısı", "Hizmet", "Genel", "Hizmet", "İlkokul", 0),
        ("Yemekhaneci", "Hizmet", "Genel", "Hizmet", "İlkokul", 0),
        ("Çaycı", "Hizmet", "Genel", "Hizmet", "İlkokul", 0),

        # ========== KARŞILAMA & MÜŞTERİ HİZMETLERİ ==========
        ("Karşılama Memuru", "Hizmet", "Genel", "Hizmet", "Lise", 0),
        ("Karşılama Görevlisi", "Hizmet", "Genel", "Hizmet", "Lise", 0),
        ("Resepsiyonist", "Hizmet", "Genel", "İdari", "Lise", 1),
        ("Danışma Görevlisi", "Hizmet", "Genel", "Hizmet", "Lise", 1),
        ("Müşteri Temsilcisi", "Satış", "Genel", "Satış", "Ön Lisans", 1),

        # ========== SATIŞ & PAZARLAMA ==========
        ("Satış Müdürü", "Satış", "Genel", "Satış", "Lisans", 5),
        ("Satış Uzmanı", "Satış", "Genel", "Satış", "Lisans", 2),
        ("Satış Temsilcisi", "Satış", "Genel", "Satış", "Ön Lisans", 1),
        ("Pazarlama Müdürü", "Pazarlama", "Genel", "Pazarlama", "Lisans", 5),
        ("Pazarlama Uzmanı", "Pazarlama", "Genel", "Pazarlama", "Lisans", 2),

        # ========== BİLGİ TEKNOLOJİLERİ ==========
        ("IT Müdürü", "IT", "Genel", "IT", "Lisans", 5),
        ("Sistem Yöneticisi", "IT", "Genel", "IT", "Lisans", 3),
        ("Yazılım Geliştirici", "IT", "Genel", "IT", "Lisans", 2),
        ("IT Destek Uzmanı", "IT", "Genel", "IT", "Ön Lisans", 1),
    ]

    # Insert işlemleri için yeni bağlantı
    with get_connection() as conn:
        cursor = conn.cursor()
        for unvan, kategori, sektor, departman, egitim, deneyim in job_titles:
            cursor.execute("""
                INSERT INTO job_titles (unvan, kategori, sektor, departman, varsayilan_egitim, varsayilan_deneyim, varsayilan)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (unvan, kategori, sektor, departman, egitim, deneyim))
        logger.info(f"✓ {len(job_titles)} meslek unvanı eklendi")


# ============ EMAIL SABLON ISLEMLERI ============

def get_email_template(sablon_kodu: str, company_id: Optional[int] = None) -> Optional[dict]:
    """
    Tek bir email şablonunu getir

    Önce şirkete özel, yoksa global şablonu döndürür.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Önce şirkete özel şablonu ara
        if company_id:
            cursor.execute("""
                SELECT id, company_id, sablon_kodu, sablon_adi, konu, icerik,
                       degiskenler, aktif, olusturma_tarihi, guncelleme_tarihi
                FROM email_templates
                WHERE sablon_kodu = ? AND company_id = ? AND aktif = 1
            """, (sablon_kodu, company_id))
            row = cursor.fetchone()
            if row:
                return dict(row)

        # Şirkete özel yoksa global şablonu al
        cursor.execute("""
            SELECT id, company_id, sablon_kodu, sablon_adi, konu, icerik,
                   degiskenler, aktif, olusturma_tarihi, guncelleme_tarihi
            FROM email_templates
            WHERE sablon_kodu = ? AND company_id IS NULL AND aktif = 1
        """, (sablon_kodu,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_department_templates(company_id: int) -> list[dict]:
    """Firma için tanımlı departman şablonlarını getir"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, company_id, name, icon, description, display_order, is_active, created_at
            FROM department_templates
            WHERE company_id = ? AND is_active = 1
            ORDER BY display_order, name
        """, (company_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_all_department_templates(company_id: int) -> list[dict]:
    """Firma için tüm departman şablonlarını getir (pasifler dahil)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, company_id, name, icon, description, display_order, is_active, created_at
            FROM department_templates
            WHERE company_id = ?
            ORDER BY display_order, name
        """, (company_id,))
        return [dict(row) for row in cursor.fetchall()]


def create_department_template(company_id: int, name: str, icon: str = '📁',
                               description: str = '', display_order: int = 0) -> int:
    """Yeni departman şablonu oluştur"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO department_templates (company_id, name, icon, description, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (company_id, name.strip(), icon, description, display_order))
        return cursor.lastrowid


def update_department_template(template_id: int, **kwargs) -> bool:
    """Departman şablonunu güncelle"""
    allowed_fields = ['name', 'icon', 'description', 'display_order', 'is_active']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return False

    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [template_id]

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE department_templates SET {set_clause} WHERE id = ?
        """, values)
        return cursor.rowcount > 0


def delete_department_template(template_id: int) -> bool:
    """Departman şablonunu sil"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM department_templates WHERE id = ?", (template_id,))
        return cursor.rowcount > 0


def seed_default_department_templates(company_id: int):
    """Şirket için varsayılan departman şablonlarını oluştur (15 standart Türk şirket departmanı)"""
    default_departments = [
        {"name": "Satın Alma", "icon": "🛒", "description": "Tedarik ve satın alma yönetimi"},
        {"name": "İnsan Kaynakları", "icon": "👥", "description": "İK, işe alım ve personel yönetimi"},
        {"name": "Finans", "icon": "💰", "description": "Finansal planlama ve yönetim"},
        {"name": "Muhasebe", "icon": "📊", "description": "Muhasebe ve mali işler"},
        {"name": "Bilgi Teknolojileri", "icon": "💻", "description": "IT altyapı ve yazılım geliştirme"},
        {"name": "Üretim", "icon": "🏭", "description": "Üretim ve imalat operasyonları"},
        {"name": "Kalite Kontrol", "icon": "✅", "description": "Kalite güvence ve kontrol"},
        {"name": "Satış", "icon": "📈", "description": "Satış ve iş geliştirme"},
        {"name": "Pazarlama", "icon": "📢", "description": "Pazarlama, reklam ve iletişim"},
        {"name": "Lojistik", "icon": "🚚", "description": "Lojistik, depo ve tedarik zinciri"},
        {"name": "Ar-Ge", "icon": "🔬", "description": "Araştırma ve geliştirme"},
        {"name": "Hukuk", "icon": "⚖️", "description": "Hukuk müşavirliği ve sözleşmeler"},
        {"name": "İdari İşler", "icon": "🏢", "description": "Genel idari ve ofis yönetimi"},
        {"name": "Müşteri Hizmetleri", "icon": "📞", "description": "Müşteri destek ve çağrı merkezi"},
        {"name": "Teknik Servis", "icon": "🔧", "description": "Teknik destek ve saha hizmetleri"},
    ]

    with get_connection() as conn:
        cursor = conn.cursor()
        for i, dept in enumerate(default_departments):
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO department_templates (company_id, name, icon, description, display_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (company_id, dept["name"], dept["icon"], dept["description"], i))
            except Exception as e:
                logger.debug(f"Departman template ekleme hatası (zaten var olabilir): {e}")
                # Zaten var, atla


# ============ CANDIDATE_POSITIONS CRUD ============

def add_candidate_to_position(candidate_id: int, position_id: int, match_score: int = 0) -> bool:
    """Adayı pozisyona ekle

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID
        match_score: Eşleşme skoru (0-100)

    Returns:
        True: Başarılı, False: Zaten mevcut veya hata
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO candidate_positions (candidate_id, position_id, match_score)
                VALUES (?, ?, ?)
            """, (candidate_id, position_id, match_score))
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False  # UNIQUE constraint - zaten mevcut


def get_candidate_details(candidate_id: int) -> dict:
    """Aday detay bilgilerini getirir"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, ad_soyad, email, telefon, lokasyon,
                       mevcut_pozisyon, mevcut_sirket, toplam_deneyim_yil,
                       teknik_beceriler, egitim, olusturma_tarihi
                FROM candidates
                WHERE id = ?
            """, (candidate_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'ad_soyad': row[1],
                    'email': row[2],
                    'telefon': row[3],
                    'lokasyon': row[4],
                    'mevcut_pozisyon': row[5],
                    'mevcut_sirket': row[6],
                    'toplam_deneyim_yil': row[7],
                    'teknik_beceriler': row[8],
                    'egitim_bilgileri': row[9],
                    'olusturma_tarihi': row[10]
                }
            return None
    except Exception as e:
        logger.error(f"get_candidate_details hatası: {e}", exc_info=True)
        return None


def get_candidate_positions(candidate_id: int) -> list[dict]:
    """Adayın bulunduğu pozisyonları getir

    Args:
        candidate_id: Aday ID

    Returns:
        Pozisyon listesi [{id, baslik, departman, match_score, status, created_at}, ...]
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.id, cp.position_id, dp.name as baslik,
                   COALESCE(parent.name, 'Bilinmiyor') as departman,
                   cp.match_score, cp.status, cp.created_at
            FROM candidate_positions cp
            JOIN department_pools dp ON cp.position_id = dp.id
            LEFT JOIN department_pools parent ON dp.parent_id = parent.id
            WHERE cp.candidate_id = ?
            ORDER BY cp.created_at DESC
        """, (candidate_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_position_candidates(position_id: int) -> list[dict]:
    """Pozisyondaki adayları getir

    Args:
        position_id: Pozisyon ID

    Returns:
        Aday listesi [{id, ad_soyad, email, match_score, status, created_at}, ...]
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.id, cp.candidate_id, c.ad_soyad, c.email, c.telefon,
                   c.mevcut_pozisyon, cp.match_score, cp.status, cp.created_at
            FROM candidate_positions cp
            JOIN candidates c ON cp.candidate_id = c.id
            WHERE cp.position_id = ?
            ORDER BY cp.match_score DESC, cp.created_at DESC
        """, (position_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_candidate_position_count(candidate_id: int, conn=None) -> int:
    """Adayın kaç pozisyonda olduğunu say

    Args:
        candidate_id: Aday ID
        conn: Mevcut veritabanı bağlantısı (isteğe bağlı). Verilmezse yeni bağlantı açılır.

    Returns:
        Pozisyon sayısı
    """
    # Bağlantı yönetimi
    close_conn = False
    if conn is None:
        from config import DATABASE_PATH
        ensure_data_dir()
        conn = sqlite3.connect(DATABASE_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM candidate_positions cp
            JOIN department_pools dp ON dp.id = cp.position_id
            WHERE cp.candidate_id = ? AND cp.status = 'aktif'
        """, (candidate_id,))
        return cursor.fetchone()[0]
    finally:
        # Bağlantıyı kapat (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.close()


def remove_candidate_from_position(candidate_id: int, position_id: int) -> bool:
    """Adayı pozisyondan çıkar

    Args:
        candidate_id: Aday ID
        position_id: Pozisyon ID

    Returns:
        True: Başarılı, False: Bulunamadı
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM candidate_positions
            WHERE candidate_id = ? AND position_id = ?
        """, (candidate_id, position_id))
        return cursor.rowcount > 0


def handle_position_deletion(position_id: int, company_id: int, conn=None) -> dict:
    """Pozisyon silindiğinde adayları uygun havuzlara taşı

    Mantık:
    - Adayın başka pozisyonu varsa: Sadece bu pozisyondan sil
    - Adayın başka pozisyonu yoksa:
      - CV 30 günden yeni ise: Genel Havuz'a taşı
      - CV 30 günden eski ise: Arşiv'e taşı

    Args:
        position_id: Silinen pozisyon ID
        company_id: Firma ID
        conn: Mevcut veritabanı bağlantısı (isteğe bağlı). Verilmezse yeni bağlantı açılır.

    Returns:
        {'deleted': int, 'to_general': int, 'to_archive': int}
    """
    stats = {'deleted': 0, 'to_general': 0, 'to_archive': 0}

    # Bağlantı yönetimi
    close_conn = False
    if conn is None:
        from config import DATABASE_PATH
        ensure_data_dir()
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        close_conn = True

    try:
        # Genel Havuz ve Arşiv'i bul
        general_pool = get_pool_by_name(company_id, 'Genel Havuz', conn=conn)
        archive_pool = get_pool_by_name(company_id, 'Arşiv', conn=conn)

        cursor = conn.cursor()

        # Bu pozisyondaki adayları al
        cursor.execute("""
            SELECT cp.candidate_id, c.olusturma_tarihi
            FROM candidate_positions cp
            JOIN candidates c ON cp.candidate_id = c.id
            WHERE cp.position_id = ?
        """, (position_id,))
        candidates = cursor.fetchall()

        for candidate_id, created_at in candidates:
            # Adayın başka pozisyonu var mı?
            other_positions = get_candidate_position_count(candidate_id, conn=conn)

            if other_positions > 1:
                # Başka pozisyonu var, sadece bu pozisyondan sil
                cursor.execute("""
                    DELETE FROM candidate_positions
                    WHERE candidate_id = ? AND position_id = ?
                """, (candidate_id, position_id))
                stats['deleted'] += 1
            else:
                # Başka pozisyonu yok, havuza taşı
                cursor.execute("""
                    DELETE FROM candidate_positions
                    WHERE candidate_id = ? AND position_id = ?
                """, (candidate_id, position_id))

                # CV yaşını hesapla
                if created_at:
                    try:
                        from datetime import datetime
                        if isinstance(created_at, str):
                            cv_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        else:
                            cv_date = created_at
                        days_old = (datetime.now() - cv_date.replace(tzinfo=None)).days
                    except Exception as e:
                        logger.debug(f"CV tarihi parse hatası: {e}")
                        days_old = 0
                else:
                    days_old = 0

                # 30 günden yeni mi?
                if days_old < 30 and general_pool:
                    assign_candidate_to_department_pool(
                        candidate_id, general_pool['id'], company_id, 'auto', 0,
                        'Pozisyon silindi - Genel Havuz\'a taşındı', conn=conn
                    )
                    stats['to_general'] += 1
                elif archive_pool:
                    assign_candidate_to_department_pool(
                        candidate_id, archive_pool['id'], company_id, 'auto', 0,
                        'Pozisyon silindi - Arşiv\'e taşındı', conn=conn
                    )
                    stats['to_archive'] += 1

        # Commit işlemi (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.commit()
    finally:
        # Bağlantıyı kapat (sadece yeni bağlantı açıldıysa)
        if close_conn:
            conn.close()

    return stats


def get_all_keywords() -> list:
    """Tüm aktif keyword'leri getir"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT keyword, category FROM keyword_dictionary ORDER BY usage_count DESC"
        ).fetchall()
        return [{'keyword': r[0], 'category': r[1]} for r in rows]


def add_keyword(keyword: str, category: str = 'genel', source: str = 'user_edit') -> bool:
    """Yeni keyword ekle, varsa False dön"""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO keyword_dictionary (keyword, category, source) VALUES (?, ?, ?)",
                (keyword.lower().strip(), category, source)
            )
            return conn.total_changes > 0
    except:
        return False


def increment_keyword_usage(keyword: str):
    """Kullanım sayısını artır"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE keyword_dictionary SET usage_count = usage_count + 1 WHERE keyword = ?",
            (keyword.lower().strip(),)
        )


def search_keywords_in_text(text: str) -> list:
    """Metinde keyword_dictionary'deki terimleri bul"""
    if not text:
        return []
    
    text_lower = text.lower()
    found = []
    
    keywords = get_all_keywords()
    for kw_dict in keywords:
        kw = kw_dict['keyword']
        # Word boundary ile ara (tam kelime eşleşmesi)
        pattern = r'(?<![a-zA-ZğüşıöçĞÜŞİÖÇ0-9])' + re.escape(kw) + r'(?![a-zA-ZğüşıöçĞÜŞİÖÇ0-9])'
        if re.search(pattern, text_lower):
            found.append(kw)
    
    return found


# ========== AKILLI HAVUZ: EŞDEĞER POZİSYON ÖNERİLERİ ==========

def save_suggested_titles(position_id: int, title_mappings: dict) -> bool:
    """
    categorize_and_save() sonrası AI'ın ürettiği başlıkları approved_title_mappings'e kaydet.
    title_mappings formatı: {'exact': [...], 'close': [...], 'partial': [...]}
    Tüm başlıklar is_approved=0 (bekliyor) olarak kaydedilir.
    Duplicate varsa IGNORE et.
    Return: True/False
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Tüm kategorileri işle
            for category in ['exact', 'close', 'partial']:
                titles = title_mappings.get(category, [])
                for title in titles:
                    if title and title.strip():
                        try:
                            cursor.execute("""
                                INSERT OR IGNORE INTO approved_title_mappings 
                                (position_id, title, category, is_approved)
                                VALUES (?, ?, ?, 0)
                            """, (position_id, title.strip(), category))
                        except Exception as e:
                            logger.warning(f"save_suggested_titles: Başlık eklenemedi ({title}): {e}")
                            continue
            
            return True
    except Exception as e:
        logger.error(f"save_suggested_titles FAILED: {e}", exc_info=True)
        return False


def get_pending_titles(position_id: int) -> list:
    """
    Onay bekleyen başlıkları getir.
    Return: [{'id': int, 'title': str, 'category': str}, ...]
    Sıralama: exact önce, sonra close, sonra partial
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, category
                FROM approved_title_mappings
                WHERE position_id = ? AND is_approved = 0
                ORDER BY 
                    CASE category
                        WHEN 'exact' THEN 1
                        WHEN 'close' THEN 2
                        WHEN 'partial' THEN 3
                        ELSE 4
                    END,
                    title
            """, (position_id,))
            
            rows = cursor.fetchall()
            return [{'id': row['id'], 'title': row['title'], 'category': row['category']} for row in rows]
    except Exception as e:
        logger.error(f"get_pending_titles FAILED: {e}", exc_info=True)
        return []


def get_approved_titles(position_id: int) -> list:
    """
    Onaylanmış başlıkları getir.
    Return: [{'id': int, 'title': str, 'category': str}, ...]
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, category
                FROM approved_title_mappings
                WHERE position_id = ? AND is_approved = 1
                ORDER BY 
                    CASE category
                        WHEN 'exact' THEN 1
                        WHEN 'close' THEN 2
                        WHEN 'partial' THEN 3
                        ELSE 4
                    END,
                    title
            """, (position_id,))
            
            rows = cursor.fetchall()
            return [{'id': row['id'], 'title': row['title'], 'category': row['category']} for row in rows]
    except Exception as e:
        logger.error(f"get_approved_titles FAILED: {e}", exc_info=True)
        return []


def approve_titles(position_id: int, approved_title_ids: list, rejected_title_ids: list) -> bool:
    """
    Seçilen başlıkları onayla (is_approved=1, approved_at=now), 
    seçilmeyenleri reddet (is_approved=-1).
    Return: True/False
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Onaylanan başlıkları güncelle
            if approved_title_ids:
                placeholders = ','.join(['?'] * len(approved_title_ids))
                cursor.execute(f"""
                    UPDATE approved_title_mappings
                    SET is_approved = 1, approved_at = CURRENT_TIMESTAMP
                    WHERE position_id = ? AND id IN ({placeholders})
                """, (position_id, *approved_title_ids))
            
            # Reddedilen başlıkları güncelle
            if rejected_title_ids:
                placeholders = ','.join(['?'] * len(rejected_title_ids))
                cursor.execute(f"""
                    UPDATE approved_title_mappings
                    SET is_approved = -1
                    WHERE position_id = ? AND id IN ({placeholders})
                """, (position_id, *rejected_title_ids))
            
            return True
    except Exception as e:
        logger.error(f"approve_titles FAILED: {e}", exc_info=True)
        return False


def has_pending_titles(position_id: int) -> bool:
    """
    Bu pozisyon için onay bekleyen başlık var mı?
    Return: True/False
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM approved_title_mappings
                WHERE position_id = ? AND is_approved = 0
            """, (position_id,))
            
            row = cursor.fetchone()
            return row['cnt'] > 0 if row else False
    except Exception as e:
        logger.error(f"has_pending_titles FAILED: {e}", exc_info=True)
        return False


# Veritabanini baslat
init_database()

# Varsayilan kullanicilari olustur
create_default_admin()
create_demo_company_and_user()

# Varsayilan sablonlari olustur
seed_default_templates()

# Meslek unvanlarini olustur
seed_job_titles()


def save_ai_evaluation(candidate_id: int, position_id: int, evaluation_text: str, v2_score: int = 0, eval_prompt: str = "") -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ai_evaluations 
                (candidate_id, position_id, evaluation_text, v2_score, eval_prompt, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (candidate_id, position_id, evaluation_text, v2_score, eval_prompt))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"save_ai_evaluation hatası: {e}")
        return False

def get_ai_evaluation(candidate_id: int, position_id: int) -> dict:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT evaluation_text, v2_score, created_at 
                FROM ai_evaluations 
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, position_id))
            row = cursor.fetchone()
            if row:
                return {'evaluation_text': row['evaluation_text'], 'v2_score': row['v2_score'], 'created_at': row['created_at']}
            return None
    except Exception as e:
        logger.error(f"get_ai_evaluation hatası: {e}")
        return None
