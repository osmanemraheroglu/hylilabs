"""
SmartPromptBuilder - Scoring V3 Prompt Oluşturucu

CV verisi + Pozisyon verisi → AI değerlendirme prompt'u oluşturur.
Türkiye İK piyasasına özel, Türkçe prompt üretir.

V2 Entegrasyonu:
- position_data["v2_keywords"] → Pozisyon anahtar kelimeleri
- position_data["v2_synonyms"] → Onaylı eş anlamlılar
- position_data["v2_titles"] → Onaylı pozisyon başlıkları

Kullanım:
    builder = SmartPromptBuilder()
    prompt = builder.build_evaluation_prompt(candidate_data, position_data)
"""

from typing import Any, Dict, List, Optional, Union


# ═══════════════════════════════════════════════════════════════════════════════
# SABİT PROMPTLAR
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Sen Türkiye'de 20 yıllık deneyime sahip, Fortune 500 şirketlerinde çalışmış kıdemli bir İnsan Kaynakları Direktörüsün. Binlerce CV değerlendirdin ve yüzlerce pozisyon için işe alım yaptın.

GÖREV: Verilen adayı, verilen pozisyon için 0-100 puan üzerinden değerlendir.

═══════════════════════════════════════════════════════════════════════════════
⚠️ KRİTİK: HALÜSİNASYON ÖNLEME KURALLARI (MUTLAKA UYULMALI)
═══════════════════════════════════════════════════════════════════════════════

1. SADECE CV'DE AÇIKÇA BELİRTİLEN BİLGİLERE PUAN VER
   - CV'de yazmayan bir beceri için ASLA puan verme
   - "Muhtemelen biliyordur", "Tahminimce", "Olası" gibi varsayımlarda BULUNMA
   - Eğer bir bilgi CV'de yoksa → O kategori için 0 puan

2. ÇIKARIM YAPMA, VARSAYIMDA BULUNMA
   ❌ YANLIŞ: "Python biliyor → muhtemelen Git de biliyordur"
   ✅ DOĞRU: "Python biliyor, Git CV'de belirtilmemiş → Git için 0 puan"

3. BELİRSİZLİK DURUMUNDA
   - Bilgi eksik veya belirsizse → 0 puan ver
   - "Belirtilmemiş" veya "CV'de mevcut değil" olarak reason'da belirt
   - ASLA boşlukları tahminle doldurma

4. ÖRTÜK DENEYİM TESPİTİ (İSTİSNA)
   Sadece şu kalıplar için örtük beceri kabul edilebilir:
   - "X kişilik ekip yönettim" → Ekip Yönetimi (evidence_from_cv'de belirt)
   - "Y projesini baştan sona yönettim" → Proje Yönetimi (evidence_from_cv'de belirt)
   - "Z bütçeyi planladım/yönettim" → Bütçe Yönetimi (evidence_from_cv'de belirt)
   Bu durumlar dışında örtük beceri KABUL ETMİYORUZ.

5. ZORUNLU KANIT
   - Her verdiğin puan için CV'den somut kanıt göster
   - Kanıt gösteremiyorsan → O beceri için puan verme

═══════════════════════════════════════════════════════════════════════════════
PUANLAMA MATRİSİ (100 PUAN)
═══════════════════════════════════════════════════════════════════════════════

KATMAN 0 - ÖN ELEME (KNOCKOUT):
Aşağıdaki durumlardan BİRİ varsa eligible=false ve score=0:
- Tamamen farklı kariyer yolu (örn: aşçı → yazılımcı, muhasebeci → elektrik mühendisi)
- Eğitim seviyesi yetersiz (pozisyon lisans istiyorsa lise mezunu)

NOT: Şunlar ELEME SEBEBİ DEĞİL, sadece not düşülür:
- Lokasyon uyumsuzluğu
- Deneyim yılı eksikliği
- Askerlik durumu
- Ehliyet eksikliği

KATMAN 1 - POZİSYON UYUMU (25 puan):
- Mevcut/önceki pozisyon unvanları ne kadar benzer?
- Aynı sektörde mi çalışmış?
- Kariyer yönü uyumlu mu?

KATMAN 2 - DENEYİM KALİTESİ (25 puan):
- Toplam deneyim süresi yeterli mi?
- İlgili deneyim süresi ne kadar?
- Deneyim güncelliği (son 2 yıl daha değerli)
- Şirket kalitesi/büyüklüğü

KATMAN 3 - TEKNİK YETKİNLİK (25 puan):
- Gerekli teknik beceriler var mı?
- Tercih edilen beceriler var mı?
- Eksik kritik beceriler var mı?
- Semantik eşleşme: "Siemens S7" = "PLC programlama", "REST API" = "Web servisleri"

KATMAN 4 - EĞİTİM UYUMU (15 puan):
- Eğitim seviyesi uygun mu?
- Bölüm/alan uyumlu mu?
- Üniversite kalitesi (bonus, zorunlu değil)

KATMAN 5 - DİĞER FAKTÖRLER (10 puan):
- Yabancı dil (varsa)
- Sertifikalar (varsa)
- Lokasyon uyumu (not: eleme sebebi değil)

═══════════════════════════════════════════════════════════════════════════════
SEMANTİK EŞLEŞTİRME KURALLARI
═══════════════════════════════════════════════════════════════════════════════

Aşağıdaki becerileri EŞDEĞER kabul et:
- PLC programlama = Siemens S7 = Allen Bradley = Omron PLC
- SCADA = HMI programlama = Otomasyon sistemleri
- REST API = Web servisleri = API geliştirme
- Python = Django = Flask = FastAPI (Python framework'leri)
- AutoCAD = CAD = 2D çizim
- SolidWorks = 3D modelleme = CAD/CAM
- MS Project = Proje yönetimi yazılımı = Primavera
- Elektrik tesisatı = Güç sistemleri = Enerji dağıtım

Transferable skills (aktarılabilir beceriler) için puan ver:
- Proje yönetimi deneyimi → herhangi bir yönetici pozisyonu için değerli
- Ekip liderliği → koordinasyon gerektiren roller için değerli
- Müşteri ilişkileri → satış/destek rolleri için değerli

═══════════════════════════════════════════════════════════════════════════════
ÖNEMLİ UYARILAR
═══════════════════════════════════════════════════════════════════════════════

1. OVERQUALIFIED (AŞIRI NİTELİKLİ) DEĞERLENDİRME KURALLARI:

   OVERQUALIFIED TESPİT KRİTERLERİ (herhangi biri geçerliyse):

   A) UNVAN FARKI (2+ SEVİYE):
      Seviye Hiyerarşisi: Stajyer < Uzman < Kıdemli/Senior < Müdür < Direktör < Genel Müdür
      - Pozisyon: Uzman, Aday: Direktör (3 seviye fark) → OVERQUALIFIED
      - Pozisyon: Uzman, Aday: Müdür (2 seviye fark) → OVERQUALIFIED
      - Pozisyon: Uzman, Aday: Kıdemli (1 seviye fark) → NORMAL
      - Pozisyon: Müdür, Aday: Direktör (1 seviye fark) → NORMAL

   B) DENEYİM FARKI (3X FAZLA):
      - Pozisyon: 3-5 yıl, Aday: 15+ yıl (3x+) → OVERQUALIFIED
      - Pozisyon: 5-7 yıl, Aday: 12 yıl (~2x) → NORMAL
      - Pozisyon: 2-3 yıl, Aday: 10 yıl (3x+) → OVERQUALIFIED

   OVERQUALIFIED TESPİT EDİLDİĞİNDE:
   - eligible = true (Aday uygun, sadece risk var)
   - position_match puanı DÜŞÜR:
     * Normal aday: 20-25 puan
     * Overqualified aday: 10-15 puan (motivasyon riski nedeniyle)
   - weaknesses dizisine EKLE:
     * "Overqualified: [Sebep - örn: Direktör seviyesinden Uzman pozisyonuna başvuru]"
   - notes_for_hr dizisine EKLE:
     * "⚠️ Overqualified riski: Motivasyon ve bağlılık konuları görüşmede sorulmalı"
     * "Maaş beklentisi ve kariyer hedefleri netleştirilmeli"
   - interview_questions dizisine EKLE:
     * "Bu pozisyon sizin için kariyer olarak bir geri adım gibi görünüyor, motivasyonunuz nedir?"
     * "Uzun vadeli kariyer hedefleriniz neler, bu pozisyon bunlara nasıl uyuyor?"

2. KARİYER DEĞİŞİKLİĞİ adaylarını dikkatli değerlendir:
   - Eğer ilgili sertifika/kurs almışsa → geçiş motivasyonu var demektir
   - Tamamen alakasız ise → ELEME

3. TÜM KARİYER GEÇMİŞİNİ değerlendir:
   - Sadece son pozisyona bakma
   - 10 yıl önce ilgili deneyimi varsa da değerli

4. TÜRKÇE ÖZEL DURUMLAR:
   - "Stajyer" = entry-level, deneyimsiz
   - "Uzman" = 3-5 yıl deneyim
   - "Kıdemli/Senior" = 5+ yıl deneyim
   - "Müdür/Yönetici" = 7+ yıl + ekip yönetimi
   - "Direktör" = 10+ yıl + departman yönetimi
"""


JSON_SCHEMA = """{
  "eligible": true veya false,
  "elimination_reason": "Eğer eligible=false ise sebep, değilse null",
  "scores": {
    "position_match": {
      "score": 0-25 arası puan,
      "reason": "Kısa açıklama"
    },
    "experience_quality": {
      "score": 0-25 arası puan,
      "reason": "Kısa açıklama"
    },
    "technical_skills": {
      "score": 0-25 arası puan,
      "matched_skills": ["eşleşen", "beceriler"],
      "missing_skills": ["eksik", "beceriler"],
      "reason": "Kısa açıklama"
    },
    "education": {
      "score": 0-15 arası puan,
      "reason": "Kısa açıklama"
    },
    "other": {
      "score": 0-10 arası puan,
      "reason": "Kısa açıklama (dil, sertifika, lokasyon)"
    }
  },
  "total_score": 0-100 arası toplam puan,
  "keyword_match_ratio": 0.0-1.0 arası (eşleşen keyword / toplam keyword),
  "strengths": ["Güçlü yön 1", "Güçlü yön 2", "Güçlü yön 3"],
  "weaknesses": ["Zayıf yön 1", "Zayıf yön 2"],
  "notes_for_hr": ["İK için not 1", "İK için not 2"],
  "interview_questions": ["Mülakatta sorulacak soru 1", "Soru 2"],
  "overall_assessment": "2-3 cümlelik genel değerlendirme",

  "⚠️ ZORUNLU ALANLAR": {
    "scores": "MUTLAKA doldurulmalı - 5 kategorinin hepsi (position_match, experience_quality, technical_skills, education, other) için score ve reason yazılmalı",
    "total_score": "scores içindeki 5 kategorinin toplamı olmalı (max 100)",
    "uyari": "scores alanı BOŞ bırakılamaz, aksi halde değerlendirme GEÇERSİZ sayılır"
  }
}"""


EVALUATION_TEMPLATE = """
═══════════════════════════════════════════════════════════════════════════════
POZİSYON BİLGİLERİ
═══════════════════════════════════════════════════════════════════════════════

Pozisyon: {position_title}
Şirket: {company_name}
Lokasyon: {position_location}
Gerekli Deneyim: {required_experience}
Gerekli Eğitim: {required_education}

Aranan Nitelikler:
{position_requirements}

Teknik Beceriler/Anahtar Kelimeler:
{position_keywords}

═══════════════════════════════════════════════════════════════════════════════
İK TARAFINDAN BELİRLENEN KRİTERLER (V2 VERİLERİ)
═══════════════════════════════════════════════════════════════════════════════

Aranan Anahtar Kelimeler ({v2_keyword_count} adet):
{v2_keywords_formatted}

Kabul Edilen Eş Anlamlılar:
{v2_synonyms_formatted}

Uyumlu Pozisyon Başlıkları:
{v2_titles_formatted}

───────────────────────────────────────────────────────────────────────────────
V2 KEYWORD EŞLEŞME TALİMATI:
───────────────────────────────────────────────────────────────────────────────
- Adayın CV'sinde bulunan keyword sayısını / toplam keyword sayısına böl
- Bu oran %70+ ise YÜKSEK eşleşme (teknik beceri puanı yüksek)
- %40-70 arası ORTA eşleşme (teknik beceri puanı orta)
- %40 altı DÜŞÜK eşleşme (teknik beceri puanı düşük)
- keyword_match_ratio alanına bu oranı yaz (0.0-1.0 arası)

───────────────────────────────────────────────────────────────────────────────
V2 SYNONYM AĞIRLIK TALİMATI:
───────────────────────────────────────────────────────────────────────────────
- Eş anlamlı eşleşmesi de keyword eşleşmesi sayılır
- weight değeri 0.9+ ise TAM eşleşme (keyword bulunmuş sayılır)
- weight değeri 0.7-0.9 ise KISMİ eşleşme (0.8 keyword sayılır)
- weight değeri 0.7 altı ise ZAYIF eşleşme (0.5 keyword sayılır)

───────────────────────────────────────────────────────────────────────────────
V2 TITLE EŞLEŞME TALİMATI:
───────────────────────────────────────────────────────────────────────────────
- Adayın son pozisyon başlığı "exact" listesinde varsa → pozisyon uyumu YÜKSEK (+20-25 puan)
- "related" listesinde varsa → pozisyon uyumu ORTA (+10-15 puan)
- Hiçbirinde yoksa → pozisyon uyumu DÜŞÜK (+0-10 puan)

═══════════════════════════════════════════════════════════════════════════════
ADAY BİLGİLERİ
═══════════════════════════════════════════════════════════════════════════════

Ad Soyad: {candidate_name}
E-posta: {candidate_email}
Lokasyon: {candidate_location}
Toplam Deneyim: {candidate_experience}
Eğitim: {candidate_education}

Mevcut/Son Pozisyon: {current_position}
Mevcut/Son Şirket: {current_company}

Kariyer Geçmişi:
{career_history}

Teknik Beceriler:
{candidate_skills}

Sertifikalar:
{certifications}

Yabancı Dil:
{languages}

═══════════════════════════════════════════════════════════════════════════════
DEĞERLENDİRME TALİMATI
═══════════════════════════════════════════════════════════════════════════════

1. Yukarıdaki V2 anahtar kelimelerini CV'de ARA
2. Eş anlamlıları da kabul et (örn: "forklift" yerine "fork lift" geçerli)
3. Pozisyon başlıkları uyumunu değerlendir (exact > related > yok)
4. Puanlama matrisine göre 0-100 puan ver
5. SADECE JSON formatında yanıt ver, başka hiçbir şey yazma

⚠️ KRİTİK TALİMAT:
Aşağıdaki JSON şemasına TAMAMEN uymalısın. "scores" alanı ZORUNLUDUR.
Her kategori için puan (score) ve gerekçe (reason) MUTLAKA yazılmalı.
scores alanını BOŞ bırakma, aksi halde değerlendirme geçersiz sayılır.
total_score = position_match + experience_quality + technical_skills + education + other toplamı olmalıdır.

{json_schema}
"""


class SmartPromptBuilder:
    """
    CV ve Pozisyon verisinden AI değerlendirme promptu oluşturur.
    Türkiye İK piyasasına özel, Türkçe prompt üretir.

    V2 Entegrasyonu:
    - position_data["v2_keywords"] → Pozisyon anahtar kelimeleri
    - position_data["v2_synonyms"] → Onaylı eş anlamlılar
    - position_data["v2_titles"] → Onaylı pozisyon başlıkları
    """

    def __init__(self):
        """SmartPromptBuilder başlat"""
        self.system_prompt = self._build_system_prompt()

    # ═══════════════════════════════════════════════════════════════════════════
    # P0-B: AI DATA MASKING - KVKK UYUMLULUĞU
    # ═══════════════════════════════════════════════════════════════════════════

    def _mask_personal_data(self, value: str, prefix: str = "MASKED") -> str:
        """
        Kişisel veriyi AI servisleri için maskeler.
        KVKK uyumluluğu için zorunlu - AI'ya gerçek kişisel veri gönderilmez.

        Args:
            value: Maskelenecek değer
            prefix: Maskeleme prefix'i (ADAY, SIRKET, FIRMA)

        Returns:
            str: Maskelenmiş değer
        """
        if not value or str(value).strip() == "" or value == "Belirtilmemiş":
            return "Belirtilmemiş"
        return f"{prefix}_MASKED"

    def _build_system_prompt(self) -> str:
        """
        AI için sabit sistem promptu döndürür.

        Returns:
            str: Sistem promptu metni
        """
        return SYSTEM_PROMPT

    def build_evaluation_prompt(
        self,
        candidate_data: Dict[str, Any],
        position_data: Dict[str, Any]
    ) -> str:
        """
        Aday ve pozisyon verisinden değerlendirme promptu oluşturur.

        Args:
            candidate_data: Aday bilgileri dict'i
                - name/ad_soyad: Aday adı
                - email: E-posta
                - lokasyon: Lokasyon
                - toplam_deneyim_yil: Deneyim yılı
                - egitim: Eğitim seviyesi
                - mevcut_pozisyon: Mevcut pozisyon
                - mevcut_sirket: Mevcut şirket
                - teknik_beceriler: Teknik beceriler
                - sertifikalar: Sertifikalar
                - diller: Diller
                - parsed_data: CV parse edilmiş veri (opsiyonel)
                - cv_raw_text: Ham CV metni (opsiyonel)
                - deneyim_detay: Deneyim detayları (opsiyonel)
                - deneyim_aciklama: Deneyim açıklamaları (opsiyonel)

            position_data: Pozisyon bilgileri dict'i
                - name/title/pozisyon_adi: Pozisyon adı
                - company_name/sirket: Şirket adı
                - lokasyon: Lokasyon
                - gerekli_deneyim_yil: Gerekli deneyim
                - gerekli_egitim: Gerekli eğitim
                - description/aranan_nitelikler: Aranan nitelikler
                - keywords: Anahtar kelimeler
                - v2_keywords: V2 anahtar kelimeleri (opsiyonel)
                - v2_synonyms: V2 eş anlamlıları (opsiyonel)
                - v2_titles: V2 pozisyon başlıkları (opsiyonel)

        Returns:
            str: AI'ya gönderilecek tam prompt metni (system + evaluation)
        """
        # V2 verilerini formatla
        v2_keywords = position_data.get("v2_keywords", [])
        v2_synonyms = position_data.get("v2_synonyms", {})
        v2_titles = position_data.get("v2_titles", {"exact": [], "related": []})

        v2_keywords_formatted = self._format_v2_keywords(v2_keywords)
        v2_synonyms_formatted = self._format_v2_synonyms(v2_synonyms)
        v2_titles_formatted = self._format_v2_titles(v2_titles)

        # JSON şemasını al
        json_schema = self._get_json_schema()

        # Değişkenleri hazırla
        # P0-B: Kişisel veriler maskeleniyor (KVKK uyumluluğu)
        template_vars = {
            # Pozisyon bilgileri
            "position_title": self._safe_get(position_data, "name", "title", "pozisyon_adi"),
            # P0-B: Firma adı maskelendi
            "company_name": self._mask_personal_data(
                self._safe_get(position_data, "company_name", "sirket", "company"), "FIRMA"
            ),
            "position_location": self._safe_get(position_data, "lokasyon", "location"),
            "required_experience": self._format_experience_years(
                self._safe_get(position_data, "gerekli_deneyim_yil", "experience_years", default=None)
            ),
            "required_education": self._safe_get(position_data, "gerekli_egitim", "education"),
            "position_requirements": self._format_requirements(position_data),
            "position_keywords": self._format_keywords(position_data),

            # V2 verileri
            "v2_keyword_count": len(v2_keywords),
            "v2_keywords_formatted": v2_keywords_formatted,
            "v2_synonyms_formatted": v2_synonyms_formatted,
            "v2_titles_formatted": v2_titles_formatted,

            # Aday bilgileri - P0-B: Kişisel veriler maskelendi
            "candidate_name": self._mask_personal_data(
                self._safe_get(candidate_data, "name", "ad_soyad"), "ADAY"
            ),
            "candidate_email": "masked@privacy.local",  # P0-B: Email maskelendi
            "candidate_location": self._safe_get(candidate_data, "lokasyon", "location"),
            "candidate_experience": self._format_experience_years(
                self._safe_get(candidate_data, "toplam_deneyim_yil", "experience_years", default=None)
            ),
            "candidate_education": self._extract_education(candidate_data),
            "current_position": self._safe_get(candidate_data, "mevcut_pozisyon", "current_position"),
            # P0-B: Şirket adı maskelendi
            "current_company": self._mask_personal_data(
                self._safe_get(candidate_data, "mevcut_sirket", "current_company"), "SIRKET"
            ),
            "career_history": self._extract_career_history(candidate_data),
            "candidate_skills": self._extract_skills(candidate_data),
            "certifications": self._safe_get(candidate_data, "sertifikalar", "certifications"),
            "languages": self._safe_get(candidate_data, "diller", "languages"),

            # JSON şeması
            "json_schema": json_schema
        }

        # Template'i doldur
        evaluation_prompt = EVALUATION_TEMPLATE.format(**template_vars)

        # System prompt + Evaluation prompt birleştir
        full_prompt = f"{self.system_prompt}\n\n{evaluation_prompt}"

        return full_prompt

    # ═══════════════════════════════════════════════════════════════════════════
    # V2 VERİ FORMATLAMA FONKSİYONLARI
    # ═══════════════════════════════════════════════════════════════════════════

    def _format_v2_keywords(self, keywords: List[str]) -> str:
        """
        V2 keyword listesini bullet points formatında döndürür.

        Args:
            keywords: Keyword listesi

        Returns:
            Formatlanmış string (bullet points)
        """
        if not keywords:
            return "• (Henüz İK tarafından keyword belirlenmemiş)"

        lines = []
        for kw in keywords:
            if kw:
                lines.append(f"• {kw}")

        if not lines:
            return "• (Henüz İK tarafından keyword belirlenmemiş)"

        return "\n".join(lines)

    def _format_v2_synonyms(self, synonyms: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        V2 synonym dict'ini keyword: [synonyms] formatında döndürür.

        Args:
            synonyms: {keyword: [{synonym, weight, type}, ...]}

        Returns:
            Formatlanmış string
        """
        if not synonyms:
            return "• (Henüz İK tarafından eş anlamlı belirlenmemiş)"

        lines = []
        for keyword, synonym_list in synonyms.items():
            if synonym_list:
                # Synonym'ları weight'e göre sırala
                sorted_synonyms = sorted(synonym_list, key=lambda x: x.get("weight", 0), reverse=True)

                # En fazla 5 synonym göster
                synonym_texts = []
                for syn in sorted_synonyms[:5]:
                    weight = syn.get("weight", 0.85)
                    synonym_text = syn.get("synonym", "")
                    if synonym_text:
                        # Weight'i yüzde olarak göster
                        weight_pct = int(weight * 100)
                        synonym_texts.append(f"{synonym_text} ({weight_pct}%)")

                if synonym_texts:
                    lines.append(f"• {keyword}: {', '.join(synonym_texts)}")

        if not lines:
            return "• (Henüz İK tarafından eş anlamlı belirlenmemiş)"

        return "\n".join(lines)

    def _format_v2_titles(self, titles: Dict[str, List[str]]) -> str:
        """
        V2 title dict'ini exact/related formatında döndürür.

        Args:
            titles: {exact: [...], related: [...]}

        Returns:
            Formatlanmış string
        """
        exact_titles = titles.get("exact", [])
        related_titles = titles.get("related", [])

        if not exact_titles and not related_titles:
            return "• (Henüz İK tarafından pozisyon başlığı belirlenmemiş)"

        lines = []

        if exact_titles:
            lines.append("TAM EŞLEŞME (exact):")
            for title in exact_titles[:10]:  # Max 10
                lines.append(f"  • {title}")

        if related_titles:
            if exact_titles:
                lines.append("")  # Boş satır
            lines.append("İLİŞKİLİ (related):")
            for title in related_titles[:10]:  # Max 10
                lines.append(f"  • {title}")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════════════════════
    # MEVCUT YARDIMCI FONKSİYONLAR
    # ═══════════════════════════════════════════════════════════════════════════

    def _format_candidate_section(self, candidate_data: Dict[str, Any]) -> str:
        """
        Aday bilgilerini formatlı metin olarak döndürür.

        Args:
            candidate_data: Aday bilgileri dict'i

        Returns:
            str: Formatlanmış aday bilgileri
        """
        lines = []

        # Temel bilgiler
        name = self._safe_get(candidate_data, "name", "ad_soyad")
        email = self._safe_get(candidate_data, "email")
        location = self._safe_get(candidate_data, "lokasyon", "location")

        lines.append(f"Ad Soyad: {name}")
        lines.append(f"E-posta: {email}")
        lines.append(f"Lokasyon: {location}")

        # Deneyim
        experience = self._safe_get(candidate_data, "toplam_deneyim_yil", "experience_years", default=None)
        if experience is not None:
            lines.append(f"Toplam Deneyim: {experience} yıl")

        # Eğitim
        education = self._extract_education(candidate_data)
        lines.append(f"Eğitim: {education}")

        # Mevcut pozisyon
        current_pos = self._safe_get(candidate_data, "mevcut_pozisyon", "current_position")
        current_company = self._safe_get(candidate_data, "mevcut_sirket", "current_company")
        lines.append(f"Mevcut Pozisyon: {current_pos}")
        lines.append(f"Mevcut Şirket: {current_company}")

        # Kariyer geçmişi
        career = self._extract_career_history(candidate_data)
        if career and career != "Belirtilmemiş":
            lines.append(f"\nKariyer Geçmişi:\n{career}")

        # Teknik beceriler
        skills = self._extract_skills(candidate_data)
        lines.append(f"\nTeknik Beceriler: {skills}")

        # Sertifikalar
        certs = self._safe_get(candidate_data, "sertifikalar", "certifications")
        if certs and certs != "Belirtilmemiş":
            lines.append(f"Sertifikalar: {certs}")

        # Diller
        languages = self._safe_get(candidate_data, "diller", "languages")
        if languages and languages != "Belirtilmemiş":
            lines.append(f"Yabancı Dil: {languages}")

        return "\n".join(lines)

    def _format_position_section(self, position_data: Dict[str, Any]) -> str:
        """
        Pozisyon gereksinimlerini formatlı metin olarak döndürür.

        Args:
            position_data: Pozisyon bilgileri dict'i

        Returns:
            str: Formatlanmış pozisyon bilgileri
        """
        lines = []

        # Temel bilgiler
        title = self._safe_get(position_data, "name", "title", "pozisyon_adi")
        company = self._safe_get(position_data, "company_name", "sirket", "company")
        location = self._safe_get(position_data, "lokasyon", "location")

        lines.append(f"Pozisyon: {title}")
        lines.append(f"Şirket: {company}")
        lines.append(f"Lokasyon: {location}")

        # Gereksinimler
        exp = self._safe_get(position_data, "gerekli_deneyim_yil", "experience_years", default=None)
        if exp is not None:
            lines.append(f"Gerekli Deneyim: {exp} yıl")

        edu = self._safe_get(position_data, "gerekli_egitim", "education")
        lines.append(f"Gerekli Eğitim: {edu}")

        # Aranan nitelikler
        requirements = self._format_requirements(position_data)
        if requirements and requirements != "Belirtilmemiş":
            lines.append(f"\nAranan Nitelikler:\n{requirements}")

        # Anahtar kelimeler
        keywords = self._format_keywords(position_data)
        if keywords and keywords != "Belirtilmemiş":
            lines.append(f"\nTeknik Beceriler/Anahtar Kelimeler:\n{keywords}")

        return "\n".join(lines)

    def _get_json_schema(self) -> str:
        """
        Beklenen JSON çıktı şemasını döndürür.

        Returns:
            str: JSON şema metni
        """
        return JSON_SCHEMA

    def _extract_career_history(self, candidate_data: Dict[str, Any]) -> str:
        """
        CV parsed_data veya diğer alanlardan kariyer geçmişini formatlı string olarak çıkarır.

        Format:
        • [2020-2024] Şirket Adı - Pozisyon
          Sorumluluklar: ...

        Args:
            candidate_data: Aday bilgileri dict'i

        Returns:
            str: Formatlanmış kariyer geçmişi
        """
        lines = []

        # 1. parsed_data'dan experience çıkar
        parsed_data = candidate_data.get("parsed_data", {})
        if isinstance(parsed_data, str):
            try:
                import json
                parsed_data = json.loads(parsed_data)
            except (json.JSONDecodeError, TypeError):
                parsed_data = {}

        experience_list = parsed_data.get("experience", []) or parsed_data.get("is_deneyimi", [])

        if experience_list and isinstance(experience_list, list):
            for exp in experience_list[:5]:  # Max 5 deneyim
                if isinstance(exp, dict):
                    company = exp.get("company", exp.get("sirket", ""))
                    title = exp.get("title", exp.get("pozisyon", ""))
                    years = exp.get("years", exp.get("tarih", ""))
                    description = exp.get("description", exp.get("aciklama", ""))

                    if company or title:
                        line = f"• [{years}] {company} - {title}" if years else f"• {company} - {title}"
                        lines.append(line)
                        if description:
                            # Açıklamayı kısalt (max 150 karakter)
                            desc_short = description[:150] + "..." if len(description) > 150 else description
                            lines.append(f"  Sorumluluklar: {desc_short}")

        # 2. deneyim_detay alanından çıkar (fallback)
        if not lines:
            deneyim_detay = candidate_data.get("deneyim_detay", "")
            if deneyim_detay:
                # "Pozisyon @ Şirket | Pozisyon2 @ Şirket2" formatını parse et
                parts = deneyim_detay.split("|")
                for part in parts[:5]:
                    part = part.strip()
                    if "@" in part:
                        pos, company = part.split("@", 1)
                        lines.append(f"• {company.strip()} - {pos.strip()}")
                    elif part:
                        lines.append(f"• {part}")

        # 3. deneyim_aciklama alanından çıkar (son fallback)
        if not lines:
            deneyim_aciklama = candidate_data.get("deneyim_aciklama", "")
            if deneyim_aciklama:
                # Açıklamayı paragraf olarak döndür
                return deneyim_aciklama[:500] + ("..." if len(deneyim_aciklama) > 500 else "")

        # 4. cv_raw_text'ten özet çıkar (son çare)
        if not lines:
            cv_raw = candidate_data.get("cv_raw_text", "")
            if cv_raw:
                # EXPERIENCE bölümünü bul
                cv_lower = cv_raw.lower()
                exp_start = cv_lower.find("experience")
                if exp_start == -1:
                    exp_start = cv_lower.find("deneyim")

                if exp_start != -1:
                    exp_section = cv_raw[exp_start:exp_start + 800]
                    return exp_section.strip()

        if lines:
            return "\n".join(lines)

        return "Belirtilmemiş"

    def _extract_skills(self, candidate_data: Dict[str, Any]) -> str:
        """
        CV parsed_data veya teknik_beceriler alanından becerileri çıkarır.

        Args:
            candidate_data: Aday bilgileri dict'i

        Returns:
            str: Virgülle ayrılmış beceri listesi
        """
        skills = []

        # 1. teknik_beceriler alanından
        teknik = candidate_data.get("teknik_beceriler", "")
        if teknik:
            if isinstance(teknik, list):
                skills.extend(teknik)
            elif isinstance(teknik, str):
                # Virgülle ayrılmış veya satır satır olabilir
                if "," in teknik:
                    skills.extend([s.strip() for s in teknik.split(",") if s.strip()])
                else:
                    skills.extend([s.strip() for s in teknik.split("\n") if s.strip()])

        # 2. parsed_data'dan skills çıkar
        if not skills:
            parsed_data = candidate_data.get("parsed_data", {})
            if isinstance(parsed_data, str):
                try:
                    import json
                    parsed_data = json.loads(parsed_data)
                except (json.JSONDecodeError, TypeError):
                    parsed_data = {}

            skills_data = parsed_data.get("skills", []) or parsed_data.get("beceriler", [])
            if skills_data:
                if isinstance(skills_data, list):
                    skills.extend(skills_data)
                elif isinstance(skills_data, str):
                    skills.extend([s.strip() for s in skills_data.split(",") if s.strip()])

        # 3. skills parametresinden (test verileri için)
        if not skills:
            skills_param = candidate_data.get("skills", [])
            if isinstance(skills_param, list):
                skills.extend(skills_param)

        if skills:
            # Unique skills, sırayı koru
            seen = set()
            unique_skills = []
            for s in skills:
                s_lower = s.lower() if isinstance(s, str) else str(s)
                if s_lower not in seen:
                    seen.add(s_lower)
                    unique_skills.append(s)
            return ", ".join(unique_skills[:20])  # Max 20 beceri

        return "Belirtilmemiş"

    def _extract_education(self, candidate_data: Dict[str, Any]) -> str:
        """
        CV parsed_data veya egitim alanından eğitim bilgisini çıkarır.

        Format: Derece - Bölüm - Üniversite (Yıl)

        Args:
            candidate_data: Aday bilgileri dict'i

        Returns:
            str: Formatlanmış eğitim bilgisi
        """
        # 1. Doğrudan egitim alanından
        egitim = candidate_data.get("egitim", "") or candidate_data.get("education", "")
        bolum = candidate_data.get("bolum", "") or candidate_data.get("field", "")
        universite = candidate_data.get("universite", "") or candidate_data.get("university", "")

        if egitim:
            parts = [egitim]
            if bolum:
                parts.append(bolum)
            if universite:
                parts.append(universite)
            return " - ".join(parts)

        # 2. parsed_data'dan education çıkar
        parsed_data = candidate_data.get("parsed_data", {})
        if isinstance(parsed_data, str):
            try:
                import json
                parsed_data = json.loads(parsed_data)
            except (json.JSONDecodeError, TypeError):
                parsed_data = {}

        education_data = parsed_data.get("education", {}) or parsed_data.get("egitim", {})

        if isinstance(education_data, dict):
            degree = education_data.get("degree", education_data.get("derece", ""))
            field = education_data.get("field", education_data.get("bolum", ""))
            university = education_data.get("university", education_data.get("universite", ""))
            year = education_data.get("year", education_data.get("yil", ""))

            parts = []
            if degree:
                parts.append(degree)
            if field:
                parts.append(field)
            if university:
                parts.append(university)
            if year:
                parts.append(f"({year})")

            if parts:
                return " - ".join(parts)

        elif isinstance(education_data, list) and education_data:
            # Liste ise ilk elemanı al
            first_edu = education_data[0]
            if isinstance(first_edu, dict):
                return self._extract_education({"parsed_data": {"education": first_edu}})
            elif isinstance(first_edu, str):
                return first_edu

        return "Belirtilmemiş"

    def _format_requirements(self, position_data: Dict[str, Any]) -> str:
        """
        Pozisyon gereksinimlerini formatlar.

        Args:
            position_data: Pozisyon bilgileri dict'i

        Returns:
            str: Formatlanmış gereksinimler
        """
        # Farklı alan adlarını dene
        requirements = (
            position_data.get("description", "") or
            position_data.get("aranan_nitelikler", "") or
            position_data.get("requirements", "") or
            position_data.get("is_tanimi", "")
        )

        if requirements:
            return requirements

        return "Belirtilmemiş"

    def _format_keywords(self, position_data: Dict[str, Any]) -> str:
        """
        Pozisyon anahtar kelimelerini formatlar.

        Args:
            position_data: Pozisyon bilgileri dict'i

        Returns:
            str: Formatlanmış anahtar kelimeler
        """
        keywords = position_data.get("keywords", [])

        if not keywords:
            return "Belirtilmemiş"

        if isinstance(keywords, list):
            # Liste içinde liste olabilir (DB'den gelen format)
            flat_keywords = []
            for kw in keywords:
                if isinstance(kw, list):
                    flat_keywords.extend(kw)
                elif isinstance(kw, str):
                    # JSON string olabilir
                    if kw.startswith("["):
                        try:
                            import json
                            parsed = json.loads(kw)
                            if isinstance(parsed, list):
                                flat_keywords.extend(parsed)
                        except (json.JSONDecodeError, TypeError):
                            flat_keywords.append(kw)
                    else:
                        # Tırnak işaretlerini temizle
                        clean_kw = kw.strip('"\'[]')
                        if clean_kw:
                            flat_keywords.append(clean_kw)

            if flat_keywords:
                return ", ".join(flat_keywords)

        elif isinstance(keywords, str):
            # Virgülle ayrılmış string
            return keywords

        return "Belirtilmemiş"

    def _format_experience_years(self, years: Any) -> str:
        """
        Deneyim yılını formatlar.

        Args:
            years: Deneyim yılı (int, float, str veya None)

        Returns:
            str: Formatlanmış deneyim yılı
        """
        if years is None:
            return "Belirtilmemiş"

        try:
            years_float = float(years)
            if years_float == int(years_float):
                return f"{int(years_float)} yıl"
            else:
                return f"{years_float:.1f} yıl"
        except (ValueError, TypeError):
            return str(years) if years else "Belirtilmemiş"

    def _safe_get(self, data: Dict[str, Any], *keys: str, default: str = "Belirtilmemiş") -> Any:
        """
        Nested dictionary'den güvenli veri çeker.
        Birden fazla anahtar dener, ilk bulunan değeri döner.

        Args:
            data: Veri dict'i
            *keys: Denenecek anahtarlar
            default: Varsayılan değer (hiçbiri bulunamazsa)

        Returns:
            Bulunan değer veya default
        """
        for key in keys:
            if "." in key:
                # Nested key (örn: "parsed_data.name")
                parts = key.split(".")
                value = data
                try:
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break
                    if value is not None:
                        return value
                except (KeyError, TypeError, AttributeError):
                    continue
            else:
                value = data.get(key)
                if value is not None and value != "":
                    return value

        return default


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 77)
    print("SmartPromptBuilder Test (V2 Entegrasyonu)")
    print("=" * 77)

    builder = SmartPromptBuilder()

    # Test verisi - Gerçek veri formatında
    candidate = {
        "ad_soyad": "Emir Kaan Yıldız",
        "email": "emir.yildiz.eng@gmail.com",
        "lokasyon": "Tekirdağ",
        "toplam_deneyim_yil": 10,
        "egitim": "Yüksek Lisans",
        "bolum": "Elektrik ve Elektronik Mühendisliği",
        "universite": "Kocaeli Üniversitesi",
        "mevcut_pozisyon": "Electrical & Instrument Manager",
        "mevcut_sirket": "Khor Mor Gas Field Expansion Project",
        "teknik_beceriler": "SCADA, ETAP, AutoCAD, SolidWorks, E-PLAN, MS Project",
        "sertifikalar": None,
        "diller": "İngilizce (İleri)",
        "deneyim_detay": "Electrical & Instrument Manager @ Khor Mor | QC Chief @ Combined Cycle Power Plant"
    }

    position = {
        "name": "Gas Groups System Integration Specialist",
        "company_name": "AKSA",
        "lokasyon": "Tekirdağ",
        "gerekli_deneyim_yil": 3,
        "gerekli_egitim": "Lisans",
        "description": """Aranan Nitelikler:
• Elektrik Mühendisliği mezunu
• Minimum 3 yıl deneyim
• SCADA, AutoCAD, E-PLAN bilgisi
• İngilizce (yazılı ve sözlü)""",
        "keywords": ["scada", "autocad", "e-plan", "solidworks", "etap"],
        # V2 verileri
        "v2_keywords": ["scada", "autocad", "e-plan", "solidworks", "etap", "plc", "hmi"],
        "v2_synonyms": {
            "scada": [
                {"synonym": "supervisory control", "weight": 0.95, "type": "exact_synonym"},
                {"synonym": "otomasyon sistemi", "weight": 0.85, "type": "turkish"}
            ],
            "plc": [
                {"synonym": "siemens s7", "weight": 0.90, "type": "exact_synonym"},
                {"synonym": "allen bradley", "weight": 0.90, "type": "exact_synonym"}
            ]
        },
        "v2_titles": {
            "exact": ["Sistem Entegrasyon Uzmanı", "System Integration Specialist"],
            "related": ["Otomasyon Mühendisi", "Elektrik Mühendisi", "SCADA Mühendisi"]
        }
    }

    # Prompt oluştur
    prompt = builder.build_evaluation_prompt(candidate, position)

    print(f"\nOluşturulan prompt uzunluğu: {len(prompt)} karakter")
    print(f"Tahmini token sayısı: ~{len(prompt) // 4}")
    print("\n" + "-" * 77)
    print("PROMPT ÖNİZLEME (ilk 3000 karakter):")
    print("-" * 77)
    print(prompt[:3000])
    print("\n... (devamı var)")
    print("\n" + "=" * 77)
    print("TEST TAMAMLANDI")
    print("=" * 77)
