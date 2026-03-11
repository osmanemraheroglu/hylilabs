"""
V2 Veri Entegrasyonu - V3 AI için İK verilerini çeker

Bu modül, İK'nın girdiği verileri V3 AI değerlendirme sistemine aktarır:
- department_pools.keywords → Pozisyon anahtar kelimeleri
- keyword_synonyms → Onaylı eş anlamlılar
- approved_title_mappings → Onaylı pozisyon başlıkları

Kullanım:
    from api.core.scoring_v3.data_integration import (
        get_pool_keywords,
        get_approved_synonyms,
        get_approved_pool_titles,
        get_v2_data_for_prompt
    )

    # Tek fonksiyonla tüm veriyi al
    v2_data = get_v2_data_for_prompt(pool_id=123)
"""

import json
import sqlite3
import os
from typing import List, Dict, Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE BAĞLANTISI
# ═══════════════════════════════════════════════════════════════════════════════

def _get_db_path() -> str:
    """Veritabanı yolunu döndürür."""
    return os.environ.get(
        'DATABASE_PATH',
        '/var/www/hylilabs/api/data/talentflow.db'
    )


def _get_connection() -> sqlite3.Connection:
    """
    SQLite bağlantısı oluşturur.
    CLAUDE.md Kural 33: WAL mode, busy_timeout, foreign_keys zorunlu.
    """
    conn = sqlite3.connect(_get_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ═══════════════════════════════════════════════════════════════════════════════
# POOL KEYWORDS (department_pools.keywords)
# ═══════════════════════════════════════════════════════════════════════════════

def get_pool_keywords(pool_id: int) -> List[str]:
    """
    Pozisyona ait anahtar kelimeleri çeker.

    department_pools.keywords JSON kolonu parse edilir.

    Args:
        pool_id: department_pools.id

    Returns:
        ["forklift", "depo", "lojistik", ...]
        Boş veya NULL ise boş liste döner.
    """
    if not pool_id:
        return []

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT keywords
            FROM department_pools
            WHERE id = ?
        """, (pool_id,))

        row = cursor.fetchone()
        if not row or not row[0]:
            return []

        keywords_raw = row[0]

        # JSON parse et
        try:
            if isinstance(keywords_raw, str):
                # JSON string olabilir
                if keywords_raw.startswith('['):
                    keywords = json.loads(keywords_raw)
                    if isinstance(keywords, list):
                        # Nested list kontrolü
                        flat_keywords = []
                        for kw in keywords:
                            if isinstance(kw, list):
                                flat_keywords.extend(kw)
                            elif isinstance(kw, str):
                                flat_keywords.append(kw.strip())
                        return [k for k in flat_keywords if k]
                else:
                    # Virgülle ayrılmış string olabilir
                    return [k.strip() for k in keywords_raw.split(',') if k.strip()]
            elif isinstance(keywords_raw, list):
                return [str(k).strip() for k in keywords_raw if k]
        except (json.JSONDecodeError, TypeError):
            # Parse hatası - string olarak döndür
            return [k.strip() for k in keywords_raw.split(',') if k.strip()]

        return []

    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVED SYNONYMS (keyword_synonyms)
# ═══════════════════════════════════════════════════════════════════════════════

def get_approved_synonyms(pool_id: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Pool'a ait onaylı eş anlamlıları çeker.

    Önce pool'un company_id'sini alır, sonra:
    - Firma synonym'ları (company_id = pool_company_id)
    - Global synonym'lar (company_id IS NULL)

    Args:
        pool_id: department_pools.id

    Returns:
        {
            "forklift": [
                {"synonym": "fork lift", "weight": 0.9, "type": "exact_synonym"},
                {"synonym": "forklift operatörü", "weight": 0.85, "type": "turkish"}
            ],
            "depo": [
                {"synonym": "warehouse", "weight": 0.9, "type": "english"}
            ]
        }
    """
    if not pool_id:
        return {}

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # 1. Pool'un company_id'sini al
        cursor.execute("""
            SELECT company_id
            FROM department_pools
            WHERE id = ?
        """, (pool_id,))

        row = cursor.fetchone()
        if not row:
            return {}

        pool_company_id = row[0]

        # 2. Onaylı synonym'ları çek (firma + global)
        cursor.execute("""
            SELECT keyword, synonym, match_weight, synonym_type, confidence_score
            FROM keyword_synonyms
            WHERE (company_id = ? OR company_id IS NULL)
              AND status = 'approved'
            ORDER BY keyword, match_weight DESC
        """, (pool_company_id,))

        rows = cursor.fetchall()

        # 3. Keyword bazlı grupla
        synonyms_by_keyword: Dict[str, List[Dict[str, Any]]] = {}

        for row in rows:
            keyword = row[0].lower() if row[0] else ""
            synonym = row[1] if row[1] else ""
            weight = row[2] if row[2] else 0.85  # varsayılan weight
            synonym_type = row[3] if row[3] else "unknown"
            confidence = row[4] if row[4] else 0.58  # FAZ 10.1 varsayılan

            if not keyword or not synonym:
                continue

            if keyword not in synonyms_by_keyword:
                synonyms_by_keyword[keyword] = []

            synonyms_by_keyword[keyword].append({
                "synonym": synonym,
                "weight": weight,
                "type": synonym_type,
                "confidence": confidence
            })

        return synonyms_by_keyword

    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVED POOL TITLES (approved_title_mappings)
# ═══════════════════════════════════════════════════════════════════════════════

def get_approved_pool_titles(pool_id: int) -> Dict[str, List[str]]:
    """
    Pool'a ait onaylı pozisyon başlıklarını çeker.

    Args:
        pool_id: department_pools.id

    Returns:
        {
            "exact": ["Depo Şefi", "Warehouse Manager", "Depo Sorumlusu"],
            "related": ["Lojistik Uzmanı", "Sevkiyat Sorumlusu"]
        }
    """
    if not pool_id:
        return {"exact": [], "related": []}

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT title, category
            FROM approved_title_mappings
            WHERE position_id = ?
              AND is_approved = 1
            ORDER BY category, title
        """, (pool_id,))

        rows = cursor.fetchall()

        result = {
            "exact": [],
            "related": []
        }

        for row in rows:
            title = row[0] if row[0] else ""
            category = row[1].lower() if row[1] else "related"

            if not title:
                continue

            if category == "exact":
                result["exact"].append(title)
            else:
                result["related"].append(title)

        return result

    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# BİRLEŞİK VERİ FONKSİYONU (CONVENIENCE)
# ═══════════════════════════════════════════════════════════════════════════════

def get_v2_data_for_prompt(pool_id: int) -> Dict[str, Any]:
    """
    V3 prompt'u için tüm V2 verilerini tek seferde çeker.

    Args:
        pool_id: department_pools.id

    Returns:
        {
            "keywords": ["forklift", "depo", "lojistik"],
            "synonyms": {
                "forklift": [{"synonym": "fork lift", "weight": 0.9, "type": "exact_synonym"}]
            },
            "titles": {
                "exact": ["Depo Şefi"],
                "related": ["Lojistik Uzmanı"]
            },
            "stats": {
                "keyword_count": 3,
                "synonym_count": 5,
                "exact_title_count": 1,
                "related_title_count": 1
            }
        }
    """
    keywords = get_pool_keywords(pool_id)
    synonyms = get_approved_synonyms(pool_id)
    titles = get_approved_pool_titles(pool_id)

    # Sadece keyword'lerle eşleşen synonym'ları filtrele
    filtered_synonyms = {}
    keywords_lower = [k.lower() for k in keywords]

    for keyword, synonym_list in synonyms.items():
        if keyword in keywords_lower:
            filtered_synonyms[keyword] = synonym_list

    # Toplam synonym sayısı
    total_synonyms = sum(len(v) for v in filtered_synonyms.values())

    return {
        "keywords": keywords,
        "synonyms": filtered_synonyms,
        "titles": titles,
        "stats": {
            "keyword_count": len(keywords),
            "synonym_count": total_synonyms,
            "exact_title_count": len(titles.get("exact", [])),
            "related_title_count": len(titles.get("related", []))
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("data_integration.py Test")
    print("=" * 60)

    # Test için bir pool_id kullan
    test_pool_id = 1  # Varsayılan test ID

    print(f"\nTest pool_id: {test_pool_id}")
    print("-" * 60)

    # Keywords
    keywords = get_pool_keywords(test_pool_id)
    print(f"\n1. Keywords ({len(keywords)}):")
    for kw in keywords[:10]:
        print(f"   - {kw}")
    if len(keywords) > 10:
        print(f"   ... ve {len(keywords) - 10} tane daha")

    # Synonyms
    synonyms = get_approved_synonyms(test_pool_id)
    print(f"\n2. Synonyms ({len(synonyms)} keyword):")
    for kw, syns in list(synonyms.items())[:5]:
        print(f"   {kw}: {[s['synonym'] for s in syns[:3]]}")

    # Titles
    titles = get_approved_pool_titles(test_pool_id)
    print(f"\n3. Titles:")
    print(f"   Exact ({len(titles['exact'])}): {titles['exact'][:5]}")
    print(f"   Related ({len(titles['related'])}): {titles['related'][:5]}")

    # Combined
    v2_data = get_v2_data_for_prompt(test_pool_id)
    print(f"\n4. Combined Stats:")
    print(f"   {v2_data['stats']}")

    print("\n" + "=" * 60)
    print("TEST TAMAMLANDI")
    print("=" * 60)
