"""
FAZ 3 - Keyword İstatistikleri API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
import sys
sys.path.append("/var/www/hylilabs/api")

from core.keyword_stats import (
    get_keyword_overview,
    get_position_keyword_report,
    get_missing_skills_report,
    sync_keyword_usage,
)
from routes.auth import get_current_user

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("/overview")
async def keyword_overview(current_user: dict = Depends(get_current_user)):
    try:
        company_id = current_user["company_id"]
        data = get_keyword_overview(company_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/position-report")
async def position_keyword_report(
    position_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        company_id = current_user["company_id"]
        data = get_position_keyword_report(position_id, company_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/missing-skills")
async def missing_skills_report(current_user: dict = Depends(get_current_user)):
    try:
        company_id = current_user["company_id"]
        data = get_missing_skills_report(company_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_keywords(current_user: dict = Depends(get_current_user)):
    try:
        company_id = current_user["company_id"]
        result = sync_keyword_usage(company_id)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def list_positions(current_user: dict = Depends(get_current_user)):
    try:
        company_id = current_user["company_id"]
        from database import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name FROM department_pools WHERE company_id = ? AND pool_type = 'position' AND is_active = 1",
                (company_id,)
            )
            positions = cursor.fetchall()
        return {"success": True, "data": [{"id": r["id"], "title": r["name"]} for r in positions]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
