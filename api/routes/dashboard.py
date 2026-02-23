from fastapi import APIRouter, Depends
import sys
sys.path.append("/var/www/hylilabs/api")
from database import (
    get_dashboard_stats,
    get_recent_applications,
    get_recent_evaluations,
    get_connection
)
from routes.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats")
def dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Dashboard istatistikleri"""
    company_id = current_user.get("company_id")
    stats = get_dashboard_stats(company_id)
    return stats

@router.get("/pool-distribution")
def pool_distribution(current_user: dict = Depends(get_current_user)):
    """Havuz dağılımı - aday durumlarına göre"""
    company_id = current_user.get("company_id")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Aday durumlarına göre dağılım
        if company_id:
            cursor.execute("""
                SELECT 
                    COALESCE(durum, 'beklemede') as durum,
                    COUNT(*) as count
                FROM candidates
                WHERE company_id = ?
                GROUP BY durum
            """, (company_id,))
        else:
            cursor.execute("""
                SELECT 
                    COALESCE(durum, 'beklemede') as durum,
                    COUNT(*) as count
                FROM candidates
                GROUP BY durum
            """)
        
        rows = cursor.fetchall()
        
        # Durum etiketleri
        labels = {
            "yeni": "Yeni",
            "beklemede": "Beklemede",
            "kisa_liste": "Kısa Liste",
            "mulakat": "Mülakat",
            "teklif": "Teklif",
            "ise_alindi": "İşe Alındı",
            "reddedildi": "Reddedildi",
            "arsiv": "Arşiv"
        }
        
        distribution = []
        for row in rows:
            durum = row["durum"] if row["durum"] else "beklemede"
            distribution.append({
                "durum": durum,
                "label": labels.get(durum, durum),
                "count": row["count"]
            })
        
        return {"distribution": distribution}

@router.get("/recent-activities")
def recent_activities(current_user: dict = Depends(get_current_user)):
    """Son aktiviteler - başvurular ve değerlendirmeler"""
    company_id = current_user.get("company_id")
    
    applications = get_recent_applications(company_id, limit=10)
    evaluations = get_recent_evaluations(company_id, limit=10)
    
    return {
        "recent_applications": applications,
        "recent_evaluations": evaluations
    }
