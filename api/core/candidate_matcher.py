"""
TalentFlow Aday Eslestirme
Pozisyon kriterleriyle aday profilini karsilastirma ve puanlama
"""

import json
import re
import logging
import time
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

import anthropic

logger = logging.getLogger(__name__)

# Fuzzy matching için thefuzz kütüphanesi
try:
    from thefuzz import fuzz
except ImportError:
    # Fallback: fuzzy matching olmadan çalış
    class FuzzFallback:
        @staticmethod
        def ratio(a, b): return 0
        @staticmethod
        def partial_ratio(a, b): return 0
    fuzz = FuzzFallback()

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from models import Candidate, Position, Match
from database import (
    save_match, update_candidate, get_position_criteria,
    add_candidate_to_pool, update_pool_candidate, get_position_pool,
    log_api_usage
)
from scoring_v2 import calculate_match_score_v2

# ========== PUANLAMA SABİTLERİ ==========
# Hardcoded değerleri kaldırmak için sabitler
KEYWORD_WEIGHT = 40
EXPERIENCE_WEIGHT = 25
EDUCATION_WEIGHT = 20
LOCATION_WEIGHT = 15

# Fallback skorlama sabitleri
DEFAULT_BASE_SCORE = 50
EXPERIENCE_MULTIPLIER = 0.7
EXPERIENCE_HALF_MULTIPLIER = 0.5
MAX_KEYWORD_BONUS = 20
KEYWORD_POINTS_PER_MATCH = 5
EXPERIENCE_FULL_BONUS = 20
EXPERIENCE_PARTIAL_BONUS = 10


# Match Status Enum
class MatchStatus(Enum):
    FULL_MATCH = "full_match"      # 80+ puan
    PARTIAL_MATCH = "partial_match"  # 50-79 puan
    MISMATCH = "mismatch"          # 0-49 puan
    KNOCKOUT = "knockout"          # Zorunlu kriter karsilanmadi


# Katman 2: Yaygın kısaltma/synonym sözlüğü
KEYWORD_SYNONYMS = {
    # Office & Microsoft
    'ms office': ['microsoft office', 'ms office', 'office'],
    'microsoft office': ['ms office', 'microsoft office', 'office'],
    'excel': ['excel', 'microsoft excel', 'ms excel', 'microsoft office excel'],
    'word': ['microsoft word', 'ms word'],
    'powerpoint': ['powerpoint', 'ppt', 'microsoft powerpoint'],
    
    # Programlama
    'js': ['javascript', 'js'],
    'javascript': ['javascript', 'js'],
    'ts': ['typescript', 'ts'],
    'typescript': ['typescript', 'ts'],
    'react': ['react', 'reactjs', 'react.js'],
    'node': ['node', 'nodejs', 'node.js'],
    'python': ['python', 'py'],
    'c#': ['c#', 'csharp', 'c sharp'],
    '.net': ['.net', 'dotnet', 'dot net'],
    
    # Veritabanı
    'sql': ['sql', 'mysql', 'postgresql', 'mssql', 'sqlite', 'tsql'],
    'nosql': ['nosql', 'mongodb', 'redis', 'cassandra'],
    
    # Cloud & DevOps
    'aws': ['aws', 'amazon web services'],
    'gcp': ['gcp', 'google cloud', 'google cloud platform'],
    'azure': ['azure', 'microsoft azure'],
    'ci/cd': ['ci/cd', 'cicd', 'jenkins', 'github actions', 'gitlab ci'],
    'docker': ['docker', 'container', 'konteyner'],
    'kubernetes': ['kubernetes', 'k8s'],
    
    # İK & İş
    'ik': ['ik', 'insan kaynakları', 'human resources', 'hr', 'i.k.'],
    'erp': ['erp', 'sap', 'sap erp', 'oracle erp', 'microsoft dynamics', 'kurumsal kaynak planlama', 'enterprise resource planning'],
    'sap': ['sap', 'sap erp', 'sap r/3', 'sap hana'],
    'crm': ['crm', 'müşteri ilişkileri', 'customer relationship'],
    
    # Finans & Muhasebe
    'muhasebe': ['muhasebe', 'accounting', 'mali müşavir', 'muhasebecilik'],
    'ufrs': ['ufrs', 'ifrs', 'uluslararası finansal raporlama'],
    'bütçe': ['bütçe', 'budget', 'bütçeleme'],
    'denetim': ['denetim', 'audit', 'iç denetim', 'dış denetim'],
    'finans': ['finans', 'finance', 'finansal'],
    
    # Mühendislik
    'autocad': ['autocad', 'auto cad', 'cad'],
    'solidworks': ['solidworks', 'solid works'],
    'revit': ['revit', 'autodesk revit'],
    
    # AI & Data
    'ai': ['ai', 'yapay zeka', 'artificial intelligence'],
    'ml': ['ml', 'machine learning', 'makine öğrenmesi', 'makine öğrenimi'],
    'veri analizi': ['veri analizi', 'data analysis', 'veri analitiği'],
    
    # Genel
    'ms project': ['ms project', 'microsoft project', 'project'],
    'scrum': ['scrum', 'agile', 'çevik'],
    'proje yönetimi': ['proje yönetimi', 'project management', 'pm'],
}

# Katman 3: Fuzzy matching eşik değeri
try:
    from config import FUZZY_MATCH_THRESHOLD
except ImportError:
    # Fallback: config.py'de yoksa default değer
    FUZZY_MATCH_THRESHOLD = 80


def check_keyword_match(keyword, search_text, skills_text, turkish_lower_func):
    """3 katmanlı keyword eşleştirme
    
    Katman 1: Birebir substring eşleşme (word boundary ile)
    Katman 2: Synonym sözlüğünden eşleşme  
    Katman 3: Fuzzy matching (benzerlik oranı)
    
    Args:
        keyword: Aranan keyword
        search_text: Tüm aday metni (cv + beceriler + deneyim) - turkish_lower uygulanmış
        skills_text: Sadece teknik beceriler listesi (virgülle ayrılmış) - orijinal
        turkish_lower_func: Türkçe normalize fonksiyonu
    
    Returns:
        (bool, str, str): (eşleşti_mi, eşleşen_kelime, eşleşme_yöntemi)
    """
    kw_lower = turkish_lower_func(keyword)
    
    # ═══ KATMAN 1: Birebir eşleşme (word boundary ile) ═══
    # TÜM kelimeler için word boundary kontrolü yap (uzunluk fark etmez)
    # Örnek: 'sap' keyword'ü 'SAP2000' içinde bulunmamalı
    # Örnek: 'sap2000' keyword'ü 'SAP' içinde bulunmamalı
    pattern = r'(?<![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])' + re.escape(kw_lower) + r'(?![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])'
    if re.search(pattern, search_text):
        return True, kw_lower, 'exact'
    
    # ═══ KATMAN 2: Synonym eşleşme (word boundary ile) ═══
    synonyms = KEYWORD_SYNONYMS.get(kw_lower, [])
    for syn in synonyms:
        syn_lower = turkish_lower_func(syn)
        if syn_lower == kw_lower:
            continue  # Kendisi zaten Katman 1'de arandı
        # TÜM synonym'ler için word boundary kontrolü yap
        pattern = r'(?<![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])' + re.escape(syn_lower) + r'(?![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])'
        if re.search(pattern, search_text):
            return True, syn, 'synonym'
    
    # ═══ KATMAN 3: Fuzzy matching ═══
    # Adayın beceri listesindeki her beceriyle karşılaştır
    # NOT: partial_ratio word boundary'yi dikkate almaz, bu yüzden sadece tam fuzzy ratio kullanıyoruz
    if skills_text:
        candidate_skills = [turkish_lower_func(s.strip()) for s in skills_text.split(',') if s.strip()]
        for skill in candidate_skills:
            # Tam fuzzy eşleşme (word boundary kontrolü ile)
            # Önce word boundary kontrolü yap, sonra fuzzy hesapla
            skill_pattern = r'(?<![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])' + re.escape(skill) + r'(?![a-zA-ZğüşıöçĞÜŞİÖÇâîûêôäëïüö0-9])'
            if re.search(skill_pattern, search_text):
                # Word boundary ile eşleşti, şimdi fuzzy benzerlik kontrol et
                ratio = fuzz.ratio(kw_lower, skill)
                if ratio >= FUZZY_MATCH_THRESHOLD:
                    return True, skill, f'fuzzy({ratio}%)'
    
    return False, None, None


@dataclass
class CriteriaMatchResult:
    """Kriter eslestirme sonucu"""
    kriter_tipi: str
    kriter_degeri: str
    puan: float
    max_puan: float
    karsilandi: bool
    zorunlu: bool
    aciklama: str = ""


@dataclass
class PositionMatchResult:
    """Pozisyon eslestirme detayli sonucu"""
    candidate_id: int
    position_id: int
    toplam_puan: float
    max_puan: float
    yuzde_puan: float
    match_status: MatchStatus
    knockout_failed: bool = False
    failed_knockouts: list = field(default_factory=list)
    kriter_sonuclari: list = field(default_factory=list)
    egitim_puani: float = 0
    deneyim_puani: float = 0
    dil_puani: float = 0
    beceri_puani: float = 0
    aciklama: str = ""


MATCH_PROMPT = """
Aşağıdaki aday profilini pozisyon gereksinimleriyle karşılaştır.

POZİSYON:
- Başlık: {position_title}
- Departman: {department}
- Lokasyon: {location}
- Minimum Deneyim: {required_experience} yıl
- Minimum Eğitim: {required_education}
- Zorunlu Beceriler: {required_skills}
- Tercih Edilen: {preferred_skills}

KNOCKOUT KRİTERLER (biri bile yoksa ELENECEK):
{knockout_criteria}

ADAY:
- Ad: {candidate_name}
- Lokasyon: {candidate_location}
- Deneyim: {candidate_experience} yıl
- Pozisyon: {current_position}
- Şirket: {current_company}
- Eğitim: {education} - {university} - {candidate_department}
- Beceriler: {technical_skills}
- Diller: {languages}
- Sertifikalar: {certificates}
- Ehliyet: {driving_license}

---

JSON formatında yanıt ver:

{{
    "knockout_passed": true,
    "failed_knockouts": [],
    "puanlar": {{
        "deneyim": {{"puan": 0, "aciklama": ""}},
        "egitim": {{"puan": 0, "aciklama": ""}},
        "beceri": {{"puan": 0, "eslesen": [], "eksik": []}},
        "dil": {{"puan": 0, "aciklama": ""}},
        "lokasyon": {{"puan": 0, "aciklama": ""}}
    }},
    "toplam_puan": 0,
    "uyum_durumu": "FULL_MATCH/PARTIAL_MATCH/MISMATCH/KNOCKOUT",
    "guclu_yonler": [],
    "eksik_yonler": [],
    "degerlendirme": "",
    "mulakat_sorulari": [],
    "alternatif_pozisyonlar": []
}}

AĞIRLIKLAR: Deneyim %30, Eğitim %25, Beceri %25, Dil %15, Lokasyon %5
KNOCKOUT varsa ve geçemediyse: toplam_puan = 0, uyum_durumu = "KNOCKOUT"
ÖNEMLİ: KNOCKOUT durumunda bile deneyim, egitim, beceri, dil, lokasyon puanlarını hesapla ve doldur. Bu alt puanlar KNOCKOUT durumunda bile görünecek ve kullanıcıya hangi kriterlerin karşılandığını gösterecek.
FULL_MATCH: 80+, PARTIAL_MATCH: 50-79, MISMATCH: 0-49

SADECE JSON döndür.
"""


def calculate_match_score_ai(candidate: Candidate, position: Position, knockout_criteria: str = None) -> Match:
    """
    Aday ile pozisyon arasindaki uyum puanini hesapla

    Args:
        candidate: Aday bilgileri
        position: Pozisyon bilgileri
        knockout_criteria: Eleyici kriterler (opsiyonel)

    Returns:
        Match objesi (puanlar ve analiz)
    """
    if not ANTHROPIC_API_KEY:
        # API key yoksa basit puanlama yap
        return _simple_match(candidate, position)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)

    # Knockout kriterlerini hazirla
    if not knockout_criteria:
        knockout_parts = []
        if position.gerekli_deneyim_yil:
            knockout_parts.append(f"- Minimum {position.gerekli_deneyim_yil} yıl deneyim")
        if position.gerekli_egitim:
            knockout_parts.append(f"- {position.gerekli_egitim} mezunu")
        if position.gerekli_beceriler:
            knockout_parts.append(f"- Zorunlu beceriler: {position.gerekli_beceriler}")
        knockout_criteria = "\n".join(knockout_parts) if knockout_parts else "Knockout kriteri belirtilmemiş"

    # Ehliyet bilgisini al (varsa)
    driving_license = getattr(candidate, 'ehliyet', None) or "Belirtilmemis"

    prompt = MATCH_PROMPT.format(
        position_title=position.baslik,
        department=position.departman or "Belirtilmemis",
        location=position.lokasyon or "Belirtilmemis",
        required_experience=position.gerekli_deneyim_yil or "Belirtilmemis",
        required_education=position.gerekli_egitim or "Belirtilmemis",
        required_skills=position.gerekli_beceriler or "Belirtilmemis",
        preferred_skills=position.tercih_edilen_beceriler or "Belirtilmemis",
        knockout_criteria=knockout_criteria,
        candidate_name=candidate.ad_soyad,
        candidate_location=candidate.lokasyon or "Belirtilmemis",
        candidate_experience=candidate.toplam_deneyim_yil or "Belirtilmemis",
        current_position=candidate.mevcut_pozisyon or "Belirtilmemis",
        current_company=candidate.mevcut_sirket or "Belirtilmemis",
        education=candidate.egitim or "Belirtilmemis",
        university=candidate.universite or "Belirtilmemis",
        candidate_department=candidate.bolum or "Belirtilmemis",
        technical_skills=candidate.teknik_beceriler or "Belirtilmemis",
        languages=candidate.diller or "Belirtilmemis",
        certificates=candidate.sertifikalar or "Belirtilmemis",
        driving_license=driving_license
    )

    try:
        start_time = time.time()

        # Retry mekanizması (max 2 deneme, timeout 60s)
        max_retries = 2
        last_error = None
        message = None

        for attempt in range(1, max_retries + 1):
            try:
                message = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                break  # Başarılı, döngüden çık
            except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2)  # Kısa bekleme sonra tekrar dene
                    continue
                raise ValueError(f"Claude API zaman aşımı/bağlantı hatası: {max_retries} deneme sonrası yanıt alınamadı (60s timeout)")
            except anthropic.APIStatusError as e:
                # Rate limit veya sunucu hatası - retry yapılabilir
                if e.status_code in (429, 500, 502, 503, 529) and attempt < max_retries:
                    last_error = e
                    time.sleep(3)
                    continue
                raise ValueError(f"Claude API hatası (HTTP {e.status_code}): {e.message}")

        if message is None:
            raise ValueError("API çağrısı başarısız oldu")

        # API kullanımını logla
        elapsed_ms = int((time.time() - start_time) * 1000)
        try:
            log_api_usage(
                islem_tipi="pozisyon_eslestirme",
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                model=CLAUDE_MODEL,
                basarili=True,
                islem_suresi_ms=elapsed_ms
            )
        except Exception:
            pass  # Loglama hatası ana işlemi etkilemesin

        response_text = message.content[0].text.strip()

        # JSON blogu cikar
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        # JSON parse ve validation
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"AI yanıtı JSON parse hatası: {e}\nYanıt: {response_text[:500]}")
            raise ValueError(f"AI yanıtı geçerli JSON değil: {e}")
        
        # JSON validation
        if not isinstance(result, dict):
            raise ValueError(f"AI yanıtı dict formatında değil: {type(result).__name__}")
        
        # Zorunlu alanlar kontrolü
        if 'puanlar' not in result:
            logger.warning("AI yanıtında 'puanlar' alanı eksik, varsayılan değerler kullanılıyor")
            result['puanlar'] = {}
        
        if 'toplam_puan' not in result:
            logger.warning("AI yanıtında 'toplam_puan' alanı eksik, 0 olarak ayarlanıyor")
            result['toplam_puan'] = 0

        # Yeni JSON yapisini isle
        puanlar = result.get("puanlar", {})
        knockout_passed = result.get("knockout_passed", True)
        failed_knockouts = result.get("failed_knockouts", [])

        # Puanlari cikar
        deneyim_puan = puanlar.get("deneyim", {}).get("puan", 0)
        egitim_puan = puanlar.get("egitim", {}).get("puan", 0)
        beceri_puan = puanlar.get("beceri", {}).get("puan", 0)
        dil_puan = puanlar.get("dil", {}).get("puan", 0)
        lokasyon_puan = puanlar.get("lokasyon", {}).get("puan", 0)

        # Toplam puan (knockout gecilmediyse 0)
        if knockout_passed:
            toplam_puan = result.get("toplam_puan", 0)
        else:
            toplam_puan = 0

        # Detayli analiz metni olustur
        detayli_analiz_parts = []

        # Degerlendirme
        detayli_analiz_parts.append(f"Değerlendirme: {result.get('degerlendirme', '')}")
        detayli_analiz_parts.append(f"Uyum Durumu: {result.get('uyum_durumu', '')}")

        # Knockout sonucu
        if not knockout_passed:
            detayli_analiz_parts.append(f"\n⛔ KNOCKOUT - Elenen Kriterler: {', '.join(failed_knockouts)}")

        # Guclu ve eksik yonler
        guclu = result.get("guclu_yonler", [])
        eksik = result.get("eksik_yonler", [])

        if guclu:
            detayli_analiz_parts.append("\n✅ Güçlü Yönler:")
            for g in guclu:
                detayli_analiz_parts.append(f"  - {g}")

        if eksik:
            detayli_analiz_parts.append("\n⚠️ Eksik Yönler:")
            for e in eksik:
                detayli_analiz_parts.append(f"  - {e}")

        # Mulakat sorulari
        sorular = result.get("mulakat_sorulari", [])
        if sorular:
            detayli_analiz_parts.append("\n📋 Önerilen Mülakat Soruları:")
            for s in sorular[:3]:
                detayli_analiz_parts.append(f"  - {s}")

        # Alternatif pozisyonlar
        alternatifler = result.get("alternatif_pozisyonlar", [])
        if alternatifler:
            detayli_analiz_parts.append(f"\n💡 Alternatif Pozisyonlar: {', '.join(alternatifler)}")

        detayli_analiz = "\n".join(detayli_analiz_parts)

        return Match(
            candidate_id=candidate.id,
            position_id=position.id,
            uyum_puani=toplam_puan,
            deneyim_puani=deneyim_puan,
            egitim_puani=egitim_puan,
            beceri_puani=beceri_puan,
            detayli_analiz=detayli_analiz
        )

    except Exception as e:
        logger.error(f"Eslestirme hatasi: {e}", exc_info=True)
        return _simple_match(candidate, position)


def _simple_match(candidate: Candidate, position: Position) -> Match:
    """Basit keyword tabanlı fallback eşleştirme.
    
    AI eşleştirme başarısız olduğunda kullanılır.
    Deneyim yılı, keyword eşleşmesi ve eğitim seviyesine göre
    0-100 arası temel bir skor hesaplar.
    
    Args:
        candidate: Aday dict veya Candidate objesi
        position: Pozisyon dict veya Position objesi
    
    Returns:
        Match: Basit skor içeren Match objesi
    """
    score = DEFAULT_BASE_SCORE  # Baslangic puani

    # Deneyim kontrolu
    if candidate.toplam_deneyim_yil and position.gerekli_deneyim_yil:
        if candidate.toplam_deneyim_yil >= position.gerekli_deneyim_yil:
            score += EXPERIENCE_FULL_BONUS
        elif candidate.toplam_deneyim_yil >= position.gerekli_deneyim_yil * EXPERIENCE_MULTIPLIER:
            score += EXPERIENCE_PARTIAL_BONUS

    # Beceri kontrolu (basit kelime eslesmesi)
    if candidate.teknik_beceriler and position.gerekli_beceriler:
        candidate_skills = set(s.strip().lower() for s in candidate.teknik_beceriler.split(","))
        required_skills = set(s.strip().lower() for s in position.gerekli_beceriler.split(","))
        matching = len(candidate_skills & required_skills)
        if matching > 0:
            score += min(matching * KEYWORD_POINTS_PER_MATCH, MAX_KEYWORD_BONUS)

    return Match(
        candidate_id=candidate.id,
        position_id=position.id,
        uyum_puani=min(score, 100),
        detayli_analiz="Basit puanlama (API kullanilmadi)"
    )


def determine_pool(score: float, has_position: bool = True) -> str:
    """
    Havuz belirle

    Args:
        score: Uyum puani (0-100)
        has_position: Belirli bir pozisyona mi basvurdu

    Returns:
        Havuz kodu
    """
    if has_position:
        return "pozisyon_havuzu"

    return "genel_havuz"


def match_candidate_to_positions_ai(
    candidate: Candidate,
    positions: list[Position],
    save_results: bool = True
) -> list[Match]:
    """
    Adayi tum aktif pozisyonlarla eslestir (AI destekli)

    Args:
        candidate: Aday
        positions: Pozisyon listesi
        save_results: Sonuclari veritabanina kaydet

    Returns:
        Match listesi
    """
    matches = []

    for position in positions:
        match = calculate_match_score_ai(candidate, position)

        if save_results and candidate.id and position.id:
            save_match(match)

        matches.append(match)

    # En iyi eslesmeye gore havuz belirle
    if matches:
        best_match = max(matches, key=lambda m: m.uyum_puani)
        pool = determine_pool(best_match.uyum_puani)

        if save_results and candidate.id:
            update_candidate(candidate.id, havuz=pool)

    return matches


def match_all_candidates_to_position(
    candidates: list[Candidate],
    position: Position,
    save_results: bool = True
) -> list[Match]:
    """
    Tum adaylari belirli bir pozisyonla eslestir

    Args:
        candidates: Aday listesi
        position: Pozisyon
        save_results: Sonuclari veritabanina kaydet

    Returns:
        Match listesi (puanlarına gore sirali)
    """
    matches = []

    for candidate in candidates:
        match = calculate_match_score_ai(candidate, position)

        if save_results and candidate.id and position.id:
            save_match(match)
            # Havuz guncelle
            pool = determine_pool(match.uyum_puani)
            update_candidate(candidate.id, havuz=pool)

        matches.append(match)

    # Puana gore sirala
    matches.sort(key=lambda m: m.uyum_puani, reverse=True)

    return matches


# ============ KRITER BAZLI ESLESTIRME SISTEMI ============

def match_candidate_to_position_criteria(candidate_data: dict, position_id: int) -> PositionMatchResult:
    """
    Adayi pozisyon kriterleriyle eslestir ve detayli puan hesapla

    Args:
        candidate_data: Aday verileri (dict)
        position_id: Pozisyon ID

    Returns:
        PositionMatchResult objesi
    """
    # Pozisyon kriterlerini getir
    criteria = get_position_criteria(position_id)

    if not criteria:
        # Kriter yoksa basit puanlama
        return PositionMatchResult(
            candidate_id=candidate_data.get("id", 0),
            position_id=position_id,
            toplam_puan=50,
            max_puan=100,
            yuzde_puan=50,
            match_status=MatchStatus.PARTIAL_MATCH,
            aciklama="Pozisyon icin kriter tanimlanmamis, varsayilan puan verildi"
        )

    # Her kriter icin puanlama yap
    kriter_sonuclari = []
    toplam_puan = 0
    max_puan = 0
    failed_knockouts = []

    egitim_puan = 0
    egitim_max = 0
    deneyim_puan = 0
    deneyim_max = 0
    dil_puan = 0
    dil_max = 0
    beceri_puan = 0
    beceri_max = 0

    for kriter in criteria:
        kriter_tipi = kriter.get("kriter_tipi")
        deger = kriter.get("deger", "")
        zorunlu = kriter.get("zorunlu", 0) == 1
        agirlik = kriter.get("agirlik", 1.0)

        # Kriter bazli puan hesapla (max 100 * agirlik)
        kriter_max = 100 * agirlik
        max_puan += kriter_max

        # Kriter tipine gore puanlama
        if kriter_tipi == "egitim":
            puan, karsilandi, aciklama = _evaluate_education_criteria(candidate_data, kriter)
            egitim_max += kriter_max
            egitim_puan += puan * agirlik

        elif kriter_tipi == "deneyim":
            puan, karsilandi, aciklama = _evaluate_experience_criteria(candidate_data, kriter)
            deneyim_max += kriter_max
            deneyim_puan += puan * agirlik

        elif kriter_tipi == "dil":
            puan, karsilandi, aciklama = _evaluate_language_criteria(candidate_data, kriter)
            dil_max += kriter_max
            dil_puan += puan * agirlik

        elif kriter_tipi == "beceri":
            puan, karsilandi, aciklama = _evaluate_skill_criteria(candidate_data, kriter)
            beceri_max += kriter_max
            beceri_puan += puan * agirlik

        else:
            puan, karsilandi, aciklama = 50, True, "Bilinmeyen kriter tipi"

        # Knockout kontrolu
        if zorunlu and not karsilandi:
            failed_knockouts.append({
                "kriter_tipi": kriter_tipi,
                "deger": deger,
                "aciklama": aciklama
            })

        # Sonucu kaydet
        kriter_sonuclari.append(CriteriaMatchResult(
            kriter_tipi=kriter_tipi,
            kriter_degeri=deger,
            puan=puan * agirlik,
            max_puan=kriter_max,
            karsilandi=karsilandi,
            zorunlu=zorunlu,
            aciklama=aciklama
        ))

        toplam_puan += puan * agirlik

    # Yuzde puan hesapla
    yuzde_puan = (toplam_puan / max_puan * 100) if max_puan > 0 else 0

    # Knockout kontrolu - zorunlu kriter karsilanmadiysa 0 puan
    knockout_failed = len(failed_knockouts) > 0
    if knockout_failed:
        match_status = MatchStatus.KNOCKOUT
        yuzde_puan = 0
    elif yuzde_puan >= 80:
        match_status = MatchStatus.FULL_MATCH
    elif yuzde_puan >= 50:
        match_status = MatchStatus.PARTIAL_MATCH
    else:
        match_status = MatchStatus.MISMATCH

    # Aciklama olustur
    aciklama = _generate_match_summary(match_status, yuzde_puan, failed_knockouts, kriter_sonuclari)

    return PositionMatchResult(
        candidate_id=candidate_data.get("id", 0),
        position_id=position_id,
        toplam_puan=toplam_puan,
        max_puan=max_puan,
        yuzde_puan=round(yuzde_puan, 1),
        match_status=match_status,
        knockout_failed=knockout_failed,
        failed_knockouts=failed_knockouts,
        kriter_sonuclari=kriter_sonuclari,
        egitim_puani=round((egitim_puan / egitim_max * 100) if egitim_max > 0 else 0, 1),
        deneyim_puani=round((deneyim_puan / deneyim_max * 100) if deneyim_max > 0 else 0, 1),
        dil_puani=round((dil_puan / dil_max * 100) if dil_max > 0 else 0, 1),
        beceri_puani=round((beceri_puan / beceri_max * 100) if beceri_max > 0 else 0, 1),
        aciklama=aciklama
    )


def _evaluate_education_criteria(candidate: dict, kriter: dict) -> tuple:
    """Egitim kriterini degerlendir"""
    deger = kriter.get("deger", "").lower()
    seviye = kriter.get("seviye", "")

    candidate_egitim = (candidate.get("egitim") or "").lower()
    candidate_bolum = (candidate.get("bolum") or "").lower()

    # Egitim seviyesi siralama
    egitim_levels = {
        "lise": 1,
        "on lisans": 2,
        "onlisans": 2,
        "lisans": 3,
        "yuksek lisans": 4,
        "yüksek lisans": 4,
        "master": 4,
        "doktora": 5,
        "phd": 5
    }

    # Seviye kontrolu
    if seviye:
        required_level = egitim_levels.get(seviye.lower(), 0)
        candidate_level = egitim_levels.get(candidate_egitim, 0)

        if candidate_level >= required_level:
            puan = 100
            karsilandi = True
            aciklama = f"Egitim seviyesi uygun: {candidate_egitim.title()}"
        elif candidate_level == required_level - 1:
            puan = 60
            karsilandi = False
            aciklama = f"Egitim seviyesi yakin: {candidate_egitim.title()} (Aranan: {seviye})"
        else:
            puan = 20
            karsilandi = False
            aciklama = f"Egitim seviyesi yetersiz: {candidate_egitim.title()} (Aranan: {seviye})"
    # Bolum kontrolu
    elif deger:
        if deger in candidate_bolum or deger in candidate_egitim:
            puan = 100
            karsilandi = True
            aciklama = f"Bolum eslesti: {deger.title()}"
        elif any(word in candidate_bolum for word in deger.split()):
            puan = 70
            karsilandi = True
            aciklama = f"Bolum kismi eslesti: {candidate_bolum.title()}"
        else:
            puan = 30
            karsilandi = False
            aciklama = f"Bolum eslesmedi (Aranan: {deger.title()})"
    else:
        puan = 50
        karsilandi = True
        aciklama = "Egitim kriteri belirsiz"

    return puan, karsilandi, aciklama


def _evaluate_experience_criteria(candidate: dict, kriter: dict) -> tuple:
    """Deneyim kriterini degerlendir"""
    min_deger = kriter.get("min_deger")
    max_deger = kriter.get("max_deger")
    alan = kriter.get("deger", "")

    candidate_exp = candidate.get("toplam_deneyim_yil") or 0
    candidate_pozisyon = (candidate.get("mevcut_pozisyon") or "").lower()
    candidate_sirket = (candidate.get("mevcut_sirket") or "").lower()

    puan = 50
    karsilandi = True
    aciklama_parts = []

    # Yil kontrolu
    if min_deger:
        try:
            min_yil = float(min_deger)
            if candidate_exp >= min_yil:
                puan = 100
                aciklama_parts.append(f"Deneyim yeterli: {candidate_exp} yil")
            elif candidate_exp >= min_yil * 0.7:
                puan = 70
                karsilandi = False
                aciklama_parts.append(f"Deneyim yakin: {candidate_exp} yil (Min: {min_yil})")
            else:
                puan = 30
                karsilandi = False
                aciklama_parts.append(f"Deneyim yetersiz: {candidate_exp} yil (Min: {min_yil})")
        except ValueError:
            pass

    # Alan kontrolu
    if alan:
        alan_lower = alan.lower()
        if alan_lower in candidate_pozisyon or alan_lower in candidate_sirket:
            if puan < 100:
                puan = min(puan + 30, 100)
            aciklama_parts.append(f"Alan eslesti: {alan}")
        else:
            aciklama_parts.append(f"Alan eslesmedi: {alan}")

    aciklama = " | ".join(aciklama_parts) if aciklama_parts else "Deneyim degerlendirme tamamlandi"

    return puan, karsilandi, aciklama


def _evaluate_language_criteria(candidate: dict, kriter: dict) -> tuple:
    """Dil kriterini degerlendir"""
    dil = kriter.get("deger", "").lower()
    seviye = kriter.get("seviye", "").upper()

    candidate_diller = (candidate.get("diller") or "").lower()

    # Dil seviye siralama
    dil_levels = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6, "ANADIL": 7}

    if dil in candidate_diller:
        # Seviye kontrolu
        if seviye:
            required_level = dil_levels.get(seviye, 3)
            # Aday seviyesini bulmaya calis
            candidate_level = 3  # Varsayilan B1
            for level_code in ["C2", "C1", "B2", "B1", "A2", "A1", "ANADIL"]:
                if level_code.lower() in candidate_diller:
                    candidate_level = dil_levels.get(level_code, 3)
                    break

            if candidate_level >= required_level:
                puan = 100
                karsilandi = True
                aciklama = f"{dil.title()} dil seviyesi uygun"
            else:
                puan = 50
                karsilandi = False
                aciklama = f"{dil.title()} seviye yetersiz (Aranan: {seviye})"
        else:
            puan = 100
            karsilandi = True
            aciklama = f"{dil.title()} dili mevcut"
    else:
        puan = 0
        karsilandi = False
        aciklama = f"{dil.title()} dili bulunamadi"

    return puan, karsilandi, aciklama


def _evaluate_skill_criteria(candidate: dict, kriter: dict) -> tuple:
    """Beceri kriterini degerlendir"""
    beceri = kriter.get("deger", "").lower()
    candidate_skills = (candidate.get("teknik_beceriler") or "").lower()

    if beceri in candidate_skills:
        puan = 100
        karsilandi = True
        aciklama = f"{beceri.title()} becerisi mevcut"
    elif any(word in candidate_skills for word in beceri.split()):
        puan = 60
        karsilandi = True
        aciklama = f"{beceri.title()} ile ilgili beceri mevcut"
    else:
        puan = 0
        karsilandi = False
        aciklama = f"{beceri.title()} becerisi bulunamadi"

    return puan, karsilandi, aciklama


def _generate_match_summary(status: MatchStatus, puan: float,
                           failed_knockouts: list, kriter_sonuclari: list) -> str:
    """Eslestirme ozeti olustur"""
    if status == MatchStatus.KNOCKOUT:
        knockout_list = ", ".join([k["deger"] for k in failed_knockouts])
        return f"UYUMSUZ - Zorunlu kriterler karsilanamadi: {knockout_list}"
    elif status == MatchStatus.FULL_MATCH:
        return f"TAM UYUMLU - Puan: {puan:.1f}% - Tum kriterler karsilandi"
    elif status == MatchStatus.PARTIAL_MATCH:
        return f"KISMI UYUMLU - Puan: {puan:.1f}% - Bazi eksikler mevcut"
    else:
        return f"UYUMSUZ - Puan: {puan:.1f}% - Onemli eksikler var"


def auto_match_candidate_to_all_positions(candidate_data: dict, company_id: int = None) -> list:
    """
    Adayi tum aktif pozisyonlarla otomatik eslestir ve havuzlara ekle

    Args:
        candidate_data: Aday verileri
        company_id: Firma ID

    Returns:
        Eslestirme sonuclari listesi
    """
    from database import get_all_positions

    positions = get_all_positions(only_active=True, company_id=company_id)
    results = []

    for position in positions:
        # Kriter bazli eslestirme
        match_result = match_candidate_to_position_criteria(candidate_data, position.id)

        # Match tablosuna kaydet
        match = Match(
            candidate_id=candidate_data.get("id"),
            position_id=position.id,
            uyum_puani=match_result.yuzde_puan,
            deneyim_puani=match_result.deneyim_puani,
            egitim_puani=match_result.egitim_puani,
            beceri_puani=match_result.beceri_puani,
            detayli_analiz=match_result.aciklama
        )
        save_match(match)

        # Havuza ekle veya guncelle
        durum_map = {
            MatchStatus.FULL_MATCH: "beklemede",
            MatchStatus.PARTIAL_MATCH: "beklemede",
            MatchStatus.MISMATCH: "beklemede",
            MatchStatus.KNOCKOUT: "red"
        }
        durum = durum_map.get(match_result.match_status, "beklemede")

        try:
            add_candidate_to_pool(
                position_id=position.id,
                candidate_id=candidate_data.get("id"),
                uyum_puani=match_result.yuzde_puan,
                durum=durum,
                notlar=match_result.aciklama
            )
        except Exception:
            # Zaten havuzda, guncelle
            update_pool_candidate(
                position_id=position.id,
                candidate_id=candidate_data.get("id"),
                uyum_puani=match_result.yuzde_puan,
                durum=durum,
                notlar=match_result.aciklama
            )

        results.append({
            "position_id": position.id,
            "position_title": position.baslik,
            "match_result": match_result,
            "match_status": match_result.match_status.value,
            "puan": match_result.yuzde_puan
        })

    # En iyi eslesmeye gore aday havuzunu guncelle
    if results:
        best = max(results, key=lambda r: r["puan"])
        pool = determine_pool(best["puan"])
        update_candidate(candidate_data.get("id"), havuz=pool)

    return results


def get_match_status_label(status: MatchStatus) -> dict:
    """Match status icin etiket ve renk dondur"""
    labels = {
        MatchStatus.FULL_MATCH: {"label": "Tam Uyumlu", "color": "green", "icon": "✅"},
        MatchStatus.PARTIAL_MATCH: {"label": "Kismi Uyumlu", "color": "orange", "icon": "⚠️"},
        MatchStatus.MISMATCH: {"label": "Uyumsuz", "color": "red", "icon": "❌"},
        MatchStatus.KNOCKOUT: {"label": "Knockout", "color": "red", "icon": "🚫"}
    }
    return labels.get(status, {"label": "Bilinmiyor", "color": "gray", "icon": "❓"})


# ============ YENİ EŞLEŞTİRME SİSTEMİ ============

MAX_POSITIONS_PER_CANDIDATE = 5  # Bir aday en fazla 5 pozisyonda olabilir


def match_candidate_to_positions_keyword(candidate_id: int, company_id: int) -> dict:
    """Yeni CV geldiğinde TÜM açık pozisyonlarla eşleştir (Keyword bazlı)

    Kurallar:
    - Tüm açık pozisyonlarla eşleştir
    - Skor hesapla ve sırala
    - En yüksek skorlu MAX 5 pozisyona ekle

    Args:
        candidate_id: Aday ID
        company_id: Firma ID

    Returns:
        {'total_positions': int, 'matched': int, 'added': int, 'scores': [...]}
    """
    from database import (
        get_candidate, get_department_pools,
        add_candidate_to_position, get_candidate_position_count
    )

    stats = {'total_positions': 0, 'matched': 0, 'added': 0, 'scores': []}

    # Adayı getir (company_id ile güvenli erişim)
    candidate = get_candidate(candidate_id, company_id=company_id)
    if not candidate:
        return stats

    # Candidate'i dict'e çevir (v2 için)
    if isinstance(candidate, dict):
        candidate_dict = candidate
    elif hasattr(candidate, 'model_dump'):  # Pydantic v2
        candidate_dict = candidate.model_dump()
    elif hasattr(candidate, 'dict'):  # Pydantic v1
        candidate_dict = candidate.dict()
    else:
        # Candidate object ise attribute'ları dict'e çevir
        candidate_dict = {
            'id': getattr(candidate, 'id', None),
            'ad_soyad': getattr(candidate, 'ad_soyad', '') or '',
            'toplam_deneyim_yil': getattr(candidate, 'toplam_deneyim_yil', 0) or 0,
            'egitim': getattr(candidate, 'egitim', '') or '',
            'mevcut_pozisyon': getattr(candidate, 'mevcut_pozisyon', '') or '',
            'lokasyon': getattr(candidate, 'lokasyon', '') or '',
            'teknik_beceriler': getattr(candidate, 'teknik_beceriler', '') or '',
            'cv_raw_text': getattr(candidate, 'cv_raw_text', '') or '',
            'deneyim_detay': getattr(candidate, 'deneyim_detay', '') or '',
            'mevcut_sirket': getattr(candidate, 'mevcut_sirket', '') or ''
        }
    
    aday_adi = candidate_dict.get('ad_soyad', 'İsimsiz')

    # Aday kaç pozisyonda?
    current_count = get_candidate_position_count(candidate_id)
    if current_count >= MAX_POSITIONS_PER_CANDIDATE:
        return stats  # Limit dolmuş

    # Açık pozisyonları getir (department_pools tablosundan)
    pools = get_department_pools(company_id, include_inactive=False, pool_type='position')
    
    # department_pools kayıtlarını position dict formatına çevir
    positions = []
    for pool in pools:
        if pool.get('is_system', 0):
            continue  # Sistem havuzlarını atla
        keywords_value = pool.get('keywords', '') or ''
        # keywords None ise boş string'e çevir
        if keywords_value is None:
            keywords_value = ''
        position = {
            'id': pool['id'],
            'baslik': pool.get('name', ''),
            'name': pool.get('name', ''),
            'departman': '',
            'lokasyon': pool.get('lokasyon', '') or '',
            'gerekli_deneyim_yil': pool.get('gerekli_deneyim_yil', 0) or 0,
            'gerekli_egitim': pool.get('gerekli_egitim', '') or '',
            'gerekli_beceriler': '',  # keywords alanı ayrı okunacak
            'keywords': keywords_value,  # JSON string olarak (None değil, boş string)
            'tercih_edilen_beceriler': ''
        }
        positions.append(position)
    
    stats['total_positions'] = len(positions)

    # Her pozisyon için skor hesapla (v2 öncelikli, v1 fallback)
    position_scores = []
    for pos in positions:
        pozisyon_adi = pos.get('baslik', '') or pos.get('name', '')
        v2_result = None
        score_result = None
        score = 0
        use_v2 = False
        
        # Önce v2 dene
        try:
            v2_result = calculate_match_score_v2(candidate_dict, pos)
            if v2_result is not None:
                use_v2 = True
                title_score = v2_result.get('title_match_score', 0)
                
                # title_match_score == 0 ise skip et (pozisyon başlığı eşleşmesi yok)
                if title_score == 0:
                    logger.info(f"SKIP: {aday_adi} → {pozisyon_adi}: title_match_score=0, pozisyon başlığı eşleşmesi yok")
                    continue
                
                score = v2_result.get('total', 0)
                pos_score = v2_result.get('position_score', 0)
                logger.info(f"v2 scoring: {aday_adi} → {pozisyon_adi}: {score} (position_score: {pos_score}, title_match_score: {title_score})")
            else:
                # v2 verisi yok, v1'e fallback
                score_result = calculate_match_score_keyword(candidate, pos)
                score = score_result['total'] if isinstance(score_result, dict) else score_result
                logger.info(f"v1 fallback: {aday_adi} → {pozisyon_adi}: {score}")
        except Exception as e:
            # v2 hatası, v1'e fallback
            logger.warning(f"v2 hata ({aday_adi} → {pozisyon_adi}), v1 fallback: {e}")
            try:
                score_result = calculate_match_score_keyword(candidate, pos)
                score = score_result['total'] if isinstance(score_result, dict) else score_result
                logger.info(f"v1 fallback: {aday_adi} → {pozisyon_adi}: {score}")
            except Exception as e2:
                logger.error(f"v1 fallback hatası ({aday_adi} → {pozisyon_adi}): {e2}")
                continue
        
        if score > 0:  # Sadece eşleşenler
            # Detaylı puan bilgilerini de ekle
            ps = {
                'position_id': pos.get('id') or pos.id,
                'baslik': pozisyon_adi,
                'score': score,
                'use_v2': use_v2,
                'v2_result': v2_result
            }
            
            if use_v2 and v2_result:
                # v2 sonucu
                ps['keyword_score'] = v2_result.get('technical_score', 0)  # v2'de technical_score beceri_puani
                ps['experience_score'] = v2_result.get('experience_score', 0)
                ps['education_score'] = v2_result.get('education_score', 0)
                ps['location_score'] = v2_result.get('location_score', 0)
                ps['matched_keywords'] = v2_result.get('critical_matched', []) + v2_result.get('important_matched', [])
                ps['keyword_details'] = []
                ps['total_keywords'] = len(v2_result.get('critical_matched', [])) + len(v2_result.get('important_matched', []))
            elif score_result and isinstance(score_result, dict):
                # v1 sonucu
                ps['keyword_score'] = score_result.get('keyword_score', 0)
                ps['experience_score'] = score_result.get('experience_score', 0)
                ps['education_score'] = score_result.get('education_score', 0)
                ps['location_score'] = score_result.get('location_score', 0)
                ps['matched_keywords'] = score_result.get('matched_keywords', [])
                ps['keyword_details'] = score_result.get('keyword_details', [])
                ps['total_keywords'] = score_result.get('total_keywords', 0)
            else:
                # Eski format için varsayılan değerler
                ps['keyword_score'] = 0
                ps['experience_score'] = 0
                ps['education_score'] = 0
                ps['location_score'] = 0
                ps['matched_keywords'] = []
                ps['keyword_details'] = []
                ps['total_keywords'] = 0
            
            position_scores.append(ps)
            stats['matched'] += 1

    # Skora göre sırala (yüksekten düşüğe)
    position_scores.sort(key=lambda x: x['score'], reverse=True)
    stats['scores'] = position_scores

    # En yüksek skorlu pozisyonlara ekle (MAX 5'e kadar)
    slots_available = MAX_POSITIONS_PER_CANDIDATE - current_count
    for ps in position_scores[:slots_available]:
        if add_candidate_to_position(candidate_id, ps['position_id'], ps['score']):
            stats['added'] += 1
            
            # Detaylı puanları matches tablosuna da kaydet
            try:
                import json
                
                # v2 sonucu varsa v2 formatında kaydet
                if ps.get('use_v2') and ps.get('v2_result'):
                    v2_result = ps['v2_result']
                    detayli_analiz_json = json.dumps({
                        'version': 'v2',
                        'position_score': v2_result.get('position_score', 0),
                        'title_match_score': v2_result.get('title_match_score', 0),
                        'title_match_level': v2_result.get('title_match_level', 'none'),
                        'matched_title': v2_result.get('matched_title', ''),
                        'sector_score': v2_result.get('sector_score', 0),
                        'detected_sector': v2_result.get('detected_sector', ''),
                        'technical_score': v2_result.get('technical_score', 0),
                        'critical_score': v2_result.get('critical_score', 0),
                        'critical_matched': v2_result.get('critical_matched', []),
                        'critical_missing': v2_result.get('critical_missing', []),
                        'important_score': v2_result.get('important_score', 0),
                        'important_matched': v2_result.get('important_matched', []),
                        'general_score': v2_result.get('general_score', 0),
                        'experience_score': v2_result.get('experience_score', 0),
                        'education_score': v2_result.get('education_score', 0),
                        'elimination_score': v2_result.get('elimination_score', 0),
                        'location_score': v2_result.get('location_score', 0),
                        'knockout': v2_result.get('knockout', False),
                        'knockout_reason': v2_result.get('knockout_reason')
                    }, ensure_ascii=False)
                    
                    match = Match(
                        candidate_id=candidate_id,
                        position_id=ps['position_id'],
                        uyum_puani=v2_result.get('total', 0),
                        deneyim_puani=v2_result.get('experience_score', 0),
                        egitim_puani=v2_result.get('education_score', 0),
                        beceri_puani=v2_result.get('technical_score', 0),
                        detayli_analiz=detayli_analiz_json
                    )
                else:
                    # v1 fallback formatında kaydet
                    detayli_analiz_json = json.dumps({
                        'keyword_score': ps.get('keyword_score', 0),
                        'experience_score': ps.get('experience_score', 0),
                        'education_score': ps.get('education_score', 0),
                        'location_score': ps.get('location_score', 0),
                        'matched_keywords': ps.get('matched_keywords', []),
                        'keyword_details': ps.get('keyword_details', []),
                        'total_keywords': ps.get('total_keywords', 0)
                    }, ensure_ascii=False)
                    
                    match = Match(
                        candidate_id=candidate_id,
                        position_id=ps['position_id'],
                        uyum_puani=ps['score'],
                        deneyim_puani=ps.get('experience_score', 0),
                        egitim_puani=ps.get('education_score', 0),
                        beceri_puani=ps.get('keyword_score', 0),
                        detayli_analiz=detayli_analiz_json
                    )
                
                save_match(match)
            except Exception:
                pass  # matches kaydı başarısız olsa bile ana akış bozulmasın

    return stats


def match_position_to_candidates(position_id: int, company_id: int) -> dict:
    """Yeni pozisyon açıldığında uygun adayları bul ve ekle

    Taranacak havuzlar:
    - Genel Havuz
    - Diğer pozisyonlardaki adaylar (5 pozisyona ulaşmamışsa)

    Kurallar:
    - Aday max 5 pozisyonda olabilir
    - En yüksek skorlu adaylar öncelikli

    Args:
        position_id: Pozisyon ID
        company_id: Firma ID

    Returns:
        {'total_scanned': int, 'matched': int, 'added': int, 'from_general': int, 'from_other': int}
    """
    from database import (
        get_position,
        get_candidate_position_count, add_candidate_to_position,
        get_candidate, get_candidates_by_ids
    )

    stats = {'total_scanned': 0, 'matched': 0, 'added': 0, 'from_general': 0, 'from_other': 0}

    # Pozisyonu getir
    # candidate_positions.position_id department_pools'a referans ediyor
    # Önce department_pools'tan bakalım
    from database import get_connection
    position = None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, keywords, description, company_id, parent_id, pool_type,
                   gerekli_deneyim_yil, gerekli_egitim, lokasyon
            FROM department_pools
            WHERE id = ? AND company_id = ?
        """, (position_id, company_id))
        dp_row_raw = cursor.fetchone()
        
    if dp_row_raw:
        # department_pools kaydını position dict formatına çevir
        dp_row = dict(dp_row_raw)
        keywords_value = dp_row.get('keywords', '') or ''
        # keywords None ise boş string'e çevir
        if keywords_value is None:
            keywords_value = ''
        position = {
            'id': dp_row['id'],
            'baslik': dp_row['name'],
            'name': dp_row['name'],
            'departman': '',
            'lokasyon': dp_row.get('lokasyon', '') or '',
            'gerekli_deneyim_yil': dp_row.get('gerekli_deneyim_yil', 0) or 0,
            'gerekli_egitim': dp_row.get('gerekli_egitim', '') or '',
            'gerekli_beceriler': '',  # keywords alanı ayrı okunacak
            'keywords': keywords_value,  # JSON string olarak (None değil, boş string)
            'tercih_edilen_beceriler': ''
        }
    else:
        # Eski sistem: positions tablosundan dene
        position_obj = get_position(position_id, company_id)
        if position_obj:
            if hasattr(position_obj, '__dict__'):
                position = {
                    'id': position_obj.id,
                    'baslik': position_obj.baslik,
                    'name': getattr(position_obj, 'baslik', ''),
                    'departman': getattr(position_obj, 'departman', ''),
                    'lokasyon': getattr(position_obj, 'lokasyon', ''),
                    'gerekli_deneyim_yil': getattr(position_obj, 'gerekli_deneyim_yil', 0),
                    'gerekli_egitim': getattr(position_obj, 'gerekli_egitim', ''),
                    'gerekli_beceriler': getattr(position_obj, 'gerekli_beceriler', ''),
                    'keywords': getattr(position_obj, 'gerekli_beceriler', ''),
                    'tercih_edilen_beceriler': getattr(position_obj, 'tercih_edilen_beceriler', '')
                }
            else:
                position = dict(position_obj)
                position['name'] = position.get('baslik', '')
                position['keywords'] = position.get('gerekli_beceriler', '')
    
    if not position:
        return stats

    # Taranacak adayları topla
    candidates_to_scan = []

    # 1. Genel Havuz'daki adaylar (candidates.havuz alanından)
    from database import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM candidates
            WHERE company_id = ? AND havuz = 'genel_havuz' AND is_anonymized = 0
        """, (company_id,))
        for row in cursor.fetchall():
            candidates_to_scan.append({
                'candidate_id': row[0],
                'source': 'general'
            })

    # 2. Diğer pozisyonlardaki adaylar (5'e ulaşmamış olanlar)
    from database import get_connection
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT cp.candidate_id
            FROM candidate_positions cp
            JOIN candidates c ON cp.candidate_id = c.id
            WHERE c.company_id = ? AND cp.position_id != ?
        """, (company_id, position_id))
        for row in cursor.fetchall():
            cid = row[0]
            # Aynı aday iki kez eklenmemeli
            if not any(c['candidate_id'] == cid for c in candidates_to_scan):
                candidates_to_scan.append({
                    'candidate_id': cid,
                    'source': 'other'
                })

    stats['total_scanned'] = len(candidates_to_scan)

    # PERFORMANS: Tüm adayları tek sorguda çek (N+1 query sorununu önle)
    candidate_ids_to_fetch = [c['candidate_id'] for c in candidates_to_scan]
    candidates_map = get_candidates_by_ids(candidate_ids_to_fetch, company_id)

    # PERFORMANS: Tüm adayların pozisyon sayılarını tek sorguda çek (N+1 query sorununu önle)
    from database import get_connection
    position_counts_map = {}
    if candidate_ids_to_fetch:
        with get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in candidate_ids_to_fetch])
            cursor.execute(f"""
                SELECT candidate_id, COUNT(*) as position_count
                FROM candidate_positions
                WHERE candidate_id IN ({placeholders})
                GROUP BY candidate_id
            """, candidate_ids_to_fetch)
            for row in cursor.fetchall():
                position_counts_map[row[0]] = row[1]

    # Her aday için skor hesapla
    candidate_scores = []
    for c in candidates_to_scan:
        cid = c['candidate_id']

        # 5 pozisyon limitini kontrol et (batch fetch'ten)
        current_count = position_counts_map.get(cid, 0)
        if current_count >= MAX_POSITIONS_PER_CANDIDATE:
            continue

        # Aday bilgilerini getir (batch fetch'ten)
        candidate = candidates_map.get(cid)
        if not candidate:
            continue

        # Skor hesapla
        score_result = calculate_match_score_keyword(candidate, position)
        score = score_result['total'] if isinstance(score_result, dict) else score_result
        if score > 0:
            candidate_scores.append({
                'candidate_id': cid,
                'score': score,
                'source': c['source']
            })
            stats['matched'] += 1

    # Skora göre sırala
    candidate_scores.sort(key=lambda x: x['score'], reverse=True)

    # Pozisyona ekle
    for cs in candidate_scores:
        if add_candidate_to_position(cs['candidate_id'], position_id, cs['score']):
            stats['added'] += 1
            if cs['source'] == 'general':
                stats['from_general'] += 1
            else:
                stats['from_other'] += 1

    return stats


def calculate_match_score_keyword(candidate: dict, position: dict) -> dict:
    """Aday-pozisyon eşleşme skoru hesapla (0-100) - Detaylı puanlama

    Kriterler:
    - Anahtar kelime eşleşmesi (40 puan)
    - Deneyim uyumu (25 puan)
    - Eğitim uyumu (20 puan)
    - Lokasyon uyumu (15 puan)

    Args:
        candidate: Aday dict veya Candidate object
        position: Pozisyon dict veya Position object

    Returns:
        dict: {
            'total': int (0-100),
            'keyword_score': int,
            'experience_score': int,
            'education_score': int,
            'location_score': int,
            'matched_keywords': list,
            'total_keywords': int
        }
    """
    score = 0
    
    # Ara puanları ayrı değişkenlerde tut
    keyword_score = 0
    experience_score = 0
    education_score = 0
    location_score = 0
    matched_keywords_list = []

    # Aday bilgilerini al (dict veya object)
    cv_text = candidate.get('cv_raw_text', '') or getattr(candidate, 'cv_raw_text', '') or ''
    skills = candidate.get('teknik_beceriler', '') or getattr(candidate, 'teknik_beceriler', '') or ''
    experience = candidate.get('deneyim_detay', '') or getattr(candidate, 'deneyim_detay', '') or ''
    current_pos = candidate.get('mevcut_pozisyon', '') or getattr(candidate, 'mevcut_pozisyon', '') or ''
    cand_exp_years = candidate.get('toplam_deneyim_yil', 0) or getattr(candidate, 'toplam_deneyim_yil', 0) or 0
    cand_location = candidate.get('lokasyon', '') or getattr(candidate, 'lokasyon', '') or ''
    cand_education = candidate.get('egitim', '') or getattr(candidate, 'egitim', '') or ''

    # Pozisyon bilgilerini al
    pos_title = (
        position.get('baslik', '') or 
        position.get('name', '') or 
        getattr(position, 'baslik', '') or 
        getattr(position, 'name', '') or 
        ''
    )
    pos_dept = position.get('departman', '') or getattr(position, 'departman', '') or ''
    # Keywords okuma - öncelik sırası: keywords (JSON) > gerekli_beceriler (string)
    pos_keywords = ''
    if isinstance(position, dict):
        pos_keywords = position.get('keywords', '') or position.get('gerekli_beceriler', '')
    else:
        # Object ise attribute'lardan oku
        pos_keywords = getattr(position, 'keywords', '') or getattr(position, 'gerekli_beceriler', '')
    
    pos_exp_years = position.get('gerekli_deneyim_yil', 0) or getattr(position, 'gerekli_deneyim_yil', 0) or 0
    pos_education = position.get('gerekli_egitim', '') or getattr(position, 'gerekli_egitim', '') or ''
    pos_location = position.get('lokasyon', '') or getattr(position, 'lokasyon', '') or ''

    # Türkçe normalize fonksiyonu
    def turkish_lower(text):
        return text.replace('İ', 'i').replace('I', 'ı').lower()

    # Aranacak metin (Türkçe normalize)
    # skills'i de ekle - keyword eşleştirme için kritik
    # skills en önemli alan, mutlaka eklenmeli
    search_text = turkish_lower(' '.join(filter(None, [cv_text, skills, experience, current_pos])))
    

    # 1. Anahtar kelime eşleşmesi (40 puan)
    keywords = []
    if pos_keywords:
        if isinstance(pos_keywords, str):
            # JSON array string desteği: '["sap", "ms office", "erp"]'
            import json
            try:
                parsed_json = json.loads(pos_keywords)
                if isinstance(parsed_json, list):
                    keywords = [turkish_lower(str(k).strip()) for k in parsed_json if str(k).strip()]
                else:
                    keywords = [turkish_lower(k.strip()) for k in pos_keywords.split(',') if k.strip()]
            except (json.JSONDecodeError, TypeError):
                keywords = [turkish_lower(k.strip()) for k in pos_keywords.split(',') if k.strip()]
        elif isinstance(pos_keywords, list):
            parsed = []
            for k in pos_keywords:
                if ',' in k:
                    parsed.extend([sub.strip() for sub in k.split(',') if sub.strip()])
                else:
                    parsed.append(k.strip())
            keywords = [turkish_lower(k) for k in parsed if k]

    # Aday becerilerini orijinal halde tut (fuzzy matching için)
    skills_original = candidate.get('teknik_beceriler', '') or getattr(candidate, 'teknik_beceriler', '') or ''
    
    # 1. Anahtar kelime eşleşmesi (KEYWORD_WEIGHT puan)
    keyword_details = []
    points_per_keyword = float(KEYWORD_WEIGHT) / len(keywords) if keywords else 0
    
    # DEBUG: Keyword eşleştirme detayları
    logger.debug(f"calculate_match_score_keyword DEBUG:")
    logger.debug(f"  Position keywords: {keywords}")
    logger.debug(f"  Candidate skills: {skills_original[:200]}...")
    logger.debug(f"  Search text length: {len(search_text)}")
    logger.debug(f"  Points per keyword: {points_per_keyword}")
    
    for kw in keywords:
        found, matched_via, match_method = check_keyword_match(
            kw, search_text, skills_original, turkish_lower
        )
        if found:
            kw_points = round(points_per_keyword, 1)
            keyword_details.append({
                'keyword': kw,
                'matched': True,
                'matched_via': matched_via,
                'method': match_method,
                'points': kw_points
            })
            keyword_score += points_per_keyword
            matched_keywords_list.append(kw)
            logger.debug(f"  ✅ Keyword '{kw}' matched via {match_method} (matched_via: {matched_via}), +{points_per_keyword:.2f} points")
        else:
            keyword_details.append({
                'keyword': kw,
                'matched': False,
                'matched_via': None,
                'method': None,
                'points': 0
            })
            logger.debug(f"  ❌ Keyword '{kw}' NOT matched")
    
    keyword_score = int(round(keyword_score))
    score += keyword_score
    logger.debug(f"  Total keyword_score: {keyword_score}/{KEYWORD_WEIGHT} (matched {len(matched_keywords_list)}/{len(keywords)} keywords)")

    # 2. Deneyim uyumu (EXPERIENCE_WEIGHT puan)
    if pos_exp_years > 0:
        if cand_exp_years >= pos_exp_years:
            experience_score = EXPERIENCE_WEIGHT
            score += EXPERIENCE_WEIGHT
        elif cand_exp_years >= pos_exp_years * EXPERIENCE_MULTIPLIER:
            experience_score = 15
            score += 15
        elif cand_exp_years >= pos_exp_years * EXPERIENCE_HALF_MULTIPLIER:
            experience_score = 10
            score += 10

    # 3. Eğitim uyumu (EDUCATION_WEIGHT puan)
    education_levels = {
        'doktora': 5, 'phd': 5,
        'yüksek lisans': 4, 'master': 4, 'mba': 4,
        'lisans': 3, 'üniversite': 3, 'bachelor': 3,
        'ön lisans': 2, 'associate': 2,
        'lise': 1, 'high school': 1
    }

    cand_edu_level = 0
    pos_edu_level = 0

    for edu, level in education_levels.items():
        if edu in cand_education.lower():
            cand_edu_level = max(cand_edu_level, level)
        if edu in pos_education.lower():
            pos_edu_level = max(pos_edu_level, level)

    if pos_edu_level > 0:
        if cand_edu_level >= pos_edu_level:
            education_score = EDUCATION_WEIGHT
            score += EDUCATION_WEIGHT
        elif cand_edu_level == pos_edu_level - 1:
            education_score = 10
            score += 10

    # 4. Lokasyon uyumu (LOCATION_WEIGHT puan)
    if pos_location and cand_location:
        pos_loc_lower = pos_location.lower()
        cand_loc_lower = cand_location.lower()

        if pos_loc_lower in cand_loc_lower or cand_loc_lower in pos_loc_lower:
            location_score = LOCATION_WEIGHT
            score += LOCATION_WEIGHT
        # Şehir eşleşmesi
        elif any(city in cand_loc_lower for city in pos_loc_lower.split()):
            location_score = 10
            score += 10

    return {
        'total': min(score, 100),
        'keyword_score': keyword_score,
        'experience_score': experience_score,
        'education_score': education_score,
        'location_score': location_score,
        'matched_keywords': matched_keywords_list,
        'keyword_details': keyword_details,
        'total_keywords': len(keywords)
    }


def calculate_match_score(candidate, position, use_ai: bool = False, **kwargs):
    """Aday-pozisyon eşleşme skoru hesapla (wrapper)

    Default olarak keyword tabanlı puanlama kullanır.
    use_ai=True ile AI destekli puanlama aktifleştirilir.

    Args:
        candidate: Aday (dict, Candidate object)
        position: Pozisyon (dict, Position object)
        use_ai: True ise Claude AI ile puanlama yapar
        **kwargs: AI versiyonu için ek parametreler (knockout_criteria vb.)

    Returns:
        use_ai=True: Match objesi (detaylı analiz)
        use_ai=False: dict (detaylı puanlama sonucu)
    """
    if use_ai:
        return calculate_match_score_ai(candidate, position, **kwargs)
    return calculate_match_score_keyword(candidate, position)


def get_candidate_available_slots(candidate_id: int) -> int:
    """Adayın kaç pozisyona daha eklenebileceğini hesapla

    Args:
        candidate_id: Aday ID

    Returns:
        Kalan slot sayısı (0-5)
    """
    from database import get_candidate_position_count
    current = get_candidate_position_count(candidate_id)
    return max(0, MAX_POSITIONS_PER_CANDIDATE - current)


def recalculate_all_keyword_scores(company_id: int) -> dict:
    """Mevcut tüm candidate_positions kayıtları için 
    keyword skorlarını yeniden hesapla ve matches tablosuna kaydet.
    
    Bu fonksiyon bir kerelik migration amaçlı kullanılacak.
    
    Args:
        company_id: Firma ID
    
    Returns:
        dict: {'total': int, 'updated': int, 'errors': int}
    """
    from database import (
        get_connection, get_candidate, get_department_pools, save_match, get_candidates_by_ids
    )
    
    stats = {'total': 0, 'updated': 0, 'errors': 0}
    
    # candidate_positions tablosundan tüm kayıtları çek (company_id'ye göre)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.candidate_id, cp.position_id, cp.match_score
            FROM candidate_positions cp
            JOIN candidates c ON cp.candidate_id = c.id
            WHERE c.company_id = ?
        """, (company_id,))
        cp_records_raw = cursor.fetchall()
        # sqlite3.Row objelerini dict'e çevir
        cp_records = [dict(row) for row in cp_records_raw]
    
    stats['total'] = len(cp_records)
    
    # PERFORMANS: Tüm adayları tek sorguda çek (N+1 query sorununu önle)
    candidate_ids = [cp['candidate_id'] for cp in cp_records]
    candidates_map = get_candidates_by_ids(candidate_ids, company_id)
    
    # Tüm pozisyonları department_pools'dan çek (pool_type='position')
    pools = get_department_pools(company_id, include_inactive=False, pool_type='position')
    positions_dict = {}
    for pool in pools:
        if pool.get('is_system', 0):
            continue  # Sistem havuzlarını atla
        keywords_value = pool.get('keywords', '') or ''
        if keywords_value is None:
            keywords_value = ''
        position = {
            'id': pool['id'],
            'baslik': pool.get('name', ''),
            'name': pool.get('name', ''),
            'departman': '',
            'lokasyon': pool.get('lokasyon', '') or '',
            'gerekli_deneyim_yil': pool.get('gerekli_deneyim_yil', 0) or 0,
            'gerekli_egitim': pool.get('gerekli_egitim', '') or '',
            'gerekli_beceriler': '',
            'keywords': keywords_value,  # JSON string olarak
            'tercih_edilen_beceriler': ''
        }
        positions_dict[pool['id']] = position
    
    # Her kayıt için işlem yap
    for cp_record in cp_records:
        candidate_id = cp_record['candidate_id']
        position_id = cp_record['position_id']
        
        try:
            # Aday bilgilerini çek (batch fetch'ten)
            candidate = candidates_map.get(candidate_id)
            if not candidate:
                stats['errors'] += 1
                continue
            
            # Pozisyon bilgilerini çek (positions_dict'ten - zaten department_pools'dan okundu)
            position = positions_dict.get(position_id)
            
            # Eğer positions_dict'te yoksa, department_pools'tan direkt çek
            if not position:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, name, keywords, description, company_id, 
                               gerekli_deneyim_yil, gerekli_egitim, lokasyon
                        FROM department_pools
                        WHERE id = ? AND company_id = ? AND pool_type = 'position'
                    """, (position_id, company_id))
                    dp_row_raw = cursor.fetchone()
                    
                if not dp_row_raw:
                    stats['errors'] += 1
                    continue
                
                # sqlite3.Row objesini dict'e çevir
                dp_row = dict(dp_row_raw)
                keywords_value = dp_row.get('keywords', '') or ''
                if keywords_value is None:
                    keywords_value = ''
                
                # department_pools kaydını position dict formatına çevir
                position = {
                    'id': dp_row['id'],
                    'baslik': dp_row['name'],
                    'name': dp_row['name'],
                    'departman': '',
                    'lokasyon': dp_row.get('lokasyon', '') or '',
                    'gerekli_deneyim_yil': dp_row.get('gerekli_deneyim_yil', 0) or 0,
                    'gerekli_egitim': dp_row.get('gerekli_egitim', '') or '',
                    'gerekli_beceriler': '',
                    'keywords': keywords_value,  # JSON string olarak
                    'tercih_edilen_beceriler': ''
                }
            
            # Candidate objesini dict'e çevir
            if hasattr(candidate, '__dict__'):
                candidate_dict = {
                    'id': candidate.id,
                    'cv_raw_text': getattr(candidate, 'cv_raw_text', ''),
                    'teknik_beceriler': getattr(candidate, 'teknik_beceriler', ''),
                    'deneyim_detay': getattr(candidate, 'deneyim_detay', ''),
                    'mevcut_pozisyon': getattr(candidate, 'mevcut_pozisyon', ''),
                    'toplam_deneyim_yil': getattr(candidate, 'toplam_deneyim_yil', 0),
                    'lokasyon': getattr(candidate, 'lokasyon', ''),
                    'egitim': getattr(candidate, 'egitim', '')
                }
            else:
                candidate_dict = dict(candidate)
            
            # Skor hesapla
            score_result = calculate_match_score_keyword(candidate_dict, position)
            
            # Dict formatına çevir (backward compatibility)
            if isinstance(score_result, dict):
                total_score = score_result['total']
                keyword_score = score_result.get('keyword_score', 0)
                experience_score = score_result.get('experience_score', 0)
                education_score = score_result.get('education_score', 0)
                location_score = score_result.get('location_score', 0)
                matched_keywords = score_result.get('matched_keywords', [])
                keyword_details = score_result.get('keyword_details', [])
                total_keywords = score_result.get('total_keywords', 0)
            else:
                # Eski format (int)
                total_score = score_result
                keyword_score = 0
                experience_score = 0
                education_score = 0
                location_score = 0
                matched_keywords = []
                keyword_details = []
                total_keywords = 0
            
            # Match objesi oluştur ve kaydet
            import json
            detayli_analiz_json = json.dumps({
                'keyword_score': keyword_score,
                'experience_score': experience_score,
                'education_score': education_score,
                'location_score': location_score,
                'matched_keywords': matched_keywords,
                'keyword_details': keyword_details,
                'total_keywords': total_keywords
            }, ensure_ascii=False)
            
            match = Match(
                candidate_id=candidate_id,
                position_id=position_id,
                uyum_puani=total_score,
                deneyim_puani=experience_score,
                egitim_puani=education_score,
                beceri_puani=keyword_score,
                detayli_analiz=detayli_analiz_json
            )
            save_match(match)
            
            # candidate_positions.match_score'u güncelle
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE candidate_positions
                    SET match_score = ?
                    WHERE candidate_id = ? AND position_id = ?
                """, (total_score, candidate_id, position_id))
            
            stats['updated'] += 1
            
        except Exception as e:
            stats['errors'] += 1
            # Hata loglama
            logger.error(f"Hata (candidate_id={candidate_id}, position_id={position_id}): {e}", exc_info=True)
            continue
    
    return stats


def match_candidate_to_positions(*args, **kwargs):
    """Backward compatibility wrapper for match_candidate_to_positions
    
    Otomatik olarak doğru versiyonu seçer:
    - Candidate objesi ve positions listesi varsa -> AI versiyonu
    - candidate_id (int) ve company_id (int) varsa -> Keyword versiyonu
    
    Args:
        *args: Fonksiyon argümanları
        **kwargs: Fonksiyon keyword argümanları
    
    Returns:
        Eşleştirme sonuçları (AI veya Keyword versiyonuna göre)
    """
    # AI versiyonu: candidate (Candidate object) ve positions (list) parametreleri
    # Keyword versiyonu: candidate_id (int) ve company_id (int) parametreleri
    if len(args) >= 2:
        # İki parametre var - tip kontrolü yap
        first_arg = args[0]
        second_arg = args[1]
        
        # Eğer ilk parametre int ise ve ikinci parametre de int ise -> Keyword versiyonu
        if isinstance(first_arg, int) and isinstance(second_arg, int):
            return match_candidate_to_positions_keyword(*args, **kwargs)
        # Eğer ilk parametre Candidate veya dict ise ve ikinci parametre list ise -> AI versiyonu
        elif (isinstance(first_arg, (Candidate, dict)) and isinstance(second_arg, list)):
            return match_candidate_to_positions_ai(*args, **kwargs)
    
    # Varsayılan olarak AI versiyonunu dene (eski kodlar için)
    return match_candidate_to_positions_ai(*args, **kwargs)
