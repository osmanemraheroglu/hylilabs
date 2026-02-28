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
    save_generated_synonyms
)
from routes.auth import get_current_user
from rate_limiter import check_synonym_generate_limit, record_synonym_generate

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

        # API key kontrolü
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY ayarlanmamış"
            )

        # Claude prompt
        prompt = f"""Sen bir İK (İnsan Kaynakları) alanında uzman bir asistansın.
Verilen keyword için Türkiye İK sektörüne uygun synonym ve ilişkili terimler üret.

Keyword: {keyword}

Kurallar:
1. Hem Türkçe hem İngilizce karşılıkları ver
2. Kısaltmalar varsa ekle (örn: İK = HR)
3. Sektörel varyasyonlar ekle
4. Maksimum 10 öneri üret
5. Her öneri için tip belirt: turkish, english, abbreviation, variation
6. Keyword'ün kendisini EKLEME

SADECE JSON formatında yanıt ver, başka açıklama ekleme:
{{
  "synonyms": [
    {{"synonym": "insan kaynakları", "synonym_type": "turkish"}},
    {{"synonym": "human resources", "synonym_type": "english"}},
    {{"synonym": "İK", "synonym_type": "abbreviation"}}
  ]
}}"""

        # Claude API çağrısı
        client = anthropic.Anthropic(api_key=api_key, timeout=60.0)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

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

        # Database'e kaydet
        result = save_generated_synonyms(
            keyword=keyword,
            synonyms=synonyms_list,
            company_id=company_id,
            created_by=user_id
        )

        if result.get("success"):
            # Rate limit kaydı (başarılı işlem sonrası)
            record_synonym_generate(user_id_str)

            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "generated": len(synonyms_list),
                    "inserted": result.get("inserted", 0),
                    "skipped": result.get("skipped", 0),
                    "synonyms": synonyms_list,
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
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")
