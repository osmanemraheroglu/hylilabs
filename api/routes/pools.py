from fastapi import APIRouter, Depends, HTTPException, Query
from routes.auth import get_current_user
from database import (
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
