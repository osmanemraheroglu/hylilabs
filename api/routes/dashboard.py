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



@router.get("/candidate-distribution")
def candidate_distribution(current_user: dict = Depends(get_current_user)):
    """CV Intelligence analizine gore aday dagilimi - TOP 5 + Diger"""
    company_id = current_user.get("company_id")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # candidate_intelligence tablosundan suitable_positions al
        if company_id:
            cursor.execute("""
                SELECT ci.suitable_positions
                FROM candidate_intelligence ci
                JOIN candidates c ON ci.candidate_id = c.id
                WHERE c.company_id = ? AND ci.suitable_positions IS NOT NULL AND ci.suitable_positions != ""
            """, (company_id,))
        else:
            cursor.execute("""
                SELECT suitable_positions
                FROM candidate_intelligence
                WHERE suitable_positions IS NOT NULL AND suitable_positions != ""
            """)
        
        rows = cursor.fetchall()
        
        # Her adayin birincil pozisyonunu al (ilk eleman = en uygun)
        from collections import Counter
        primary_positions = []
        
        for row in rows:
            try:
                positions_str = row["suitable_positions"] if isinstance(row, dict) else row[0]
                if positions_str:
                    # Python list literal olarak parse et
                    if positions_str.startswith("["):
                        positions = eval(positions_str)
                    else:
                        positions = [positions_str]
                    
                    if isinstance(positions, list) and len(positions) > 0:
                        primary_positions.append(positions[0])
            except:
                pass
        
        total_candidates = len(primary_positions)
        
        if total_candidates == 0:
            return {
                "total_candidates": 0,
                "distribution": []
            }
        
        # Pozisyon sayilarini hesapla
        position_counts = Counter(primary_positions)
        
        # TOP 5 al
        top5 = position_counts.most_common(5)
        top5_total = sum(c for _, c in top5)
        others_total = total_candidates - top5_total
        
        # Distribution listesi olustur
        distribution = []
        for position, count in top5:
            percentage = round((count / total_candidates) * 100, 1)
            distribution.append({
                "position": position,
                "count": count,
                "percentage": percentage
            })
        
        # Diger kategorisi ekle
        if others_total > 0:
            others_percentage = round((others_total / total_candidates) * 100, 1)
            distribution.append({
                "position": "Diger",
                "count": others_total,
                "percentage": others_percentage
            })
        
        return {
            "total_candidates": total_candidates,
            "distribution": distribution
        }
