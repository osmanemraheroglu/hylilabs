"""
TalentFlow Konfigurasyon Ayarlari
Hassas bilgiler cevre degiskenlerinden okunur.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import base64
import hashlib

# Proje dizini
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# .env dosyasini yukle
load_dotenv(BASE_DIR / ".env")

# Email sifreleme anahtari
# Onemli: Uretimde bu anahtari .env dosyasinda saklayin!
# Yeni anahtar uretmek icin: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
_encryption_key = os.getenv("EMAIL_ENCRYPTION_KEY")
if not _encryption_key:
    # Fallback: SECRET_KEY'den turet (varsa) veya sabit bir seed kullan
    _secret = os.getenv("SECRET_KEY", "talentflow-default-secret-key-change-in-production")
    # 32 byte'lik anahtar olustur ve base64 kodla
    _key_bytes = hashlib.sha256(_secret.encode()).digest()
    _encryption_key = base64.urlsafe_b64encode(_key_bytes).decode()

EMAIL_ENCRYPTION_KEY = _encryption_key

# Veritabani
DATABASE_PATH = DATA_DIR / "talentflow.db"

# CV dosyalari
CV_STORAGE_PATH = DATA_DIR / "cvs"
SAVE_CV_FILES = True  # Orijinal CV dosyalarini sakla

# Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Email saglayici on tanimlar
EMAIL_PROVIDERS = {
    "gmail": {
        "name": "Gmail",
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "use_ssl": True,
        "note": "2 adimli dogrulama + uygulama sifresi gerekli"
    },
    "outlook": {
        "name": "Outlook / Microsoft 365",
        "imap_server": "outlook.office365.com",
        "imap_port": 993,
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": True,
        "note": "Microsoft 365 hesabi gerekli"
    },
    "yandex": {
        "name": "Yandex Mail",
        "imap_server": "imap.yandex.com",
        "imap_port": 993,
        "smtp_server": "smtp.yandex.com",
        "smtp_port": 587,
        "use_ssl": True,
        "note": "Yandex hesap ayarlarindan IMAP erisimi acilmali"
    },
    "custom": {
        "name": "Ozel Sunucu",
        "imap_server": "",
        "imap_port": 993,
        "smtp_server": "",
        "smtp_port": 587,
        "use_ssl": True,
        "note": "Sirket IT'den sunucu bilgilerini alin"
    }
}

# Varsayilan email ayarlari (geriye uyumluluk icin)
EMAIL_CONFIG = {
    "imap_server": os.getenv("IMAP_SERVER", "imap.gmail.com"),
    "imap_port": int(os.getenv("IMAP_PORT", "993")),
    "email": os.getenv("EMAIL_ADDRESS", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "folder": os.getenv("EMAIL_FOLDER", "INBOX"),
}

# SMTP ayarlari (gonderme)
SMTP_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "email": os.getenv("EMAIL_ADDRESS", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "sender_name": os.getenv("SENDER_NAME", "TalentFlow IK"),
}

# Sirket bilgileri (email sablonlari icin)
COMPANY_INFO = {
    "name": os.getenv("COMPANY_NAME", "Sirket Adi"),
    "address": os.getenv("COMPANY_ADDRESS", ""),
    "phone": os.getenv("COMPANY_PHONE", ""),
    "website": os.getenv("COMPANY_WEBSITE", ""),
}

# Aday havuzlari
CANDIDATE_POOLS = {
    "genel_havuz": {"label": "Genel Havuz", "color": "blue"},
    "pozisyon_havuzu": {"label": "Pozisyon Havuzu", "color": "green"},
    "arsiv": {"label": "Arşiv", "color": "gray"},
}

# CV parsing ayarlari
MAX_CV_SIZE_MB = 10
MAX_CV_FILE_SIZE = 10 * 1024 * 1024  # 10MB (bytes)
SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".doc"]

# Session Management
SESSION_TIMEOUT = 1800  # 30 dakika (saniye cinsinden)
SESSION_TIMEOUT_MINUTES = 30  # 30 dakika (geriye uyumluluk için)

# Cache
CACHE_TTL = 300  # 5 dakika (saniye cinsinden)

# Rate Limiting
MAX_LOGIN_ATTEMPTS = 5
MAX_CV_UPLOADS_PER_HOUR = 50

# Puanlama
FUZZY_MATCH_THRESHOLD = 80  # %80 ve üzeri benzerlik = eşleşme

# Uygulama ayarlari
APP_TITLE = "TalentFlow HR"
PAGE_ICON = "👥"

# Egitim seviyeleri
EDUCATION_LEVELS = [
    "Lise",
    "On Lisans",
    "Lisans",
    "Yuksek Lisans",
    "Doktora"
]

# Universite bolumleri - Kapsamli liste
UNIVERSITY_DEPARTMENTS = [
    # Muhendislik Fakultesi
    "Bilgisayar Muhendisligi",
    "Yazilim Muhendisligi",
    "Elektrik Muhendisligi",
    "Elektronik Muhendisligi",
    "Elektrik-Elektronik Muhendisligi",
    "Makine Muhendisligi",
    "Insaat Muhendisligi",
    "Endustri Muhendisligi",
    "Kimya Muhendisligi",
    "Cevre Muhendisligi",
    "Gida Muhendisligi",
    "Biyomedikal Muhendisligi",
    "Mekatronik Muhendisligi",
    "Otomotiv Muhendisligi",
    "Malzeme Muhendisligi",
    "Metalurji Muhendisligi",
    "Tekstil Muhendisligi",
    "Maden Muhendisligi",
    "Petrol ve Dogalgaz Muhendisligi",
    "Jeoloji Muhendisligi",
    "Harita Muhendisligi",
    "Sehir ve Bolge Planlama",
    "Uzay Muhendisligi",
    "Havacılık Muhendisligi",
    "Denizcilik Muhendisligi",
    "Gemi Insaati Muhendisligi",
    "Kontrol ve Otomasyon Muhendisligi",
    "Enerji Sistemleri Muhendisligi",
    "Yapay Zeka Muhendisligi",

    # Iktisadi ve Idari Bilimler / Isletme Fakultesi
    "Isletme",
    "Iktisat",
    "Maliye",
    "Calisma Ekonomisi",
    "Ekonometri",
    "Kamu Yonetimi",
    "Uluslararasi Iliskiler",
    "Uluslararasi Ticaret",
    "Siyaset Bilimi",
    "Lojistik Yonetimi",
    "Sağlık Yonetimi",
    "Turizm Isletmeciligi",
    "Bankacılık ve Finans",
    "Muhasebe ve Finansal Yonetim",
    "Pazarlama",
    "Insan Kaynaklari Yonetimi",
    "Yonetim Bilisim Sistemleri",

    # Hukuk Fakultesi
    "Hukuk",

    # Tip Fakultesi / Saglik Bilimleri
    "Tip",
    "Dis Hekimligi",
    "Eczacilik",
    "Hemsirelik",
    "Fizik Tedavi ve Rehabilitasyon",
    "Beslenme ve Diyetetik",
    "Ebelik",
    "Saglik Yonetimi",
    "Acil Yardim ve Afet Yonetimi",
    "Laborant ve Veteriner Saglik",
    "Radyoloji",
    "Anestezi",
    "Tibbi Laboratuvar",
    "Optik ve Optometri",
    "Odyoloji",
    "Cocuk Gelisimi",

    # Fen-Edebiyat / Fen Fakultesi
    "Matematik",
    "Fizik",
    "Kimya",
    "Biyoloji",
    "Molekuler Biyoloji",
    "Istatistik",
    "Turk Dili ve Edebiyati",
    "Ingiliz Dili ve Edebiyati",
    "Alman Dili ve Edebiyati",
    "Fransiz Dili ve Edebiyati",
    "Arap Dili ve Edebiyati",
    "Tarih",
    "Cografya",
    "Felsefe",
    "Sosyoloji",
    "Psikoloji",
    "Arkeoloji",
    "Sanat Tarihi",
    "Antropoloji",
    "Dilbilim",
    "Mutercim Tercumanlik",

    # Egitim Fakultesi
    "Okul Oncesi Ogretmenligi",
    "Sinif Ogretmenligi",
    "Turkce Ogretmenligi",
    "Ingilizce Ogretmenligi",
    "Almanca Ogretmenligi",
    "Matematik Ogretmenligi",
    "Fen Bilgisi Ogretmenligi",
    "Sosyal Bilgiler Ogretmenligi",
    "Rehberlik ve Psikolojik Danismanlik",
    "Ozel Egitim Ogretmenligi",
    "Beden Egitimi Ogretmenligi",
    "Muzik Ogretmenligi",
    "Resim-Is Ogretmenligi",
    "Bilgisayar ve Ogretim Teknolojileri",

    # Mimarlik / Guzel Sanatlar
    "Mimarlik",
    "Ic Mimarlik",
    "Peyzaj Mimarligi",
    "Endustriyel Tasarim",
    "Grafik Tasarim",
    "Tekstil ve Moda Tasarimi",
    "Seramik ve Cam Tasarimi",
    "Gorsel Iletisim Tasarimi",
    "Resim",
    "Heykel",
    "Geleneksel Turk Sanatlari",

    # Iletisim Fakultesi
    "Gazetecilik",
    "Halkla Iliskiler ve Tanitim",
    "Radyo Televizyon ve Sinema",
    "Reklamcilik",
    "Gorsel Iletisim",
    "Yeni Medya",
    "Iletisim Tasarimi",

    # Ziraat / Veteriner
    "Ziraat Muhendisligi",
    "Veteriner",
    "Bahce Bitkileri",
    "Tarla Bitkileri",
    "Toprak Bilimi",
    "Tarimsal Yapilar ve Sulama",
    "Gıda Isleme",
    "Bitki Koruma",
    "Hayvansal Uretim",
    "Su Urunleri",

    # Spor Bilimleri
    "Spor Yonetimi",
    "Antrenorluk Egitimi",
    "Rekreasyon",
    "Spor Bilimleri",

    # Ilahiyat
    "Ilahiyat",
    "Islam Bilimleri",

    # Diger
    "Diger"
]

# Fakulte bazli bolum gruplamasi (autocomplete icin)
FACULTY_DEPARTMENTS = {
    "Muhendislik": [
        "Bilgisayar Muhendisligi",
        "Yazilim Muhendisligi",
        "Elektrik Muhendisligi",
        "Elektronik Muhendisligi",
        "Elektrik-Elektronik Muhendisligi",
        "Makine Muhendisligi",
        "Insaat Muhendisligi",
        "Endustri Muhendisligi",
        "Kimya Muhendisligi",
        "Cevre Muhendisligi",
        "Gida Muhendisligi",
        "Biyomedikal Muhendisligi",
        "Mekatronik Muhendisligi",
        "Otomotiv Muhendisligi",
        "Malzeme Muhendisligi",
        "Metalurji Muhendisligi",
        "Tekstil Muhendisligi",
        "Maden Muhendisligi",
        "Petrol ve Dogalgaz Muhendisligi",
        "Jeoloji Muhendisligi",
        "Harita Muhendisligi",
        "Sehir ve Bolge Planlama",
        "Uzay Muhendisligi",
        "Havacılık Muhendisligi",
        "Denizcilik Muhendisligi",
        "Gemi Insaati Muhendisligi",
        "Kontrol ve Otomasyon Muhendisligi",
        "Enerji Sistemleri Muhendisligi",
        "Yapay Zeka Muhendisligi",
    ],
    "Isletme / Iktisadi Idari Bilimler": [
        "Isletme",
        "Iktisat",
        "Maliye",
        "Calisma Ekonomisi",
        "Ekonometri",
        "Kamu Yonetimi",
        "Uluslararasi Iliskiler",
        "Uluslararasi Ticaret",
        "Siyaset Bilimi",
        "Lojistik Yonetimi",
        "Sağlık Yonetimi",
        "Turizm Isletmeciligi",
        "Bankacılık ve Finans",
        "Muhasebe ve Finansal Yonetim",
        "Pazarlama",
        "Insan Kaynaklari Yonetimi",
        "Yonetim Bilisim Sistemleri",
    ],
    "Hukuk": ["Hukuk"],
    "Tip / Saglik Bilimleri": [
        "Tip",
        "Dis Hekimligi",
        "Eczacilik",
        "Hemsirelik",
        "Fizik Tedavi ve Rehabilitasyon",
        "Beslenme ve Diyetetik",
        "Ebelik",
        "Saglik Yonetimi",
        "Acil Yardim ve Afet Yonetimi",
        "Radyoloji",
        "Anestezi",
        "Tibbi Laboratuvar",
        "Optik ve Optometri",
        "Odyoloji",
        "Cocuk Gelisimi",
    ],
    "Fen-Edebiyat": [
        "Matematik",
        "Fizik",
        "Kimya",
        "Biyoloji",
        "Molekuler Biyoloji",
        "Istatistik",
        "Turk Dili ve Edebiyati",
        "Ingiliz Dili ve Edebiyati",
        "Alman Dili ve Edebiyati",
        "Fransiz Dili ve Edebiyati",
        "Arap Dili ve Edebiyati",
        "Tarih",
        "Cografya",
        "Felsefe",
        "Sosyoloji",
        "Psikoloji",
        "Arkeoloji",
        "Sanat Tarihi",
        "Antropoloji",
        "Dilbilim",
        "Mutercim Tercumanlik",
    ],
    "Egitim": [
        "Okul Oncesi Ogretmenligi",
        "Sinif Ogretmenligi",
        "Turkce Ogretmenligi",
        "Ingilizce Ogretmenligi",
        "Almanca Ogretmenligi",
        "Matematik Ogretmenligi",
        "Fen Bilgisi Ogretmenligi",
        "Sosyal Bilgiler Ogretmenligi",
        "Rehberlik ve Psikolojik Danismanlik",
        "Ozel Egitim Ogretmenligi",
        "Beden Egitimi Ogretmenligi",
        "Muzik Ogretmenligi",
        "Resim-Is Ogretmenligi",
        "Bilgisayar ve Ogretim Teknolojileri",
    ],
    "Mimarlik / Guzel Sanatlar": [
        "Mimarlik",
        "Ic Mimarlik",
        "Peyzaj Mimarligi",
        "Endustriyel Tasarim",
        "Grafik Tasarim",
        "Tekstil ve Moda Tasarimi",
        "Seramik ve Cam Tasarimi",
        "Gorsel Iletisim Tasarimi",
        "Resim",
        "Heykel",
        "Geleneksel Turk Sanatlari",
    ],
    "Iletisim": [
        "Gazetecilik",
        "Halkla Iliskiler ve Tanitim",
        "Radyo Televizyon ve Sinema",
        "Reklamcilik",
        "Gorsel Iletisim",
        "Yeni Medya",
        "Iletisim Tasarimi",
    ],
    "Ziraat / Veteriner": [
        "Ziraat Muhendisligi",
        "Veteriner",
        "Bahce Bitkileri",
        "Tarla Bitkileri",
        "Toprak Bilimi",
        "Tarimsal Yapilar ve Sulama",
        "Gıda Isleme",
        "Bitki Koruma",
        "Hayvansal Uretim",
        "Su Urunleri",
    ],
    "Spor Bilimleri": [
        "Spor Yonetimi",
        "Antrenorluk Egitimi",
        "Rekreasyon",
        "Spor Bilimleri",
    ],
}

def search_departments(query: str, limit: int = 10) -> list:
    """Bolum ara - yazilan metne gore oneri don"""
    if not query or len(query) < 2:
        return []

    query_lower = query.lower().replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ğ", "g").replace("ç", "c")
    results = []

    # Oncelik 1: Baslangicla eslesenler
    for dept in UNIVERSITY_DEPARTMENTS:
        dept_lower = dept.lower().replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ğ", "g").replace("ç", "c")
        if dept_lower.startswith(query_lower):
            # Fakulteyi bul
            fakulte = None
            for fak, bolumler in FACULTY_DEPARTMENTS.items():
                if dept in bolumler:
                    fakulte = fak
                    break
            results.append({"bolum": dept, "fakulte": fakulte})

    # Oncelik 2: Icinde gecenler (baslangicta olmayanlar)
    for dept in UNIVERSITY_DEPARTMENTS:
        dept_lower = dept.lower().replace("ı", "i").replace("ö", "o").replace("ü", "u").replace("ş", "s").replace("ğ", "g").replace("ç", "c")
        if query_lower in dept_lower and not dept_lower.startswith(query_lower):
            fakulte = None
            for fak, bolumler in FACULTY_DEPARTMENTS.items():
                if dept in bolumler:
                    fakulte = fak
                    break
            results.append({"bolum": dept, "fakulte": fakulte})

    return results[:limit]

# Diller ve seviyeleri
LANGUAGES = [
    "Turkce",
    "Ingilizce",
    "Almanca",
    "Fransizca",
    "Ispanyolca",
    "Italyanca",
    "Rusca",
    "Arapca",
    "Cince",
    "Japonca",
    "Korece",
    "Portekizce",
    "Hollandaca"
]

LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Anadil"]

# Departmanlar
DEPARTMENTS = [
    "Yazilim Gelistirme",
    "Urun Yonetimi",
    "Tasarim / UX",
    "Veri Bilimi",
    "DevOps / Altyapi",
    "Kalite Guvence (QA)",
    "Insan Kaynaklari",
    "Finans / Muhasebe",
    "Pazarlama",
    "Satis",
    "Musteri Hizmetleri",
    "Hukuk",
    "Operasyon",
    "Yonetim",
    "Diger"
]

# Lokasyonlar
LOCATIONS = [
    "Istanbul (Avrupa)",
    "Istanbul (Anadolu)",
    "Ankara",
    "Izmir",
    "Bursa",
    "Antalya",
    "Konya",
    "Adana",
    "Gaziantep",
    "Kocaeli",
    "Uzaktan (Remote)",
    "Hibrit",
    "Diger"
]

# Kriter tipleri
CRITERIA_TYPES = {
    "egitim": {"label": "Egitim Kriteri", "icon": "🎓"},
    "deneyim": {"label": "Deneyim Kriteri", "icon": "💼"},
    "dil": {"label": "Dil Kriteri", "icon": "🌍"},
    "beceri": {"label": "Beceri Kriteri", "icon": "⚡"},
    "lokasyon": {"label": "Lokasyon Kriteri", "icon": "📍"},
    "sertifika": {"label": "Sertifika Kriteri", "icon": "📜"}
}

# Pozisyon havuz durumlari
POOL_STATUSES = {
    "beklemede": {"label": "Beklemede", "color": "gray"},
    "inceleniyor": {"label": "Inceleniyor", "color": "blue"},
    "mulakat": {"label": "Mulakat", "color": "orange"},
    "teklif": {"label": "Teklif", "color": "green"},
    "red": {"label": "Reddedildi", "color": "red"},
    "kabul": {"label": "Kabul Edildi", "color": "green"}
}


# ============ KVKK METİNLERİ (2025 Güncel) ============

KVKK_AYDINLATMA_METNI = """
## KİŞİSEL VERİLERİN KORUNMASI HAKKINDA AYDINLATMA METNİ

6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") uyarınca, kişisel verileriniz aşağıda açıklanan çerçevede işlenmektedir.

### 1. Veri Sorumlusu
{firma_adi} ("Şirket") olarak, KVKK kapsamında veri sorumlusu sıfatıyla hareket etmekteyiz.

### 2. İşlenen Kişisel Veriler
- **Kimlik bilgileri:** Ad, soyad
- **İletişim bilgileri:** Telefon numarası, e-posta adresi
- **Özgeçmiş bilgileri:** Eğitim geçmişi, iş deneyimi, beceriler, sertifikalar
- **Mesleki yeterlilik bilgileri:** Dil becerileri, teknik yetkinlikler

### 3. İşleme Amaçları
Kişisel verileriniz aşağıdaki amaçlarla işlenmektedir:
- İşe alım süreçlerinin yürütülmesi
- Aday değerlendirme ve seçme işlemlerinin gerçekleştirilmesi
- İletişim faaliyetlerinin yürütülmesi
- Yasal yükümlülüklerin yerine getirilmesi

### 4. Hukuki Sebepler
KVKK madde 5/2 kapsamında:
- Bir sözleşmenin kurulması veya ifasıyla doğrudan doğruya ilgili olması
- Veri sorumlusunun meşru menfaatleri için veri işlenmesinin zorunlu olması
- Veri sorumlusunun hukuki yükümlülüğünü yerine getirebilmesi için zorunlu olması

### 5. Veri Aktarımı
Kişisel verileriniz, KVKK madde 8 ve madde 9 çerçevesinde:
- İş ortakları ve hizmet sağlayıcılara
- Yasal zorunluluk halinde yetkili kamu kurum ve kuruluşlarına
aktarılabilir.

### 6. Saklama Süresi
Kişisel verileriniz, işleme amacının gerektirdiği süre boyunca ve ilgili mevzuatta öngörülen yasal saklama süreleri dahilinde muhafaza edilir. İşe alım süreçleri için başvuru tarihinden itibaren 2 yıl saklanır.

### 7. Haklarınız (KVKK Madde 11)
Kanun'un 11. maddesi uyarınca aşağıdaki haklara sahipsiniz:
- Kişisel verilerinizin işlenip işlenmediğini öğrenme
- Kişisel verileriniz işlenmişse buna ilişkin bilgi talep etme
- Kişisel verilerinizin işlenme amacını ve bunların amacına uygun kullanılıp kullanılmadığını öğrenme
- Yurt içinde veya yurt dışında kişisel verilerinizin aktarıldığı üçüncü kişileri bilme
- Kişisel verilerinizin eksik veya yanlış işlenmiş olması hâlinde bunların düzeltilmesini isteme
- KVKK madde 7 çerçevesinde kişisel verilerinizin silinmesini veya yok edilmesini isteme
- Düzeltme ve silme işlemlerinin kişisel verilerinizin aktarıldığı üçüncü kişilere bildirilmesini isteme
- İşlenen verilerin münhasıran otomatik sistemler vasıtasıyla analiz edilmesi suretiyle aleyhinize bir sonucun ortaya çıkmasına itiraz etme
- Kişisel verilerinizin kanuna aykırı olarak işlenmesi sebebiyle zarara uğramanız hâlinde zararın giderilmesini talep etme

### 8. Başvuru
Haklarınızı kullanmak için **{iletisim_email}** adresine başvurabilirsiniz.

**Güncellenme Tarihi:** {tarih}
"""

KVKK_ACIK_RIZA_METNI = """
## AÇIK RIZA BEYANI

6698 sayılı Kişisel Verilerin Korunması Kanunu kapsamında, yukarıdaki aydınlatma metnini okudum ve anladım.

Özgeçmişimde yer alan kişisel verilerimin **{firma_adi}** tarafından işe alım süreçlerinde kullanılmak üzere:
- İşlenmesine
- Saklanmasına
- Gerekli hallerde üçüncü kişilerle paylaşılmasına

**açık rızam ile onay veriyorum.**

Bu onayımı dilediğim zaman **{iletisim_email}** adresine başvurarak geri alabileceğimi biliyorum.
"""

KVKK_VERI_TALEBI_TURLERI = [
    "Kişisel verilerimin işlenip işlenmediğini öğrenme",
    "Kişisel verilerime ilişkin bilgi talep etme",
    "Kişisel verilerimin işlenme amacını öğrenme",
    "Kişisel verilerimin aktarıldığı üçüncü kişileri öğrenme",
    "Kişisel verilerimin düzeltilmesi",
    "Kişisel verilerimin silinmesi/yok edilmesi",
    "Düzeltme/silme işlemlerinin üçüncü kişilere bildirilmesi",
    "Otomatik analiz sonuçlarına itiraz"
]
