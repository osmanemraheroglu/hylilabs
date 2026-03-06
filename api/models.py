"""
TalentFlow Veri Modelleri
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """Aday modeli"""
    id: Optional[int] = None
    ad_soyad: str
    email: str
    telefon: Optional[str] = None
    lokasyon: Optional[str] = None

    # Egitim bilgileri
    egitim: Optional[str] = None
    universite: Optional[str] = None
    bolum: Optional[str] = None

    # Deneyim
    toplam_deneyim_yil: Optional[float] = None
    mevcut_pozisyon: Optional[str] = None
    mevcut_sirket: Optional[str] = None
    deneyim_detay: Optional[str] = None
    deneyim_aciklama: Optional[str] = None  # Görev tanımları (pipe-separated)

    # Beceriler
    teknik_beceriler: Optional[str] = None
    diller: Optional[str] = None
    sertifikalar: Optional[str] = None

    # Ek bilgiler
    ehliyet: Optional[str] = None
    askerlik: Optional[str] = None
    linkedin: Optional[str] = None
    ozet: Optional[str] = None

    # CV bilgisi
    cv_raw_text: Optional[str] = None
    cv_dosya_adi: Optional[str] = None
    cv_dosya_yolu: Optional[str] = None  # Kaydedilen CV dosyasinin yolu

    # Durum
    havuz: Optional[str] = "genel_havuz"
    durum: str = "yeni"
    notlar: Optional[str] = None

    # Tarihler
    olusturma_tarihi: datetime = Field(default_factory=datetime.now)
    guncelleme_tarihi: datetime = Field(default_factory=datetime.now)


class Position(BaseModel):
    """Pozisyon modeli"""
    id: Optional[int] = None
    baslik: str
    departman: Optional[str] = None
    lokasyon: Optional[str] = None

    # Gereksinimler
    aciklama: Optional[str] = None
    gerekli_deneyim_yil: Optional[float] = None
    gerekli_egitim: Optional[str] = None
    gerekli_beceriler: Optional[str] = None
    tercih_edilen_beceriler: Optional[str] = None

    # Durum
    aktif: bool = True
    acilis_tarihi: datetime = Field(default_factory=datetime.now)
    kapanis_tarihi: Optional[datetime] = None


class Application(BaseModel):
    """Basvuru modeli - Aday ile Pozisyon arasindaki iliski"""
    id: Optional[int] = None
    candidate_id: int
    position_id: Optional[int] = None  # None ise genel basvuru

    # Kaynak
    kaynak: str = "email"  # email, manuel, api
    email_id: Optional[str] = None

    # Tarih
    basvuru_tarihi: datetime = Field(default_factory=datetime.now)


class Match(BaseModel):
    """Eslestirme sonucu modeli"""
    id: Optional[int] = None
    candidate_id: int
    position_id: int

    # Puanlama
    uyum_puani: float = 0.0  # 0-100 arasi
    detayli_analiz: Optional[str] = None

    # Kriter bazli puanlar
    deneyim_puani: Optional[float] = None
    egitim_puani: Optional[float] = None
    beceri_puani: Optional[float] = None

    # Tarih
    hesaplama_tarihi: datetime = Field(default_factory=datetime.now)


class EmailLog(BaseModel):
    """Islenen email kaydi"""
    id: Optional[int] = None
    email_id: str  # IMAP message ID
    gonderen: str
    konu: str
    tarih: datetime
    ek_sayisi: int = 0
    islendi: bool = False
    hata: Optional[str] = None
    islem_tarihi: datetime = Field(default_factory=datetime.now)


class CVParseResult(BaseModel):
    """CV parse sonucu"""
    basarili: bool = True
    candidate: Optional[Candidate] = None
    hata_mesaji: Optional[str] = None
    raw_text: Optional[str] = None
    parsed_json: Optional[dict] = None  # Orijinal AI ciktisi
    cv_source: Optional[str] = None  # CV kaynağı: linkedin, kariyernet, yenibiris, secretcv, genel


class Interview(BaseModel):
    """Mulakat modeli"""
    id: Optional[int] = None
    candidate_id: int
    position_id: Optional[int] = None

    # Mulakat detaylari
    tarih: datetime
    sure_dakika: int = 60
    tur: str = "teknik"  # teknik, hr, yonetici, genel
    lokasyon: str = "online"  # online, ofis, telefon
    mulakatci: Optional[str] = None

    # Durum
    durum: str = "planlanmis"  # planlanmis, tamamlandi, iptal, ertelendi
    notlar: Optional[str] = None
    degerlendirme: Optional[str] = None  # Mulakat sonrasi degerlendirme
    puan: Optional[int] = None  # 1-5 arasi

    # Tarihler
    olusturma_tarihi: datetime = Field(default_factory=datetime.now)
