from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from routes.auth import get_current_user
from core.cv_parser import validate_cv_access
from database import (
    get_connection,
    get_department_pools, get_department_pool, get_department_pool_stats,
    get_hierarchical_pool_stats, get_department_pool_candidates,
    get_pool_candidates_with_days, get_pool_by_name,
    create_department_pool, update_department_pool, delete_department_pool,
    assign_candidate_to_department_pool, remove_candidate_from_department_pool,
    remove_candidate_from_pool, transfer_candidates_to_position,
    batch_update_pool_status, verify_department_pool_ownership,
    move_candidate_to_pool
)
from typing import Optional
import traceback
import json

router = APIRouter(prefix="/api/pools", tags=["pools"])


@router.get("/hierarchical")
def get_hierarchical(current_user: dict = Depends(get_current_user)):
    """Hiyerarsik havuz agaci + istatistikler"""
    try:
        company_id = current_user["company_id"]
        departments = get_hierarchical_pool_stats(company_id)

        # Sistem havuzlarini da ekle
        system_pools = get_department_pools(company_id, pool_type=None)
        system_list = []
        for p in system_pools:
            if p.get("is_system"):
                # Aday sayisini bul
                stats = get_department_pool_stats(company_id)
                count = 0
                for s in stats:
                    if s["id"] == p["id"]:
                        count = s["candidate_count"]
                        break
                system_list.append({
                    "id": p["id"],
                    "name": p["name"],
                    "icon": p.get("icon", ""),
                    "is_system": True,
                    "candidate_count": count,
                })

        return {
            "success": True,
            "data": {
                "system_pools": system_list,
                "departments": departments,
            }
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_stats(current_user: dict = Depends(get_current_user)):
    """Duz istatistik listesi"""
    try:
        company_id = current_user["company_id"]
        stats = get_department_pool_stats(company_id)
        return {"success": True, "data": stats}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_pools(
    pool_type: Optional[str] = Query(None),
    parent_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Tum havuzlari listele"""
    try:
        company_id = current_user["company_id"]
        pools = get_department_pools(
            company_id, include_inactive=False,
            pool_type=pool_type, parent_id=parent_id, use_cache=False
        )
        return {"success": True, "data": pools, "total": len(pools)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_pool(body: dict, current_user: dict = Depends(get_current_user)):
    """Yeni departman veya pozisyon havuzu olustur"""
    try:
        company_id = current_user["company_id"]
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Havuz adi zorunludur")

        pool_type = body.get("pool_type", "department")
        parent_id = body.get("parent_id")

        # Pozisyon olusturuluyorsa parent_id zorunlu
        if pool_type == "position" and not parent_id:
            raise HTTPException(status_code=400, detail="Pozisyon icin departman (parent_id) zorunludur")

        # parent_id verilmisse sahiplik kontrolu
        if parent_id:
            if not verify_department_pool_ownership(parent_id, company_id):
                raise HTTPException(status_code=403, detail="Bu departmana erisim yetkiniz yok")

        keywords = body.get("keywords", [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except (json.JSONDecodeError, TypeError):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        new_id = create_department_pool(
            company_id=company_id,
            name=name,
            icon=body.get("icon", ""),
            keywords=keywords,
            description=body.get("description", ""),
            parent_id=parent_id,
            pool_type=pool_type,
            gerekli_deneyim_yil=body.get("gerekli_deneyim_yil", 0),
            gerekli_egitim=body.get("gerekli_egitim", ""),
            lokasyon=body.get("lokasyon", ""),
            aranan_nitelikler=body.get("aranan_nitelikler"),
            is_tanimi=body.get("is_tanimi"),
        )
        return {"success": True, "id": new_id, "message": "Havuz olusturuldu"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{pool_id}")
def update_pool(pool_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Havuz guncelle"""
    try:
        company_id = current_user["company_id"]
        fields = {k: v for k, v in body.items() if k != "id"}

        if "keywords" in fields and isinstance(fields["keywords"], str):
            try:
                fields["keywords"] = json.loads(fields["keywords"])
            except (json.JSONDecodeError, TypeError):
                fields["keywords"] = [k.strip() for k in fields["keywords"].split(",") if k.strip()]

        success = update_department_pool(pool_id, company_id=company_id, **fields)
        if not success:
            raise HTTPException(status_code=404, detail="Havuz bulunamadi veya degisiklik yok")
        return {"success": True, "message": "Havuz guncellendi"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pool_id}")
def delete_pool(pool_id: int, current_user: dict = Depends(get_current_user)):
    """Havuz sil (sistem havuzlari silinemez)"""
    try:
        company_id = current_user["company_id"]
        success = delete_department_pool(pool_id, company_id=company_id)
        if not success:
            raise HTTPException(status_code=400, detail="Havuz silinemedi (sistem havuzu olabilir)")
        return {"success": True, "message": "Havuz silindi"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pool_id}/candidates")
def get_pool_candidates(pool_id: int, current_user: dict = Depends(get_current_user)):
    """Havuzdaki adaylari getir"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erisim yetkiniz yok")

        # Havuz bilgisini al
        pool = get_department_pool(pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail="Havuz bulunamadi")

        pool_type = pool.get("pool_type", "department")
        is_system = pool.get("is_system", 0)

        # Sistem havuzlari ve departmanlar: candidate_pool_assignments
        # Pozisyonlar: candidate_positions (get_department_pool_candidates de assignments kullanir)
        if is_system:
            candidates = get_pool_candidates_with_days(pool_id, pool_type='general')
        else:
            candidates = get_department_pool_candidates(pool_id)

        # Hassas alanlari temizle
        for c in candidates:
            c.pop("cv_raw_text", None)
            c.pop("sifre", None)
            c.pop("password_hash", None)

        return {
            "success": True,
            "data": candidates,
            "total": len(candidates),
            "pool": {
                "id": pool["id"],
                "name": pool["name"],
                "icon": pool.get("icon", ""),
                "pool_type": pool_type,
                "is_system": is_system,
                "keywords": pool.get("keywords"),
                "description": pool.get("description"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pool_id}/candidates")
def assign_candidate(pool_id: int, body: dict, current_user: dict = Depends(get_current_user)):
    """Manuel aday ata"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erisim yetkiniz yok")

        candidate_id = body.get("candidate_id")
        if not candidate_id:
            raise HTTPException(status_code=400, detail="candidate_id zorunludur")

        assign_id = assign_candidate_to_department_pool(
            candidate_id=candidate_id,
            pool_id=pool_id,
            company_id=company_id,
            assignment_type="manual",
            match_score=body.get("match_score", 0),
            match_reason=body.get("reason", "Manuel atama")
        )
        return {"success": True, "id": assign_id, "message": "Aday havuza atandi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pool_id}/candidates/{candidate_id}")
def remove_candidate(
    pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)
):
    """Adayi havuzdan cikar"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erisim yetkiniz yok")

        # Her iki tablodan da sil
        removed_assignments = remove_candidate_from_department_pool(candidate_id, pool_id)
        removed_positions = remove_candidate_from_pool(pool_id, candidate_id)

        if not removed_assignments and not removed_positions:
            raise HTTPException(status_code=404, detail="Aday bu havuzda bulunamadi")

        return {"success": True, "message": "Aday havuzdan cikarildi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transfer")
def transfer_candidates(body: dict, current_user: dict = Depends(get_current_user)):
    """Adaylari havuzlar arasi tasi"""
    try:
        company_id = current_user["company_id"]
        candidate_ids = body.get("candidate_ids", [])
        source_pool_id = body.get("source_pool_id")
        target_pool_id = body.get("target_pool_id")

        if not candidate_ids or not source_pool_id or not target_pool_id:
            raise HTTPException(status_code=400, detail="candidate_ids, source_pool_id ve target_pool_id zorunludur")

        # Sahiplik kontrolu
        if not verify_department_pool_ownership(source_pool_id, company_id):
            raise HTTPException(status_code=403, detail="Kaynak havuza erisim yetkiniz yok")
        if not verify_department_pool_ownership(target_pool_id, company_id):
            raise HTTPException(status_code=403, detail="Hedef havuza erisim yetkiniz yok")

        stats = transfer_candidates_to_position(
            candidate_ids=candidate_ids,
            target_pool_id=target_pool_id,
            source_pool_id=source_pool_id
        )
        return {"success": True, "data": stats, "message": f"{stats['success']} aday tasinidi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{pool_id}/candidates/status")
def update_candidates_status(
    pool_id: int, body: dict, current_user: dict = Depends(get_current_user)
):
    """Toplu durum guncelle"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erisim yetkiniz yok")

        candidate_ids = body.get("candidate_ids", [])
        durum = body.get("durum")

        if not candidate_ids or not durum:
            raise HTTPException(status_code=400, detail="candidate_ids ve durum zorunludur")

        updated = batch_update_pool_status(pool_id, candidate_ids, durum)
        return {"success": True, "updated": updated, "message": f"{updated} aday guncellendi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pool_id}/pull-candidates")
def pull_candidates(pool_id: int, current_user: dict = Depends(get_current_user)):
    """Pozisyon icin eslesen adaylari cek (CV Cek)"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erisim yetkiniz yok")

        from database import pull_matching_candidates_to_position
        result = pull_matching_candidates_to_position(pool_id, company_id)
        return {
            "success": True,
            "data": result,
            "message": f"{result.get('transferred', 0)} aday eslesti ve aktarildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-all")
def sync_all_positions(current_user: dict = Depends(get_current_user)):
    """Tum pozisyonlar icin aday eslestirmesi yap"""
    try:
        company_id = current_user["company_id"]
        from database import sync_candidates_to_all_positions
        result = sync_candidates_to_all_positions(company_id)
        return {
            "success": True,
            "data": result,
            "message": f"{result['positions_scanned']} pozisyon taranidi, {result['total_transferred']} aday aktarildi"
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{pool_id}/candidates/{candidate_id}/detail")
def get_candidate_detail(pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Aday detay karti"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, ad_soyad, email, telefon, lokasyon, egitim, universite, bolum,
                       toplam_deneyim_yil, mevcut_pozisyon, mevcut_sirket, deneyim_detay,
                       teknik_beceriler, diller, sertifikalar, cv_dosya_adi,
                       linkedin, egitim_detay, olusturma_tarihi
                FROM candidates WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Aday bulunamadi")

            cols = [d[0] for d in cursor.description]
            candidate = dict(zip(cols, row))

            cursor.execute("""
                SELECT detayli_analiz, uyum_puani
                FROM matches WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, pool_id))
            match_row = cursor.fetchone()
            v2_detail = None
            if match_row and match_row[0]:
                try:
                    v2_detail = json.loads(match_row[0]) if str(match_row[0]).startswith('{') else {"text": str(match_row[0])}
                except Exception:
                    v2_detail = {"text": str(match_row[0])}
                v2_detail["uyum_puani"] = match_row[1]

            cursor.execute("""
                SELECT match_score, status FROM candidate_positions
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, pool_id))
            cp_row = cursor.fetchone()

            cursor.execute("""
                SELECT evaluation_text, v2_score, created_at FROM ai_evaluations
                WHERE candidate_id = ? AND position_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (candidate_id, pool_id))
            ai_row = cursor.fetchone()
            ai_eval = None
            if ai_row:
                ai_eval = {"text": ai_row[0], "v2_score": ai_row[1], "date": ai_row[2]}

        return {
            "success": True,
            "candidate": candidate,
            "position_score": cp_row[0] if cp_row else None,
            "position_status": cp_row[1] if cp_row else None,
            "v2_detail": v2_detail,
            "ai_evaluation": ai_eval
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pool_id}/candidates/export")
def export_candidates(pool_id: int, current_user: dict = Depends(get_current_user)):
    """CSV export"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        pool = get_department_pool(pool_id)
        pool_type = pool.get("pool_type", "department") if pool else "department"

        with get_connection() as conn:
            cursor = conn.cursor()
            if pool and pool.get("is_system"):
                cursor.execute("""
                    SELECT c.ad_soyad, c.email, c.telefon, c.mevcut_pozisyon,
                           c.toplam_deneyim_yil, c.lokasyon, c.egitim, c.teknik_beceriler,
                           cpa.match_score, cpa.assignment_type
                    FROM candidate_pool_assignments cpa
                    JOIN candidates c ON cpa.candidate_id = c.id
                    WHERE cpa.department_pool_id = ?
                    ORDER BY cpa.match_score DESC
                """, (pool_id,))
            elif pool_type == "position":
                cursor.execute("""
                    SELECT c.ad_soyad, c.email, c.telefon, c.mevcut_pozisyon,
                           c.toplam_deneyim_yil, c.lokasyon, c.egitim, c.teknik_beceriler,
                           cp.match_score, cp.status
                    FROM candidate_positions cp
                    JOIN candidates c ON cp.candidate_id = c.id
                    WHERE cp.position_id = ?
                    ORDER BY cp.match_score DESC
                """, (pool_id,))
            else:
                cursor.execute("""
                    SELECT c.ad_soyad, c.email, c.telefon, c.mevcut_pozisyon,
                           c.toplam_deneyim_yil, c.lokasyon, c.egitim, c.teknik_beceriler,
                           cpa.match_score, cpa.assignment_type
                    FROM candidate_pool_assignments cpa
                    JOIN candidates c ON cpa.candidate_id = c.id
                    WHERE cpa.department_pool_id = ?
                    ORDER BY cpa.match_score DESC
                """, (pool_id,))
            rows = cursor.fetchall()

        import csv, io
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(["Ad Soyad", "Email", "Telefon", "Mevcut Pozisyon",
                         "Deneyim (Yil)", "Lokasyon", "Egitim", "Teknik Beceriler",
                         "Uyum Puani", "Durum"])
        for row in rows:
            writer.writerow([str(v) if v is not None else '' for v in row])

        from fastapi.responses import Response
        csv_bytes = b'\xef\xbb\xbf' + output.getvalue().encode('utf-8')
        import unicodedata, re
        pool_name = pool.get("name", "havuz") if pool else "havuz"
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', unicodedata.normalize('NFKD', pool_name).encode('ascii', 'ignore').decode('ascii'))
        if not safe_name: safe_name = "havuz"
        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_adaylar.csv"}
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/from-url")
def parse_position_from_url(data: dict, current_user: dict = Depends(get_current_user)):
    """URL'den pozisyon parse et (kariyer.net)"""
    try:
        url = data.get("url", "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL gerekli")

        from job_scraper import process_job_url
        result = process_job_url(url)

        if not result.get("basarili"):
            error_msg = result.get("hata", "Bilinmeyen hata")
            print(f"[URL Parse] Basarisiz: {url[:50]}... -> {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        print(f"[URL Parse] Basarili: {result.get('pozisyon_adi', 'N/A')}")
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        print(f"[URL Parse] Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/from-document")
async def parse_position_from_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Dokumandan pozisyon parse et (PDF/Word/Image)"""
    from fastapi import UploadFile, File
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Dosya adi bos")
        
        # Dosya icerigi oku
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Dosya bos")
        
        # job_scraper.process_job_document kullan (KILITLI - sadece import)
        from job_scraper import process_job_document
        result = process_job_document(content, file.filename)
        
        if not result.get("basarili"):
            raise HTTPException(status_code=400, detail=result.get("hata", "Parse hatasi"))
        
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/position/save-parsed")
def save_parsed_position(data: dict, current_user: dict = Depends(get_current_user)):
    try:
        company_id = current_user["company_id"]
        parent_id = data.get("parent_id")
        if not parent_id:
            raise HTTPException(status_code=400, detail="parent_id gerekli")
        if not data.get("pozisyon_adi"):
            raise HTTPException(status_code=400, detail="pozisyon_adi gerekli")

        # Verify parent ownership
        if not verify_department_pool_ownership(parent_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        # Create position pool
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        description_parts = []
        if data.get("aranan_nitelikler"):
            description_parts.append(f"Aranan Nitelikler: {data['aranan_nitelikler']}")
        if data.get("is_tanimi"):
            description_parts.append(f"Is Tanimi: {data['is_tanimi']}")

        pool_data = {
            "name": data["pozisyon_adi"],
            "pool_type": "position",
            "parent_id": parent_id,
            "icon": "\U0001F3AF",
            "keywords": keywords,
            "description": "\n".join(description_parts) if description_parts else None,
            "gerekli_deneyim_yil": float(data.get("deneyim_yil", 0) or 0),
            "gerekli_egitim": data.get("egitim_seviyesi", ""),
            "lokasyon": data.get("lokasyon", ""),
            "company_id": company_id
        }

        pool_id = create_department_pool(**pool_data)
        if not pool_id:
            raise HTTPException(status_code=500, detail="Pozisyon olusturulamadi")

        # categorize_and_save - v2 tablolarini doldur
        position_text = f"{data.get('pozisyon_adi','')} {data.get('aranan_nitelikler','')} {data.get('is_tanimi','')}"
        try:
            from scoring_v2 import categorize_and_save
            categorize_and_save(pool_id, data["pozisyon_adi"], position_text, keywords)
        except Exception as cat_err:
            print(f"categorize_and_save hatasi (devam ediliyor): {cat_err}")

        # Otomatik CV Cek
        transferred = 0
        try:
            from database import pull_matching_candidates_to_position
            result = pull_matching_candidates_to_position(pool_id, company_id)
            transferred = result.get("transferred", 0)
        except Exception as pull_err:
            print(f"pull_matching hatasi (devam ediliyor): {pull_err}")

        return {
            "success": True,
            "pool_id": pool_id,
            "transferred": transferred,
            "message": f"Pozisyon olusturuldu, {transferred} aday eslestirildi"
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{pool_id}/keywords")
def update_keywords(pool_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    """Keyword ekle/sil"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        action = data.get("action")  # "add" or "remove"
        keyword = data.get("keyword", "").strip()
        if not action or not keyword:
            raise HTTPException(status_code=400, detail="action ve keyword gerekli")

        pool = get_department_pool(pool_id)
        if not pool:
            raise HTTPException(status_code=404, detail="Havuz bulunamadi")

        current_keywords = pool.get("keywords") or []
        if isinstance(current_keywords, str):
            current_keywords = [k.strip() for k in current_keywords.split(",") if k.strip()]

        if action == "add" and keyword not in current_keywords:
            current_keywords.append(keyword)
        elif action == "remove" and keyword in current_keywords:
            current_keywords.remove(keyword)

        update_department_pool(pool_id, company_id=company_id, keywords=current_keywords)

        return {"success": True, "keywords": current_keywords}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============ AKILLI HAVUZ - TITLE MAPPINGS ============

@router.get("/{pool_id}/approved-titles")
def get_approved_titles(pool_id: int, current_user: dict = Depends(get_current_user)):
    """Onaylanmis baslik eslesmelerini getir"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, related_title, match_level, source
                FROM position_title_mappings
                WHERE position_id = ? AND approved = 1
                ORDER BY match_level, related_title
            """, (pool_id,))
            rows = cursor.fetchall()

        # match_level bazli grupla
        result = {"exact": [], "similar": [], "related": []}
        for row in rows:
            item = {
                "id": row["id"],
                "related_title": row["related_title"],
                "match_level": row["match_level"],
                "source": row["source"]
            }
            level = row["match_level"] or "related"
            if level in result:
                result[level].append(item)
            else:
                result["related"].append(item)

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pool_id}/pending-titles")
def get_pending_titles(pool_id: int, current_user: dict = Depends(get_current_user)):
    """Onay bekleyen baslik onerilerini getir"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, related_title, match_level, source
                FROM position_title_mappings
                WHERE position_id = ? AND approved = 0
                ORDER BY match_level, related_title
            """, (pool_id,))
            rows = cursor.fetchall()

        # match_level bazli grupla
        result = {"exact": [], "similar": [], "related": []}
        for row in rows:
            item = {
                "id": row["id"],
                "related_title": row["related_title"],
                "match_level": row["match_level"],
                "source": row["source"]
            }
            level = row["match_level"] or "related"
            if level in result:
                result[level].append(item)
            else:
                result["related"].append(item)

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pool_id}/approve-titles")
def approve_titles(pool_id: int, data: dict, current_user: dict = Depends(get_current_user)):
    """Baslik onerilerini onayla veya reddet"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        approved_ids = data.get("approved_ids", [])
        rejected_ids = data.get("rejected_ids", [])

        approved_count = 0
        rejected_count = 0

        with get_connection() as conn:
            cursor = conn.cursor()

            # Onaylananlar
            if approved_ids:
                placeholders = ",".join("?" * len(approved_ids))
                cursor.execute(f"""
                    UPDATE position_title_mappings
                    SET approved = 1
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*approved_ids, pool_id))
                approved_count = cursor.rowcount

            # Reddedilenler (sil)
            if rejected_ids:
                placeholders = ",".join("?" * len(rejected_ids))
                cursor.execute(f"""
                    DELETE FROM position_title_mappings
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*rejected_ids, pool_id))
                rejected_count = cursor.rowcount

            conn.commit()

        # Onay sonrasi aday eslestir
        transferred = 0
        try:
            from database import pull_matching_candidates_to_position
            result = pull_matching_candidates_to_position(pool_id, company_id)
            transferred = result.get("transferred", 0)
        except Exception as pull_err:
            print(f"pull_matching hatasi (devam ediliyor): {pull_err}")

        return {
            "success": True,
            "approved": approved_count,
            "rejected": rejected_count,
            "transferred": transferred
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============ AI DEĞERLENDİRME ============

@router.post("/{pool_id}/candidates/{candidate_id}/evaluate")
def evaluate_candidate(pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)):
    """AI ile aday değerlendirmesi yap"""
    import anthropic
    import os
    import json as json_lib
    
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Aday bilgileri (company_id filtresi ile IDOR koruması)
            cursor.execute("""
                SELECT ad_soyad, mevcut_pozisyon, toplam_deneyim_yil, egitim,
                       teknik_beceriler, deneyim_detay, lokasyon
                FROM candidates WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            cand = cursor.fetchone()
            if not cand:
                raise HTTPException(status_code=404, detail="Aday bulunamadi")

            # Pozisyon bilgileri (company_id filtresi ile IDOR koruması)
            cursor.execute("SELECT name, keywords FROM department_pools WHERE id = ? AND company_id = ?", (pool_id, company_id))
            pos = cursor.fetchone()
            if not pos:
                raise HTTPException(status_code=404, detail="Pozisyon bulunamadi")
            
            # v2 skor bilgileri
            cursor.execute("""
                SELECT uyum_puani, detayli_analiz 
                FROM matches 
                WHERE candidate_id = ? AND position_id = ?
                ORDER BY id DESC LIMIT 1
            """, (candidate_id, pool_id))
            match_row = cursor.fetchone()
            
            # Varsayılan değerler
            total_v2 = 0
            pos_score = 0
            title_match_level = "-"
            technical_score = 0
            critical_matched = []
            critical_missing = []
            experience_score = 0
            education_score = 0
            knockout = False
            knockout_reason = ""
            
            if match_row:
                total_v2 = match_row["uyum_puani"] or 0
                if match_row["detayli_analiz"]:
                    try:
                        detail = json_lib.loads(match_row["detayli_analiz"])
                        pos_score = detail.get("position_score", 0)
                        title_match_level = detail.get("title_match_level", "-")
                        technical_score = detail.get("technical_score", 0)
                        critical_matched = detail.get("critical_matched", [])[:5]
                        critical_missing = detail.get("critical_missing", [])[:5]
                        experience_score = detail.get("experience_score", 0)
                        education_score = detail.get("education_score", 0)
                        knockout = detail.get("knockout", False)
                        knockout_reason = detail.get("knockout_reason", "")
                    except:
                        pass
            
            # Prompt oluştur (TalentFlow formatı)
            crit_matched_str = ", ".join(critical_matched) if critical_matched else "Yok"
            crit_missing_str = ", ".join(critical_missing) if critical_missing else "Yok"
            ko_str = f"KNOCKOUT: {knockout_reason}" if knockout else ""
            
            eval_prompt = f"""Asagidaki adayi belirtilen pozisyon icin degerlendir. Turkce yanit ver.

ADAY: {cand["ad_soyad"]}
Mevcut Pozisyon: {cand["mevcut_pozisyon"] or "-"}
Deneyim: {cand["toplam_deneyim_yil"] or 0} yil
Egitim: {cand["egitim"] or "-"}
Teknik Beceriler: {cand["teknik_beceriler"] or "-"}
Deneyim Detay: {(cand["deneyim_detay"] or "-")[:500]}
Lokasyon: {cand["lokasyon"] or "-"}

POZISYON: {pos["name"]}
Keywords: {pos["keywords"] or ""}

V2 SKOR: {total_v2}/100
Pozisyon Uyumu: {pos_score}/33 (baslik: {title_match_level})
Teknik Yetkinlik: {technical_score}/37
Kritik eslesen: {crit_matched_str}
Kritik eksik: {crit_missing_str}
Deneyim: {experience_score}/10, Egitim: {education_score}/10
{ko_str}

Asagidaki formatta yanit ver (kisa ve oz, her baslik 2-3 madde):

**Guclu Yonleri:**
- ...

**Eksiklikleri:**
- ...

**Genel Degerlendirme:**
(2-3 cumle)

**Alternatif Pozisyonlar:**
- ...
"""
        
        # Claude API çağır
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY ayarlanmamis")
        
        try:
            client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": eval_prompt}]
            )
            ai_result = message.content[0].text
        except anthropic.APITimeoutError:
            raise HTTPException(status_code=504, detail="Claude API zaman asimi")
        except anthropic.APIConnectionError:
            raise HTTPException(status_code=503, detail="Claude API baglanti hatasi")
        except Exception as api_err:
            raise HTTPException(status_code=500, detail=f"Claude API hatasi: {str(api_err)}")
        
        # DB'ye kaydet
        from database import save_ai_evaluation
        save_ai_evaluation(candidate_id, pool_id, ai_result, total_v2, eval_prompt)
        
        return {
            "success": True,
            "evaluation": {
                "text": ai_result,
                "v2_score": total_v2
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pool_id}/candidates/{candidate_id}/report")
def get_candidate_report(pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)):
    """AI değerlendirme raporu (HTML)"""
    from fastapi.responses import HTMLResponse
    import json as json_lib
    
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()
            
            # AI evaluation
            cursor.execute("""
                SELECT evaluation_text, v2_score, created_at 
                FROM ai_evaluations 
                WHERE candidate_id = ? AND position_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (candidate_id, pool_id))
            ai_row = cursor.fetchone()
            if not ai_row:
                raise HTTPException(status_code=404, detail="AI degerlendirme bulunamadi. Once degerlendirme yapin.")
            
            # Aday adı (company_id filtresi ile IDOR koruması)
            cursor.execute("SELECT ad_soyad FROM candidates WHERE id = ? AND company_id = ?", (candidate_id, company_id))
            cand = cursor.fetchone()
            candidate_name = cand["ad_soyad"] if cand else "Bilinmeyen"

            # Pozisyon adı (company_id filtresi ile IDOR koruması)
            cursor.execute("SELECT name FROM department_pools WHERE id = ? AND company_id = ?", (pool_id, company_id))
            pos = cursor.fetchone()
            position_name = pos["name"] if pos else "Bilinmeyen"
            
            # v2 detay
            cursor.execute("""
                SELECT detayli_analiz FROM matches 
                WHERE candidate_id = ? AND position_id = ?
                ORDER BY id DESC LIMIT 1
            """, (candidate_id, pool_id))
            match_row = cursor.fetchone()
            
            v2_data = {
                "total": ai_row["v2_score"] or 0,
                "pos_score": 0, "technical_score": 0, "experience_score": 0,
                "education_score": 0, "elimination_score": 0, "title_match_level": "-",
                "matched_title": "", "sector_detail": "", "location_detail": "",
                "critical_matched": [], "critical_missing": [],
                "knockout": False, "knockout_reason": ""
            }
            
            if match_row and match_row["detayli_analiz"]:
                try:
                    detail = json_lib.loads(match_row["detayli_analiz"])
                    v2_data.update({
                        "pos_score": detail.get("position_score", 0),
                        "technical_score": detail.get("technical_score", 0),
                        "experience_score": detail.get("experience_score", 0),
                        "education_score": detail.get("education_score", 0),
                        "elimination_score": detail.get("elimination_score", 0),
                        "title_match_level": detail.get("title_match_level", "-"),
                        "matched_title": detail.get("matched_title", ""),
                        "sector_detail": detail.get("sector_detail", ""),
                        "location_detail": detail.get("location_detail", ""),
                        "critical_matched": detail.get("critical_matched", []),
                        "critical_missing": detail.get("critical_missing", []),
                        "knockout": detail.get("knockout", False),
                        "knockout_reason": detail.get("knockout_reason", "")
                    })
                except:
                    pass
        
        # HTML rapor oluştur
        from eval_report import generate_eval_html
        html = generate_eval_html(
            candidate_name=candidate_name,
            position_name=position_name,
            v2_data=v2_data,
            ai_text=ai_row["evaluation_text"],
            eval_date=str(ai_row["created_at"])[:16] if ai_row["created_at"] else None
        )
        
        return HTMLResponse(content=html, media_type="text/html")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============ CV GÖRÜNTÜLEME ============

@router.get("/{pool_id}/candidates/{candidate_id}/cv")
def get_candidate_cv(pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Aday CV dosyasını döndür"""
    from fastapi.responses import Response
    import os

    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT cv_dosya_yolu, cv_dosya_adi
                FROM candidates WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Aday bulunamadi")

            cv_path = row["cv_dosya_yolu"]
            cv_filename = row["cv_dosya_adi"] or "cv.pdf"

            if not cv_path:
                raise HTTPException(status_code=404, detail="CV dosyasi bulunamadi")

            # Guvenlik: CV erisim kontrolu (2x3)
            if not validate_cv_access(cv_path, company_id):
                raise HTTPException(status_code=403, detail="CV erisim yetkisi yok")

            if not os.path.exists(cv_path):
                raise HTTPException(status_code=404, detail="CV dosyasi fiziksel olarak bulunamadi")

            with open(cv_path, "rb") as f:
                file_bytes = f.read()

            # MIME type belirle
            if cv_path.lower().endswith('.pdf'):
                media_type = "application/pdf"
            elif cv_path.lower().endswith('.docx'):
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                media_type = "application/octet-stream"

            return Response(
                content=file_bytes,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'inline; filename="{cv_filename}"'
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
