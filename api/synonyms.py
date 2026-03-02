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
    delete_keyword_importance
)
from routes.auth import get_current_user
from rate_limiter import (
    check_synonym_generate_limit,
    record_synonym_generate,
    check_synonym_batch_generate_limit,
    record_synonym_batch_generate
)

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

SYNONYM_BLACKLIST = [
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

GENERAL_WORDS = [
    # Çok genel kelimeler - synonym olarak anlamsız
    "is", "iş", "proje", "gorev", "görev", "yonetim", "yönetim", "sistem",
    "surekli", "sürekli", "gelistirme", "geliştirme", "iyilestirme", "iyileştirme",
    "analiz", "kontrol", "takip", "destek", "hizmet", "uygulama", "cozum", "çözüm",
    "strateji", "operasyon", "surec", "süreç", "faaliyet"
]


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

    Filtreler:
    1. Blacklist kontrolü (soft skills, kişilik özellikleri)
    2. General words kontrolü (çok genel terimler)
    3. Confidence score kontrolü (0.7 threshold)
    4. Keyword ile aynı olanları çıkar
    5. Dinamik max synonym limiti (FAZ 8.2.3: firma bazlı + HIGH_COVERAGE fallback)

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

        # Blacklist kontrolü
        if synonym in SYNONYM_BLACKLIST:
            continue

        # General words kontrolü
        if synonym in GENERAL_WORDS:
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


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELLERİ
# ═══════════════════════════════════════════════════════════════════════════════

class SynonymCreateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    synonym: str = Field(..., min_length=1, max_length=100)
    synonym_type: Optional[str] = None  # turkish, english, abbreviation, variation
    auto_approve: bool = False


class SynonymBulkActionRequest(BaseModel):
    synonym_ids: List[int] = Field(..., min_length=1)


class SynonymRejectRequest(BaseModel):
    synonym_ids: List[int] = Field(..., min_length=1)
    reject_reason: str = Field(..., min_length=1, description="Red sebebi kodu")
    reject_note: Optional[str] = Field(None, description="Opsiyonel aciklama notu")


class SynonymGenerateRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1: GET /api/synonyms - Keyword için synonym listesi
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("")
def list_synonyms(
    keyword: str = Query(..., min_length=1, description="Aranacak keyword (zorunlu)"),
    status: Optional[str] = Query(None, description="Filtre: pending, approved, rejected"),
    current_user: dict = Depends(get_current_user)
):
    """
    Belirli bir keyword için synonym listesi döndür.
    Global ve firma-özel synonym'ları içerir.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

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
# ENDPOINT 4: POST /api/synonyms - Manuel synonym ekle
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("")
def create_synonym(
    request: SynonymCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Yeni synonym ekle.
    auto_approve=True ise direkt onaylanır, False ise pending olur.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]
        user_id = current_user["id"]

        result = add_manual_synonym(
            keyword=request.keyword.strip(),
            synonym=request.synonym.strip(),
            synonym_type=request.synonym_type,
            company_id=company_id,
            created_by=user_id,
            auto_approve=request.auto_approve
        )

        if result.get("success"):
            # Loglama
            logger.info(f"Synonym created: user={user_id}, company={company_id}, keyword={request.keyword}, synonym={request.synonym}")

            return {
                "success": True,
                "data": {
                    "id": result.get("id"),
                    "message": "Synonym başarıyla eklendi"
                }
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
    Synonym sil.
    Sadece firma'nın kendi synonym'larını silebilir (global olanları değil).
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        deleted = delete_synonym(
            synonym_id=synonym_id,
            company_id=company_id
        )

        if deleted:
            # Loglama
            logger.info(f"Synonym deleted: user={current_user['id']}, company={company_id}, synonym_id={synonym_id}")

            return {
                "success": True,
                "data": {
                    "message": "Synonym başarıyla silindi"
                }
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Synonym bulunamadı veya silme yetkisi yok"
            )
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
    Seçili synonym'ları onayla.
    Toplu onay için kullanılır.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]
        user_id = current_user["id"]

        result = approve_synonyms(
            synonym_ids=request.synonym_ids,
            approved_by=user_id,
            company_id=company_id
        )

        if result.get("success"):
            # Loglama
            logger.info(f"Synonyms approved: user={user_id}, company={company_id}, count={result.get('updated', 0)}, ids={request.synonym_ids}")

            return {
                "success": True,
                "data": {
                    "updated": result.get("updated", 0),
                    "message": f"{result.get('updated', 0)} synonym onaylandı"
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
