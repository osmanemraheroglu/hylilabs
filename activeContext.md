# HyliLabs — Aktif Bağlam

Son güncelleme: 22.03.2026

## ✅ TAMAMLANAN GÖREV: V3 Scoring Prompt İyileştirme - FAZ 1

**Tarih:** 2026-03-22
**Commit:** 51bce65

### Yapılan Değişiklikler

| Değişiklik | Dosya | Açıklama |
|------------|-------|----------|
| 1. Halüsinasyon Önleme | smart_prompt_builder.py:29-55 | 5 kural: CV kanıtı zorunlu, çıkarım yasak, belirsizlikte 0 puan |
| 2. Temperature 0.3→0.1 | ai_evaluator.py:521,614,704 | Gemini, Hermes, OpenAI için (Claude Judge hariç) |
| 3. Overqualified Kuralları | smart_prompt_builder.py:122-152 | Matematiksel sınır: 2+ seviye veya 3x deneyim farkı |

### Halüsinasyon Önleme Kuralları (5 Kural)

1. SADECE CV'de açıkça belirtilen bilgilere puan ver
2. Çıkarım yapma, varsayımda bulunma
3. Belirsizlik durumunda 0 puan ver
4. Örtük deneyim tespiti sadece 3 kalıp için (ekip/proje/bütçe yönetimi)
5. Her verdiğin puan için CV'den somut kanıt göster

### Overqualified Tespit Kriterleri

**A) Unvan Farkı (2+ seviye):**
- Hiyerarşi: Stajyer < Uzman < Kıdemli < Müdür < Direktör < Genel Müdür
- Örnek: Pozisyon Uzman, Aday Direktör (3 seviye) → OVERQUALIFIED

**B) Deneyim Farkı (3x fazla):**
- Örnek: Pozisyon 3-5 yıl, Aday 15+ yıl → OVERQUALIFIED

**Skor Etkisi:**
- Normal aday: 20-25 puan
- Overqualified aday: 10-15 puan (motivasyon riski)

---

## ✅ Son Commitler

| Tarih | Commit | Açıklama |
|-------|--------|----------|
| 22.03.2026 | 51bce65 | feat(v3-scoring): FAZ 1 - halüsinasyon önleme, temperature 0.1, overqualified kuralları |
| 21.03.2026 | 542f4fc | Senior Engineer Prensipleri eklendi |
| 21.03.2026 | 7584285 | P2 Güvenlik - Orta öncelikli düzeltmeler |

---

## 📋 Sonraki Görev

FAZ 2 veya kullanıcı yeni görev belirleyecek.

---

## 📚 Referans

### V3 Scoring Dosyaları
- `api/core/scoring_v3/smart_prompt_builder.py` - AI prompt oluşturucu
- `api/core/scoring_v3/ai_evaluator.py` - Multi-model evaluator

### Temperature Ayarları
| Model | Temperature | Neden |
|-------|-------------|-------|
| Gemini | 0.1 | Deterministik, tutarlı sonuçlar |
| Hermes | 0.1 | Deterministik, tutarlı sonuçlar |
| OpenAI | 0.1 | Deterministik, tutarlı sonuçlar |
| Claude Judge | 0.3 | Tahkim için farklı perspektif gerekli |
