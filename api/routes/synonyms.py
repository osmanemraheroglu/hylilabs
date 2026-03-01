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
    log_api_usage
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

SYNONYM_PROMPT_BATCH_V2 = """Sen İK alanında TEKNIK BECERİ uzmanisin.
Verilen keyword'ler için SADECE teknik/mesleki synonym öner.

Keywords: {keywords}

YASAK ÖNERILER (ASLA ÜRETMEYECEKSİN):
- Soft skills: iletişim, liderlik, takım çalışması, problem çözme
- Kişilik özellikleri: dinamik, titiz, proaktif, özgüvenli
- Genel terimler: deneyim, bilgi, beceri, yetenek, proje, görev

SADECE BUNLARI ÜRET:
- Türkçe teknik karşılık (synonym_type: "turkish")
- İngilizce teknik karşılık (synonym_type: "english")
- Resmi kısaltma (synonym_type: "abbreviation")

Kurallar:
1. Her keyword için MAX 3 synonym
2. Her öneriye 0.0-1.0 arası confidence puanı ver
3. Sadece 0.7+ confidence olanları dahil et
4. Keyword'ün kendisini EKLEME

JSON formatı:
{{
  "results": [
    {{
      "keyword": "python",
      "synonyms": [
        {{"synonym": "py", "synonym_type": "abbreviation", "confidence": 0.95}},
        {{"synonym": "python programlama", "synonym_type": "turkish", "confidence": 0.85}}
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

SADECE BUNLARI ÜRET:
- Türkçe teknik karşılık (synonym_type: "turkish")
- İngilizce teknik karşılık (synonym_type: "english")
- Resmi kısaltma (synonym_type: "abbreviation")

Kurallar:
1. MAX 3 synonym öner
2. Her öneriye 0.0-1.0 arası confidence puanı ver
3. Sadece 0.7+ confidence olanları dahil et
4. Keyword'ün kendisini EKLEME

JSON formatı:
{{
  "synonyms": [
    {{"synonym": "insan kaynakları", "synonym_type": "turkish", "confidence": 0.95}},
    {{"synonym": "human resources", "synonym_type": "english", "confidence": 0.90}},
    {{"synonym": "İK", "synonym_type": "abbreviation", "confidence": 0.85}}
  ]
}}"""


def filter_ai_synonyms(keyword: str, ai_synonyms: list) -> list:
    """
    AI tarafından üretilen synonym'ları filtrele ve kalite kontrolünden geçir.

    Filtreler:
    1. Blacklist kontrolü (soft skills, kişilik özellikleri)
    2. General words kontrolü (çok genel terimler)
    3. Confidence score kontrolü (0.7 threshold)
    4. Keyword ile aynı olanları çıkar
    5. Max 3 synonym limiti

    Args:
        keyword: Ana keyword
        ai_synonyms: AI'dan gelen synonym listesi

    Returns:
        Filtrelenmiş synonym listesi (confidence olmadan, synonym_type ile)
    """
    filtered = []
    keyword_lower = keyword.lower().strip()

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

        # "variation" tipini kaldır - sadece turkish, english, abbreviation kabul et
        if syn_type == "variation":
            syn_type = "turkish"

        # Geçerli tip kontrolü
        if syn_type not in ["turkish", "english", "abbreviation"]:
            syn_type = "turkish"

        # Sonuca ekle (confidence OLMADAN, sadece synonym ve synonym_type)
        filtered.append({
            "synonym": synonym,
            "synonym_type": syn_type
        })

        # Max 3 synonym limiti
        if len(filtered) >= 3:
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
    request: SynonymBulkActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Seçili synonym'ları reddet.
    Toplu red için kullanılır.
    """
    try:
        require_company_user(current_user)
        company_id = current_user["company_id"]

        result = reject_synonyms(
            synonym_ids=request.synonym_ids,
            company_id=company_id
        )

        if result.get("success"):
            # Loglama
            logger.info(f"Synonyms rejected: user={current_user['id']}, company={company_id}, count={result.get('updated', 0)}, ids={request.synonym_ids}")

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

            # v2: AI synonym'ları filtrele
            filtered_synonyms = filter_ai_synonyms(kw, synonyms_list)

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

        # v2: AI synonym'ları filtrele
        filtered_synonyms = filter_ai_synonyms(keyword, synonyms_list)

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
