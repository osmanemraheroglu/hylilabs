# HyliLabs — Aktif Bağlam

Son güncelleme: 22.03.2026

## TAMAMLANAN GÖREV: V3 Scoring Prompt İyileştirme - FAZ 3

**Tarih:** 2026-03-22
**Commit:** 32d702a

### Yapılan Değişiklikler

- 7A: confidence alanları JSON_SCHEMA (smart_prompt_builder.py satır 57-95, 101-105)
- 7B: GÜVEN SKORU kuralları SYSTEM_PROMPT (smart_prompt_builder.py satır 171-240)
- 7C: confidence parse EvaluationResult (ai_evaluator.py dataclass, _parse_response)

### DEĞİŞİKLİK 7A: JSON_SCHEMA confidence

Her 5 kategori için confidence alanı (0.0-1.0):
- position_match.confidence
- technical_skills.confidence
- experience_quality.confidence
- education.confidence
- elimination_factors.confidence

Üst seviye alanlar:
- confidence_score: Ortalama güven skoru
- low_confidence_areas: confidence < 0.50 olan kategoriler

### DEĞİŞİKLİK 7B: GÜVEN SKORU Kuralları

- YÜKSEK GÜVEN (0.85-1.0): CV'de açık ve net bilgi
- ORTA GÜVEN (0.50-0.84): Bilgi var ama detaysız
- DÜŞÜK GÜVEN (0.00-0.49): Bilgi eksik veya belirsiz
- AŞIRI GÜVEN ÖNLEME: evidence_from_cv korelasyonu zorunlu

### DEĞİŞİKLİK 7C: ai_evaluator.py Parse

- EvaluationResult: confidence_score, low_confidence_areas alanları
- FinalEvaluation: confidence_score, low_confidence_areas alanları
- _parse_response: Kategori bazlı confidence parse
- _average_scores: Confidence ortalaması hesaplama
- to_dict: confidence alanları dahil

---

## Son Commitler

- 22.03.2026 - 32d702a - feat(v3-scoring): FAZ 3 - confidence_score, GÜVEN SKORU
- 22.03.2026 - 48ebe9b - feat(v3-scoring): FAZ 2 - evidence_from_cv, tarih hesaplama, job hopping
- 22.03.2026 - 51bce65 - feat(v3-scoring): FAZ 1 - halüsinasyon önleme, temperature 0.1, overqualified
- 21.03.2026 - 542f4fc - Senior Engineer Prensipleri eklendi

---

## Sonraki Görev

FAZ 4 (isteğe bağlı) veya kullanıcı yeni görev belirleyecek.

---

## Referans

### V3 Scoring Dosyaları
- api/core/scoring_v3/smart_prompt_builder.py - AI prompt oluşturucu
- api/core/scoring_v3/ai_evaluator.py - Multi-model evaluator

### FAZ 1 + FAZ 2 + FAZ 3 Özet

- FAZ 1.1: Halüsinasyon Önleme (satır 29-55)
- FAZ 1.2: Temperature 0.1 (ai_evaluator.py)
- FAZ 1.3: Overqualified Kuralları (satır 193-221)
- FAZ 2.4: evidence_from_cv (satır 57-82, 333, 340, 345)
- FAZ 2.5: Tarih Hesaplama (satır 110-152)
- FAZ 2.6: Job Hopping / Boşluk (satır 223-303)
- FAZ 3.7A: confidence JSON_SCHEMA (satır 57-95, 101-105)
- FAZ 3.7B: GÜVEN SKORU kuralları (satır 171-240)
- FAZ 3.7C: confidence parse (ai_evaluator.py)
