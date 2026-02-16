# -*- coding: utf-8 -*-
"""
Job Scraper - İlan URL'lerinden pozisyon bilgilerini çeker
Bright Data Web Unlocker API kullanarak kariyer.net ilanlarını scrape eder
"""

import requests
import os
import json
import anthropic
import re
from bs4 import BeautifulSoup
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY", "")
BRIGHT_DATA_ZONE = os.getenv("BRIGHT_DATA_ZONE", "web_unlocker1")


def scrape_kariyer_net(url: str) -> dict:
    """Bright Data Web Unlocker ile kariyer.net ilanını çeker"""
    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}"
            },
            json={
                "zone": BRIGHT_DATA_ZONE,
                "url": url,
                "format": "raw"
            },
            timeout=60
        )
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Gereksiz etiketleri kaldır
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'meta', 'link', 'noscript']):
                tag.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            # Çoklu boşlukları temizle
            text = re.sub(r'\s+', ' ', text)
            
            # Sadece ilan içeriğini kes
            start_markers = ["İş İlanı Hakkında", "İlan Hakkında"]
            end_markers = ["Şirket Hakkında", "Şirketin Diğer İlanları", "Benzer İlanlar", "Bu İlanı Paylaş"]
            
            start_idx = 0
            for marker in start_markers:
                idx = text.find(marker)
                if idx != -1:
                    start_idx = idx
                    break
            
            end_idx = len(text)
            for marker in end_markers:
                idx = text.find(marker)
                if idx != -1 and idx > start_idx:
                    end_idx = idx
                    break
            
            clean_text = text[start_idx:end_idx].strip()
            
            # Aday Kriterleri bölümünü de ekle (deneyim, eğitim bilgisi için)
            aday_idx = text.find("Aday Kriterleri")
            if aday_idx != -1:
                aday_end = text.find("Şirket Hakkında", aday_idx)
                if aday_end == -1:
                    aday_end = aday_idx + 500
                clean_text += " " + text[aday_idx:aday_end].strip()
            
            # Maksimum 3000 karakter
            clean_text = clean_text[:3000]
            
            return {"basarili": True, "text": clean_text}
        else:
            return {"basarili": False, "hata": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"basarili": False, "hata": str(e)}


def parse_job_with_ai(text: str) -> dict:
    """Claude API ile ilan metnini analiz eder.

    Args:
        text: İlan ham metni

    Returns:
        Yapılandırılmış ilan verisi dict

    Raises:
        ValueError: API anahtarı eksik veya parse hatası
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY ayarlanmamış")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=60.0)

    JOB_PARSE_PROMPT = """İş ilanından şu bilgileri çıkar:

1. pozisyon_adi: Tırnak içindeki pozisyon adı
2. firma: Şirket adı (ilk cümlede geçen)
3. lokasyon: Şehir/ilçe (örn: "İstanbul", "Ankara", "İzmir")
4. deneyim_yil: Minimum deneyim yılı SAYI olarak (örn: "3-5 yıl" → 3, "En az 5 yıl" → 5, "5+" → 5)
5. egitim_seviyesi: İstenen eğitim seviyesi STANDART FORMATTA (Lise, Ön Lisans, Lisans, Yüksek Lisans, Doktora)
   - "Üniversite(Mezun)" → "Lisans"
   - "Yüksek Lisans" → "Yüksek Lisans"
   - "Lise" → "Lise"
6. tercih_edilen_bolum: Tercih edilen bölüm/fakülte (örn: "Yapı Mühendisliği")
7. askerlik: Askerlik durumu (örn: "Yapılmış", "Muaf", "Belirtilmemiş")
8. yabanci_dil: Dil ve seviye (örn: "İngilizce - İyi")
9. keywords: Teknik programlar ve standartlar listesi
   - Metinde 2 veya daha fazla kez tekrar eden mesleki/teknik terimler varsa (örn: çizim, proje, tasarım, analiz, rapor, kontrol, yönetim, planlama, koordinasyon), bunları da keywords listesine ekle. Genel kelimeler (ve, ile, için, olan, gibi) hariç.
10. aranan_nitelikler: İlandaki "Aranan Nitelikler" veya "Genel Nitelikler" bölümünü madde madde çıkar. Her maddeyi "• " ile başlat. Örnek: "• En az 5 yıl deneyim\n• Lisans mezunu\n• İyi düzeyde İngilizce"
11. is_tanimi: İlandaki "İş Tanımı" veya "Görev Tanımı" bölümünü madde madde çıkar. Her maddeyi "• " ile başlat. Örnek: "• Proje yönetimi yapmak\n• Müşteri ilişkilerini yürütmek\n• Raporlama yapmak"

ÖRNEK ÇIKTI:
{{
    "pozisyon_adi": "Dizayn Mühendisi",
    "firma": "STFA İnşaat Grubu",
    "lokasyon": "İstanbul",
    "deneyim_yil": 5,
    "egitim_seviyesi": "Lisans",
    "tercih_edilen_bolum": "Yapı Mühendisliği",
    "askerlik": "Yapılmış",
    "yabanci_dil": "İngilizce - İyi",
    "keywords": ["SAP2000", "ETABS", "TEKLA", "AutoCAD", "EC", "ACI", "AISC"],
    "aranan_nitelikler": "• En az 5 yıl deneyim\n• Lisans mezunu\n• İyi düzeyde İngilizce\n• SAP2000 ve ETABS bilgisi",
    "is_tanimi": "• Statik ve dinamik analiz yapmak\n• Proje çizimlerini hazırlamak\n• Şantiye koordinasyonu yapmak\n• Teknik raporlama yapmak"
}}

ÖNEMLİ:
- deneyim_yil SAYI olmalı (string değil, örn: 3, 5, 0)
- egitim_seviyesi STANDART FORMATTA olmalı: Lise, Ön Lisans, Lisans, Yüksek Lisans, Doktora
- lokasyon sadece şehir adı (ilçe bilgisi varsa parantez içinde: "İstanbul(Avr.)" → "İstanbul")
- aranan_nitelikler: İlandaki "Aranan Nitelikler" veya "Genel Nitelikler" bölümünü madde madde çıkar. Her maddeyi "• " ile başlat.
- is_tanimi: İlandaki "İş Tanımı" veya "Görev Tanımı" bölümünü madde madde çıkar. Her maddeyi "• " ile başlat.

SADECE JSON döndür.

İlan:
{job_text}
"""

    prompt_content = JOB_PARSE_PROMPT.format(job_text=text[:15000])

    # Retry mekanizması (max 2 deneme)
    import time
    max_retries = 2
    message = None

    for attempt in range(1, max_retries + 1):
        try:
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt_content}]
            )
            break
        except anthropic.APITimeoutError:
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise ValueError(f"Claude API zaman aşımı: {max_retries} deneme sonrası yanıt alınamadı")
        except anthropic.APIConnectionError:
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise ValueError(f"Claude API bağlantı hatası: {max_retries} deneme sonrası bağlanılamadı")
        except anthropic.APIStatusError as e:
            if e.status_code in (429, 500, 502, 503, 529) and attempt < max_retries:
                time.sleep(3)
                continue
            raise ValueError(f"Claude API hatası (HTTP {e.status_code}): {e.message}")

    # JSON parse
    response_text = message.content[0].text.strip()

    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        if end == -1:
            end = len(response_text)
        response_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        if end == -1:
            end = len(response_text)
        response_text = response_text[start:end].strip()

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        brace_start = response_text.find('{')
        brace_end = response_text.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                parsed = json.loads(response_text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                raise ValueError(f"JSON parse hatası: {e}\nYanıt: {response_text[:500]}")
        else:
            raise ValueError(f"JSON parse hatası: {e}\nYanıt: {response_text[:500]}")

    if not isinstance(parsed, dict):
        raise ValueError(f"Beklenmeyen yanıt formatı: dict beklendi, {type(parsed).__name__} geldi")

    # Default değerler
    parsed.setdefault("pozisyon_adi", None)
    parsed.setdefault("firma", None)
    parsed.setdefault("lokasyon", None)
    parsed.setdefault("deneyim_yil", 0)
    
    # deneyim_yil'i sayıya çevir
    if parsed.get("deneyim_yil"):
        try:
            if isinstance(parsed["deneyim_yil"], str):
                # "5+", "3-5", "En az 5" gibi formatları parse et
                import re
                numbers = re.findall(r'\d+', parsed["deneyim_yil"])
                if numbers:
                    parsed["deneyim_yil"] = float(numbers[0])
                else:
                    parsed["deneyim_yil"] = 0
            elif isinstance(parsed["deneyim_yil"], (int, float)):
                parsed["deneyim_yil"] = float(parsed["deneyim_yil"])
            else:
                parsed["deneyim_yil"] = 0
        except (ValueError, TypeError):
            parsed["deneyim_yil"] = 0
    else:
        parsed["deneyim_yil"] = 0
    
    # egitim_seviyesi'ni standart formata çevir
    if parsed.get("egitim_seviyesi"):
        egitim = str(parsed["egitim_seviyesi"]).strip()
        # Standart formatlara çevir
        if "lise" in egitim.lower():
            parsed["egitim_seviyesi"] = "Lise"
        elif "ön lisans" in egitim.lower() or "önlisans" in egitim.lower():
            parsed["egitim_seviyesi"] = "Ön Lisans"
        elif "lisans" in egitim.lower() and "yüksek" not in egitim.lower():
            parsed["egitim_seviyesi"] = "Lisans"
        elif "yüksek lisans" in egitim.lower() or "yükseklisans" in egitim.lower() or "master" in egitim.lower():
            parsed["egitim_seviyesi"] = "Yüksek Lisans"
        elif "doktora" in egitim.lower() or "phd" in egitim.lower():
            parsed["egitim_seviyesi"] = "Doktora"
        else:
            parsed["egitim_seviyesi"] = ""
    else:
        parsed["egitim_seviyesi"] = ""
    parsed.setdefault("egitim_seviyesi", None)
    parsed.setdefault("tercih_edilen_bolum", None)
    parsed.setdefault("askerlik", None)
    parsed.setdefault("yabanci_dil", None)
    parsed.setdefault("keywords", [])
    parsed.setdefault("aranan_nitelikler", None)
    parsed.setdefault("is_tanimi", None)

    # keywords list kontrolü
    if not isinstance(parsed["keywords"], list):
        parsed["keywords"] = []

    # Fallback: AI keywords az veya boş dönerse, metinden keyword çıkar
    from database import search_keywords_in_text

    ai_keywords = parsed.get("keywords", []) or []
    if isinstance(ai_keywords, str):
        ai_keywords = [k.strip() for k in ai_keywords.split(',') if k.strip()]

    # Metinden ek keyword'ler bul
    extra_keywords = search_keywords_in_text(text)

    # Birleştir ve duplicate temizle
    all_keywords = list(set([k.lower() for k in ai_keywords] + extra_keywords))
    parsed["keywords"] = all_keywords

    return parsed


def process_job_url(url: str) -> dict:
    """İlan URL'sini işle ve pozisyon bilgilerini çıkar"""
    # URL kontrolü
    if not url or "kariyer.net" not in url:
        return {"basarili": False, "hata": "Geçerli bir kariyer.net URL'si girin"}
    
    # İlanı scrape et
    scrape_result = scrape_kariyer_net(url)
    if not scrape_result.get("basarili"):
        return scrape_result
    
    text = scrape_result.get("text", "")
    if not text:
        return {"basarili": False, "hata": "İlan içeriği alınamadı"}
    
    # AI ile parse et
    try:
        ai_result = parse_job_with_ai(text)
        return {
            "basarili": True,
            "pozisyon_adi": ai_result.get("pozisyon_adi", ""),
            "firma": ai_result.get("firma", ""),
            "lokasyon": ai_result.get("lokasyon", ""),
            "deneyim_yil": ai_result.get("deneyim_yil", ""),
            "egitim_seviyesi": ai_result.get("egitim_seviyesi", ""),
            "tercih_edilen_bolum": ai_result.get("tercih_edilen_bolum", ""),
            "askerlik": ai_result.get("askerlik", ""),
            "yabanci_dil": ai_result.get("yabanci_dil", ""),
            "keywords": ai_result.get("keywords", []),
            "aranan_nitelikler": ai_result.get("aranan_nitelikler", ""),
            "is_tanimi": ai_result.get("is_tanimi", "")
        }
    except Exception as e:
        return {"basarili": False, "hata": f"AI parse hatası: {str(e)}"}


def process_job_document(file_content: bytes, filename: str) -> dict:
    """PDF/DOCX/JPEG dosyasından pozisyon bilgilerini çıkar
    
    Args:
        file_content: Dosya içeriği (bytes)
        filename: Dosya adı (uzantıya göre format belirlenir)
    
    Returns:
        {
            "basarili": bool,
            "pozisyon_adi": str,
            "firma": str,
            "lokasyon": str,
            "deneyim_yil": int,
            "egitim_seviyesi": str,
            "keywords": list,
            ...
        } veya {"basarili": False, "hata": str}
    """
    import os
    from cv_parser import (
        extract_text_from_pdf,
        extract_text_from_docx,
        extract_text_from_doc,
        extract_text_from_image
    )
    
    # Dosya uzantısına göre format belirle
    ext = os.path.splitext(filename)[1].lower()
    
    # Metin çıkar
    try:
        if ext == '.pdf':
            text = extract_text_from_pdf(file_content)
        elif ext == '.docx':
            text = extract_text_from_docx(file_content)
        elif ext == '.doc':
            text = extract_text_from_doc(file_content)
        elif ext in ['.jpg', '.jpeg', '.png']:
            text = extract_text_from_image(file_content)
        else:
            return {"basarili": False, "hata": f"Desteklenmeyen dosya formatı: {ext}. PDF, DOCX, DOC, JPEG veya PNG kullanın."}
        
        if not text or len(text.strip()) < 50:
            return {"basarili": False, "hata": "Dosyadan yeterli metin çıkarılamadı. Dosya boş veya korumalı olabilir."}
        
        # AI ile parse et (parse_job_with_ai kullan)
        ai_result = parse_job_with_ai(text)
        
        return {
            "basarili": True,
            "pozisyon_adi": ai_result.get("pozisyon_adi", ""),
            "firma": ai_result.get("firma", ""),
            "lokasyon": ai_result.get("lokasyon", ""),
            "deneyim_yil": ai_result.get("deneyim_yil", ""),
            "egitim_seviyesi": ai_result.get("egitim_seviyesi", ""),
            "tercih_edilen_bolum": ai_result.get("tercih_edilen_bolum", ""),
            "askerlik": ai_result.get("askerlik", ""),
            "yabanci_dil": ai_result.get("yabanci_dil", ""),
            "keywords": ai_result.get("keywords", []),
            "aranan_nitelikler": ai_result.get("aranan_nitelikler", ""),
            "is_tanimi": ai_result.get("is_tanimi", "")
        }
    except ValueError as e:
        return {"basarili": False, "hata": str(e)}
    except Exception as e:
        return {"basarili": False, "hata": f"Dosya işleme hatası: {str(e)}"}
