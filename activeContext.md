# HyliLabs — Aktif Bağlam

Son güncelleme: 22.03.2026

## ✅ TAMAMLANAN GÖREV: V3 Scoring Prompt İyileştirme - FAZ 2

**Tarih:** 2026-03-22
**Commit:** 48ebe9b

### Yapılan Değişiklikler

| # | Değişiklik | Dosya | Satır |
|---|------------|-------|-------|
| 4 | evidence_from_cv alanı | smart_prompt_builder.py | 57-82, 333, 340, 345 |
| 5 | Tarih ve Deneyim Hesaplama | smart_prompt_builder.py | 110-152 |
| 6 | Job Hopping / Kariyer Boşluğu Uyarı | smart_prompt_builder.py | 223-303 |

### DEĞİŞİKLİK 4: evidence_from_cv

3 kategori için CV kanıtı ZORUNLU:
- technical_skills.evidence_from_cv
- experience_quality.evidence_from_cv
- education.evidence_from_cv

### DEĞİŞİKLİK 5: Tarih Hesaplama Kuralları

- Temel: AY/YIL formatı
- Çakışan tarihler: Tek süre say
- Belirsiz: TAHMİN YAPMA
- Yuvarlama: 6 ay eşik
- Toplam vs İlgili Deneyim ayrımı

### DEĞİŞİKLİK 6: Kariyer Uyarı Mekanizması

- Job Hopping: 5 yılda 4+ iş → UYARI (puan düşmez)
- Kariyer Boşluğu: 6+ ay → UYARI (puan düşmez)
- Sektör istisnaları: Startup, Danışmanlık, Mevsimlik

---

## ✅ Son Commitler

| Tarih | Commit | Açıklama |
|-------|--------|----------|
| 22.03.2026 | 48ebe9b | feat(v3-scoring): FAZ 2 - evidence_from_cv, tarih hesaplama, job hopping |
| 22.03.2026 | 51bce65 | feat(v3-scoring): FAZ 1 - halüsinasyon önleme, temperature 0.1, overqualified |
| 21.03.2026 | 542f4fc | Senior Engineer Prensipleri eklendi |

---

## 📋 Sonraki Görev

FAZ 3 veya kullanıcı yeni görev belirleyecek.

---

## 📚 Referans

### V3 Scoring Dosyaları
- `api/core/scoring_v3/smart_prompt_builder.py` - AI prompt oluşturucu
- `api/core/scoring_v3/ai_evaluator.py` - Multi-model evaluator

### FAZ 1 + FAZ 2 Özet

| FAZ | Değişiklik | Satır |
|-----|------------|-------|
| 1.1 | Halüsinasyon Önleme | 29-55 |
| 1.2 | Temperature 0.1 | ai_evaluator.py |
| 1.3 | Overqualified Kuralları | 193-221 |
| 2.4 | evidence_from_cv | 57-82, 333, 340, 345 |
| 2.5 | Tarih Hesaplama | 110-152 |
| 2.6 | Job Hopping / Boşluk | 223-303 |
