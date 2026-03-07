from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from routes.auth import get_current_user
from core.cv_parser import validate_cv_access, get_safe_content_disposition, convert_to_pdf
from database import (
    get_connection,
    get_department_pools, get_department_pool, get_department_pool_stats,
    get_hierarchical_pool_stats, get_department_pool_candidates,
    get_pool_candidates_with_days, get_pool_by_name,
    create_department_pool, update_department_pool, delete_department_pool,
    assign_candidate_to_department_pool, remove_candidate_from_department_pool,
    remove_candidate_from_pool, transfer_candidates_to_position,
    batch_update_pool_status, verify_department_pool_ownership,
    move_candidate_to_pool, get_position_candidates, add_candidate_to_position,
    increment_keyword_usage  # FAZ 7.3
)
from typing import Optional
import traceback
import json
import logging

router = APIRouter(prefix="/api/pools", tags=["pools"])


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ 7.1: KEYWORD BLACKLIST
# Soft skill ve genel terimler - pozisyonlara EKLENMEYECEK
# Bu keyword'ler her ilanda geçtiği için ayırt edici değil
# ═══════════════════════════════════════════════════════════════════════════════
KEYWORD_BLACKLIST = {
    # ═══ SOFT SKILLS ═══
    'iletişim', 'communication', 'iletişim becerileri',
    'takım çalışması', 'teamwork', 'takım', 'team', 'ekip çalışması',
    'liderlik', 'leadership', 'leader', 'lider',
    'problem çözme', 'problem solving', 'sorun çözme',
    'analitik düşünme', 'analytical thinking',
    'organizasyon', 'organization', 'organizasyonel',
    'koordinasyon', 'coordination', 'koordine', 'eşgüdüm',
    'sunum', 'presentation', 'sunum becerileri',
    'planlama', 'planning',
    'adaptasyon', 'adaptation', 'uyum', 'esneklik',
    'motivasyon', 'motivation', 'motivasyonel',
    'yaratıcılık', 'creativity', 'yaratıcı',
    'zaman yönetimi', 'time management',
    'müzakere', 'negotiation', 'ikna',
    'empati', 'empathy',
    'stres yönetimi', 'stress management',
    'karar verme', 'decision making',
    'öğrenme', 'learning', 'öğrenmeye açık',

    # ═══ ÇOK GENEL TERİMLER ═══
    'eğitim', 'education', 'training',
    'deneyim', 'experience', 'tecrübe',
    'yönetim', 'management', 'yönetici',
    'performans', 'performance',
    'kontrol', 'control',
    'kariyer', 'career',
    'raporlama', 'reporting', 'rapor', 'report',
    'takip', 'follow-up', 'izleme',
    'süreç', 'process', 'süreçler',
    'destek', 'support',
    'geliştirme', 'development', 'gelişim',
    'uygulama', 'implementation', 'application',
    'değerlendirme', 'evaluation', 'assessment',

    # ═══ İK TERİMLERİ ═══
    'mülakat', 'interview', 'görüşme',
    'işe alım', 'recruitment', 'hiring',
    'bordro', 'payroll',
    'özlük', 'personnel',
    'yan haklar', 'benefits',
    'sgk', 'sigorta',

    # ═══ OFİS PROGRAMLARI (Excel HARİÇ) ═══
    'word', 'powerpoint', 'outlook', 'teams',
    'ms office', 'microsoft office', 'office',
}


def filter_keywords(keywords: list) -> list:
    """
    FAZ 7.1: BLACKLIST'teki keyword'leri filtrele.

    Soft skill ve genel terimler pozisyonlara eklenmez çünkü
    her ilanda geçtiği için ayırt edici değil.

    Args:
        keywords: Keyword listesi

    Returns:
        Filtrelenmiş keyword listesi (blacklist'te olmayanlar)
    """
    if not keywords:
        return []

    filtered = []
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower and kw_lower not in KEYWORD_BLACKLIST:
            filtered.append(kw)

    return filtered


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

        # Toplam aday sayısı (Dashboard ile aynı kaynak)
        from database import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM candidates WHERE company_id = ?", (company_id,))
            total_candidates = cursor.fetchone()[0]

        return {
            "success": True,
            "data": {
                "system_pools": system_list,
                "departments": departments,
                "total_candidates": total_candidates,
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
        return {"success": True, "id": new_id, "message": "Havuz oluşturuldu"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="Bu isimde havuz zaten mevcut")
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
            raise HTTPException(status_code=404, detail="Havuz bulunamadı veya değişiklik yok")
        return {"success": True, "message": "Havuz güncellendi"}
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
            raise HTTPException(status_code=404, detail="Havuz bulunamadı")

        pool_type = pool.get("pool_type", "department")
        is_system = pool.get("is_system", 0)

        # Sistem havuzları: get_pool_candidates_with_days
        # Pozisyonlar: candidate_positions tablosu
        # Departmanlar: candidate_pool_assignments tablosu
        if is_system:
            candidates = get_pool_candidates_with_days(pool_id, pool_type='general')
        elif pool_type == "position":
            candidates = get_position_candidates(pool_id)
            # Pozisyon adayları için location_status zenginleştirmesi
            if candidates:
                from database import get_connection
                import json as json_lib
                import logging
                with get_connection() as conn:
                    cursor = conn.cursor()
                    for c in candidates:
                        try:
                            cid = c["id"]
                            cursor.execute("""
                                SELECT detayli_analiz FROM matches
                                WHERE candidate_id = ? AND position_id = ?
                            """, (cid, pool_id))
                            match_row = cursor.fetchone()
                            if match_row and match_row["detayli_analiz"]:
                                detail = json_lib.loads(match_row["detayli_analiz"])
                                c["location_status"] = detail.get("location_status", {})
                        except Exception as e:
                            logging.error(f"location_status enrichment error: candidate_id={c.get('id')}, pool_id={pool_id}, error={e}")
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
            raise HTTPException(status_code=403, detail="Bu havuza erişim yetkiniz yok")

        candidate_id = body.get("candidate_id")
        if not candidate_id:
            raise HTTPException(status_code=400, detail="candidate_id zorunludur")

        # Pool tipini kontrol et
        pool = get_department_pool(pool_id)
        pool_type = pool.get("pool_type", "department") if pool else "department"

        if pool_type == "position":
            # Pozisyon havuzu → candidate_positions tablosuna
            result = add_candidate_to_position(
                candidate_id=candidate_id,
                position_id=pool_id,
                match_score=body.get("match_score", 0),
                company_id=company_id
            )
            if not result["success"]:
                raise HTTPException(status_code=400, detail=result["error"])
            return {"success": True, "message": "Aday pozisyona atandı"}
        else:
            # Departman/sistem havuzu → candidate_pool_assignments tablosuna
            assign_id = assign_candidate_to_department_pool(
                candidate_id=candidate_id,
                pool_id=pool_id,
                company_id=company_id,
                assignment_type="manual",
                match_score=body.get("match_score", 0),
                match_reason=body.get("reason", "Manuel atama")
            )
            return {"success": True, "id": assign_id, "message": "Aday havuza atandı"}
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

        # Havuz tipini kontrol et ve durumu güncelle
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM department_pools WHERE id = ? AND company_id = ?",
                (pool_id, company_id)
            )
            pool = cursor.fetchone()

            if pool:
                pool_name = pool[0]

                if pool_name == 'Genel Havuz':
                    raise HTTPException(
                        status_code=400,
                        detail="Genel Havuz'dan aday silinemez. Adayı arşivlemek için Arşivle butonunu kullanın."
                    )

                elif pool_name == 'Arşiv':
                    # Arşivden çıkarıldı → Genel Havuza taşı
                    cursor.execute("""
                        UPDATE candidates SET durum='yeni', havuz='genel_havuz', guncelleme_tarihi=datetime('now')
                        WHERE id=? AND company_id=?
                    """, (candidate_id, company_id))
                    cursor.execute(
                        "SELECT id FROM department_pools WHERE company_id=? AND name='Genel Havuz' AND is_system=1",
                        (company_id,)
                    )
                    genel = cursor.fetchone()
                    if genel:
                        cursor.execute("""
                            INSERT OR IGNORE INTO candidate_pool_assignments
                            (candidate_id, department_pool_id, company_id)
                            VALUES (?,?,?)
                        """, (candidate_id, genel[0], company_id))

                else:
                    # Pozisyon/Departmandan çıkarıldı → yeni'ye döner
                    cursor.execute("""
                        UPDATE candidates SET durum='yeni', havuz='genel_havuz', guncelleme_tarihi=datetime('now')
                        WHERE id=? AND company_id=?
                    """, (candidate_id, company_id))

            conn.commit()

        # Her iki tablodan da sil
        removed_assignments = remove_candidate_from_department_pool(candidate_id, pool_id)
        removed_positions = remove_candidate_from_pool(pool_id, candidate_id)

        if not removed_assignments and not removed_positions:
            raise HTTPException(status_code=404, detail="Aday bu havuzda bulunamadı")

        return {"success": True, "message": "Aday havuzdan çıkarıldı"}
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
        return {"success": True, "updated": updated, "message": f"{updated} aday güncellendi"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pool_id}/pull-candidates")
def pull_candidates(
    pool_id: int,
    limit: int = Query(default=50, ge=1, le=500, description="Maksimum eşleşme sayısı (varsayılan 50, max 500)"),
    current_user: dict = Depends(get_current_user)
):
    """Pozisyon için eşleşen adayları çek (CV Çek) - En yüksek skorlu TOP N aday"""
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Bu havuza erişim yetkiniz yok")

        from database import pull_matching_candidates_to_position
        result = pull_matching_candidates_to_position(pool_id, company_id, limit=limit)
        return {
            "success": True,
            "data": result,
            "message": f"{result.get('transferred', 0)} aday eşleşti ve aktarıldı (skor sıralı, limit: {limit})"
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
                       linkedin, egitim_detay, olusturma_tarihi, deneyim_aciklama
                FROM candidates WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Aday bulunamadı")

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
        print(f"[save-parsed] START - data: {data}")
        company_id = current_user["company_id"]
        parent_id = data.get("parent_id")
        print(f"[save-parsed] company_id={company_id}, parent_id={parent_id}")

        if not parent_id:
            raise HTTPException(status_code=400, detail="parent_id gerekli")
        if not data.get("pozisyon_adi"):
            raise HTTPException(status_code=400, detail="pozisyon_adi gerekli")

        # Verify parent ownership
        print(f"[save-parsed] Verifying parent ownership...")
        if not verify_department_pool_ownership(parent_id, company_id):
            raise HTTPException(status_code=403, detail="Erisim yetkiniz yok")
        print(f"[save-parsed] Parent ownership verified")

        # Create position pool
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        # ═══ FAZ 7.1: BLACKLIST Filtresi ═══
        original_count = len(keywords)
        keywords = filter_keywords(keywords)
        filtered_count = original_count - len(keywords)
        if filtered_count > 0:
            print(f"[save-parsed] BLACKLIST: {filtered_count} keyword filtrelendi, kalan: {len(keywords)}")

        # ═══ FAZ 7.3: Usage Count Artır ═══
        if keywords:
            try:
                usage_result = increment_keyword_usage(keywords, source="position")
                if usage_result.get("incremented", 0) > 0 or usage_result.get("created", 0) > 0:
                    print(f"[save-parsed] USAGE: {usage_result.get('incremented', 0)} güncellendi, {usage_result.get('created', 0)} oluşturuldu")
            except Exception as usage_err:
                print(f"[save-parsed] USAGE hatası (devam ediliyor): {usage_err}")

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
            "company_id": company_id,
            # Sorun 2 Fix: aranan_nitelikler ve is_tanimi eklendi
            "aranan_nitelikler": data.get("aranan_nitelikler"),
            "is_tanimi": data.get("is_tanimi"),
        }
        print(f"[save-parsed] Creating pool with data: {pool_data}")

        pool_id = create_department_pool(**pool_data)
        print(f"[save-parsed] Pool created with id={pool_id}")
        if not pool_id:
            raise HTTPException(status_code=500, detail="Pozisyon oluşturulamadı")

        # categorize_and_save - v2 tablolarini doldur
        print(f"[save-parsed] Running categorize_and_save...")
        position_text = f"{data.get('pozisyon_adi','')} {data.get('aranan_nitelikler','')} {data.get('is_tanimi','')}"
        try:
            from scoring_v2 import categorize_and_save
            categorize_and_save(pool_id, data["pozisyon_adi"], position_text, keywords)
            print(f"[save-parsed] categorize_and_save completed")
        except Exception as cat_err:
            print(f"[save-parsed] categorize_and_save hatasi (devam ediliyor): {cat_err}")

        # Otomatik CV Cek
        print(f"[save-parsed] Running pull_matching_candidates...")
        transferred = 0
        try:
            from database import pull_matching_candidates_to_position
            result = pull_matching_candidates_to_position(pool_id, company_id)
            transferred = result.get("transferred", 0)
            print(f"[save-parsed] pull_matching completed, transferred={transferred}")
        except Exception as pull_err:
            print(f"[save-parsed] pull_matching hatasi (devam ediliyor): {pull_err}")

        print(f"[save-parsed] SUCCESS - pool_id={pool_id}, transferred={transferred}")

        # FAZ 6.3: Keyword'ler için batch synonym üret (ARKA PLAN)
        # AI API çağrısı 30-90sn sürer — senkron çalışırsa DB kilitlenir
        # Thread ile arka plana taşıyoruz, HTTP response hemen döner
        if keywords:
            try:
                import threading
                # Thread-safe kopyalar (closure için)
                _kw = list(keywords)
                _cid = company_id
                _uid = current_user["id"]

                def _background_synonym_generation():
                    try:
                        # Import thread içinde — circular import önlemi
                        from routes.synonyms import _generate_synonyms_batch_internal
                        result = _generate_synonyms_batch_internal(
                            keywords=_kw,
                            company_id=_cid,
                            user_id=_uid
                        )
                        print(f"[save-parsed] Arka plan synonym üretimi tamamlandı: {result.get('message', '')}")
                    except Exception as e:
                        print(f"[save-parsed] Arka plan synonym üretimi HATASI: {e}")

                thread = threading.Thread(target=_background_synonym_generation, daemon=True)
                thread.start()
                print(f"[save-parsed] Synonym üretimi arka planda başlatıldı ({len(keywords)} keyword)")
            except Exception as syn_err:
                print(f"[save-parsed] Synonym thread başlatma hatası: {syn_err}")

        return {
            "success": True,
            "pool_id": pool_id,
            "transferred": transferred,
            "message": f"Pozisyon oluşturuldu, {transferred} aday eşleştirildi",
            "synonym_generation": "started_in_background"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[save-parsed] ERROR: {e}")
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
            raise HTTPException(status_code=404, detail="Havuz bulunamadı")

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

                # Önce onaylanacak başlıkları al (approved_title_mappings sync için)
                cursor.execute(f"""
                    SELECT related_title, match_level FROM position_title_mappings
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*approved_ids, pool_id))
                titles_to_approve = cursor.fetchall()

                # position_title_mappings güncelle
                cursor.execute(f"""
                    UPDATE position_title_mappings
                    SET approved = 1
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*approved_ids, pool_id))
                approved_count = cursor.rowcount

                # approved_title_mappings tablosunu da güncelle (KRITIK SYNC)
                for title_row in titles_to_approve:
                    title = title_row[0]
                    category = title_row[1]  # match_level = category
                    cursor.execute("""
                        UPDATE approved_title_mappings
                        SET is_approved = 1, approved_at = CURRENT_TIMESTAMP
                        WHERE position_id = ? AND title = ?
                    """, (pool_id, title))
                    # Eğer kayıt yoksa ekle
                    if cursor.rowcount == 0:
                        cursor.execute("""
                            INSERT OR IGNORE INTO approved_title_mappings (position_id, title, category, is_approved, approved_at)
                            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                        """, (pool_id, title, category))

            # Reddedilenler (sil)
            if rejected_ids:
                placeholders = ",".join("?" * len(rejected_ids))

                # Önce silinecek başlıkları al (approved_title_mappings sync için)
                cursor.execute(f"""
                    SELECT related_title FROM position_title_mappings
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*rejected_ids, pool_id))
                titles_to_reject = [r[0] for r in cursor.fetchall()]

                # position_title_mappings'den sil
                cursor.execute(f"""
                    DELETE FROM position_title_mappings
                    WHERE id IN ({placeholders}) AND position_id = ?
                """, (*rejected_ids, pool_id))
                rejected_count = cursor.rowcount

                # approved_title_mappings'den de sil
                for title in titles_to_reject:
                    cursor.execute("""
                        DELETE FROM approved_title_mappings
                        WHERE position_id = ? AND title = ?
                    """, (pool_id, title))

            conn.commit()

        # Onay sonrasi aday eslestir
        transferred = 0
        try:
            from database import pull_matching_candidates_to_position
            result = pull_matching_candidates_to_position(pool_id, company_id)
            transferred = result.get("transferred", 0)
        except Exception as pull_err:
            print(f"pull_matching hatasi (devam ediliyor): {pull_err}")

        # G8: Mevcut adayları rescore et (yeni başlıklar position_score'u değiştirir)
        rescore_count = 0
        try:
            from database import get_connection as get_rescore_conn
            from scoring_v2 import calculate_match_score_v2
            import json as json_rescore

            with get_rescore_conn() as rescore_conn:
                rc = rescore_conn.cursor()

                # Pozisyon bilgilerini al
                rc.execute("""
                    SELECT name, gerekli_deneyim_yil, gerekli_egitim, lokasyon
                    FROM department_pools WHERE id = ? AND company_id = ?
                """, (pool_id, company_id))
                pos = rc.fetchone()

                if pos:
                    # Pozisyon dict oluştur
                    position_dict = {
                        'id': pool_id,
                        'baslik': pos[0] or '',
                        'name': pos[0] or '',  # Uyumluluk için her ikisi de
                        'gerekli_deneyim_yil': pos[1] or 0,
                        'gerekli_egitim': pos[2] or '',
                        'lokasyon': pos[3] or '',
                        'company_id': company_id
                    }

                    # Mevcut eşleşmiş adayları al
                    rc.execute("""
                        SELECT candidate_id FROM candidate_positions
                        WHERE position_id = ?
                    """, (pool_id,))
                    existing_candidates = [r[0] for r in rc.fetchall()]

                    for cid in existing_candidates:
                        rc.execute("""
                            SELECT id, ad_soyad, teknik_beceriler, mevcut_pozisyon,
                                   deneyim_detay, toplam_deneyim_yil, egitim, lokasyon,
                                   mevcut_sirket, cv_raw_text
                            FROM candidates WHERE id = ? AND company_id = ?
                        """, (cid, company_id))
                        r = rc.fetchone()
                        if not r:
                            continue

                        candidate_dict = {
                            'id': r[0],
                            'ad_soyad': r[1] or '',
                            'teknik_beceriler': r[2] or '',
                            'mevcut_pozisyon': r[3] or '',
                            'deneyim_detay': r[4] or '',
                            'toplam_deneyim_yil': r[5] or 0,
                            'egitim': r[6] or '',
                            'lokasyon': r[7] or '',
                            'mevcut_sirket': r[8] or '',
                            'cv_raw_text': r[9] or '',
                            'company_id': company_id
                        }

                        v2_result = calculate_match_score_v2(candidate_dict, position_dict)
                        if v2_result:
                            new_score = v2_result.get('total', 0)
                            rc.execute("""
                                UPDATE matches SET uyum_puani = ?, detayli_analiz = ?
                                WHERE candidate_id = ? AND position_id = ?
                            """, (new_score, json_rescore.dumps(v2_result, ensure_ascii=False), cid, pool_id))
                            rc.execute("""
                                UPDATE candidate_positions SET match_score = ?
                                WHERE candidate_id = ? AND position_id = ?
                            """, (new_score, cid, pool_id))
                            rescore_count += 1

                    rescore_conn.commit()

            print(f"[approve-titles] G8 rescore: {rescore_count} aday güncellendi")
        except Exception as rescore_err:
            print(f"[approve-titles] G8 rescore hatası (devam ediliyor): {rescore_err}")

        return {
            "success": True,
            "approved": approved_count,
            "rejected": rejected_count,
            "transferred": transferred,
            "rescored": rescore_count
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

        # Mevcut değerlendirme kontrolü - her aday+pozisyon için sadece 1 kere AI çağrılır
        from database import get_ai_evaluation, check_ai_daily_limit
        existing_eval = get_ai_evaluation(candidate_id, pool_id)
        if existing_eval:
            return {
                "success": True,
                "evaluation": {
                    "text": existing_eval.get("evaluation_text", ""),
                    "v2_score": existing_eval.get("v2_score", 0)
                },
                "cached": True
            }

        # === AI GÜNLÜK LİMİT KONTROLÜ (27.02.2026) ===
        allowed, limit_msg, remaining = check_ai_daily_limit(company_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=limit_msg
            )
        # === LİMİT KONTROL SONU ===

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
                raise HTTPException(status_code=404, detail="Aday bulunamadı")

            # Pozisyon bilgileri (company_id filtresi ile IDOR koruması)
            cursor.execute("SELECT name, keywords FROM department_pools WHERE id = ? AND company_id = ?", (pool_id, company_id))
            pos = cursor.fetchone()
            if not pos:
                raise HTTPException(status_code=404, detail="Pozisyon bulunamadı")
            
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
            raise HTTPException(status_code=503, detail="Claude API bağlantı hatası")
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
                raise HTTPException(status_code=404, detail="AI değerlendirme bulunamadı. Önce değerlendirme yapın.")
            
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
                        "location_status": detail.get("location_status", {}),
                        "critical_matched": detail.get("critical_matched", []),
                        "critical_missing": detail.get("critical_missing", []),
                        "knockout": detail.get("knockout", False),
                        "knockout_reason": detail.get("knockout_reason", "")
                    })
                except:
                    pass
        
        # HTML rapor oluştur
        from eval_report_v2 import generate_eval_html
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
                raise HTTPException(status_code=404, detail="Aday bulunamadı")

            cv_path = row["cv_dosya_yolu"]
            cv_filename = row["cv_dosya_adi"] or "cv.pdf"

            if not cv_path:
                raise HTTPException(status_code=404, detail="CV dosyası bulunamadı")

            # Guvenlik: CV erisim kontrolu (2x3)
            if not validate_cv_access(cv_path, company_id):
                raise HTTPException(status_code=403, detail="CV erisim yetkisi yok")

            if not os.path.exists(cv_path):
                raise HTTPException(status_code=404, detail="CV dosyası fiziksel olarak bulunamadı")

            # ═══ DEFENSIVE DOCX→PDF DÖNÜŞÜM ═══
            # DB'de hala DOCX kalmışsa runtime'da çevir
            if cv_path.lower().endswith(('.docx', '.doc')):
                pdf_path = convert_to_pdf(cv_path)
                if pdf_path:
                    # DB'yi de güncelle (bir daha runtime dönüşüm olmasın)
                    try:
                        cursor.execute("UPDATE candidates SET cv_dosya_yolu = ? WHERE id = ?", (pdf_path, candidate_id))
                        conn.commit()
                    except Exception as db_err:
                        logging.error(f"CV path DB update failed: {db_err}")
                    cv_path = pdf_path
                    cv_filename = os.path.splitext(cv_filename)[0] + ".pdf"
                # Dönüşüm başarısız olsa bile devam et — DOCX olarak döndür
            # ═══ DEFENSIVE DÖNÜŞÜM SONU ═══

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
                    "Content-Disposition": get_safe_content_disposition(cv_filename, "inline")
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pool_id}/candidates/{candidate_id}/rescore")
def rescore_candidate(pool_id: int, candidate_id: int, current_user: dict = Depends(get_current_user)):
    """Tek aday için v2 skorunu yeniden hesapla"""
    from scoring_v2 import calculate_match_score_v2
    import json as json_lib
    
    try:
        company_id = current_user["company_id"]
        if not verify_department_pool_ownership(pool_id, company_id):
            raise HTTPException(status_code=403, detail="Erişim yetkiniz yok")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Eski skoru al
            cursor.execute("""
                SELECT match_score FROM candidate_positions 
                WHERE candidate_id = ? AND position_id = ?
            """, (candidate_id, pool_id))
            old_row = cursor.fetchone()
            old_score = old_row["match_score"] if old_row else 0
            
            # Aday bilgileri
            cursor.execute("""
                SELECT id, ad_soyad, teknik_beceriler, toplam_deneyim_yil,
                       egitim, lokasyon, cv_raw_text, deneyim_detay,
                       mevcut_pozisyon, mevcut_sirket
                FROM candidates WHERE id = ? AND company_id = ?
            """, (candidate_id, company_id))
            cand = cursor.fetchone()
            if not cand:
                raise HTTPException(status_code=404, detail="Aday bulunamadı")
            
            # Pozisyon bilgileri
            cursor.execute("""
                SELECT id, name, keywords, gerekli_deneyim_yil, gerekli_egitim, lokasyon
                FROM department_pools WHERE id = ? AND company_id = ? AND pool_type = 'position'
            """, (pool_id, company_id))
            pos = cursor.fetchone()
            if not pos:
                raise HTTPException(status_code=404, detail="Pozisyon bulunamadı")
            
            # Dict'leri oluştur
            candidate_dict = {
                'id': cand['id'],
                'ad_soyad': cand['ad_soyad'] or '',
                'teknik_beceriler': cand['teknik_beceriler'] or '',
                'toplam_deneyim_yil': cand['toplam_deneyim_yil'] or 0,
                'egitim': cand['egitim'] or '',
                'lokasyon': cand['lokasyon'] or '',
                'cv_raw_text': cand['cv_raw_text'] or '',
                'deneyim_detay': cand['deneyim_detay'] or '',
                'mevcut_pozisyon': cand['mevcut_pozisyon'] or '',
                'mevcut_sirket': cand['mevcut_sirket'] or ''
            }
            
            position_dict = {
                'id': pos['id'],
                'name': pos['name'] or '',
                'keywords': pos['keywords'] or '[]',
                'gerekli_deneyim_yil': pos['gerekli_deneyim_yil'] or 0,
                'gerekli_egitim': pos['gerekli_egitim'] or '',
                'lokasyon': pos['lokasyon'] or ''
            }
            
            # V2 skorlama
            v2_result = calculate_match_score_v2(candidate_dict, position_dict)
            
            if not v2_result:
                raise HTTPException(status_code=500, detail="Skorlama başarısız")
            
            new_score = v2_result.get('total', 0)
            
            # candidate_positions güncelle
            cursor.execute("""
                UPDATE candidate_positions SET match_score = ?
                WHERE candidate_id = ? AND position_id = ?
            """, (new_score, candidate_id, pool_id))
            
            # matches tablosunu güncelle
            cursor.execute("""
                INSERT OR REPLACE INTO matches (
                    candidate_id, position_id, uyum_puani, detayli_analiz,
                    deneyim_puani, egitim_puani, beceri_puani, company_id,
                    hesaplama_tarihi
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                candidate_id,
                pool_id,
                new_score,
                json_lib.dumps(v2_result, ensure_ascii=False),
                v2_result.get('experience_score', 0),
                v2_result.get('education_score', 0),
                v2_result.get('technical_score', 0),
                company_id
            ))
            
            # ai_evaluations.v2_score güncelle (varsa)
            cursor.execute("""
                UPDATE ai_evaluations SET v2_score = ?
                WHERE candidate_id = ? AND position_id = ?
            """, (new_score, candidate_id, pool_id))
            
            conn.commit()
            
            return {
                "success": True,
                "old_score": old_score,
                "new_score": new_score,
                "candidate_id": candidate_id,
                "position_id": pool_id,
                "v2_result": v2_result
            }
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# FAZ B: GÖREV TANIMI UPLOAD (06.03.2026)
# Mevcut pozisyona görev tanımı PDF/DOCX yükleyerek keyword zenginleştirme
# ═══════════════════════════════════════════════════════════════════════════════

def save_job_description_file(content: bytes, filename: str,
                               company_id: int, pool_id: int) -> str:
    """Görev tanımı dosyasını kaydet"""
    from config import JD_STORAGE_PATH
    import os

    jd_dir = JD_STORAGE_PATH / str(company_id)
    jd_dir.mkdir(parents=True, exist_ok=True)

    # Güvenlik: path traversal koruması
    safe_filename = os.path.basename(filename)
    file_path = jd_dir / f"{pool_id}_{safe_filename}"

    with open(file_path, 'wb') as f:
        f.write(content)

    return str(file_path)


def parse_job_description_with_ai(raw_text: str, pozisyon_adi: str,
                                   mevcut_keywords: list) -> dict:
    """Görev tanımı dökümanını AI ile parse et"""
    import anthropic
    import os
    import re

    client = anthropic.Anthropic(
        api_key=os.environ.get('ANTHROPIC_API_KEY'),
        timeout=60.0
    )

    mevcut_kw_str = ", ".join(mevcut_keywords) if mevcut_keywords else "Yok"

    prompt = f"""Bu doküman bir şirket içi görev tanımı belgesidir.
Formatı ne olursa olsun aşağıdaki bilgileri çıkar.
SADECE JSON döndür, başka hiçbir şey yazma.

Pozisyon Adı (referans): {pozisyon_adi}
Mevcut Keyword'ler (TEKRAR ÖNERME): {mevcut_kw_str}

Doküman:
{raw_text[:4000]}

JSON formatı:
{{
  "pozisyon_basligi": "Dokümandaki pozisyon başlığı",
  "genel_amac": "Görevin genel amacı/özeti (1-3 cümle)",
  "gorevler": [
    "Görev/sorumluluk maddesi 1",
    "Görev/sorumluluk maddesi 2"
  ],
  "gerekli_nitelikler": {{
    "egitim": "Gerekli eğitim seviyesi ve alan",
    "deneyim_yil": 0,
    "yoneticilik_yil": 0,
    "yabanci_dil": "Dil ve seviye",
    "araclar": ["Araç1", "Araç2", "Sertifika1"]
  }},
  "organizasyon": {{
    "ust_yonetici": "Bağlı olduğu pozisyon",
    "astlar": ["Ast pozisyon1"],
    "seviye": "Direktör/Müdür/Şef/Uzman/Mühendis/Tekniker"
  }},
  "ek_keywordler": {{
    "must_have": ["ZORUNLU araçlar/beceriler - yukarıdaki mevcut listede OLMAYAN"],
    "critical": ["Görevlerden çıkarılan teknik terimler - mevcut listede OLMAYAN"],
    "important": ["Önemli ama zorunlu olmayan - mevcut listede OLMAYAN"]
  }},
  "ek_titlelar": {{
    "exact": ["Pozisyon başlığının TR ve EN karşılıkları"],
    "close": ["Benzer pozisyon başlıkları (TR+EN, max 6)"]
  }}
}}

KURALLAR:
1. gorevler: "Kalite/Çevre/İSG uyum" ve "Yöneticisinin vereceği görevler" maddelerini ATLA
2. ek_keywordler: SADECE mevcut keyword listesinde OLMAYAN yeni keyword'ler
   Genel terimler KOYMA (yönetim, takip, kontrol, proje, iletişim gibi)
   Teknik araç, yazılım, sertifika, sektör terimleri KOY
3. gerekli_nitelikler.araclar: Yazılım ve araç adlarını çıkar (ERP, SAP, AutoCAD gibi)
4. deneyim_yil: Sayısal değer ("minimum 8 yıl" → 8, belirtilmemişse 0)
5. seviye: Ast varsa yönetici seviyesi, yoksa uzman/mühendis
6. Türkçe keyword varsa İngilizce karşılığını da ek_keywordler'e ekle
7. ek_titlelar.exact: Hem Türkçe hem İngilizce ZORUNLU
"""

    try:
        message = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)
        result = json.loads(response_text.strip())
        return result

    except Exception as e:
        print(f"[job-description] AI parse hatası: {e}")
        return None


def save_job_description_results(pool_id: int, company_id: int,
                                  parsed: dict, raw_text: str) -> int:
    """Görev tanımı parse sonuçlarını DB'ye kaydet (MERGE)"""

    ek_keyword_sayisi = 0

    # 1. department_pools güncelle
    gorevler = parsed.get("gorevler", [])
    is_tanimi_text = " | ".join(gorevler) if gorevler else ""

    nitelikler = parsed.get("gerekli_nitelikler", {})
    aranan_text = json.dumps(nitelikler, ensure_ascii=False) if nitelikler else ""

    update_department_pool(pool_id, company_id,
        aranan_nitelikler=aranan_text,
        is_tanimi=is_tanimi_text,
        gorev_tanimi_raw_text=raw_text
    )

    # 2. position_keywords_v2'ye MERGE (additive)
    ek_keywords = parsed.get("ek_keywordler", {})

    with get_connection() as conn:
        cursor = conn.cursor()

        for category, keyword_list in ek_keywords.items():
            if category not in ('must_have', 'critical', 'important'):
                continue

            # must_have → DB'de category='critical', priority='must_have'
            db_category = category
            db_priority = None
            if category == 'must_have':
                db_category = 'critical'
                db_priority = 'must_have'

            for keyword in (keyword_list or []):
                keyword = keyword.strip()
                if not keyword:
                    continue

                # Blacklist kontrolü
                if keyword.lower() in KEYWORD_BLACKLIST:
                    continue

                # Duplicate kontrolü (case-insensitive)
                cursor.execute("""
                    SELECT id FROM position_keywords_v2
                    WHERE position_id = ? AND LOWER(keyword) = LOWER(?)
                """, (pool_id, keyword))

                if cursor.fetchone():
                    continue  # Zaten var — atla

                # Yeni keyword ekle
                cursor.execute("""
                    INSERT INTO position_keywords_v2
                    (position_id, keyword, category, priority, source)
                    VALUES (?, ?, ?, ?, 'job_description')
                """, (pool_id, keyword, db_category, db_priority))
                ek_keyword_sayisi += 1

        conn.commit()

    # 3. Yeni title'lar PENDING olarak ekle
    ek_titlelar = parsed.get("ek_titlelar", {})

    with get_connection() as conn:
        cursor = conn.cursor()

        for match_level, title_list in ek_titlelar.items():
            if match_level not in ('exact', 'close'):
                continue

            for title in (title_list or []):
                title = title.strip()
                if not title:
                    continue

                # Duplicate kontrolü
                cursor.execute("""
                    SELECT id FROM position_title_mappings
                    WHERE position_id = ? AND LOWER(related_title) = LOWER(?)
                """, (pool_id, title))

                if cursor.fetchone():
                    continue

                # Pending olarak ekle
                cursor.execute("""
                    INSERT INTO position_title_mappings
                    (position_id, related_title, match_level, source, approved, created_at)
                    VALUES (?, ?, ?, 'job_description', 0, datetime('now'))
                """, (pool_id, title, match_level))

        conn.commit()

    return ek_keyword_sayisi


def rescore_position_candidates(pool_id: int, company_id: int) -> int:
    """Pozisyondaki mevcut adayları yeniden puanla (G8 benzeri)"""
    from scoring_v2 import calculate_match_score_v2
    import json as json_lib

    rescore_count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        # Pozisyon dict
        cursor.execute("""
            SELECT name, gerekli_deneyim_yil, gerekli_egitim, lokasyon
            FROM department_pools WHERE id = ?
        """, (pool_id,))
        pos = cursor.fetchone()
        if not pos:
            return 0

        cursor.execute("""
            SELECT keyword, category FROM position_keywords_v2
            WHERE position_id = ?
        """, (pool_id,))
        kws = cursor.fetchall()

        position_dict = {
            'id': pool_id,
            'baslik': pos[0],
            'name': pos[0],
            'gerekli_deneyim_yil': pos[1] or 0,
            'gerekli_egitim': pos[2] or '',
            'lokasyon': pos[3] or '',
            'keywords': {},
            'company_id': company_id
        }
        for kw, cat in kws:
            position_dict['keywords'].setdefault(cat, []).append(kw)

        # Mevcut adaylar
        cursor.execute("""
            SELECT candidate_id FROM candidate_positions
            WHERE position_id = ?
        """, (pool_id,))
        cids = [r[0] for r in cursor.fetchall()]

        for cid in cids:
            cursor.execute("""
                SELECT id, ad_soyad, teknik_beceriler, mevcut_pozisyon,
                       deneyim_detay, toplam_deneyim_yil, egitim, lokasyon,
                       mevcut_sirket, cv_raw_text, diller, sertifikalar,
                       deneyim_aciklama
                FROM candidates WHERE id = ?
            """, (cid,))
            r = cursor.fetchone()
            if not r:
                continue

            candidate_dict = {
                'id': r[0], 'ad_soyad': r[1],
                'teknik_beceriler': r[2] or '',
                'mevcut_pozisyon': r[3] or '',
                'deneyim_detay': r[4] or '',
                'toplam_deneyim_yil': r[5] or 0,
                'egitim': r[6] or '',
                'lokasyon': r[7] or '',
                'mevcut_sirket': r[8] or '',
                'cv_raw_text': r[9] or '',
                'diller': r[10] or '',
                'sertifikalar': r[11] or '',
                'deneyim_aciklama': r[12] or '',
                'company_id': company_id
            }

            v2_result = calculate_match_score_v2(candidate_dict, position_dict)
            if v2_result:
                new_score = v2_result.get('total', 0)
                cursor.execute("""
                    UPDATE matches SET uyum_puani = ?, detayli_analiz = ?
                    WHERE candidate_id = ? AND position_id = ?
                """, (new_score, json_lib.dumps(v2_result, ensure_ascii=False),
                      cid, pool_id))
                cursor.execute("""
                    UPDATE candidate_positions SET match_score = ?
                    WHERE candidate_id = ? AND position_id = ?
                """, (new_score, cid, pool_id))
                rescore_count += 1

        conn.commit()

    return rescore_count


@router.post("/{pool_id}/job-description")
async def upload_job_description(
    pool_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Mevcut pozisyona görev tanımı PDF/DOCX yükle.
    Görev tanımından ek keyword'ler çıkarır ve pozisyonu zenginleştirir."""

    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=403, detail="Firma bilgisi bulunamadı")

    # 1. Sahiplik kontrolü
    if not verify_department_pool_ownership(pool_id, company_id):
        raise HTTPException(status_code=403, detail="Bu pozisyona erişim yetkiniz yok")

    # 2. Dosya uzantı kontrolü
    from config import SUPPORTED_EXTENSIONS
    import os
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400,
            detail=f"Desteklenmeyen dosya formatı. Desteklenen: {', '.join(SUPPORTED_EXTENSIONS)}")

    # 3. Dosyayı oku
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş")

    # 4. Text çıkar (mevcut fonksiyon)
    from core.cv_parser import extract_text_from_file
    raw_text = extract_text_from_file(content, file.filename)

    if not raw_text or len(raw_text.strip()) < 50:
        raise HTTPException(status_code=400,
            detail="Görev tanımı metni çıkarılamadı veya çok kısa")

    # 5. Dosyayı kaydet
    file_path = save_job_description_file(content, file.filename,
                                           company_id, pool_id)

    # 6. Mevcut keyword'leri al (AI'a duplicate önleme için)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT keyword FROM position_keywords_v2
            WHERE position_id = ?
        """, (pool_id,))
        mevcut_keywords = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT name FROM department_pools WHERE id = ?", (pool_id,))
        pos_row = cursor.fetchone()
        pozisyon_adi = pos_row[0] if pos_row else ""

    # 7. AI ile görev tanımı parse
    parsed = parse_job_description_with_ai(raw_text, pozisyon_adi, mevcut_keywords)

    if not parsed:
        raise HTTPException(status_code=500,
            detail="Görev tanımı parse edilemedi")

    # 8. Sonuçları DB'ye kaydet
    ek_keyword_sayisi = save_job_description_results(
        pool_id, company_id, parsed, raw_text)

    # 9. Mevcut adayları rescore (arka planda)
    rescore_count = 0
    try:
        rescore_count = rescore_position_candidates(pool_id, company_id)
    except Exception as e:
        print(f"[job-description] Rescore hatası (devam ediliyor): {e}")

    return {
        "success": True,
        "pozisyon_basligi": parsed.get("pozisyon_basligi", ""),
        "gorev_sayisi": len(parsed.get("gorevler", [])),
        "ek_keyword_sayisi": ek_keyword_sayisi,
        "rescore_sayisi": rescore_count,
        "dosya_yolu": file_path
    }
