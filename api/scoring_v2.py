"""
TalentFlow Scoring V2 Modülü
Puanlama v2 için hesaplama fonksiyonları
"""

import json
import logging
import math
import os
import re
import time
from typing import Optional, Dict, List, Union
from database import get_connection
# from candidate_matcher import check_keyword_match  # lazy import - circular dependency

# Anthropic Claude API
try:
    import anthropic
except ImportError:
    anthropic = None

# Fuzzy matching için thefuzz
try:
    from thefuzz import fuzz
except ImportError:
    class FuzzFallback:
        @staticmethod
        def ratio(a, b): return 0
        @staticmethod
        def partial_ratio(a, b): return 0
    fuzz = FuzzFallback()

logger = logging.getLogger(__name__)


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri normalize et ve küçük harfe çevir"""
    if not text:
        return ""
    return text.replace('İ', 'i').replace('I', 'ı').lower()


# =====================================================
# FIX #2: Seniority (Kıdem Seviyesi) Tespiti
# =====================================================
SENIORITY_KEYWORDS = {
    'senior': 3, 'kıdemli': 3, 'uzman': 3, 'baş': 3, 'başmühendis': 3,
    'lead': 3, 'principal': 3, 'şef': 3, 'chef': 3, 'müdür': 3,
    'junior': 1, 'stajyer': 1, 'asistan': 1, 'yardımcı': 1,
    'intern': 1, 'trainee': 1, 'çırak': 1,
}

def detect_seniority(title: str) -> int:
    if not title:
        return 2
    title_lower = turkish_lower(title)
    for keyword, level in SENIORITY_KEYWORDS.items():
        if keyword in title_lower:
            return level
    return 2


# Komşu şehir mapping
NEIGHBOR_CITIES = {
    'istanbul': ['kocaeli', 'bursa', 'tekirdağ', 'yalova'],
    'ankara': ['eskişehir', 'konya', 'kırıkkale'],
    'izmir': ['manisa', 'aydın', 'balıkesir'],
    'bursa': ['istanbul', 'kocaeli', 'balıkesir', 'yalova'],
    'antalya': ['burdur', 'isparta', 'mersin'],
}


def safe_get(obj, key, default=None):
    """Dict veya object'ten güvenli değer al"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_v2_keywords(position_id: int) -> Dict[str, List[str]]:
    """
    position_keywords_v2 tablosundan kategorize keyword'leri çek
    
    Returns:
        {
            'critical': [...],
            'important': [...],
            'bonus': [...],
            'generic_ignore': [...],
            'must_have': [...]
        }
    """
    result = {
        'critical': [],
        'important': [],
        'bonus': [],
        'generic_ignore': [],
        'must_have': []
    }
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # priority sütunu varsa kullan, yoksa fallback
            try:
                cursor.execute("""
                    SELECT keyword, category, COALESCE(priority, 'normal') as priority
                    FROM position_keywords_v2
                    WHERE position_id = ?
                    ORDER BY category, keyword
                """, (position_id,))
            except Exception:
                # priority sütunu yok, fallback
                cursor.execute("""
                    SELECT keyword, category
                    FROM position_keywords_v2
                    WHERE position_id = ?
                    ORDER BY category, keyword
                """, (position_id,))
            
            rows = cursor.fetchall()
            for row in rows:
                keyword = row['keyword']
                category = row['category']
                # sqlite3.Row objesi dict gibi erişilebilir ama .get() yok
                try:
                    priority = row['priority']
                except (KeyError, IndexError):
                    priority = 'normal'
                
                if category in result:
                    result[category].append(keyword)
                
                # must_have: critical + priority == 'must_have'
                if category == 'critical' and priority == 'must_have':
                    result['must_have'].append(keyword)
        
        logger.debug(f"get_v2_keywords({position_id}): {len(result['critical'])} critical, "
                    f"{len(result['important'])} important, {len(result['must_have'])} must_have")
        
    except Exception as e:
        logger.error(f"get_v2_keywords({position_id}) hatası: {e}")
    
    return result


def get_title_mappings(position_id: int) -> Dict[str, List[str]]:
    """
    approved_title_mappings tablosundan ONAYLANMIŞ başlıkları çek
    
    Returns:
        {
            'exact': [...],
            'close': [...],
            'partial': [...]
        }
    """
    result = {
        'exact': [],
        'close': [],
        'partial': []
    }
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # approved_title_mappings tablosundan sadece onaylanmış başlıkları çek
            cursor.execute("""
                SELECT title, category
                FROM approved_title_mappings
                WHERE position_id = ? AND is_approved = 1
                ORDER BY 
                    CASE category
                        WHEN 'exact' THEN 1
                        WHEN 'close' THEN 2
                        WHEN 'partial' THEN 3
                        ELSE 4
                    END,
                    title
            """, (position_id,))
            
            rows = cursor.fetchall()
            for row in rows:
                title = row['title']
                category = row['category']
                # category -> match_level mapping
                if category == 'exact':
                    result['exact'].append(title)
                elif category == 'close':
                    result['close'].append(title)
                elif category == 'partial':
                    result['partial'].append(title)
        
        logger.debug(f"get_title_mappings({position_id}): {len(result['exact'])} exact, "
                    f"{len(result['close'])} close, {len(result['partial'])} partial")
        
    except Exception as e:
        logger.error(f"get_title_mappings({position_id}) hatası: {e}")
    
    return result


def get_sector_preferences(position_id: int) -> Dict[str, List[str]]:
    """
    position_sector_preferences tablosundan çek
    
    Returns:
        {
            'preferred': [...],
            'acceptable': [...],
            'irrelevant': [...]
        }
    """
    result = {
        'preferred': [],
        'acceptable': [],
        'irrelevant': []
    }
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sector_name, preference
                FROM position_sector_preferences
                WHERE position_id = ?
                ORDER BY preference, sector_name
            """, (position_id,))
            
            rows = cursor.fetchall()
            for row in rows:
                sector = row['sector_name']
                pref = row['preference']
                if pref in result:
                    result[pref].append(sector)
        
        logger.debug(f"get_sector_preferences({position_id}): {len(result['preferred'])} preferred, "
                    f"{len(result['acceptable'])} acceptable")
        
    except Exception as e:
        logger.error(f"get_sector_preferences({position_id}) hatası: {e}")
    
    return result


def calculate_position_match_score(
    candidate: Union[Dict, object],
    position: Union[Dict, object],
    title_mappings: Dict[str, List[str]],
    sector_preferences: Dict[str, List[str]]
) -> Dict:
    """
    KATMAN 1: Pozisyon Uyumu (33 puan)
    - Pozisyon başlığı: 23 puan
    - Sektör deneyimi: 10 puan
    """
    # Aday bilgilerini al
    current_pos = safe_get(candidate, 'mevcut_pozisyon', '') or ''
    experience_detail = safe_get(candidate, 'deneyim_detay', '') or ''
    current_company = safe_get(candidate, 'mevcut_sirket', '') or ''
    
    # Pozisyon başlığı eşleşmesi (23 puan)
    title_match_score = 0
    title_match_level = None
    matched_title = None
    
    # Adayın pozisyon başlıklarını bul
    candidate_titles = []
    if current_pos:
        candidate_titles.append(current_pos)
    
    # deneyim_detay'dan pozisyon başlıkları çıkar (basit regex)
    import re
    if experience_detail:
        # "Pozisyon: X" veya "X pozisyonunda" gibi pattern'ler
        pos_patterns = re.findall(r'(?:Pozisyon|Unvan|Görev)[:\s]+([^,\n]+)', experience_detail, re.IGNORECASE)
        candidate_titles.extend(pos_patterns)
    
    # title_mappings ile karşılaştır
    best_match_score = 0
    best_match_level = None
    best_matched_title = None
    
    for title in candidate_titles:
        title_normalized = turkish_lower(title.strip())
        if not title_normalized:
            continue
        
        # Exact match
        for exact_title in title_mappings.get('exact', []):
            if turkish_lower(exact_title) == title_normalized:
                if 23 > best_match_score:
                    best_match_score = 23
                    best_match_level = 'exact'
                    best_matched_title = exact_title
        
        # Close match (fuzzy >= 85)
        for close_title in title_mappings.get('close', []):
            ratio = fuzz.ratio(title_normalized, turkish_lower(close_title))
            if ratio >= 90:
                if 14 > best_match_score:
                    best_match_score = 14
                    best_match_level = 'close'
                    best_matched_title = close_title
        
        # Partial match (fuzzy >= 70)
        for partial_title in title_mappings.get('partial', []):
            ratio = fuzz.ratio(title_normalized, turkish_lower(partial_title))
            if ratio >= 90:
                if 7 > best_match_score:
                    best_match_score = 7
                    best_match_level = 'partial'
                    best_matched_title = partial_title
    
    title_match_score = best_match_score
    title_match_level = best_match_level or 'none'
    matched_title = best_matched_title or current_pos or 'Bulunamadı'
    
    # Seniority penaltısı
    pos_name = safe_get(position, 'pozisyon_adi', '') or safe_get(position, 'name', '') or ''
    pos_seniority = detect_seniority(pos_name)
    cand_seniority = detect_seniority(current_pos)
    
    seniority_penalty = 0
    seniority_detail = f"Pozisyon: {pos_seniority}, Aday: {cand_seniority}"
    
    if pos_seniority > cand_seniority:
        gap = pos_seniority - cand_seniority
        seniority_penalty = gap * 6
        seniority_detail += f" (Eksik kıdem: -{seniority_penalty} puan)"
    elif cand_seniority > pos_seniority:
        seniority_penalty = 2
        seniority_detail += f" (Fazla kıdem: -{seniority_penalty} puan)"
    else:
        seniority_detail += " (Eşit)"
    
    title_match_score = max(0, best_match_score - seniority_penalty)
    
    # Sektör deneyimi (10 puan)
    sector_score = 0
    detected_sector = None
    
    # Adayın sektör ipuçlarını bul
    search_text = turkish_lower(f"{current_company} {experience_detail}")
    
    for pref_level, sectors in sector_preferences.items():
        for sector in sectors:
            sector_normalized = turkish_lower(sector)
            if sector_normalized in search_text:
                if pref_level == 'preferred':
                    sector_score = 10
                    detected_sector = sector
                    break
                elif pref_level == 'acceptable' and sector_score < 5:
                    sector_score = 5
                    detected_sector = sector
    
    position_score = title_match_score + sector_score
    
    return {
        'position_score': int(position_score),
        'title_match_score': int(title_match_score),
        'title_match_level': title_match_level,
        'matched_title': matched_title,
        'sector_score': int(sector_score),
        'detected_sector': detected_sector or 'Bulunamadı',
        'seniority_penalty': int(seniority_penalty),
        'seniority_detail': seniority_detail
    }


def calculate_technical_score(
    candidate: Union[Dict, object],
    position: Union[Dict, object],
    v2_keywords: Dict[str, List[str]],
    company_id: int = None
) -> Dict:
    """
    KATMAN 2: Teknik Yetkinlik (47 puan)
    - Must-have keyword'ler: 20 puan (MOD A)
    - Critical keyword'ler: 35 puan (MOD B) veya 12 puan (MOD A)
    - Important keyword'ler: 12 puan
    """
    # Aday bilgilerini al
    # Lazy import to avoid circular dependency
    try:
        from candidate_matcher import check_keyword_match
    except ImportError:
        from core.candidate_matcher import check_keyword_match
    skills = safe_get(candidate, 'teknik_beceriler', '') or ''
    cv_text = safe_get(candidate, 'cv_raw_text', '') or ''
    experience_detail = safe_get(candidate, 'deneyim_detay', '') or ''
    
    # Search text oluştur
    search_text = turkish_lower(f"{skills} {cv_text} {experience_detail}")
    skills_original = skills
    
    # Must-have keyword'ler (MOD A: varsa)
    must_have_keywords = v2_keywords.get('must_have', [])
    must_have_matched = []
    must_have_missing = []
    must_have_score = 0
    
    if must_have_keywords:
        # MOD A: Must-have varsa
        for keyword in must_have_keywords:
            found, matched_via, method = check_keyword_match(
                keyword, search_text, skills_original, turkish_lower, company_id
            )
            if found:
                must_have_matched.append(keyword)
            else:
                must_have_missing.append(keyword)
        
        # Must-have: 20 puan (eksik başına -4 ekstra ceza)
        matched_ratio = len(must_have_matched) / len(must_have_keywords) if must_have_keywords else 0
        must_have_score = int(matched_ratio * 20)
        # Eksik başına -4 ekstra ceza
        missing_count = len(must_have_missing)
        must_have_score = max(0, must_have_score - (missing_count * 4))
    
    # Critical keyword'ler
    critical_keywords = v2_keywords.get('critical', [])
    critical_matched = []
    critical_missing = []
    
    if critical_keywords:
        for keyword in critical_keywords:
            found, matched_via, method = check_keyword_match(
                keyword, search_text, skills_original, turkish_lower, company_id
            )
            if found:
                critical_matched.append(keyword)
            else:
                critical_missing.append(keyword)
    
    # Critical score hesaplama
    if must_have_keywords:
        # MOD A: Must-have varsa → Critical 10 puan (lineer)
        if critical_keywords:
            critical_score = int((len(critical_matched) / len(critical_keywords)) * 12)
        else:
            critical_score = 0
    else:
        # MOD B: Must-have yoksa → Critical 27 puan (exponential)
        if critical_keywords:
            matched_ratio = len(critical_matched) / len(critical_keywords)
            critical_score = int((matched_ratio ** 1.5) * 35)
        else:
            critical_score = 0
    
    # Important keyword'ler (10 puan)
    important_keywords = v2_keywords.get('important', [])
    important_matched = []
    important_missing = []
    
    if important_keywords:
        for keyword in important_keywords:
            found, matched_via, method = check_keyword_match(
                keyword, search_text, skills_original, turkish_lower, company_id
            )
            if found:
                important_matched.append(keyword)
            else:
                important_missing.append(keyword)
        
        important_score = int((len(important_matched) / len(important_keywords)) * 12)
    else:
        important_score = 0
    
    # Bonus keyword'ler (sadece listele, puana dahil etme)
    bonus_keywords = v2_keywords.get('bonus', [])
    bonus_matched = []
    
    for keyword in bonus_keywords:
        found, matched_via, method = check_keyword_match(
            keyword, search_text, skills_original, turkish_lower, company_id
        )
        if found:
            bonus_matched.append(keyword)
    
    technical_score = must_have_score + critical_score + important_score
    
    return {
        'technical_score': int(technical_score),
        'must_have_score': int(must_have_score),
        'must_have_matched': must_have_matched,
        'must_have_missing': must_have_missing,
        'critical_score': int(critical_score),
        'critical_matched': critical_matched,
        'critical_missing': critical_missing,
        'important_score': int(important_score),
        'important_matched': important_matched,
        'important_missing': important_missing,
        'bonus_matched': bonus_matched
    }


def calculate_general_score(
    candidate: Union[Dict, object],
    position: Union[Dict, object]
) -> Dict:
    """
    KATMAN 3: Genel Kriterler (20 puan)
    - Deneyim yılı: 10 puan
    - Eğitim seviyesi: 10 puan
    """
    # Aday bilgileri
    cand_exp_years = safe_get(candidate, 'toplam_deneyim_yil', 0) or 0
    cand_education = safe_get(candidate, 'egitim', '') or ''
    
    # Pozisyon bilgileri
    pos_exp_years = safe_get(position, 'gerekli_deneyim_yil', 0) or 0
    pos_education = safe_get(position, 'gerekli_egitim', '') or ''
    
    # Deneyim puanı (10 puan)
    experience_score = 0
    knockout = False
    knockout_reason = None
    
    if pos_exp_years > 0:
        exp_ratio = cand_exp_years / pos_exp_years if pos_exp_years > 0 else 0
        
        if exp_ratio >= 1.0:
            experience_score = 10
        elif exp_ratio >= 0.80:
            experience_score = 8
        elif exp_ratio >= 0.60:
            experience_score = 5
        elif exp_ratio >= 0.50:
            experience_score = 2
        else:
            # KNOCKOUT (< 0.50)
            knockout = True
            knockout_reason = f"Deneyim çok düşük ({cand_exp_years} yıl < {pos_exp_years * 0.50:.1f} yıl)"
            experience_score = 0
    
    # Eğitim puanı (10 puan)
    education_levels = {
        'doktora': 5, 'phd': 5,
        'yüksek lisans': 4, 'master': 4, 'mba': 4,
        'lisans': 3, 'üniversite': 3, 'bachelor': 3,
        'ön lisans': 2, 'associate': 2,
        'lise': 1, 'high school': 1
    }
    
    cand_edu_level = 0
    pos_edu_level = 0
    
    cand_edu_lower = turkish_lower(cand_education)
    pos_edu_lower = turkish_lower(pos_education)
    
    # Adayın en yüksek eğitim seviyesini bul
    for edu, level in education_levels.items():
        if edu in cand_edu_lower:
            cand_edu_level = max(cand_edu_level, level)
        if edu in pos_edu_lower:
            pos_edu_level = max(pos_edu_level, level)
    
    education_score = 0
    if pos_edu_level > 0:
        if cand_edu_level >= pos_edu_level:
            education_score = 10
        elif cand_edu_level == pos_edu_level - 1:
            education_score = 7
        elif cand_edu_level == pos_edu_level - 2:
            education_score = 3
        else:
            education_score = 0
    
    general_score = experience_score + education_score
    
    return {
        'general_score': int(general_score),
        'experience_score': int(experience_score),
        'education_score': int(education_score),
        'knockout': knockout,
        'knockout_reason': knockout_reason
    }


def get_location_status(
    cand_location: str,
    pos_location: str
) -> Dict:
    """
    Lokasyon uyum durumunu görsel indicator için hesapla.
    PUAN VERMEZ - sadece görsel gösterim için status döndürür.
    
    Args:
        cand_location: Aday lokasyonu
        pos_location: Pozisyon lokasyonu
        
    Returns:
        {
            "status": "green" | "yellow" | "red",
            "candidate_location": str,
            "position_location": str,
            "match_type": "Aynı şehir" | "Komşu şehir (X)" | "Eşleşme yok"
        }
    """
    cand_loc = (cand_location or "").strip()
    pos_loc = (pos_location or "").strip()
    
    # Default: kırmızı (eşleşme yok)
    result = {
        "status": "red",
        "candidate_location": cand_loc or "-",
        "position_location": pos_loc or "-",
        "match_type": "Eşleşme yok"
    }
    
    # Her iki lokasyon da boşsa → kırmızı
    if not cand_loc or not pos_loc:
        return result
    
    cand_loc_normalized = turkish_lower(cand_loc)
    pos_loc_normalized = turkish_lower(pos_loc)
    
    # Aynı şehir → yeşil
    if cand_loc_normalized == pos_loc_normalized:
        result["status"] = "green"
        result["match_type"] = "Aynı şehir"
        return result
    
    # Komşu şehir kontrolü → sarı
    for city, neighbors in NEIGHBOR_CITIES.items():
        if city in pos_loc_normalized:
            for neighbor in neighbors:
                if neighbor in cand_loc_normalized:
                    result["status"] = "yellow"
                    result["match_type"] = f"Komşu şehir ({neighbor})"
                    return result
    
    # Eşleşme yok → kırmızı (default)
    return result


def calculate_elimination_score(
    candidate: Union[Dict, object],
    position: Union[Dict, object]
) -> Dict:
    """
    KATMAN 4: Eleme - DEVRE DIŞI (0 puan)
    Lokasyon artık PUAN VERMIYOR, sadece görsel indicator döndürüyor.
    
    NOT: Bu katman puanlamadan çıkarıldı. KATMAN 2 +10 puan aldı.
    Geriye uyumluluk için elimination_score = 0 döndürülüyor.
    """
    # Lokasyon bilgilerini al
    cand_location = safe_get(candidate, "lokasyon", "") or ""
    pos_location = safe_get(position, "lokasyon", "") or ""
    
    # Görsel indicator için location_status hesapla
    location_status = get_location_status(cand_location, pos_location)
    
    # PUAN YOK - hepsi 0 (geriye uyumluluk için alanlar korunuyor)
    return {
        "elimination_score": 0,
        "location_score": 0,
        "location_detail": location_status["match_type"],
        "requirements_score": 0,
        "location_status": location_status
    }


def calculate_match_score_v2(
    candidate: Union[Dict, object],
    position: Union[Dict, object]
) -> Optional[Dict]:
    """
    ANA FONKSİYON: Scoring V2 hesaplama
    
    Returns:
        Dict veya None (v2 verisi yoksa None döner, v1'e fallback yapılır)
    """
    # Position ID'yi al
    position_id = safe_get(position, 'id') or safe_get(position, 'position_id')
    if not position_id:
        logger.warning("calculate_match_score_v2: position_id bulunamadı")
        return None
    
    # V2 keyword'leri kontrol et
    v2_keywords = get_v2_keywords(position_id)
    
    # Eğer v2_keywords boşsa (critical, must_have ve important yoksa), None dön
    has_keywords = (v2_keywords.get('critical') or v2_keywords.get('must_have') or v2_keywords.get('important'))
    if not has_keywords:
        logger.debug(f"calculate_match_score_v2({position_id}): V2 verisi yok, None dönüyor")
        return None
    
    # Title mappings ve sector preferences
    title_mappings = get_title_mappings(position_id)
    sector_preferences = get_sector_preferences(position_id)
    
    # 4 katmanı hesapla
    position_result = calculate_position_match_score(
        candidate, position, title_mappings, sector_preferences
    )
    
    # Company ID'yi candidate'den al
    candidate_company_id = safe_get(candidate, 'company_id')
    
    technical_result = calculate_technical_score(
        candidate, position, v2_keywords, candidate_company_id
    )
    
    general_result = calculate_general_score(
        candidate, position
    )
    
    elimination_result = calculate_elimination_score(
        candidate, position
    )
    
    # Toplam puan
    total = (
        position_result['position_score'] +
        technical_result['technical_score'] +
        general_result['general_score'] +
        elimination_result['elimination_score']
    )
    
    # KNOCKOUT kontrolü
    knockout = general_result.get('knockout', False)
    if knockout:
        pass  # Puanı sıfırlama, knockout flag yeterli
    
    # Max 100 ile sınırla
    total = min(total, 100)
    
    # Sonuç dict'i oluştur
    result = {
        'total': int(total),
        'version': 'v2',
        'knockout': knockout,
        'knockout_reason': general_result.get('knockout_reason'),
        **position_result,
        **technical_result,
        **general_result,
        **elimination_result
    }
    
    logger.debug(f"calculate_match_score_v2({position_id}): total={total}, knockout={knockout}")
    
    return result


def categorize_position_with_ai(
    position_name: str,
    position_text: str,
    keywords_list: Optional[List[str]] = None,
    candidate_titles: Optional[List[str]] = None
) -> Optional[Dict]:
    """
    Claude AI ile pozisyon keyword'lerini kategorize et ve pozisyon eşleşmeleri al
    
    Args:
        position_name: Pozisyon adı
        position_text: İlan metni
        keywords_list: Mevcut keyword'ler (opsiyonel)
        
    Returns:
        Dict veya None (hata durumunda)
    """
    if not anthropic:
        logger.error("anthropic modülü bulunamadı")
        return None
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY bulunamadı")
        return None
    
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # Keywords listesini formatla
    keywords_str = ", ".join(keywords_list) if keywords_list else "Yok"
    candidate_titles_str = ", ".join(candidate_titles[:30]) if candidate_titles else "Yok"
    
    # Prompt oluştur
    prompt = f"""Aşağıdaki iş ilanını analiz et. SADECE JSON döndür, başka hiçbir şey yazma.

Pozisyon: {position_name}
İlan Metni: {position_text}
Mevcut Anahtar Kelimeler: {keywords_str}
Sistemdeki Mevcut Aday Pozisyonları: {candidate_titles_str}


ÖNEMLİ KURALLAR:
1. position_title_matches SADECE aynı işi farklı isimle yapan pozisyonları içermeli
2. "İnşaat Mühendisi", "Proje Mühendisi", "Saha Mühendisi" gibi genel başlıklar SADECE doğrudan ilgili pozisyonlara eklenebilir
3. Farklı uzmanlık alanlarını karıştırma. Örnek: Makine Şefi ≠ İnşaat Mühendisi, Maliyet Kontrol ≠ İnşaat Mühendisi
4. exact: SADECE birebir aynı iş (farklı dilde veya kısaltma)
5. close: SADECE aynı departmanda aynı seviyede çalışan, günlük işleri %80+ örtüşen pozisyonlar
6. partial: KULLANMA. Boş liste döndür. Kısmi eşleşmeler çok fazla yanlış pozitif üretiyor.
7. Her kategoride max 5 başlık
8. Yukarıda verilen "Mevcut Aday Pozisyonları" listesini mutlaka değerlendir. Bu başlıklardan pozisyonla ilgili olanları exact veya close kategorisine ekle.

Aşağıdaki JSON formatında yanıt ver:
{{
  "position_title_matches": {{
    "exact": ["Bu pozisyonla birebir aynı iş başlıkları, Türkçe ve İngilizce dahil. Max 5"],
    "close": ["Aynı departmanda aynı işi yapan, günlük görevleri %80+ örtüşen pozisyonlar. Max 5"],
    "partial": []
  }},
  "keywords": {{
    "must_have": ["OLMAZSA OLMAZ yazılım/araç/sertifika. Max 3. Teknik değilse boş liste."],
    "critical": ["OLMAZSA OLMAZ yetkinlikler (must_have'dekiler HARİÇ). CV'lerde sıkça geçen genel teknik terimler kullan, çok spesifik/niş terimler KULLANMA. Örnek: 'SAP' iyi, 'SAP MM modülü' çok spesifik. 'bakım' iyi, 'önleyici bakım planlaması' çok spesifik. Max 5-7 adet"],
    "important": ["Önemli ama zorunlu olmayan yetkinlikler"],
    "bonus": ["Olsa güzel olan ekstra yetkinlikler"],
    "generic_ignore": ["Her CVde geçen genel kelimeler: eğitim, yönetim, takip, kontrol, proje gibi"]
  }},
  "sectors": {{
    "preferred": ["Bu pozisyon için en uygun sektörler"],
    "acceptable": ["Kabul edilebilir sektörler"],
    "irrelevant": ["İlgisiz sektörler"]
  }}
}}"""
    
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
    
    # 3 kez deneme
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"categorize_position_with_ai: Deneme {attempt + 1}/{max_retries}")
            
            message = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Yanıtı al
            response_text = message.content[0].text
            
            # ```json varsa temizle
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            response_text = response_text.strip()
            
            # JSON parse et
            try:
                result = json.loads(response_text)
                logger.info(f"categorize_position_with_ai: Başarılı, {len(result.get('keywords', {}).get('critical', []))} critical keyword")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"categorize_position_with_ai: JSON parse hatası (deneme {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            logger.warning(f"categorize_position_with_ai: API timeout/connection hatası (deneme {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
        
        except anthropic.APIStatusError as e:
            logger.error(f"categorize_position_with_ai: API hatası (HTTP {e.status_code}): {e.message}")
            if e.status_code in (429, 500, 502, 503, 529) and attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
        
        except Exception as e:
            logger.error(f"categorize_position_with_ai: Beklenmeyen hata (deneme {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    
    logger.error("categorize_position_with_ai: Tüm denemeler başarısız")
    return None


def save_categorized_data(position_id: int, categorized_data: Dict) -> bool:
    """
    categorize_position_with_ai() sonucunu veritabanına kaydet
    
    Args:
        position_id: Pozisyon ID
        categorized_data: categorize_position_with_ai() sonucu
        
    Returns:
        bool: Başarılı ise True
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # a) position_keywords_v2 tablosuna keyword'leri kaydet
            keywords = categorized_data.get('keywords', {})
            for category, keyword_list in keywords.items():
                if category not in ['critical', 'important', 'bonus', 'generic_ignore', 'must_have']:
                    continue
                
                for keyword in keyword_list:
                    if not keyword or not isinstance(keyword, str):
                        continue
                    
                    keyword_normalized = keyword.strip()
                    if not keyword_normalized:
                        continue
                    
                    # must_have → db_category = 'critical', db_priority = 'must_have'
                    db_category = category
                    db_priority = None
                    if category == 'must_have':
                        db_category = 'critical'
                        db_priority = 'must_have'
                    
                    try:
                        # priority sütunu varsa kullan
                        try:
                            cursor.execute("""
                                INSERT OR REPLACE INTO position_keywords_v2 
                                (position_id, keyword, category, source, priority)
                                VALUES (?, ?, ?, 'ai_parsed', ?)
                            """, (position_id, keyword_normalized, db_category, db_priority))
                        except Exception:
                            # priority sütunu yok, fallback
                            cursor.execute("""
                                INSERT OR REPLACE INTO position_keywords_v2 
                                (position_id, keyword, category, source)
                                VALUES (?, ?, ?, 'ai_parsed')
                            """, (position_id, keyword_normalized, db_category))
                    except Exception as e:
                        logger.warning(f"save_categorized_data: Keyword kayıt hatası ({keyword}): {e}")
            
            # b) position_title_mappings tablosuna pozisyon eşleşmelerini kaydet
            title_matches = categorized_data.get('position_title_matches', {})
            for match_level, title_list in title_matches.items():
                if match_level not in ['exact', 'close', 'partial']:
                    continue
                
                for title in title_list:
                    if not title or not isinstance(title, str):
                        continue
                    
                    title_normalized = title.strip()
                    if not title_normalized:
                        continue
                    
                    try:
                        # position_title_mappings tablosuna ekle
                        cursor.execute("""
                            INSERT OR REPLACE INTO position_title_mappings 
                            (position_id, related_title, match_level, source, approved)
                            VALUES (?, ?, ?, 'ai_suggested', 0)
                        """, (position_id, title_normalized, match_level))
                        
                        # approved_title_mappings tablosuna da otomatik olarak is_approved=1 ile ekle
                        # match_level -> category mapping (aynı değerler: exact, close, partial)
                        cursor.execute("""
                            INSERT OR REPLACE INTO approved_title_mappings 
                            (position_id, title, category, is_approved, approved_at)
                            VALUES (?, ?, ?, 0, NULL)
                        """, (position_id, title_normalized, match_level))
                    except Exception as e:
                        logger.warning(f"save_categorized_data: Title mapping kayıt hatası ({title}): {e}")
            
            # c) position_sector_preferences tablosuna sektör tercihlerini kaydet
            sectors = categorized_data.get('sectors', {})
            for preference, sector_list in sectors.items():
                if preference not in ['preferred', 'acceptable', 'irrelevant']:
                    continue
                
                for sector in sector_list:
                    if not sector or not isinstance(sector, str):
                        continue
                    
                    sector_normalized = sector.strip()
                    if not sector_normalized:
                        continue
                    
                    try:
                        cursor.execute("""
                            INSERT OR REPLACE INTO position_sector_preferences 
                            (position_id, sector_name, preference)
                            VALUES (?, ?, ?)
                        """, (position_id, sector_normalized, preference))
                    except Exception as e:
                        logger.warning(f"save_categorized_data: Sector preference kayıt hatası ({sector}): {e}")
            
            logger.info(f"save_categorized_data({position_id}): Veriler başarıyla kaydedildi")
            return True
    
    except Exception as e:
        logger.error(f"save_categorized_data({position_id}) hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def categorize_and_save(
    position_id: int,
    position_name: str,
    position_text: str,
    keywords_list: Optional[List[str]] = None
) -> bool:
    """
    Wrapper fonksiyon: AI ile kategorize et ve veritabanına kaydet
    
    Args:
        position_id: Pozisyon ID
        position_name: Pozisyon adı
        position_text: İlan metni
        keywords_list: Mevcut keyword'ler (opsiyonel)
        
    Returns:
        bool: Başarılı ise True
    """
    logger.info(f"categorize_and_save({position_id}): Başlatılıyor...")
    
    # AI ile kategorize et
    # Mevcut adaylarin pozisyon basliklarini cek
    try:
        from database import get_connection
        with get_connection() as _conn:
            _cur = _conn.cursor()
            _cur.execute("SELECT DISTINCT mevcut_pozisyon FROM candidates WHERE mevcut_pozisyon IS NOT NULL AND mevcut_pozisyon != '' ORDER BY mevcut_pozisyon")
            _candidate_titles = [r["mevcut_pozisyon"] for r in _cur.fetchall()]
    except Exception as e:
        logger.warning(f"Aday pozisyonlari alinamadi: {e}")
        _candidate_titles = []

    result = categorize_position_with_ai(position_name, position_text, keywords_list, _candidate_titles)
    
    if result is None:
        logger.error(f"categorize_and_save({position_id}): AI kategorizasyon başarısız")
        return False
    
    # Veritabanına kaydet
    success = save_categorized_data(position_id, result)
    
    if success:
        logger.info(f"categorize_and_save({position_id}): Başarıyla tamamlandı")
    else:
        logger.error(f"categorize_and_save({position_id}): Veritabanı kaydı başarısız")
    
    return success
