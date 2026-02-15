"""
TalentFlow Keyword İstatistik Modülü
Mevcut keyword eşleştirme verilerini okuyarak istatistik ve rapor üretir.
Bu modül READ-ONLY çalışır (sadece keyword_dictionary.usage_count güncellenir).
candidate_matcher.py'a DOKUNMAZ.
"""

import json
import logging
from typing import Dict, List, Optional
from database import get_connection

logger = logging.getLogger(__name__)


def sync_keyword_usage(company_id: int) -> dict:
    """
    Pozisyonlardaki keyword'leri okuyup keyword_dictionary.usage_count'u günceller.
    
    Args:
        company_id: Firma ID
        
    Returns:
        {
            'total_positions': int,
            'total_unique_keywords': int,
            'new_keywords_added': int,
            'usage_counts_updated': int
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Önce tüm usage_count'ları sıfırla (tutarlılık için)
        cursor.execute("UPDATE keyword_dictionary SET usage_count = 0")
        
        # Pozisyonları getir (pool_type='position')
        cursor.execute("""
            SELECT id, name, keywords
            FROM department_pools
            WHERE company_id = ? 
                AND pool_type = 'position'
                AND is_active = 1
        """, (company_id,))
        
        positions = cursor.fetchall()
        total_positions = len(positions)
        
        # Keyword sayacı
        keyword_counts = {}
        new_keywords_added = 0
        
        for pos in positions:
            pos_id = pos['id']
            pos_name = pos['name']
            keywords_json = pos['keywords']
            
            if not keywords_json:
                continue
            
            # JSON parse et
            try:
                if isinstance(keywords_json, str):
                    keywords = json.loads(keywords_json)
                elif isinstance(keywords_json, list):
                    keywords = keywords_json
                else:
                    keywords = []
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Pozisyon {pos_id} ({pos_name}) keywords parse edilemedi: {keywords_json}")
                continue
            
            # Her keyword için sayacı artır
            for kw in keywords:
                if not kw or not isinstance(kw, str):
                    continue
                
                kw_normalized = kw.lower().strip()
                if not kw_normalized:
                    continue
                
                keyword_counts[kw_normalized] = keyword_counts.get(kw_normalized, 0) + 1
        
        # keyword_dictionary'yi güncelle
        usage_counts_updated = 0
        for keyword, count in keyword_counts.items():
            # Keyword var mı kontrol et
            cursor.execute("SELECT id FROM keyword_dictionary WHERE keyword = ?", (keyword,))
            existing = cursor.fetchone()
            
            if existing:
                # Güncelle
                cursor.execute("""
                    UPDATE keyword_dictionary 
                    SET usage_count = ? 
                    WHERE keyword = ?
                """, (count, keyword))
                usage_counts_updated += 1
            else:
                # Yeni ekle
                cursor.execute("""
                    INSERT INTO keyword_dictionary (keyword, category, source, usage_count)
                    VALUES (?, 'genel', 'position', ?)
                """, (keyword, count))
                new_keywords_added += 1
        
        return {
            'total_positions': total_positions,
            'total_unique_keywords': len(keyword_counts),
            'new_keywords_added': new_keywords_added,
            'usage_counts_updated': usage_counts_updated
        }


def get_keyword_overview(company_id: int) -> dict:
    """
    Genel keyword istatistiklerini döner.
    
    Returns:
        {
            'total_keywords_in_use': int,
            'total_keywords_in_dictionary': int,
            'top_keywords': List[dict],
            'category_distribution': dict,
            'keywords_by_position': dict
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Dictionary'deki toplam keyword sayısı
        cursor.execute("SELECT COUNT(*) FROM keyword_dictionary")
        total_keywords_in_dictionary = cursor.fetchone()[0]
        
        # Kullanılan keyword'ler (usage_count > 0)
        cursor.execute("""
            SELECT keyword, category, usage_count
            FROM keyword_dictionary
            WHERE usage_count > 0
            ORDER BY usage_count DESC
        """)
        used_keywords = cursor.fetchall()
        
        total_keywords_in_use = len(used_keywords)
        
        # En çok kullanılan keyword'ler (top 20)
        top_keywords = [
            {
                'keyword': row['keyword'],
                'usage_count': row['usage_count'],
                'category': row['category']
            }
            for row in used_keywords[:20]
        ]
        
        # Kategori dağılımı
        cursor.execute("""
            SELECT category, SUM(usage_count) as total_usage
            FROM keyword_dictionary
            WHERE usage_count > 0
            GROUP BY category
            ORDER BY total_usage DESC
        """)
        category_rows = cursor.fetchall()
        category_distribution = {
            row['category']: row['total_usage']
            for row in category_rows
        }
        
        # Pozisyon bazında keyword sayıları
        cursor.execute("""
            SELECT dp.name, COUNT(DISTINCT json_each.value) as keyword_count
            FROM department_pools dp,
                 json_each(dp.keywords) json_each
            WHERE dp.company_id = ?
                AND dp.pool_type = 'position'
                AND dp.is_active = 1
            GROUP BY dp.id, dp.name
            ORDER BY keyword_count DESC
        """, (company_id,))
        
        position_rows = cursor.fetchall()
        keywords_by_position = {
            row['name']: row['keyword_count']
            for row in position_rows
        }
        
        return {
            'total_keywords_in_use': total_keywords_in_use,
            'total_keywords_in_dictionary': total_keywords_in_dictionary,
            'top_keywords': top_keywords,
            'category_distribution': category_distribution,
            'keywords_by_position': keywords_by_position
        }


def get_position_keyword_report(position_id: int, company_id: int) -> dict:
    """
    Belirli bir pozisyon için keyword eşleşme raporu.
    
    Args:
        position_id: Pozisyon ID
        company_id: Firma ID
        
    Returns:
        {
            'position_name': str,
            'total_keywords': int,
            'total_candidates': int,
            'keyword_match_rates': List[dict],
            'hardest_keywords': List[dict],
            'easiest_keywords': List[dict]
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Pozisyon bilgilerini al
        cursor.execute("""
            SELECT name, keywords
            FROM department_pools
            WHERE id = ? AND company_id = ? AND pool_type = 'position'
        """, (position_id, company_id))
        
        pos_row = cursor.fetchone()
        if not pos_row:
            return {
                'position_name': 'Bilinmeyen Pozisyon',
                'total_keywords': 0,
                'total_candidates': 0,
                'keyword_match_rates': [],
                'hardest_keywords': [],
                'easiest_keywords': []
            }
        
        position_name = pos_row['name']
        keywords_json = pos_row['keywords']
        
        # Keywords parse et
        try:
            if isinstance(keywords_json, str):
                keywords = json.loads(keywords_json)
            elif isinstance(keywords_json, list):
                keywords = keywords_json
            else:
                keywords = []
        except (json.JSONDecodeError, TypeError):
            keywords = []
        
        total_keywords = len(keywords)
        
        # Bu pozisyondaki adayları al
        cursor.execute("""
            SELECT DISTINCT candidate_id
            FROM candidate_positions
            WHERE position_id = ?
        """, (position_id,))
        
        candidate_ids = [row['candidate_id'] for row in cursor.fetchall()]
        total_candidates = len(candidate_ids)
        
        if total_candidates == 0:
            return {
                'position_name': position_name,
                'total_keywords': total_keywords,
                'total_candidates': 0,
                'keyword_match_rates': [],
                'hardest_keywords': [],
                'easiest_keywords': []
            }
        
        # Her keyword için eşleşme oranını hesapla
        keyword_match_rates = []
        
        for keyword in keywords:
            if not keyword or not isinstance(keyword, str):
                continue
            
            kw_normalized = keyword.lower().strip()
            matched_count = 0
            
            # matches tablosundan detaylı analiz oku
            for cand_id in candidate_ids:
                cursor.execute("""
                    SELECT detayli_analiz
                    FROM matches
                    WHERE candidate_id = ? AND position_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (cand_id, position_id))
                
                match_row = cursor.fetchone()
                if not match_row or not match_row['detayli_analiz']:
                    continue
                
                try:
                    analiz = json.loads(match_row['detayli_analiz'])
                    if isinstance(analiz, dict):
                        keyword_details = analiz.get('keyword_details', [])
                        for kw_detail in keyword_details:
                            if kw_detail.get('keyword', '').lower() == kw_normalized:
                                if kw_detail.get('matched', False):
                                    matched_count += 1
                                    break
                except (json.JSONDecodeError, TypeError):
                    continue
            
            match_rate = (matched_count / total_candidates * 100) if total_candidates > 0 else 0.0
            
            keyword_match_rates.append({
                'keyword': keyword,
                'matched_count': matched_count,
                'total_candidates': total_candidates,
                'match_rate': round(match_rate, 1)
            })
        
        # En zor ve en kolay keyword'ler
        sorted_rates = sorted(keyword_match_rates, key=lambda x: x['match_rate'])
        hardest_keywords = sorted_rates[:5]
        easiest_keywords = sorted_rates[-5:][::-1]  # En yüksekten en düşüğe
        
        return {
            'position_name': position_name,
            'total_keywords': total_keywords,
            'total_candidates': total_candidates,
            'keyword_match_rates': keyword_match_rates,
            'hardest_keywords': hardest_keywords,
            'easiest_keywords': easiest_keywords
        }


def get_missing_skills_report(company_id: int) -> dict:
    """
    Tüm pozisyonlar için "en zor bulunan beceriler" raporu.
    
    Returns:
        {
            'hardest_to_find': List[dict],
            'well_covered': List[dict]
        }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tüm pozisyonları al
        cursor.execute("""
            SELECT id, name, keywords
            FROM department_pools
            WHERE company_id = ?
                AND pool_type = 'position'
                AND is_active = 1
        """, (company_id,))
        
        positions = cursor.fetchall()
        
        # Keyword bazında toplama
        keyword_stats = {}  # {keyword: {'positions_requiring': int, 'candidates_having': int}}
        
        for pos in positions:
            pos_id = pos['id']
            keywords_json = pos['keywords']
            
            # Keywords parse et
            try:
                if isinstance(keywords_json, str):
                    keywords = json.loads(keywords_json)
                elif isinstance(keywords_json, list):
                    keywords = keywords_json
                else:
                    keywords = []
            except (json.JSONDecodeError, TypeError):
                continue
            
            # Bu pozisyondaki adayları al
            cursor.execute("""
                SELECT DISTINCT candidate_id
                FROM candidate_positions
                WHERE position_id = ?
            """, (pos_id,))
            
            candidate_ids = [row['candidate_id'] for row in cursor.fetchall()]
            
            for keyword in keywords:
                if not keyword or not isinstance(keyword, str):
                    continue
                
                kw_normalized = keyword.lower().strip()
                if not kw_normalized:
                    continue
                
                if kw_normalized not in keyword_stats:
                    keyword_stats[kw_normalized] = {
                        'positions_requiring': 0,
                        'candidates_having': 0
                    }
                
                keyword_stats[kw_normalized]['positions_requiring'] += 1
                
                # Bu pozisyondaki adaylarda bu keyword var mı?
                for cand_id in candidate_ids:
                    cursor.execute("""
                        SELECT detayli_analiz
                        FROM matches
                        WHERE candidate_id = ? AND position_id = ?
                        ORDER BY id DESC
                        LIMIT 1
                    """, (cand_id, pos_id))
                    
                    match_row = cursor.fetchone()
                    if not match_row or not match_row['detayli_analiz']:
                        continue
                    
                    try:
                        analiz = json.loads(match_row['detayli_analiz'])
                        if isinstance(analiz, dict):
                            keyword_details = analiz.get('keyword_details', [])
                            for kw_detail in keyword_details:
                                if kw_detail.get('keyword', '').lower() == kw_normalized:
                                    if kw_detail.get('matched', False):
                                        keyword_stats[kw_normalized]['candidates_having'] += 1
                                        break
                    except (json.JSONDecodeError, TypeError):
                        continue
        
        # En zor bulunanlar (positions_requiring > 0 ama candidates_having = 0 veya çok az)
        hardest_to_find = []
        well_covered = []
        
        for keyword, stats in keyword_stats.items():
            pos_req = stats['positions_requiring']
            cand_have = stats['candidates_having']
            
            if pos_req > 0:
                if cand_have == 0:
                    gap = 'Hiç aday yok'
                elif cand_have < pos_req * 0.3:
                    gap = 'Ciddi eksik'
                elif cand_have < pos_req * 0.7:
                    gap = 'Orta eksik'
                else:
                    gap = None
                
                if gap:
                    hardest_to_find.append({
                        'keyword': keyword,
                        'positions_requiring': pos_req,
                        'candidates_having': cand_have,
                        'gap': gap
                    })
                else:
                    well_covered.append({
                        'keyword': keyword,
                        'positions_requiring': pos_req,
                        'candidates_having': cand_have,
                        'coverage': 'İyi'
                    })
        
        # Sırala
        hardest_to_find.sort(key=lambda x: (x['positions_requiring'], -x['candidates_having']), reverse=True)
        well_covered.sort(key=lambda x: x['candidates_having'], reverse=True)
        
        return {
            'hardest_to_find': hardest_to_find[:20],  # Top 20
            'well_covered': well_covered[:20]  # Top 20
        }
