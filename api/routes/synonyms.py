"""
FAZ 3 - Synonym Yönetimi API Routes
8 Endpoint: list, pending, pending_count, create, delete, approve, reject, generate
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import sys
import os
import json
import logging
import time
import anthropic
sys.path.append("/var/www/hylilabs/api")
from database import (
    get_keyword_synonyms,
    get_pending_synonyms,
    get_pending_synonyms_count,
    add_manual_synonym,
    delete_synonym,
    approve_synonyms,
    reject_synonyms,
    save_generated_synonyms,
    get_approved_synonym_count,
    log_api_usage,
    get_reject_stats,
    get_blacklist_candidates,
    # FAZ 8.2.3: Keyword Importance
    get_keyword_importance,
    set_keyword_importance,
    get_company_keyword_importances,
    delete_keyword_importance,
    # FAZ 10.1: Confidence sistemi
    calculate_final_confidence,
    get_connection,
    # FAZ 10.2: Semantic Similarity
    check_semantic_similarity,
    find_semantic_duplicates,
    get_embedding,
    semantic_similarity,
    save_synonym_embedding,
    # FAZ 10.3: Multi-language Normalization
    normalize_keyword,
    translate_to_canonical,
    detect_language,
    stem_word,
    TRANSLATION_DICTIONARY,
    ENGLISH_CANONICAL,
    # FAZ 10.4: ML-Based Auto-Learning
    predict_approval_probability,
    auto_process_synonym,
    train_synonym_model,
    extract_synonym_features,
    prepare_training_data,
    FEATURE_NAMES,
    check_retraining_needed,
    run_retraining_job,
    start_ab_test,
    get_ab_test_results,
    end_ab_test,
    AUTO_APPROVE_THRESHOLD,
    AUTO_REJECT_THRESHOLD,
    SKLEARN_AVAILABLE
)
from routes.auth import get_current_user
from rate_limiter import (
    check_synonym_generate_limit,
    record_synonym_generate,
    check_synonym_batch_generate_limit,
    record_synonym_batch_generate
)
from audit_logger import log_action, AuditAction, EntityType

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# AI SYNONYM KALİTE SİSTEMİ v2 - Blacklist ve Filter Kuralları
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 8.1.1: REJECT REASON KATEGORILERI
# HR in synonym reddetme sebepleri
# ═══════════════════════════════════════════════════════════════════════════════
REJECT_REASONS = {
    "too_general": {
        "code": "too_general",
        "label_tr": "Cok Genel",
        "label_en": "Too General",
        "description": "Kelime cok genis kapsamli, spesifik degil"
    },
    "technically_wrong": {
        "code": "technically_wrong",
        "label_tr": "Teknik Olarak Yanlis",
        "label_en": "Technically Wrong",
        "description": "Teknik acidan hatali veya yanlis eslestirme"
    },
    "out_of_context": {
        "code": "out_of_context",
        "label_tr": "Baglam Disi",
        "label_en": "Out of Context",
        "description": "Keyword ile alakasiz, farkli baglamda kullaniliyor"
    },
    "duplicate": {
        "code": "duplicate",
        "label_tr": "Tekrar",
        "label_en": "Duplicate",
        "description": "Zaten mevcut bir synonym ile ayni veya cok benzer"
    },
    "meaningless": {
        "code": "meaningless",
        "label_tr": "Anlamsiz",
        "label_en": "Meaningless",
        "description": "Anlam ifade etmiyor veya ise yaramaz"
    },
    "different_concept": {
        "code": "different_concept",
        "label_tr": "Farkli Kavram",
        "label_en": "Different Concept",
        "description": "Es anlamli degil, tamamen farkli bir kavram"
    },
    "other": {
        "code": "other",
        "label_tr": "Diger",
        "label_en": "Other",
        "description": "Yukaridaki kategorilere girmeyen diger sebepler"
    }
}

# Basit liste (API response icin)
REJECT_REASON_CODES = list(REJECT_REASONS.keys())

# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 9.1: GELISMIS SYNONYM TIP SISTEMI - 6 tip, weight + label_tr
# Mevcut 3 tip (abbreviation, english, turkish) + Yeni 3 tip (exact_synonym, broader_term, narrower_term)
# ═══════════════════════════════════════════════════════════════════════════════
SYNONYM_TYPES = {
    # MEVCUT TIPLER (387 kayit - degismez)
    "abbreviation": {
        "weight": 0.95,
        "label_tr": "Kısaltma",
        "desc": "cad → autocad"
    },
    "english": {
        "weight": 0.90,
        "label_tr": "İngilizce Çeviri",
        "desc": "bakım → maintenance"
    },
    "turkish": {
        "weight": 0.85,
        "label_tr": "Türkçe Çeviri",
        "desc": "maintenance → bakım"
    },
    # YENI TIPLER (FAZ 9.1)
    "exact_synonym": {
        "weight": 1.00,
        "label_tr": "Birebir Eş Anlamlı",
        "desc": "hızlı = çabuk"
    },
    "broader_term": {
        "weight": 0.70,
        "label_tr": "Üst Kavram",
        "desc": "python → programlama"
    },
    "narrower_term": {
        "weight": 0.60,
        "label_tr": "Alt Kavram",
        "desc": "programlama → python"
    }
}

# Geriye uyumluluk icin SYNONYM_TYPE_WEIGHTS (FAZ 8.3 kodu icin)
SYNONYM_TYPE_WEIGHTS = {k: v["weight"] for k, v in SYNONYM_TYPES.items()}


def get_weight_for_type(synonym_type: str) -> float:
    """
    Synonym tipine gore match_weight dondur.

    Args:
        synonym_type: Synonym tipi (abbreviation, english, turkish, exact_synonym, broader_term, narrower_term)

    Returns:
        float: 0.0-1.0 arasi agirlik degeri
    """
    type_lower = synonym_type.lower().strip() if synonym_type else ""
    if type_lower in SYNONYM_TYPES:
        return SYNONYM_TYPES[type_lower]["weight"]
    return 0.80  # Bilinmeyen tipler icin default


def get_type_label(synonym_type: str) -> str:
    """
    Synonym tipinin Turkce etiketini dondur.

    Args:
        synonym_type: Synonym tipi

    Returns:
        str: Turkce etiket
    """
    type_lower = synonym_type.lower().strip() if synonym_type else ""
    if type_lower in SYNONYM_TYPES:
        return SYNONYM_TYPES[type_lower]["label_tr"]
    return "Bilinmeyen"


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 8.2: DINAMIK MAX LIMIT - Yuksek Kapsamli Keyword'ler
# Bu keyword'ler icin maksimum 5 synonym uretilir (default 3)
# ═══════════════════════════════════════════════════════════════════════════════
HIGH_COVERAGE_KEYWORDS = {
    # Programlama Dilleri
    "python", "javascript", "java", "sql", "c#", "c++", "php", "ruby", "go", "typescript",
    "kotlin", "swift", "scala", "rust", "perl", "r", "matlab",
    # Frontend/Backend Frameworks
    "react", "angular", "vue", "node", "django", "flask", "spring", ".net", "laravel",
    "express", "fastapi", "next.js", "nuxt", "svelte",
    # DevOps & Cloud
    "docker", "kubernetes", "aws", "azure", "gcp", "linux", "git", "devops", "jenkins",
    "terraform", "ansible", "ci/cd", "gitlab", "github",
    # Veritabani
    "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "oracle", "sql server",
    # Data & AI
    "machine learning", "deep learning", "data science", "tableau", "power bi",
    "tensorflow", "pytorch", "pandas", "numpy", "spark",
    # Tasarim & Muhendislik Araclari
    "excel", "autocad", "solidworks", "sap", "revit", "catia", "nx", "creo",
    "photoshop", "illustrator", "figma", "sketch",
    # Turkce Yaygin Terimler
    "yazilim", "yazılım", "gelistirme", "geliştirme", "muhendis", "mühendis",
    "yonetim", "yönetim", "analiz", "muhasebe", "satis", "satış",
    "pazarlama", "uretim", "üretim", "kalite", "tasarim", "tasarım", "mimari"
}

# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 9.3: İKİ SEVİYELİ BLACKLIST SİSTEMİ
# ═══════════════════════════════════════════════════════════════════════════════

# GLOBAL_BLACKLIST: Her zaman engellenen kelimeler (bağlamdan bağımsız)
GLOBAL_BLACKLIST = [
    # Soft Skills (Yumuşak Beceriler) - Bunlar keyword olmamalı
    "iletisim", "iletişim", "koordinasyon", "takim calismasi", "takım çalışması",
    "liderlik", "problem cozme", "problem çözme", "analitik dusunme", "analitik düşünme",
    "yaraticilik", "yaratıcılık", "esneklik", "adaptasyon", "motivasyon",
    "zaman yonetimi", "zaman yönetimi", "stres yonetimi", "stres yönetimi",
    "karar verme", "empati", "ikna", "muzakere", "müzakere", "sunum",
    "raporlama", "organizasyon", "planlama", "detay odakli", "detay odaklı",
    "sonuc odakli", "sonuç odaklı", "inisiyatif", "proaktif", "ozguven", "özgüven",
    # Kişilik Özellikleri
    "dinamik", "titiz", "dikkatli", "sabir", "sabır", "azim", "kararlılık",
    "dürüstlük", "güvenilir", "sorumluluk", "disiplin", "profesyonel",
    # Genel İş Terimleri (çok geniş)
    "deneyim", "tecrube", "tecrübe", "uzmanlik", "uzmanlık", "bilgi", "beceri",
    "yetenek", "kabiliyet", "performans", "verimlilik", "kalite"
]

# Geriye uyumluluk alias
SYNONYM_BLACKLIST = GLOBAL_BLACKLIST

# CONTEXTUAL_BLACKLIST: Bağlama göre izin verilen kelimeler
# Key: Tek başına engellenecek kelime
# Value: Bu keyword'lerle birlikte kullanılırsa İZİN VERİLİR
CONTEXTUAL_BLACKLIST = {
    "analiz": ["risk", "veri", "sistem", "maliyet", "iş", "finansal", "data", "swot", "gap"],
    "yönetim": ["proje", "risk", "kalite", "üretim", "stok", "müşteri", "tedarik", "zaman"],
    "yonetim": ["proje", "risk", "kalite", "uretim", "stok", "musteri", "tedarik", "zaman"],
    "sistem": ["erp", "crm", "bilgi", "yönetim", "otomasyon", "entegrasyon", "veritabani"],
    "süreç": ["iş", "üretim", "kalite", "tedarik", "onay", "satın alma"],
    "surec": ["is", "uretim", "kalite", "tedarik", "onay", "satin alma"],
    "planlama": ["üretim", "kaynak", "proje", "stratejik", "kapasite", "malzeme"],
    "kontrol": ["kalite", "stok", "maliyet", "bütçe", "envanter"],
    "takip": ["proje", "sipariş", "sevkiyat", "stok", "iş"],
}

# SECTOR_BLACKLISTS: Sektör bazlı özel engeller (ileride doldurulacak)
SECTOR_BLACKLISTS = {
    "IT": set(),
    "Insaat": set(),
    "Finans": set(),
    "Uretim": set(),
    "Saglik": set(),
}

# GENERAL_WORDS: Çok genel kelimeler (tek başına anlamsız)
GENERAL_WORDS = [
    # Çok genel kelimeler - synonym olarak anlamsız
    "is", "iş", "proje", "gorev", "görev", "yonetim", "yönetim", "sistem",
    "surekli", "sürekli", "gelistirme", "geliştirme", "iyilestirme", "iyileştirme",
    "analiz", "kontrol", "takip", "destek", "hizmet", "uygulama", "cozum", "çözüm",
    "strateji", "operasyon", "surec", "süreç", "faaliyet"
]


def is_contextually_allowed(synonym: str, keyword: str) -> bool:
    """
    FAZ 9.3: Synonym'un keyword bağlamında izin verilip verilmediğini kontrol et.

    CONTEXTUAL_BLACKLIST'te olan kelimeler:
    - Tek başına synonym olarak → BLOCKED
    - Keyword ile bağlam oluşturuyorsa → ALLOWED

    Örnek:
    - "analiz" tek başına → False (blocked)
    - "risk analizi" keyword için "analiz" → True (allowed, çünkü "risk" bağlamı var)

    Args:
        synonym: Kontrol edilecek synonym
        keyword: Ana keyword

    Returns:
        True: İzin verilir (bağlam var veya blacklist'te değil)
        False: Engellenir (bağlam yok)
    """
    synonym_lower = synonym.lower().strip()
    keyword_lower = keyword.lower().strip()

    # CONTEXTUAL_BLACKLIST'te değilse → izin ver
    if synonym_lower not in CONTEXTUAL_BLACKLIST:
        return True

    # Keyword'de izin verilen bağlam kelimeleri var mı?
    allowed_contexts = CONTEXTUAL_BLACKLIST.get(synonym_lower, [])

    for context in allowed_contexts:
        # Keyword içinde bağlam kelimesi varsa izin ver
        if context in keyword_lower:
            return True

    # Bağlam bulunamadı → engelle
    return False


def get_max_synonym_limit(keyword: str, company_id: int = None) -> int:
    """
    Keyword'e göre dinamik maksimum synonym limiti döndür.

    FAZ 8.2.3: Firma Bazlı Dinamik Limit Sistemi
    Öncelik sırası:
    1. DB'de firma bazlı importance varsa: high=5, low=2
    2. HIGH_COVERAGE_KEYWORDS'de varsa: 5 synonym
    3. 20 karakterden uzun keyword: 4 synonym
    4. Standart keyword: 3 synonym

    Args:
        keyword: Limit hesaplanacak keyword
        company_id: Firma ID (opsiyonel, DB kontrolü için)

    Returns:
        int: Maksimum synonym sayısı (2, 3, 4, veya 5)
    """
    kw = keyword.lower().strip()

    # 1. Firma bazlı importance kontrolü (DB)
    if company_id:
        db_importance = get_keyword_importance(kw, company_id)
        if db_importance == 'high':
            return 5
        elif db_importance == 'low':
            return 2
        # 'normal' veya None ise fallback'e devam et

    # 2. Yüksek kapsamlı keyword'ler: 5 synonym
    if kw in HIGH_COVERAGE_KEYWORDS:
        return 5

    # 3. Uzun keyword'ler: 4 synonym
    if len(kw) > 20:
        return 4

    # 4. Standart: 3 synonym
    return 3


SYNONYM_PROMPT_BATCH_V2 = """Sen İK alanında TEKNIK BECERİ uzmanisin.
Verilen keyword'ler için SADECE teknik/mesleki synonym öner.

Keywords: {keywords}

YASAK ÖNERILER (ASLA ÜRETMEYECEKSİN):
- Soft skills: iletişim, liderlik, takım çalışması, problem çözme
- Kişilik özellikleri: dinamik, titiz, proaktif, özgüvenli
- Genel terimler: deneyim, bilgi, beceri, yetenek, proje, görev

KULLANILABILIR SYNONYM TIPLERI (6 tip):
1. "abbreviation" - Kısaltma: cad → autocad, js → javascript
2. "english" - İngilizce çeviri: bakım → maintenance
3. "turkish" - Türkçe çeviri: maintenance → bakım
4. "exact_synonym" - Birebir eş anlamlı: hızlı = çabuk, yazılım = software
5. "broader_term" - Üst kavram: python → programlama dili, react → frontend
6. "narrower_term" - Alt kavram: programlama → python, veritabanı → mysql

Kurallar:
1. Her keyword için MAX 3 synonym
2. Her öneriye 0.0-1.0 arası confidence puanı ver
3. Sadece 0.7+ confidence olanları dahil et
4. Keyword'ün kendisini EKLEME
5. exact_synonym için %100 eş anlamlı olmalı (en yüksek güvenilirlik)
6. broader_term: keyword'ün dahil olduğu daha geniş kategori
7. narrower_term: keyword'ün altında kalan daha spesifik terim

JSON formatı:
{{
  "results": [
    {{
      "keyword": "python",
      "synonyms": [
        {{"synonym": "py", "synonym_type": "abbreviation", "confidence": 0.95}},
        {{"synonym": "programlama dili", "synonym_type": "broader_term", "confidence": 0.80}}
      ]
    }}
  ]
}}"""

SYNONYM_PROMPT_SINGLE_V2 = """Sen İK alanında TEKNIK BECERİ uzmanisin.
Verilen keyword için SADECE teknik/mesleki synonym öner.

Keyword: {keyword}

YASAK ÖNERILER (ASLA ÜRETMEYECEKSİN):
- Soft skills: iletişim, liderlik, takım çalışması, problem çözme
- Kişilik özellikleri: dinamik, titiz, proaktif, özgüvenli
- Genel terimler: deneyim, bilgi, beceri, yetenek, proje, görev

KULLANILABILIR SYNONYM TIPLERI (6 tip):
1. "abbreviation" - Kısaltma: cad → autocad, js → javascript
2. "english" - İngilizce çeviri: bakım → maintenance
3. "turkish" - Türkçe çeviri: maintenance → bakım
4. "exact_synonym" - Birebir eş anlamlı: hızlı = çabuk, yazılım = software
5. "broader_term" - Üst kavram: python → programlama dili, react → frontend
6. "narrower_term" - Alt kavram: programlama → python, veritabanı → mysql

Kurallar:
1. MAX 3 synonym öner
2. Her öneriye 0.0-1.0 arası confidence puanı ver
3. Sadece 0.7+ confidence olanları dahil et
4. Keyword'ün kendisini EKLEME
5. exact_synonym için %100 eş anlamlı olmalı (en yüksek güvenilirlik)
6. broader_term: keyword'ün dahil olduğu daha geniş kategori
7. narrower_term: keyword'ün altında kalan daha spesifik terim

JSON formatı:
{{
  "synonyms": [
    {{"synonym": "insan kaynakları", "synonym_type": "turkish", "confidence": 0.95}},
    {{"synonym": "human resources", "synonym_type": "english", "confidence": 0.90}},
    {{"synonym": "İK", "synonym_type": "abbreviation", "confidence": 0.85}}
  ]
}}"""


def filter_ai_synonyms(keyword: str, ai_synonyms: list, company_id: int = None) -> list:
    """
    AI tarafından üretilen synonym'ları filtrele ve kalite kontrolünden geçir.

    FAZ 9.3: İki seviyeli blacklist sistemi:
    1. GLOBAL_BLACKLIST kontrolü (soft skills, kişilik - HER ZAMAN engelle)
    2. CONTEXTUAL_BLACKLIST kontrolü (bağlama göre izin ver)
    3. GENERAL_WORDS kontrolü (çok genel terimler)
    4. Confidence score kontrolü (0.7 threshold)
    5. Keyword ile aynı olanları çıkar
    6. Dinamik max synonym limiti (FAZ 8.2.3)

    Args:
        keyword: Ana keyword
        ai_synonyms: AI'dan gelen synonym listesi
        company_id: Firma ID (opsiyonel, dinamik limit için)

    Returns:
        Filtrelenmiş synonym listesi (confidence olmadan, synonym_type ile)
    """
    filtered = []
    keyword_lower = keyword.lower().strip()
    max_limit = get_max_synonym_limit(keyword, company_id)

    for item in ai_synonyms:
        # Dict kontrolü
        if not isinstance(item, dict):
            continue

        synonym = item.get("synonym", "").lower().strip()
        # synonym_type key'ini kontrol et (hem "synonym_type" hem "type" kabul et)
        syn_type = item.get("synonym_type") or item.get("type", "turkish")
        confidence = item.get("confidence", 0.8)  # default 0.8

        # Boş synonym kontrolü
        if not synonym:
            continue

        # Keyword ile aynı mı kontrolü
        if synonym == keyword_lower:
            continue

        # FAZ 9.3: GLOBAL_BLACKLIST kontrolü (HER ZAMAN engelle)
        if synonym in GLOBAL_BLACKLIST:
            continue

        # FAZ 9.3: CONTEXTUAL_BLACKLIST kontrolü (bağlama göre izin ver)
        if not is_contextually_allowed(synonym, keyword):
            continue

        # General words kontrolü (CONTEXTUAL_BLACKLIST'te olmayanlar için)
        if synonym in GENERAL_WORDS and synonym not in CONTEXTUAL_BLACKLIST:
            continue

        # Confidence threshold kontrolü
        if confidence < 0.7:
            continue

        # "variation" tipini "turkish" olarak dönüştür (eski AI çıktıları için)
        if syn_type == "variation":
            syn_type = "turkish"

        # FAZ 9.1: 6 geçerli tip kontrolü
        valid_types = list(SYNONYM_TYPES.keys())  # 6 tip: abbreviation, english, turkish, exact_synonym, broader_term, narrower_term
        if syn_type not in valid_types:
            syn_type = "turkish"  # Bilinmeyen tipler turkish olarak işaretlenir

        # Sonuca ekle (confidence OLMADAN, sadece synonym ve synonym_type)
        filtered.append({
            "synonym": synonym,
            "synonym_type": syn_type
        })

        # Dinamik max synonym limiti (FAZ 8.2)
        if len(filtered) >= max_limit:
            break

    return filtered


router = APIRouter(prefix="/api/synonyms", tags=["synonyms"])


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def require_company_user(current_user: dict):
    """Firma kullanıcısı kontrolü - super_admin bu endpoint'e erişemez"""
    if current_user.get("company_id") is None:
        raise HTTPException(
            status_code=403,
            detail="Bu işlem firma kullanıcılarına özeldir."
        )


def require_company_or_super_admin(current_user: dict) -> dict:
    """
    FAZ 3: Synonym approve için özel auth helper.
    - super_admin: erişebilir, company_id=None döner
    - company_admin/user: erişebilir, company_id döner

    Returns:
        {"is_super_admin": bool, "company_id": int|None, "user_id": int}
    """
    rol = current_user.get("rol")
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if rol == "super_admin":
        return {"is_super_admin": True, "company_id": None, "user_id": user_id}
    elif company_id is not None:
        return {"is_super_admin": False, "company_id": company_id, "user_id": user_id}
    else:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELLERİ
# ═══════════════════════════════════════════════════════════════════════════════

class SynonymCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    synonym: str = Field(..., min_length=1, max_length=100)
    synonym_type: Optional[str] = None  # turkish, english, abbreviation, variation
    auto_approve: bool = False
    scope: Optional[str] = Field("company", description="FAZ 3.2: 'global' veya 'company'")


class SynonymUpdateRequest(BaseModel):
    """FAZ 3.2: Synonym güncelleme request model"""
    status: Optional[str] = Field(None, description="pending, approved, rejected")
    scope: Optional[str] = Field(None, description="global veya company")
    match_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    synonym_type: Optional[str] = Field(None, description="Synonym tipi")


class SynonymBulkActionRequest(BaseModel):
    synonym_ids: List[int] = Field(..., min_length=1)
    scope: Optional[str] = Field("company", description="Onay kapsamı: 'global' veya 'company'")


class SynonymRejectRequest(BaseModel):
    synonym_ids: List[int] = Field(..., min_length=1)
    reject_reason: str = Field(..., min_length=1, description="Red sebebi kodu")
    reject_note: Optional[str] = Field(None, description="Opsiyonel aciklama notu")


class SynonymGenerateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: GET /api/synonyms - Synonym listesi (FAZ 3.2 güncellemesi)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("")
def list_synonyms(
    keyword: Optional[str] = Query(None, description="Keyword filtresi (opsiyonel)"),
    status: Optional[str] = Query(None, description="Filtre: pending, approved, rejected"),
    page: int = Query(1, ge=1, description="Sayfa numarası"),
    per_page: int = Query(20, ge=1, le=100, description="Sayfa başına kayıt"),
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3.2: Synonym listesi döndür.
    - keyword verilmezse tüm synonym'ları döndürür (pagination ile)
    - keyword verilirse o keyword'e ait synonym'ları döndürür
    - super_admin: tüm synonym'ler
    - company_admin/user: kendi firma + global (NULL) synonym'ler
    """
    try:
        # FAZ 3.2: super_admin tüm synonym'leri görebilir
        auth_info = require_company_or_super_admin(current_user)
        company_id = auth_info["company_id"]
        is_super_admin = auth_info["is_super_admin"]

        # Keyword verilmişse mevcut davranış (geriye uyumluluk)
        if keyword:
            synonyms = get_keyword_synonyms(
                keyword=keyword,
                company_id=company_id,
                status=status,
                include_global=True
            )
            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "synonyms": synonyms,
                    "total": len(synonyms)
                }
            }

        # FAZ 3.2: Keyword yoksa tüm synonym'ları getir (pagination ile)
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Count sorgusu
        if is_super_admin:
            count_sql = "SELECT COUNT(*) FROM keyword_synonyms WHERE 1=1"
            count_params = []
        else:
            count_sql = "SELECT COUNT(*) FROM keyword_synonyms WHERE (company_id IS NULL OR company_id = ?)"
            count_params = [company_id]

        if status:
            count_sql += " AND status = ?"
            count_params.append(status)

        cursor.execute(count_sql, count_params)
        total = cursor.fetchone()[0]

        # Data sorgusu
        offset = (page - 1) * per_page
        if is_super_admin:
            data_sql = """
                SELECT id, keyword, synonym, synonym_type, status, match_weight,
                       company_id, created_by, created_at, confidence_score
                FROM keyword_synonyms
                WHERE 1=1
            """
            data_params = []
        else:
            data_sql = """
                SELECT id, keyword, synonym, synonym_type, status, match_weight,
                       company_id, created_by, created_at, confidence_score
                FROM keyword_synonyms
                WHERE (company_id IS NULL OR company_id = ?)
            """
            data_params = [company_id]

        if status:
            data_sql += " AND status = ?"
            data_params.append(status)

        data_sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        data_params.extend([per_page, offset])

        cursor.execute(data_sql, data_params)

        items = []
        for row in cursor.fetchall():
            items.append({
                "id": row[0],
                "keyword": row[1],
                "synonym": row[2],
                "synonym_type": row[3],
                "status": row[4],
                "match_weight": row[5],
                "company_id": row[6],
                "created_by": row[7],
                "created_at": row[8],
                "confidence_score": row[9],
                "is_global": row[6] is None
            })

        conn.close()

        return {
            "success": True,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2: GET /api/synonyms/pending - Onay bekleyen synonym'lar
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/pending")
def list_pending_synonyms(
    keyword: Optional[str] = Query(None, description="Keyword filtresi"),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Onay bekleyen synonym listesi.
    İK kullanıcıları bu listeyi görüntüleyip onay/red yapabilir.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        synonyms = get_pending_synonyms(
            company_id=company_id,
            keyword=keyword,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "synonyms": synonyms,
                "total": len(synonyms)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3: GET /api/synonyms/pending/count - Badge için sayı
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/pending/count")
def get_pending_count(
    current_user: dict = Depends(get_current_user)
):
    """
    Onay bekleyen synonym sayısı.
    Dashboard badge için kullanılır.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        count = get_pending_synonyms_count(company_id=company_id)

        return {
            "success": True,
            "data": {
                "count": count
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.5: GET /api/synonyms/reject_reasons - Red sebepleri listesi
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/reject_reasons")
def get_reject_reasons(
    current_user: dict = Depends(get_current_user)
):
    """
    Red sebepleri listesi.
    Frontend dropdown için kullanılır.
    """
    try:
        require_company_user(current_user)

        # REJECT_REASONS dict'ini frontend-friendly listeye çevir
        reasons_list = [
            {
                "code": data["code"],
                "label": data["label_tr"],
                "description": data["description"]
            }
            for data in REJECT_REASONS.values()
        ]

        return {
            "success": True,
            "data": {
                "reasons": reasons_list
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.6: GET /api/synonyms/reject_stats - Red istatistikleri raporu
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/reject_stats")
def get_reject_statistics(
    current_user: dict = Depends(get_current_user)
):
    """
    Red istatistikleri raporu.
    FAZ 8.1.7: Sebep bazlı dağılım, kaynak bazlı dağılım, en çok reddedilenler.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        stats = get_reject_stats(company_id=company_id)

        return {
            "success": True,
            "data": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.7: GET /api/synonyms/blacklist_candidates - Blacklist adayları
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/blacklist_candidates")
def list_blacklist_candidates(
    status: Optional[str] = Query("pending", description="Filtre: pending, approved, ignored"),
    current_user: dict = Depends(get_current_user)
):
    """
    Blacklist adaylarını listele.
    FAZ 8.1.8: 3+ kez reddedilen synonym'lar otomatik olarak bu listeye eklenir.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        candidates = get_blacklist_candidates(
            company_id=company_id,
            status=status
        )

        return {
            "success": True,
            "data": {
                "candidates": candidates,
                "total": len(candidates)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.8: POST /api/synonyms/blacklist_candidates/{id}/approve
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/blacklist_candidates/{candidate_id}/approve")
def approve_blacklist_candidate(
    candidate_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.3: Blacklist adayını onayla -> GLOBAL_BLACKLIST'e ekle (approved status).
    Not: Gerçek GLOBAL_BLACKLIST Python'da sabit liste, bu sadece status günceller.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Adayı bul
        cursor.execute(
            "SELECT synonym FROM blacklist_candidates WHERE id = ? AND company_id = ?",
            (candidate_id, company_id)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Aday bulunamadı")

        synonym = row[0]

        # Status'u approved yap
        cursor.execute(
            "UPDATE blacklist_candidates SET status = 'approved' WHERE id = ?",
            (candidate_id,)
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"'{synonym}' blacklist'e eklendi",
            "data": {"synonym": synonym, "status": "approved"}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.9: POST /api/synonyms/blacklist_candidates/{id}/dismiss
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/blacklist_candidates/{candidate_id}/dismiss")
def dismiss_blacklist_candidate(
    candidate_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.3: Blacklist adayını reddet -> listeden kaldır (dismissed status).
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Adayı bul
        cursor.execute(
            "SELECT synonym FROM blacklist_candidates WHERE id = ? AND company_id = ?",
            (candidate_id, company_id)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Aday bulunamadı")

        synonym = row[0]

        # Status'u dismissed yap
        cursor.execute(
            "UPDATE blacklist_candidates SET status = 'dismissed' WHERE id = ?",
            (candidate_id,)
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"'{synonym}' aday listesinden kaldırıldı",
            "data": {"synonym": synonym, "status": "dismissed"}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.10: GET /api/synonyms/audit - Genel audit raporu
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/audit")
def get_synonym_audit(
    user_id: Optional[int] = Query(None, description="Kullanıcı ID filtresi"),
    from_date: Optional[str] = Query(None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Bitiş tarihi (YYYY-MM-DD)"),
    action: Optional[str] = Query(None, description="Action filtresi (created, approved, rejected)"),
    limit: int = Query(100, description="Maksimum kayıt sayısı"),
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.4: Genel synonym audit raporu.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Base query
        query = """
            SELECT h.id, h.synonym_id, h.action, h.old_values, h.new_values,
                   h.changed_by, h.changed_at, u.email as changed_by_email,
                   s.keyword, s.synonym
            FROM keyword_synonyms_history h
            LEFT JOIN users u ON h.changed_by = u.id
            LEFT JOIN keyword_synonyms s ON h.synonym_id = s.id
            WHERE (s.company_id IS NULL OR s.company_id = ?)
        """
        params = [company_id]

        # Filtreler
        if user_id is not None:
            query += " AND h.changed_by = ?"
            params.append(user_id)

        if from_date:
            query += " AND h.changed_at >= ?"
            params.append(from_date + " 00:00:00")

        if to_date:
            query += " AND h.changed_at <= ?"
            params.append(to_date + " 23:59:59")

        if action:
            query += " AND h.action = ?"
            params.append(action)

        query += " ORDER BY h.changed_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        audit_logs = []
        for row in cursor.fetchall():
            audit_logs.append({
                "id": row[0],
                "synonym_id": row[1],
                "action": row[2],
                "old_values": row[3],
                "new_values": row[4],
                "changed_by": row[5],
                "changed_at": row[6],
                "changed_by_email": row[7],
                "keyword": row[8],
                "synonym": row[9]
            })

        conn.close()

        return {
            "success": True,
            "data": audit_logs,
            "total": len(audit_logs)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 3.11: GET /api/synonyms/{id}/history - Tek synonym değişiklik geçmişi
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{synonym_id}/history")
def get_synonym_history(
    synonym_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.4: Tek synonym için değişiklik geçmişini getir.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Synonym'un bu firmaya ait olduğunu doğrula
        cursor.execute(
            "SELECT id FROM keyword_synonyms WHERE id = ? AND (company_id IS NULL OR company_id = ?)",
            (synonym_id, company_id)
        )
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Synonym bulunamadı")

        # History kayıtlarını getir
        cursor.execute("""
            SELECT h.id, h.synonym_id, h.action, h.old_values, h.new_values,
                   h.changed_by, h.changed_at, u.email as changed_by_email
            FROM keyword_synonyms_history h
            LEFT JOIN users u ON h.changed_by = u.id
            WHERE h.synonym_id = ?
            ORDER BY h.changed_at DESC
        """, (synonym_id,))

        history = []
        for row in cursor.fetchall():
            history.append({
                "id": row[0],
                "synonym_id": row[1],
                "action": row[2],
                "old_values": row[3],
                "new_values": row[4],
                "changed_by": row[5],
                "changed_at": row[6],
                "changed_by_email": row[7]
            })

        conn.close()

        return {
            "success": True,
            "data": history
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 4: POST /api/synonyms - Manuel synonym ekle (FAZ 3.2 scope desteği)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("")
def create_synonym(
    request: SynonymCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3.2: Yeni synonym ekle.
    - scope="company": company_id=user.company_id, status="pending" (mevcut davranış)
    - scope="global": sadece super_admin, company_id=NULL, status="approved"
    auto_approve=True ise direkt onaylanır, False ise pending olur.
    FAZ 10.2: Semantic similarity kontrolü.
    FAZ 10.4: ML auto-approve/reject entegrasyonu.
    """
    try:
        # FAZ 3.2: scope desteği için yeni auth
        auth_info = require_company_or_super_admin(current_user)
        is_super_admin = auth_info["is_super_admin"]
        user_id = auth_info["user_id"]

        keyword = request.keyword.strip()
        synonym = request.synonym.strip()
        scope = request.scope or "company"

        # FAZ 3.2: Global scope kontrolü
        if scope == "global":
            if not is_super_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Global synonym oluşturma sadece super_admin yetkisiyle yapılabilir."
                )
            company_id = None  # Global synonym
            auto_approve = True  # Global synonym direkt onaylı
        else:
            # Company scope - mevcut davranış
            if auth_info["company_id"] is None and not is_super_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Firma bazlı synonym için firma kullanıcısı olmalısınız."
                )
            company_id = auth_info["company_id"]
            auto_approve = request.auto_approve

        # FAZ 3.2: Duplicate kontrolü
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        if company_id is None:
            cursor.execute(
                "SELECT id FROM keyword_synonyms WHERE keyword = ? AND synonym = ? AND company_id IS NULL",
                (keyword, synonym)
            )
        else:
            cursor.execute(
                "SELECT id FROM keyword_synonyms WHERE keyword = ? AND synonym = ? AND company_id = ?",
                (keyword, synonym, company_id)
            )
        existing = cursor.fetchone()
        conn.close()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Bu synonym zaten mevcut (ID: {existing[0]})"
            )

        # FAZ 10.2: Semantic similarity kontrolü
        semantic_result = check_semantic_similarity(keyword, synonym)
        semantic_score = semantic_result.get("similarity", 0)

        # Uyarı mesajı (düşük benzerlik durumunda)
        semantic_warning = None
        if semantic_score < 0.70:
            semantic_warning = f"⚠️ Düşük semantik benzerlik ({semantic_score:.2f}). Bu synonym keyword ile zayıf ilişkili olabilir."

        # FAZ 10.4: ML auto-approve/reject entegrasyonu (sadece company scope için)
        ml_result = None
        ml_warning = None

        if scope == "company" and SKLEARN_AVAILABLE and not request.auto_approve:
            try:
                ml_result = auto_process_synonym(keyword, synonym)
                if ml_result.get('action') == 'auto_approved':
                    auto_approve = True  # ML otomatik onay
                    logger.info(f"ML auto-approved: {keyword} -> {synonym} (prob={ml_result.get('probability', 0):.3f})")
                elif ml_result.get('action') == 'auto_rejected':
                    # Uyarı ver ama engelleme
                    ml_warning = f"⚠️ ML düşük onay olasılığı ({ml_result.get('probability', 0):.2f}). Bu synonym reddedilebilir."
                    logger.info(f"ML warning (low prob): {keyword} -> {synonym} (prob={ml_result.get('probability', 0):.3f})")
            except Exception as ml_err:
                logger.warning(f"ML prediction hatası: {ml_err}")
                # ML hatası synonym eklemeyi engellemez

        result = add_manual_synonym(
            keyword=keyword,
            synonym=synonym,
            synonym_type=request.synonym_type,
            company_id=company_id,
            created_by=user_id,
            auto_approve=auto_approve
        )

        if result.get("success"):
            # FAZ 10.2: Synonym embedding'ini kaydet
            try:
                save_synonym_embedding(synonym, keyword)
            except Exception as emb_err:
                logger.warning(f"Synonym embedding kaydedilemedi: {emb_err}")

            # Loglama
            scope_text = "global" if scope == "global" else f"company={company_id}"
            logger.info(f"Synonym created: user={user_id}, scope={scope_text}, keyword={keyword}, synonym={synonym}, semantic_score={semantic_score:.2f}, auto_approve={auto_approve}")

            # FAZ 3.2: KVKK Audit Log
            log_action(
                action=AuditAction.SYNONYM_APPROVE.value if auto_approve else "SYNONYM_CREATE",
                user_id=user_id,
                company_id=company_id,
                entity_type=EntityType.SYNONYM.value,
                entity_id=result.get("id"),
                details={
                    "keyword": keyword,
                    "synonym": synonym,
                    "scope": scope,
                    "auto_approve": auto_approve
                }
            )

            response_data = {
                "id": result.get("id"),
                "message": "Synonym başarıyla eklendi",
                "semantic_score": round(semantic_score, 3),
                "auto_approved": auto_approve,
                "scope": scope
            }

            # FAZ 10.4: ML sonuçlarını response'a ekle
            if ml_result:
                response_data["ml_prediction"] = {
                    "probability": round(ml_result.get("probability", 0), 4),
                    "action": ml_result.get("action", "pending")
                }

            # Uyarıları birleştir
            warnings = []
            if semantic_warning:
                warnings.append(semantic_warning)
            if ml_warning:
                warnings.append(ml_warning)
            if warnings:
                response_data["warning"] = " | ".join(warnings)

            return {
                "success": True,
                "data": response_data
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Synonym eklenemedi")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5: DELETE /api/synonyms/{synonym_id} - Synonym sil
# ═══════════════════════════════════════════════════════════════════════════════

@router.delete("/{synonym_id}")
def remove_synonym(
    synonym_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3.2: Synonym sil (HARD DELETE).

    Yetki kuralları:
    - super_admin: Global synonym'leri silebilir (company_id IS NULL)
    - company_admin/user: Sadece kendi firma synonym'lerini silebilir
    """
    try:
        # FAZ 3.2: Yeni auth helper kullan
        auth_info = require_company_or_super_admin(current_user)
        company_id = auth_info["company_id"]
        user_id = auth_info["user_id"]
        is_super_admin = auth_info["is_super_admin"]

        # Synonym'ü bul ve yetki kontrolü yap
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, keyword, synonym, company_id FROM keyword_synonyms WHERE id = ?",
            (synonym_id,)
        )
        synonym_row = cursor.fetchone()
        conn.close()

        if not synonym_row:
            raise HTTPException(status_code=404, detail="Synonym bulunamadı.")

        synonym_company_id = synonym_row["company_id"]

        # Yetki kontrolü
        if synonym_company_id is None:
            # Global synonym - sadece super_admin silebilir
            if not is_super_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Global synonym'ler sadece super_admin tarafından silinebilir."
                )
        else:
            # Firma synonym - sadece aynı firma silebilir
            if company_id != synonym_company_id:
                raise HTTPException(
                    status_code=403,
                    detail="Bu synonym'ü silme yetkiniz yok."
                )

        # Silme işlemi
        deleted = delete_synonym(
            synonym_id=synonym_id,
            company_id=synonym_company_id  # Orijinal company_id ile sil
        )

        if deleted:
            # Loglama
            scope_text = "global" if synonym_company_id is None else f"company={synonym_company_id}"
            logger.info(f"Synonym deleted: user={user_id}, {scope_text}, synonym_id={synonym_id}")

            # KVKK Audit Log
            log_action(
                action=AuditAction.DATA_DELETE,
                entity_type=EntityType.SYNONYM,
                entity_id=synonym_id,
                user_id=user_id,
                company_id=company_id,
                details={
                    "keyword": synonym_row["keyword"],
                    "synonym": synonym_row["synonym"],
                    "scope": "global" if synonym_company_id is None else "company",
                    "deleted_by": "super_admin" if is_super_admin else "company_user"
                }
            )

            return {
                "success": True,
                "data": {
                    "message": "Synonym başarıyla silindi",
                    "deleted_id": synonym_id
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Synonym silinemedi."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5.1: GET /api/synonyms/{synonym_id} - Tek synonym detayı (FAZ 3.2 YENİ)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{synonym_id}")
def get_synonym_detail(
    synonym_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3.2: Tek synonym detayını getir.

    Yetki kuralları:
    - super_admin: Tüm synonym'leri görebilir
    - company_admin/user: Global + kendi firma synonym'lerini görebilir
    """
    try:
        auth_info = require_company_or_super_admin(current_user)
        company_id = auth_info["company_id"]
        is_super_admin = auth_info["is_super_admin"]

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ks.id,
                ks.keyword,
                ks.synonym,
                ks.status,
                ks.company_id,
                ks.match_weight,
                ks.synonym_type,
                ks.confidence_score,
                ks.ambiguity_score,
                ks.version,
                ks.model_version,
                ks.created_at,
                ks.updated_at,
                ks.approved_by,
                ks.approved_at,
                ks.reject_reason,
                ks.reject_note,
                u.ad_soyad as approved_by_name
            FROM keyword_synonyms ks
            LEFT JOIN users u ON ks.approved_by = u.id
            WHERE ks.id = ?
        """, (synonym_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Synonym bulunamadı.")

        synonym_company_id = row["company_id"]

        # Yetki kontrolü: Global (NULL) veya kendi firmasına ait olanları görebilir
        if not is_super_admin and synonym_company_id is not None and synonym_company_id != company_id:
            raise HTTPException(
                status_code=403,
                detail="Bu synonym'ü görüntüleme yetkiniz yok."
            )

        return {
            "success": True,
            "data": {
                "id": row["id"],
                "keyword": row["keyword"],
                "synonym": row["synonym"],
                "status": row["status"],
                "company_id": row["company_id"],
                "scope": "global" if row["company_id"] is None else "company",
                "match_weight": row["match_weight"],
                "synonym_type": row["synonym_type"],
                "confidence_score": row["confidence_score"],
                "ambiguity_score": row["ambiguity_score"],
                "version": row["version"],
                "model_version": row["model_version"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "approved_by": row["approved_by"],
                "approved_by_name": row["approved_by_name"],
                "approved_at": row["approved_at"],
                "reject_reason": row["reject_reason"],
                "reject_note": row["reject_note"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 5.2: PUT /api/synonyms/{synonym_id} - Synonym güncelle (FAZ 3.2 YENİ)
# ═══════════════════════════════════════════════════════════════════════════════

@router.put("/{synonym_id}")
def update_synonym(
    synonym_id: int,
    request: SynonymUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3.2: Synonym güncelle.

    Güncellenebilir alanlar:
    - status: pending, approved, rejected
    - scope: global (super_admin only), company
    - match_weight: 0.0-1.0
    - synonym_type: exact_synonym, abbreviation, english, turkish, broader_term, narrower_term

    Yetki kuralları:
    - super_admin: Tüm synonym'leri güncelleyebilir, global yapabilir
    - company_admin/user: Sadece kendi firma synonym'lerini güncelleyebilir
    """
    try:
        auth_info = require_company_or_super_admin(current_user)
        company_id = auth_info["company_id"]
        user_id = auth_info["user_id"]
        is_super_admin = auth_info["is_super_admin"]

        # Mevcut synonym'ü bul
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, keyword, synonym, status, company_id, match_weight, synonym_type, version FROM keyword_synonyms WHERE id = ?",
            (synonym_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Synonym bulunamadı.")

        synonym_company_id = row["company_id"]
        old_version = row["version"] or 1

        # Yetki kontrolü
        if synonym_company_id is None:
            # Global synonym - sadece super_admin güncelleyebilir
            if not is_super_admin:
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="Global synonym'ler sadece super_admin tarafından güncellenebilir."
                )
        else:
            # Firma synonym - sadece aynı firma güncelleyebilir
            if company_id != synonym_company_id:
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="Bu synonym'ü güncelleme yetkiniz yok."
                )

        # Scope değişikliği kontrolü
        new_company_id = synonym_company_id
        if request.scope is not None:
            if request.scope == "global":
                if not is_super_admin:
                    conn.close()
                    raise HTTPException(
                        status_code=403,
                        detail="Synonym'ü global yapma yetkisi sadece super_admin'de."
                    )
                new_company_id = None
            elif request.scope == "company":
                if synonym_company_id is None:
                    # Global'den company'ye çevirme - sadece super_admin
                    if not is_super_admin:
                        conn.close()
                        raise HTTPException(
                            status_code=403,
                            detail="Global synonym'ü firma synonym'üne çevirme yetkisi yok."
                        )
                    new_company_id = company_id  # super_admin'in firmasına ata (veya None kalabilir)

        # Güncelleme sorgusu oluştur
        updates = []
        params = []

        if request.status is not None:
            if request.status not in ["pending", "approved", "rejected"]:
                conn.close()
                raise HTTPException(status_code=400, detail="Geçersiz status değeri.")
            updates.append("status = ?")
            params.append(request.status)

            # Status değişikliğine göre ek alanlar
            if request.status == "approved":
                updates.append("approved_by = ?")
                params.append(user_id)
                updates.append("approved_at = datetime('now')")

        if request.scope is not None:
            updates.append("company_id = ?")
            params.append(new_company_id)

        if request.match_weight is not None:
            updates.append("match_weight = ?")
            params.append(request.match_weight)

        if request.synonym_type is not None:
            valid_types = ["exact_synonym", "abbreviation", "english", "turkish", "broader_term", "narrower_term"]
            if request.synonym_type not in valid_types:
                conn.close()
                raise HTTPException(status_code=400, detail=f"Geçersiz synonym_type. Geçerli değerler: {valid_types}")
            updates.append("synonym_type = ?")
            params.append(request.synonym_type)

        if not updates:
            conn.close()
            raise HTTPException(status_code=400, detail="Güncellenecek alan belirtilmedi.")

        # Versiyon ve timestamp ekle
        updates.append("version = ?")
        params.append(old_version + 1)
        updates.append("updated_at = datetime('now')")
        updates.append("updated_by = ?")
        params.append(user_id)

        # Güncelleme yap
        params.append(synonym_id)
        sql = f"UPDATE keyword_synonyms SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, params)
        conn.commit()

        # History tablosuna kaydet (FAZ 9.4)
        try:
            cursor.execute("""
                INSERT INTO keyword_synonyms_history (
                    synonym_id, keyword, synonym, old_status, new_status,
                    changed_by, change_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                synonym_id,
                row["keyword"],
                row["synonym"],
                row["status"],
                request.status or row["status"],
                user_id,
                "FAZ 3.2 UPDATE endpoint"
            ))
            conn.commit()
        except Exception:
            pass  # History tablosu yoksa sessizce geç

        conn.close()

        # Loglama
        scope_text = "global" if new_company_id is None else f"company={new_company_id}"
        logger.info(f"Synonym updated: user={user_id}, {scope_text}, synonym_id={synonym_id}, version={old_version + 1}")

        # KVKK Audit Log
        log_action(
            action=AuditAction.DATA_UPDATE,
            entity_type=EntityType.SYNONYM,
            entity_id=synonym_id,
            user_id=user_id,
            company_id=company_id,
            details={
                "keyword": row["keyword"],
                "synonym": row["synonym"],
                "old_version": old_version,
                "new_version": old_version + 1,
                "updates": {
                    "status": request.status,
                    "scope": request.scope,
                    "match_weight": request.match_weight,
                    "synonym_type": request.synonym_type
                }
            }
        )

        return {
            "success": True,
            "data": {
                "message": "Synonym başarıyla güncellendi",
                "id": synonym_id,
                "version": old_version + 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: POST /api/synonyms/approve - Toplu onay
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/approve")
def approve_synonym_list(
    request: SynonymBulkActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 3: Seçili synonym'ları onayla.
    Toplu onay için kullanılır.

    scope parametresi:
    - "company": Firma bazlı onay (mevcut company_id korunur)
    - "global": Global onay (company_id = NULL, tüm firmalar için)
      Sadece super_admin global scope kullanabilir.
    """
    try:
        # FAZ 3: Yeni auth helper kullan
        auth_info = require_company_or_super_admin(current_user)
        company_id = auth_info["company_id"]
        user_id = auth_info["user_id"]
        is_super_admin = auth_info["is_super_admin"]

        # Scope kontrolü: global scope sadece super_admin için
        scope = request.scope or "company"
        if scope == "global" and not is_super_admin:
            raise HTTPException(
                status_code=403,
                detail="Global onay sadece super_admin yetkisiyle yapılabilir."
            )

        result = approve_synonyms(
            synonym_ids=request.synonym_ids,
            approved_by=user_id,
            company_id=company_id,
            scope=scope
        )

        if result.get("success"):
            # Loglama
            scope_text = "global" if scope == "global" else f"company={company_id}"
            logger.info(f"Synonyms approved: user={user_id}, scope={scope_text}, count={result.get('updated', 0)}, ids={request.synonym_ids}")

            # FAZ 3: KVKK Audit Log
            log_action(
                action=AuditAction.SYNONYM_APPROVE.value,
                user_id=user_id,
                company_id=company_id if scope == "company" else None,
                entity_type=EntityType.SYNONYM.value,
                entity_id=None,
                details={
                    "synonym_ids": request.synonym_ids,
                    "scope": scope,
                    "count": result.get("updated", 0)
                }
            )

            return {
                "success": True,
                "data": {
                    "updated": result.get("updated", 0),
                    "scope": scope,
                    "message": f"{result.get('updated', 0)} synonym onaylandı ({scope})"
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Onaylama başarısız")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 7: POST /api/synonyms/reject - Toplu red
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/reject")
def reject_synonym_list(
    request: SynonymRejectRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Seçili synonym'ları reddet.
    Toplu red için kullanılır.
    FAZ 8.1.4: reject_reason ve reject_note parametreleri eklendi.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        # Reject reason validasyonu
        if request.reject_reason not in REJECT_REASON_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Gecersiz reject_reason: {request.reject_reason}. Gecerli degerler: {REJECT_REASON_CODES}"
            )

        result = reject_synonyms(
            synonym_ids=request.synonym_ids,
            company_id=company_id,
            reject_reason=request.reject_reason,
            reject_note=request.reject_note
        )

        if result.get("success"):
            # Loglama
            logger.info(f"Synonyms rejected: user={current_user['id']}, company={company_id}, count={result.get('updated', 0)}, reason={request.reject_reason}, ids={request.synonym_ids}")

            return {
                "success": True,
                "data": {
                    "updated": result.get("updated", 0),
                    "message": f"{result.get('updated', 0)} synonym reddedildi"
                }
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Reddetme başarısız")
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL: Batch Synonym Üretimi (Pozisyon kaydederken çağrılır)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_synonyms_batch_internal(
    keywords: List[str],
    company_id: int,
    user_id: int
) -> dict:
    """
    Toplu synonym üretimi (internal).
    Pozisyon kaydederken çağrılır, tek API çağrısı ile tüm keyword'ler işlenir.

    Args:
        keywords: Keyword listesi (max 25)
        company_id: Şirket ID
        user_id: Kullanıcı ID

    Returns:
        dict: {
            "success": bool,
            "total_keywords": int,
            "generated": int,
            "inserted": int,
            "skipped": int,
            "failed_keywords": [],
            "message": str
        }
    """
    import re

    # FAZ 7.2: skipped_has_approved scope için erken tanımlama
    skipped_has_approved = []

    # Boş liste kontrolü
    if not keywords:
        return {
            "success": True,
            "total_keywords": 0,
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": [],
            "failed_keywords": [],
            "message": "Keyword listesi boş"
        }

    # FAZ 7.2: Smart Synonym - Onaylı synonym varsa AI çağrısı atla
    keywords_to_process = []
    for kw in keywords:
        approved_count = get_approved_synonym_count(kw, company_id)
        if approved_count > 0:
            skipped_has_approved.append(kw)
        else:
            keywords_to_process.append(kw)

    # Tüm keyword'ler zaten onaylı synonym'e sahipse
    if not keywords_to_process:
        return {
            "success": True,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": [],
            "message": f"Tüm keyword'ler için onaylı synonym mevcut ({len(skipped_has_approved)} keyword atlandı)"
        }

    # Orijinal keywords listesini güncelle (sadece işlenecek olanlar)
    keywords = keywords_to_process

    # Rate limit kontrolü
    user_id_str = str(user_id)
    allowed, limit_msg = check_synonym_batch_generate_limit(user_id_str)
    if not allowed:
        return {
            "success": False,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": keywords,
            "message": limit_msg
        }

    # API key kontrolü
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": keywords,
            "message": "ANTHROPIC_API_KEY ayarlanmamış"
        }

    # Batch prompt v2 - Kalite sistemi ile
    prompt = SYNONYM_PROMPT_BATCH_V2.format(keywords=json.dumps(keywords, ensure_ascii=False))

    start_time = time.time()
    total_generated = 0
    total_inserted = 0
    total_skipped = 0
    failed_keywords = []

    try:
        # Claude API çağrısı
        client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()

        # JSON parse
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "total_keywords": len(keywords),
                        "generated": 0,
                        "inserted": 0,
                        "skipped": 0,
                        "skipped_has_approved": skipped_has_approved,
                        "failed_keywords": keywords,
                        "message": "AI yanıtı geçerli JSON formatında değil"
                    }
            else:
                return {
                    "success": False,
                    "total_keywords": len(keywords),
                    "generated": 0,
                    "inserted": 0,
                    "skipped": 0,
                    "skipped_has_approved": skipped_has_approved,
                    "failed_keywords": keywords,
                    "message": "AI yanıtında JSON bulunamadı"
                }

        # Sonuçları işle
        results = data.get("results", [])

        for item in results:
            kw = item.get("keyword", "").lower().strip()
            synonyms_list = item.get("synonyms", [])

            if not kw or not synonyms_list:
                if kw:
                    failed_keywords.append(kw)
                continue

            # v2: AI synonym'ları filtrele (firma bazlı limit ile)
            filtered_synonyms = filter_ai_synonyms(kw, synonyms_list, company_id)

            if not filtered_synonyms:
                # Tüm öneriler filtrelendi
                continue

            total_generated += len(filtered_synonyms)

            # Database'e kaydet (filtrelenmiş liste ile)
            result = save_generated_synonyms(
                keyword=kw,
                synonyms=filtered_synonyms,
                company_id=company_id,
                created_by=user_id
            )

            if result.get("success"):
                total_inserted += result.get("inserted", 0)
                total_skipped += result.get("skipped", 0)
            else:
                failed_keywords.append(kw)

        # Başarılı - rate limit kaydet
        record_synonym_batch_generate(user_id_str)

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Log
        try:
            log_api_usage(
                islem_tipi="synonym_batch_generate",
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                model="claude-sonnet-4-20250514",
                company_id=company_id,
                user_id=user_id,
                basarili=True,
                islem_suresi_ms=elapsed_ms,
                detay=json.dumps({
                    "keywords_count": len(keywords),
                    "generated": total_generated,
                    "inserted": total_inserted,
                    "skipped": total_skipped
                })
            )
        except Exception:
            pass  # Loglama hatası ana işlemi etkilemesin

        # FAZ 7.2: skipped_has_approved bilgisini ekle
        skip_msg = ""
        if skipped_has_approved:
            skip_msg = f" ({len(skipped_has_approved)} keyword onaylı synonym nedeniyle atlandı)"

        return {
            "success": True,
            "total_keywords": len(keywords) + len(skipped_has_approved),
            "generated": total_generated,
            "inserted": total_inserted,
            "skipped": total_skipped,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": failed_keywords,
            "message": f"{total_inserted} synonym eklendi, {total_skipped} atlandı{skip_msg}"
        }

    except anthropic.APITimeoutError:
        return {
            "success": False,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": keywords,
            "message": "Claude API zaman aşımı"
        }
    except anthropic.APIConnectionError:
        return {
            "success": False,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": keywords,
            "message": "Claude API bağlantı hatası"
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        try:
            log_api_usage(
                islem_tipi="synonym_batch_generate",
                input_tokens=0,
                output_tokens=0,
                model="claude-sonnet-4-20250514",
                company_id=company_id,
                user_id=user_id,
                basarili=False,
                islem_suresi_ms=elapsed_ms,
                hata_mesaji=str(e)
            )
        except Exception:
            pass
        return {
            "success": False,
            "total_keywords": len(keywords),
            "generated": 0,
            "inserted": 0,
            "skipped": 0,
            "skipped_has_approved": skipped_has_approved,
            "failed_keywords": keywords,
            "message": f"Hata: {str(e)}"
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 8: POST /api/synonyms/generate - AI ile synonym üret
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/generate")
def generate_synonyms(
    request: SynonymGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    AI ile keyword için synonym önerileri oluştur.
    Öneriler 'pending' durumunda kaydedilir, İK onayı bekler.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]
        user_id = current_user["id"]
        keyword = request.keyword.strip().lower()

        # Rate limit kontrolü
        user_id_str = str(user_id)
        allowed, limit_msg = check_synonym_generate_limit(user_id_str)
        if not allowed:
            raise HTTPException(status_code=429, detail=limit_msg)

        # Zaman ölçümü başlat
        start_time = time.time()

        # API key kontrolü
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY ayarlanmamış"
            )

        # Claude prompt v2 - Kalite sistemi ile
        prompt = SYNONYM_PROMPT_SINGLE_V2.format(keyword=keyword)

        # Claude API çağrısı
        client = anthropic.Anthropic(api_key=api_key, timeout=60.0)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        # İşlem süresini hesapla
        elapsed_ms = int((time.time() - start_time) * 1000)

        response_text = message.content[0].text.strip()

        # JSON parse (fallback ile)
        try:
            # Direkt parse dene
            data = json.loads(response_text)
        except json.JSONDecodeError:
            # JSON kısmını bulmaya çalış
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail="AI yanıtı geçerli JSON formatında değil"
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail="AI yanıtı geçerli JSON formatında değil"
                )

        # Synonyms listesini al
        synonyms_list = data.get("synonyms", [])

        if not synonyms_list:
            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "generated": 0,
                    "inserted": 0,
                    "skipped": 0,
                    "synonyms": [],
                    "message": "AI öneri üretemedi"
                }
            }

        # v2: AI synonym'ları filtrele (firma bazlı limit ile)
        filtered_synonyms = filter_ai_synonyms(keyword, synonyms_list, company_id)

        if not filtered_synonyms:
            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "generated": 0,
                    "inserted": 0,
                    "skipped": len(synonyms_list),
                    "synonyms": [],
                    "message": "Tüm öneriler kalite filtresinden geçemedi"
                }
            }

        # Database'e kaydet (filtrelenmiş liste ile)
        result = save_generated_synonyms(
            keyword=keyword,
            synonyms=filtered_synonyms,
            company_id=company_id,
            created_by=user_id
        )

        if result.get("success"):
            # Rate limit kaydı (başarılı işlem sonrası)
            record_synonym_generate(user_id_str)

            # API kullanımını logla
            try:
                log_api_usage(
                    islem_tipi="synonym_generate",
                    input_tokens=message.usage.input_tokens,
                    output_tokens=message.usage.output_tokens,
                    model="claude-sonnet-4-20250514",
                    company_id=company_id,
                    user_id=user_id,
                    basarili=True,
                    islem_suresi_ms=elapsed_ms,
                    detay=json.dumps({"keyword": keyword, "generated": len(filtered_synonyms), "inserted": result.get("inserted", 0)})
                )
            except Exception:
                pass  # Loglama hatası ana işlemi etkilemesin

            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "generated": len(filtered_synonyms),
                    "inserted": result.get("inserted", 0),
                    "skipped": result.get("skipped", 0),
                    "synonyms": filtered_synonyms,
                    "message": f"{result.get('inserted', 0)} synonym eklendi, {result.get('skipped', 0)} atlandı"
                }
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Synonym kaydetme hatası")
            )

    except anthropic.APITimeoutError:
        raise HTTPException(status_code=504, detail="Claude API zaman aşımı")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=503, detail="Claude API bağlantı hatası")
    except HTTPException:
        raise
    except Exception as e:
        # Hata logla
        try:
            elapsed_ms_err = int((time.time() - start_time) * 1000) if 'start_time' in dir() else 0
            log_api_usage(
                islem_tipi="synonym_generate",
                company_id=company_id if 'company_id' in dir() else None,
                user_id=user_id if 'user_id' in dir() else None,
                basarili=False,
                hata_mesaji=str(e),
                islem_suresi_ms=elapsed_ms_err
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 8.2.3: KEYWORD IMPORTANCE API
# Firma bazlı keyword öncelik yönetimi
# ═══════════════════════════════════════════════════════════════════════════════

class KeywordImportanceRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    importance_level: str = Field(..., pattern="^(high|normal|low)$")


@router.get("/keyword-importance")
async def list_keyword_importances(current_user: dict = Depends(get_current_user)):
    """
    Firma'nın keyword importance ayarlarını listele.
    """
    try:
        company_id = current_user["company_id"]
        items = get_company_keyword_importances(company_id)
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
    except Exception as e:
        logger.error(f"list_keyword_importances hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/keyword-importance")
async def create_keyword_importance(
    request: KeywordImportanceRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Keyword importance ekle veya güncelle.
    """
    try:
        company_id = current_user["company_id"]
        user_id = current_user["id"]

        result = set_keyword_importance(
            keyword=request.keyword,
            company_id=company_id,
            level=request.importance_level,
            user_id=user_id
        )

        if result["success"]:
            return {
                "success": True,
                "data": {
                    "id": result["id"],
                    "keyword": request.keyword.lower().strip(),
                    "importance_level": request.importance_level,
                    "action": result["action"]
                },
                "message": result["message"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_keyword_importance hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/keyword-importance/{id}")
async def remove_keyword_importance(
    id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Keyword importance kaydını sil.
    """
    try:
        company_id = current_user["company_id"]

        result = delete_keyword_importance(id=id, company_id=company_id)

        if result["success"]:
            return {"success": True, "message": result["message"]}
        else:
            raise HTTPException(status_code=404, detail=result["message"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"remove_keyword_importance hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 9.1: TIP BAZLI ISTATISTIK ENDPOINT
# Synonym tiplerinin dağılımını raporla
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/type_stats")
async def get_synonym_type_stats(current_user: dict = Depends(get_current_user)):
    """
    Synonym tiplerinin dağılımını döndür.

    Response:
    {
        "success": true,
        "data": {
            "type_distribution": [
                {"type": "english", "label_tr": "İngilizce Çeviri", "count": 242, "weight": 0.90, "percentage": 62.5},
                ...
            ],
            "total": 387,
            "available_types": [
                {"code": "exact_synonym", "label_tr": "Birebir Eş Anlamlı", "weight": 1.00},
                ...
            ]
        }
    }
    """
    try:
        company_id = current_user["company_id"]

        # DB'den tip dağılımını al
        from database import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()

            # Firma + global synonym'ların tip dağılımı
            cursor.execute("""
                SELECT synonym_type, COUNT(*) as count
                FROM keyword_synonyms
                WHERE (company_id IS NULL OR company_id = ?)
                AND status = 'approved'
                GROUP BY synonym_type
                ORDER BY count DESC
            """, (company_id,))

            rows = cursor.fetchall()
            total = sum(row[1] for row in rows)

            # Tip dağılımını SYNONYM_TYPES ile zenginleştir
            type_distribution = []
            for row in rows:
                syn_type = row[0]
                count = row[1]
                type_info = SYNONYM_TYPES.get(syn_type, {"weight": 0.80, "label_tr": syn_type})
                type_distribution.append({
                    "type": syn_type,
                    "label_tr": type_info["label_tr"],
                    "count": count,
                    "weight": type_info["weight"],
                    "percentage": round((count / total * 100), 1) if total > 0 else 0
                })

            # Tüm kullanılabilir tipleri listele
            available_types = [
                {"code": k, "label_tr": v["label_tr"], "weight": v["weight"], "desc": v.get("desc", "")}
                for k, v in SYNONYM_TYPES.items()
            ]

        return {
            "success": True,
            "data": {
                "type_distribution": type_distribution,
                "total": total,
                "available_types": available_types
            }
        }

    except Exception as e:
        logger.error(f"get_synonym_type_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 9.2: SYNONYM ÇAKIŞMA RAPORU
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/conflicts")
async def get_conflicts(
    min_ambiguity: float = 0.5,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.2: Yüksek ambiguity'li çakışmaları getir.

    Query Params:
        min_ambiguity: Minimum ambiguity score (varsayılan 0.5)

    Returns:
        [{synonym, primary_keyword, secondary_keywords, conflict_count, ambiguity_score}]
    """
    try:
        from database import get_synonym_conflicts

        company_id = current_user.get("company_id")
        conflicts = get_synonym_conflicts(company_id=company_id, min_ambiguity=min_ambiguity)

        return {
            "success": True,
            "data": conflicts
        }

    except Exception as e:
        logger.error(f"get_conflicts hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build_conflict_index")
async def build_conflict_index(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 9.2: Mevcut synonym'lar için çakışma indexi oluştur.

    Returns:
        {"success": True, "indexed": int, "conflicts": int}
    """
    try:
        from database import build_synonym_mapping_index

        company_id = current_user.get("company_id")
        result = build_synonym_mapping_index(company_id=company_id)

        if result.get("success"):
            return {
                "success": True,
                "data": {
                    "indexed": result.get("indexed", 0),
                    "conflicts": result.get("conflicts", 0)
                }
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Index oluşturulamadı"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"build_conflict_index hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 10.1: CONFIDENCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateConfidenceRequest(BaseModel):
    keyword: str
    synonym: str
    ai_confidence: float = Field(default=0.85, ge=0.0, le=1.0)


@router.post("/update-confidence")
def update_synonym_confidence(
    request: UpdateConfidenceRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.1: Synonym confidence değerini yeniden hesapla ve güncelle.

    Formül: (0.4 * AI) + (0.3 * corpus) + (0.3 * historical)
    """
    try:
        company_id = current_user.get("company_id")

        # Final confidence hesapla
        new_confidence = calculate_final_confidence(
            keyword=request.keyword,
            synonym=request.synonym,
            ai_confidence=request.ai_confidence,
            company_id=company_id
        )

        # DB'de güncelle
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE keyword_synonyms
                SET confidence_score = ?
                WHERE keyword = ? AND synonym = ?
                AND (company_id IS NULL OR company_id = ?)
            """, (new_confidence, request.keyword.lower(), request.synonym.lower(), company_id))
            updated = cursor.rowcount
            conn.commit()

        return {
            "success": True,
            "data": {
                "keyword": request.keyword,
                "synonym": request.synonym,
                "new_confidence": new_confidence,
                "updated_count": updated
            }
        }

    except Exception as e:
        logger.error(f"update_confidence hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/confidence-stats")
def get_confidence_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.1: Synonym confidence istatistiklerini getir.
    """
    try:
        company_id = current_user.get("company_id")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Genel istatistikler
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    AVG(confidence_score) as avg_confidence,
                    MIN(confidence_score) as min_confidence,
                    MAX(confidence_score) as max_confidence,
                    SUM(CASE WHEN confidence_score >= 0.8 THEN 1 ELSE 0 END) as high_confidence,
                    SUM(CASE WHEN confidence_score >= 0.5 AND confidence_score < 0.8 THEN 1 ELSE 0 END) as medium_confidence,
                    SUM(CASE WHEN confidence_score < 0.5 THEN 1 ELSE 0 END) as low_confidence
                FROM keyword_synonyms
                WHERE status = 'approved'
                AND (company_id IS NULL OR company_id = ?)
            """, (company_id,))
            row = cursor.fetchone()

            stats = {
                "total": row[0] or 0,
                "avg_confidence": round(row[1] or 0, 3),
                "min_confidence": round(row[2] or 0, 3),
                "max_confidence": round(row[3] or 0, 3),
                "high_confidence_count": row[4] or 0,
                "medium_confidence_count": row[5] or 0,
                "low_confidence_count": row[6] or 0
            }

            # Usage stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_usage,
                    SUM(match_count) as total_matches,
                    SUM(hired_count) as total_hired
                FROM synonym_usage_stats
                WHERE company_id IS NULL OR company_id = ?
            """, (company_id,))
            usage_row = cursor.fetchone()

            stats["usage"] = {
                "tracked_synonyms": usage_row[0] or 0,
                "total_matches": usage_row[1] or 0,
                "total_hired": usage_row[2] or 0,
                "precision": round((usage_row[2] or 0) / (usage_row[1] or 1), 3)
            }

            # En düşük confidence'a sahip synonym'lar
            cursor.execute("""
                SELECT keyword, synonym, confidence_score
                FROM keyword_synonyms
                WHERE status = 'approved'
                AND (company_id IS NULL OR company_id = ?)
                ORDER BY confidence_score ASC
                LIMIT 10
            """, (company_id,))

            stats["lowest_confidence"] = [
                {"keyword": r[0], "synonym": r[1], "confidence": round(r[2] or 0, 3)}
                for r in cursor.fetchall()
            ]

        return {"success": True, "data": stats}

    except Exception as e:
        logger.error(f"confidence_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 10.2: SEMANTIC SIMILARITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class SemanticCheckRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    synonym: str = Field(..., min_length=1, max_length=100)


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=100)
    threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=50)


@router.post("/check-semantic")
def check_semantic_endpoint(
    request: SemanticCheckRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.2: Keyword ve synonym arasındaki semantik benzerliği kontrol et.

    Returns:
        {
            "similarity": 0.82,
            "is_valid": true,
            "message": "✅ Semantik olarak uyumlu (0.82)"
        }
    """
    try:
        require_company_user(current_user)

        result = check_semantic_similarity(
            keyword=request.keyword.strip(),
            synonym=request.synonym.strip()
        )

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        logger.error(f"check_semantic hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/semantic-duplicates")
def get_semantic_duplicates(
    threshold: float = Query(default=0.92, ge=0.5, le=1.0, description="Benzerlik eşiği"),
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.2: Semantik olarak benzer (muhtemel duplicate) synonym'ları bul.

    Returns:
        [
            {
                "synonym1": "javascript",
                "keyword1": "js",
                "synonym2": "java script",
                "keyword2": "frontend",
                "similarity": 0.95
            }
        ]
    """
    try:
        require_company_user(current_user)

        duplicates = find_semantic_duplicates(threshold=threshold)

        return {
            "success": True,
            "data": duplicates,
            "count": len(duplicates)
        }

    except Exception as e:
        logger.error(f"semantic_duplicates hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/semantic-search")
def semantic_search(
    request: SemanticSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.2: Verilen sorguya semantik olarak benzer keyword/synonym'ları ara.

    Returns:
        [
            {"term": "python", "type": "keyword", "similarity": 0.85},
            {"term": "py", "type": "synonym", "keyword": "python", "similarity": 0.78}
        ]
    """
    try:
        require_company_user(current_user)
        company_id = current_user.get("company_id")

        # Sorgu embedding'ini al
        query_embedding = get_embedding(request.query.strip())
        if not query_embedding:
            return {
                "success": False,
                "data": [],
                "message": "Sorgu için embedding alınamadı"
            }

        results = []

        with get_connection() as conn:
            cursor = conn.cursor()
            import pickle

            # 1. Keyword'lerde ara
            cursor.execute("""
                SELECT keyword, embedding
                FROM keyword_embeddings
            """)
            for row in cursor.fetchall():
                keyword = row[0]
                stored_embedding = pickle.loads(row[1])
                sim = semantic_similarity(query_embedding, stored_embedding)
                if sim >= request.threshold:
                    results.append({
                        "term": keyword,
                        "type": "keyword",
                        "similarity": round(sim, 3)
                    })

            # 2. Synonym'larda ara
            cursor.execute("""
                SELECT synonym, keyword, embedding
                FROM synonym_embeddings
            """)
            for row in cursor.fetchall():
                synonym = row[0]
                keyword = row[1]
                stored_embedding = pickle.loads(row[2])
                sim = semantic_similarity(query_embedding, stored_embedding)
                if sim >= request.threshold:
                    results.append({
                        "term": synonym,
                        "type": "synonym",
                        "keyword": keyword,
                        "similarity": round(sim, 3)
                    })

        # Similarity'ye göre sırala ve limit uygula
        results.sort(key=lambda x: x["similarity"], reverse=True)
        results = results[:request.limit]

        return {
            "success": True,
            "data": results,
            "count": len(results)
        }

    except Exception as e:
        logger.error(f"semantic_search hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 10.3: MULTI-LANGUAGE NORMALIZATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class NormalizeRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    apply_stemming: bool = Field(default=False)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200)


class AddTranslationRequest(BaseModel):
    source_term: str = Field(..., min_length=1, max_length=200)
    canonical_term: str = Field(..., min_length=1, max_length=200)
    source_lang: str = Field(default="tr", max_length=10)
    sector: str = Field(default="general", max_length=50)


@router.post("/normalize")
def normalize_keyword_endpoint(
    request: NormalizeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.3: Keyword'ü normalize et (çeviri + opsiyonel stemming)

    Returns:
        {
            "original": "Makine Öğrenmesi",
            "normalized": "machine learning",
            "canonical": "machine learning",
            "source_lang": "tr",
            "was_translated": true,
            "stem": "machin learn" (if apply_stemming=true)
        }
    """
    try:
        require_company_user(current_user)

        result = normalize_keyword(
            keyword=request.keyword,
            apply_stemming=request.apply_stemming
        )

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        logger.error(f"normalize_keyword hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate")
def translate_endpoint(
    request: TranslateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.3: Metni canonical forma çevir

    Returns:
        {
            "original": "yapay zeka",
            "canonical": "artificial intelligence",
            "source_lang": "tr",
            "was_translated": true
        }
    """
    try:
        require_company_user(current_user)

        result = translate_to_canonical(text=request.text)

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        logger.error(f"translate hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dictionary-stats")
def dictionary_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.3: Sözlük istatistikleri

    Returns:
        {
            "static_tr_en": 35,
            "static_en_canonical": 21,
            "database_translations": 0,
            "total": 56
        }
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM translation_dictionary')
        db_count = cursor.fetchone()[0]
        conn.close()

        return {
            "success": True,
            "data": {
                "static_tr_en": len(TRANSLATION_DICTIONARY),
                "static_en_canonical": len(ENGLISH_CANONICAL),
                "database_translations": db_count,
                "total": len(TRANSLATION_DICTIONARY) + len(ENGLISH_CANONICAL) + db_count
            }
        }

    except Exception as e:
        logger.error(f"dictionary_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-translation")
def add_translation(
    request: AddTranslationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.3: Yeni çeviri ekle (DB sözlüğüne)

    Returns:
        {"success": true, "message": "yapay zeka -> artificial intelligence eklendi"}
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        user_id = current_user.get('id', 0)
        cursor.execute('''INSERT INTO translation_dictionary
                          (source_term, source_lang, canonical_term, sector, verified, verified_by)
                          VALUES (?, ?, ?, ?, 1, ?)
                          ON CONFLICT(source_term, source_lang) DO UPDATE SET
                          canonical_term=excluded.canonical_term''',
                       (request.source_term.lower(), request.source_lang,
                        request.canonical_term.lower(), request.sector, user_id))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"'{request.source_term}' -> '{request.canonical_term}' eklendi"
        }

    except Exception as e:
        logger.error(f"add_translation hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/language-stats")
def language_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.3.10: Dil dağılım istatistikleri

    Returns:
        {
            "total_terms_analyzed": 1000,
            "language_distribution": {"tr": 450, "en": 520, "unknown": 30},
            "untranslated_turkish_count": 15,
            "untranslated_turkish_sample": ["örnek1", "örnek2", ...]
        }
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT keyword, synonym FROM keyword_synonyms LIMIT 500')
        rows = cursor.fetchall()
        conn.close()

        lang_stats = {'tr': 0, 'en': 0, 'unknown': 0, 'other': 0}
        untranslated_tr = []

        for kw, syn in rows:
            for term in [kw, syn]:
                if not term:
                    continue
                lang = detect_language(term)
                if lang in lang_stats:
                    lang_stats[lang] += 1
                else:
                    lang_stats['other'] += 1
                # Çevrilmemiş Türkçe terimler
                if lang == 'tr':
                    trans = translate_to_canonical(term)
                    if not trans['was_translated']:
                        untranslated_tr.append(term)

        return {
            "success": True,
            "data": {
                "total_terms_analyzed": len(rows) * 2,
                "language_distribution": lang_stats,
                "untranslated_turkish_count": len(set(untranslated_tr)),
                "untranslated_turkish_sample": list(set(untranslated_tr))[:20]
            }
        }

    except Exception as e:
        logger.error(f"language_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 10.4: ML-BASED AUTO-LEARNING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class MLPredictRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    synonym: str = Field(..., min_length=1, max_length=200)


class MLTrainRequest(BaseModel):
    model_name: str = Field(default="synonym_classifier", max_length=100)


class ABTestStartRequest(BaseModel):
    model_a_version: str = Field(..., min_length=1, max_length=50)
    model_b_version: str = Field(..., min_length=1, max_length=50)


class ABTestEndRequest(BaseModel):
    winner_version: str = Field(..., min_length=1, max_length=50)


class RetrainRequest(BaseModel):
    trigger_reason: str = Field(default="manual", max_length=100)


@router.post("/ml/predict")
def ml_predict(
    request: MLPredictRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: ML modeli ile synonym onay olasılığı tahmini.

    Returns:
        {
            "probability": 0.87,
            "prediction": "approve",
            "model_version": "v1.0.0",
            "features": {...}
        }
    """
    try:
        require_company_user(current_user)

        if not SKLEARN_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="ML özellikleri kullanılamıyor (scikit-learn yüklü değil)"
            )

        result = predict_approval_probability(
            keyword=request.keyword.strip(),
            synonym=request.synonym.strip(),
            save_prediction=True
        )

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ml_predict hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/train")
def ml_train(
    request: MLTrainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Yeni ML modeli eğit.

    Returns:
        {
            "model_version": "v1.0.0",
            "accuracy": 0.85,
            "precision": 0.88,
            "recall": 0.82,
            "f1": 0.85,
            "training_samples": 500,
            "test_samples": 125
        }
    """
    try:
        require_company_user(current_user)

        if not SKLEARN_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="ML özellikleri kullanılamıyor (scikit-learn yüklü değil)"
            )

        result = train_synonym_model(model_name=request.model_name)

        if result.get("success"):
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Model eğitimi başarısız")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ml_train hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/model-stats")
def ml_model_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Aktif ML modeli istatistikleri.

    Returns:
        {
            "model_name": "synonym_classifier",
            "model_version": "v1.0.0",
            "accuracy": 0.85,
            "precision": 0.88,
            "total_predictions": 150,
            "correct_predictions": 128
        }
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        # Aktif model
        cursor.execute("""
            SELECT id, model_name, model_version, model_type, accuracy,
                   precision_score, recall_score, f1_score,
                   training_samples, test_samples, created_at
            FROM ml_models
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {
                "success": True,
                "data": {
                    "has_model": False,
                    "message": "Henüz aktif model yok"
                }
            }

        model_id = row[0]

        # Tahmin istatistikleri
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(probability) as avg_probability
            FROM ml_predictions
            WHERE model_id = ?
        """, (model_id,))
        pred_row = cursor.fetchone()

        conn.close()

        return {
            "success": True,
            "data": {
                "has_model": True,
                "model_id": row[0],
                "model_name": row[1],
                "model_version": row[2],
                "model_type": row[3],
                "accuracy": round(row[4] or 0, 4),
                "precision": round(row[5] or 0, 4),
                "recall": round(row[6] or 0, 4),
                "f1": round(row[7] or 0, 4),
                "training_samples": row[8] or 0,
                "test_samples": row[9] or 0,
                "created_at": row[10],
                "predictions": {
                    "total": pred_row[0] or 0,
                    "correct": pred_row[1] or 0,
                    "avg_probability": round(pred_row[2] or 0, 4)
                }
            }
        }

    except Exception as e:
        logger.error(f"ml_model_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/model-history")
def ml_model_history(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Model eğitim geçmişi.

    Returns:
        [
            {
                "model_version": "v1.0.0",
                "accuracy": 0.85,
                "is_active": true,
                "created_at": "2026-03-02"
            }
        ]
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, model_name, model_version, model_type,
                   accuracy, precision_score, recall_score, f1_score,
                   training_samples, test_samples,
                   is_active, is_ab_test, ab_test_group,
                   created_at
            FROM ml_models
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        models = []
        for row in cursor.fetchall():
            models.append({
                "id": row[0],
                "model_name": row[1],
                "model_version": row[2],
                "model_type": row[3],
                "accuracy": round(row[4] or 0, 4),
                "precision": round(row[5] or 0, 4),
                "recall": round(row[6] or 0, 4),
                "f1": round(row[7] or 0, 4),
                "training_samples": row[8] or 0,
                "test_samples": row[9] or 0,
                "is_active": bool(row[10]),
                "is_ab_test": bool(row[11]),
                "ab_test_group": row[12],
                "created_at": row[13]
            })

        conn.close()

        return {
            "success": True,
            "data": models,
            "count": len(models)
        }

    except Exception as e:
        logger.error(f"ml_model_history hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/training-data")
def ml_training_data_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Eğitim verisi istatistikleri.

    Returns:
        {
            "total_samples": 500,
            "approved_samples": 387,
            "rejected_samples": 113,
            "feature_names": [...]
        }
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        # Onaylı synonym sayısı
        cursor.execute("""
            SELECT COUNT(*) FROM keyword_synonyms WHERE status = 'approved'
        """)
        approved = cursor.fetchone()[0]

        # Reddedilmiş synonym sayısı
        cursor.execute("""
            SELECT COUNT(*) FROM keyword_synonyms WHERE status = 'rejected'
        """)
        rejected = cursor.fetchone()[0]

        conn.close()

        return {
            "success": True,
            "data": {
                "total_samples": approved + rejected,
                "approved_samples": approved,
                "rejected_samples": rejected,
                "approval_ratio": round(approved / (approved + rejected), 3) if (approved + rejected) > 0 else 0,
                "feature_names": FEATURE_NAMES,
                "feature_count": len(FEATURE_NAMES),
                "min_samples_for_training": 100,
                "ready_for_training": (approved + rejected) >= 100
            }
        }

    except Exception as e:
        logger.error(f"ml_training_data_stats hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/retraining-status")
def ml_retraining_status(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Retraining gerekliliği kontrolü.

    Returns:
        {
            "needs_retraining": true,
            "reason": "new_samples",
            "new_samples_count": 75,
            "current_accuracy": 0.82
        }
    """
    try:
        require_company_user(current_user)

        if not SKLEARN_AVAILABLE:
            return {
                "success": True,
                "data": {
                    "needs_retraining": False,
                    "reason": "sklearn_not_available"
                }
            }

        result = check_retraining_needed()

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        logger.error(f"ml_retraining_status hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/retrain")
def ml_retrain(
    request: RetrainRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Manuel retraining tetikle.

    Returns:
        {
            "job_id": 5,
            "new_model_version": "v1.1.0",
            "status": "completed"
        }
    """
    try:
        require_company_user(current_user)

        if not SKLEARN_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="ML özellikleri kullanılamıyor (scikit-learn yüklü değil)"
            )

        result = run_retraining_job(trigger_reason=request.trigger_reason)

        if result.get("success"):
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Retraining başarısız")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ml_retrain hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/ab-test")
def ml_ab_test_status(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: Aktif A/B test durumu.

    Returns:
        {
            "has_active_test": true,
            "model_a": {"version": "v1.0.0", "predictions": 50, "correct": 42},
            "model_b": {"version": "v1.1.0", "predictions": 48, "correct": 45}
        }
    """
    try:
        require_company_user(current_user)

        result = get_ab_test_results()

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        logger.error(f"ml_ab_test_status hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/ab-test/start")
def ml_ab_test_start(
    request: ABTestStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: A/B test başlat.

    Returns:
        {
            "success": true,
            "model_a": "v1.0.0",
            "model_b": "v1.1.0"
        }
    """
    try:
        require_company_user(current_user)

        if not SKLEARN_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="ML özellikleri kullanılamıyor (scikit-learn yüklü değil)"
            )

        result = start_ab_test(
            model_a_version=request.model_a_version,
            model_b_version=request.model_b_version
        )

        if result.get("success"):
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "A/B test başlatılamadı")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ml_ab_test_start hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ml/ab-test/end")
def ml_ab_test_end(
    request: ABTestEndRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: A/B test bitir ve kazananı seç.

    Returns:
        {
            "success": true,
            "winner": "v1.1.0",
            "new_active_model": "v1.1.0"
        }
    """
    try:
        require_company_user(current_user)

        result = end_ab_test(winner_version=request.winner_version)

        if result.get("success"):
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "A/B test bitirilemedi")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ml_ab_test_end hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/dashboard")
def ml_dashboard(
    current_user: dict = Depends(get_current_user)
):
    """
    FAZ 10.4: ML Dashboard - Tüm ML metrikleri tek endpointte.

    Returns:
        {
            "sklearn_available": true,
            "active_model": {...},
            "training_data": {...},
            "recent_predictions": [...],
            "retraining_status": {...},
            "ab_test": {...},
            "thresholds": {...}
        }
    """
    try:
        require_company_user(current_user)

        conn = get_connection()
        cursor = conn.cursor()

        dashboard = {
            "sklearn_available": SKLEARN_AVAILABLE,
            "thresholds": {
                "auto_approve": AUTO_APPROVE_THRESHOLD,
                "auto_reject": AUTO_REJECT_THRESHOLD
            }
        }

        # Aktif model
        cursor.execute("""
            SELECT id, model_name, model_version, accuracy, precision_score,
                   recall_score, f1_score, training_samples, created_at
            FROM ml_models
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """)
        model_row = cursor.fetchone()

        if model_row:
            dashboard["active_model"] = {
                "id": model_row[0],
                "name": model_row[1],
                "version": model_row[2],
                "accuracy": round(model_row[3] or 0, 4),
                "precision": round(model_row[4] or 0, 4),
                "recall": round(model_row[5] or 0, 4),
                "f1": round(model_row[6] or 0, 4),
                "training_samples": model_row[7] or 0,
                "created_at": model_row[8]
            }
        else:
            dashboard["active_model"] = None

        # Eğitim verisi
        cursor.execute("SELECT COUNT(*) FROM keyword_synonyms WHERE status = 'approved'")
        approved = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM keyword_synonyms WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]

        dashboard["training_data"] = {
            "total": approved + rejected,
            "approved": approved,
            "rejected": rejected,
            "ready": (approved + rejected) >= 100
        }

        # Son 10 tahmin
        cursor.execute("""
            SELECT keyword, synonym, probability, prediction, actual_result,
                   is_correct, created_at
            FROM ml_predictions
            ORDER BY created_at DESC
            LIMIT 10
        """)
        predictions = []
        for row in cursor.fetchall():
            predictions.append({
                "keyword": row[0],
                "synonym": row[1],
                "probability": round(row[2] or 0, 4),
                "prediction": row[3],
                "actual_result": row[4],
                "is_correct": bool(row[5]) if row[5] is not None else None,
                "created_at": row[6]
            })
        dashboard["recent_predictions"] = predictions

        # Retraining durumu
        if SKLEARN_AVAILABLE:
            dashboard["retraining_status"] = check_retraining_needed()
        else:
            dashboard["retraining_status"] = {"needs_retraining": False}

        # A/B test durumu
        dashboard["ab_test"] = get_ab_test_results()

        # Retraining job history
        cursor.execute("""
            SELECT id, job_type, status, trigger_reason, started_at, completed_at
            FROM ml_retraining_jobs
            ORDER BY created_at DESC
            LIMIT 5
        """)
        jobs = []
        for row in cursor.fetchall():
            jobs.append({
                "id": row[0],
                "type": row[1],
                "status": row[2],
                "trigger": row[3],
                "started_at": row[4],
                "completed_at": row[5]
            })
        dashboard["recent_jobs"] = jobs

        conn.close()

        return {
            "success": True,
            "data": dashboard
        }

    except Exception as e:
        logger.error(f"ml_dashboard hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))
