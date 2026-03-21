# HyliLabs — Aktif Bağlam

Son güncelleme: 21.03.2026

## ✅ TAMAMLANAN GÖREV: Senior Engineer Prensipleri Eklendi

**Tarih:** 2026-03-21
**Commit:** 542f4fc

### Eklenen Bölümler

| Bölüm | Satır Aralığı |
|-------|---------------|
| 🎯 SENIOR ENGINEER PRENSİPLERİ | 1184-1271 |
| 📋 TASK MANAGEMENT | 1274-1282 |
| 💎 CORE PRINCIPLES | 1285-1291 |

### 6 Prensip

| # | Prensip | HyliLabs Uygulaması |
|---|---------|---------------------|
| 1 | Plan Mode Default | V3 scoring değişikliklerinde spec yaz |
| 2 | Subagent Strategy | CV parsing, AI scoring, Arbitration dağıt |
| 3 | Self-Improvement Loop | 0 puan hatalarını lessons.md'ye işle |
| 4 | Verification Before Done | Anomali adaylarla mock test |
| 5 | Demand Elegance | ai_evaluator.py'de temiz fonksiyonlar |
| 6 | Autonomous Bug Fixing | Timeout/limit hatalarında otonom fallback |

### Konum
- Güvenlik bulguları (🔐) bölümünden ÖNCE eklendi
- Mevcut içerik KORUNDU

---

## ✅ TAMAMLANAN GÖREV: P2 Güvenlik - Orta Öncelikli Düzeltmeler

**Tarih:** 2026-03-21
**Commit:** 7584285

### Sorun
4 orta öncelikli güvenlik bulgusu:
- email_logs tablosunda company_id yok
- api_usage_logs'ta NULL company_id kayıtları
- SQL Injection riski (candidates.py, synonyms.py)
- Rate limiting eksik (interviews.py) + /api/test/db public endpoint

### Çözüm

**1. Database Migration (email_logs):**
- ALTER TABLE email_logs ADD COLUMN company_id
- Index oluşturuldu: idx_email_logs_company_id
- 75 mevcut kayıt NULL (tarihsel veri, email hesabı bilgisi yok)

**2. api_usage_logs Analizi:**
- company_id zaten VAR
- 653/680 kayıt NULL (eski kayıtlar, user_id de NULL)
- Tarihsel veri, düzeltme gerekli DEĞİL

**3. SQL Injection Analizi (FALSE POSITIVE):**
- candidates.py:363-365 → Parameterized query kullanılıyor (GÜVENLİ)
- synonyms.py:1624 → Hardcoded column names + parameterized values (GÜVENLİ)

**4. Rate Limiting + Test Endpoint:**
- interviews.py → Zaten rate limiting VAR (satır 816)
- /api/test/db → Endpoint KALDIRILDI (main.py)

**5. Backend Güncellemeleri:**

| Dosya | Değişiklik |
|-------|------------|
| models.py | EmailLog.company_id alanı eklendi |
| database.py | log_email() INSERT'e company_id eklendi |
| email_worker.py | EmailLog company_id ile oluşturuluyor |
| cv.py | EmailLog company_id ile oluşturuluyor |
| routes/cv.py | EmailLog company_id ile oluşturuluyor |
| main.py | /api/test/db endpoint kaldırıldı |

### 🎯 GÜVENLİK DENETİMİ TAMAMLANDI

| Öncelik | Durum |
|---------|-------|
| P0 KRİTİK | ✅ 6/6 Tamamlandı |
| P1 YÜKSEK | ✅ 4/4 Tamamlandı |
| P2 ORTA | ✅ 4/4 Tamamlandı |
| **TOPLAM** | ✅ **14/14 (%100)** |

---

## ✅ TAMAMLANAN GÖREV: P1 Güvenlik - 3 Tabloya company_id Migration

**Tarih:** 2026-03-21
**Commit:** 53d2741

### Sorun
3 tablo company_id kolonu olmadan çalışıyordu (multi-tenancy ihlali):
- position_criteria
- ai_analyses
- hr_evaluations

**Not:** ai_evaluations tablosunda company_id zaten vardı (29 kayıt).

### Çözüm

**1. DB Migration:**
- ALTER TABLE position_criteria ADD COLUMN company_id
- ALTER TABLE ai_analyses ADD COLUMN company_id
- ALTER TABLE hr_evaluations ADD COLUMN company_id
- 3 yeni index oluşturuldu

**2. database.py Fonksiyon Güncellemeleri:**

| Fonksiyon | Değişiklik |
|-----------|------------|
| add_position_criteria | + company_id parametresi |
| get_position_criteria | + company_id filtresi (opsiyonel) |
| delete_all_position_criteria | + company_id filtresi (opsiyonel) |
| save_ai_analysis | + company_id parametresi |
| get_ai_analysis | + company_id filtresi (opsiyonel) |
| save_hr_evaluation | + company_id parametresi |
| get_hr_evaluation | + company_id filtresi (opsiyonel) |
| get_all_hr_evaluations | + company_id filtresi (opsiyonel) |
| export_candidate_data | + ai_analyses company_id filtresi |

**3. workflows.py Güncellemeleri:**
- save_ai_analysis() çağrıları company_id parametresi ile güncellendi (2 yer)

### Güvenlik Durumu

| Öncelik | Durum |
|---------|-------|
| P0 KRİTİK | ✅ 6/6 Tamamlandı |
| P1 YÜKSEK | ✅ 4/4 Tamamlandı |
| P2 ORTA | ✅ 4/4 Tamamlandı |

---

## ✅ TAMAMLANAN GÖREV: P0-B Güvenlik - DELETE Sorguları + AI Data Masking

**Tarih:** 2026-03-21
**Commit:** a832d91

### Sorun
1. candidates.py'de 4 DELETE sorgusu company_id filtresi olmadan çalışıyordu (multi-tenancy ihlali)
2. smart_prompt_builder.py AI servislerine gerçek kişisel veri gönderiyordu (KVKK ihlali)

### Çözüm

**1. DELETE Sorguları (candidates.py - KİLİTLİ #9 ONAYLANDI):**

| Satır | Tablo | Değişiklik |
|-------|-------|------------|
| 146 | candidate_pool_assignments | + company_id |
| 147 | matches | + company_id |
| 148 | candidate_positions | + company_id |
| 198 | candidate_positions (elen_candidate) | + company_id |

**2. AI Data Masking (smart_prompt_builder.py):**

| Değişken | Önceki | Şimdi |
|----------|--------|-------|
| candidate_name | Ham veri | ADAY_MASKED |
| candidate_email | Ham veri | masked@privacy.local |
| current_company | Ham veri | SIRKET_MASKED |
| company_name | Ham veri | FIRMA_MASKED |

**3. Yeni Fonksiyon:**
- `_mask_personal_data(value, prefix)` - satır 275-289

### P0 Durumu

| Görev | Commit | Durum |
|-------|--------|-------|
| P0-A: 4 tablo migration | 0de76a6 | ✅ |
| P0-B: DELETE + AI masking | a832d91 | ✅ |

**P0 KRİTİK SEVİYE TAMAMLANDI: 6/6 ✅**

---

## ✅ TAMAMLANAN GÖREV: P0-A Güvenlik Migration - candidate_positions company_id

**Tarih:** 2026-03-21

### Sorun
`candidate_positions` tablosunda `company_id` kolonu yoktu → Multi-tenancy izolasyonu kırıktı.

### Çözüm

**1. DB Migration:**
- `candidate_positions` tablosuna `company_id INTEGER` kolonu eklendi
- 31 mevcut kayıt `candidates.company_id` JOIN ile güncellendi
- `applications` tablosundaki 5 NULL `company_id` kaydı düzeltildi
- 4 tabloya `idx_*_company_id` indexleri oluşturuldu

**2. INSERT Sorguları Güncellendi:**

| Dosya:Satır | Fonksiyon | Değişiklik |
|-------------|-----------|------------|
| database.py:7921-7925 | `pull_matching_candidates_to_position()` | company_id parametresi eklendi |
| database.py:12896-12903 | `add_candidate_to_position()` | company_id parametresi eklendi |
| database.py:5280-5301 | Migration recovery | candidates JOIN ile company_id |

**3. Backup:**
- `talentflow.db.backup_security_p0_20260321_165822` (10.4 MB)

### Kalan Tablolar (Zaten OK)
- `candidate_pool_assignments`: company_id VAR, NULL yok ✅
- `matches`: company_id VAR, NULL yok ✅
- `applications`: company_id VAR, NULL düzeltildi ✅

---

## ✅ TAMAMLANAN GÖREV: CV Çek Threshold - 4 Katmanlı Kalıcı Çözüm

**Tarih:** 2026-03-21

### Sorun
match_score < 40 olan adaylar pozisyon listesinde görünüyordu (Büşra Aymaz: 39, SAMET KAYA: 23).

### Çözüm (4 Katmanlı Savunma)

| Katman | Konum | Açıklama |
|--------|-------|----------|
| 1. Backend INSERT | database.py:7880-7883 | V2 skoru < 40 ise listeye ekleme |
| 2. Backend DELETE | database.py:8010,8684 | V3 sonrası < 40 ise sil |
| 3. Frontend Filter | havuzlar/index.tsx:647-650 | < 40 adayları gizle |
| 4. Data Cleanup | SQL | Mevcut < 40 adaylar silindi |

### Kod Değişiklikleri

**database.py:**
```python
# Satır 81 - Sabit tanımı
MINIMUM_MATCH_THRESHOLD = 40     # Minimum match score to insert (CV Çek threshold)

# Satır 7880-7883 - INSERT öncesi kontrol
if match_score < MINIMUM_MATCH_THRESHOLD:
    logger.info(f"[Threshold] Aday {candidate_id} elendi: match_score={match_score} < {MINIMUM_MATCH_THRESHOLD}")
    continue

# Satır 8010, 8684 - V3 sonrası DELETE
if final_score < MINIMUM_MATCH_THRESHOLD:
    cursor.execute("DELETE FROM candidate_positions WHERE candidate_id = ? AND position_id = ?", ...)
```

**havuzlar/index.tsx:**
```javascript
// Satır 647-650 - Frontend filtre
const MINIMUM_MATCH_THRESHOLD = 40
const filteredCandidates = candidates.filter(c => {
  if ((c.match_score || 0) < MINIMUM_MATCH_THRESHOLD) return false
  ...
})
```

### Veri Temizliği
- candidate_positions: 2 kayıt silindi
- matches: 2 kayıt silindi
- Etkilenen adaylar: SAMET KAYA (23), Büşra Aymaz (39)

---

## ✅ TAMAMLANAN GÖREV: Frontend score_version Filter Fix

**Tarih:** 2026-03-20

### Sorun
Frontend'de `score_version === 'v3_hylilabs_protocol'` tanınmıyordu.
3 aday (Büşra Aymaz, SAMET KAYA, Semih Aydın Demir) yanlışlıkla "Değerlendir" butonu görüyordu.

### Kök Neden
`havuzlar/index.tsx:202` satırında score_version kontrolü sadece `'v3_weighted'` ve `'v3'` kabul ediyordu.
HyliLabs Protocol rescore işlemi `score_version = 'v3_hylilabs_protocol'` değerini kullanıyordu.

### Çözüm
Satır 202'de filtre genişletildi:
```javascript
// ÖNCEKİ:
if (c.score_version === 'v3_weighted' || c.score_version === 'v3') {

// YENİ:
if (c.score_version === 'v3_weighted' || c.score_version === 'v3' || c.score_version === 'v3_hylilabs_protocol') {
```

### Etkilenen Adaylar
| Aday | ID | Önceki | Yeni |
|------|-----|--------|------|
| Büşra Aymaz | 462 | "Değerlendir" | V3 skor görünür |
| SAMET KAYA | 383 | "Değerlendir" | V3 skor görünür |
| Semih Aydın Demir | 450 | "Değerlendir" | V3 skor görünür |

### Dosya
- `src/features/havuzlar/index.tsx`: Satır 202

---

## ✅ TAMAMLANAN GÖREV: HyliLabs Protocol CLAUDE.md Dokümantasyonu

**Tarih:** 2026-03-20

### Yapılan İş
HyliLabs V3 SCORING PROTOCOL bölümü CLAUDE.md'ye eklendi (satır 1086-1148).

### Eklenen İçerik
- Protokol akış diyagramı (INITIAL → RETRY → FALLBACK → ARBITRATION → RESULT)
- Kök neden açıklaması (gemini_ok bug)
- Kod değişiklikleri tablosu (7 satır)
- Test sonuçları tablosu (3 aday)
- 5 DEĞİŞTİRİLEMEZ KURAL

### Dosya
- CLAUDE.md: +63 satır

---

## ✅ TAMAMLANAN GÖREV: HyliLabs Protocol - V3 Scoring Zero Score Bug Fix

**Tarih:** 2026-03-20

### Sorun
V3 değerlendirmede Gemini veya Hermes 0 skor döndürdüğünde sistem bunu "başarılı" sayıyordu.
Sonuç: Gemini(0) + Hermes(90) ortalaması → V3=45 (yanlış), olması gereken V3=90.

### Kök Neden
`ai_evaluator.py` satır 230-231:
```python
# ESKI (BUG):
gemini_ok = gemini_result is not None and gemini_result.error is None
# total_score > 0 kontrolü YOK!
```

### Çözüm (HyliLabs Protocol 5 Adım)

| Adım | Açıklama | Dosya/Satır |
|------|----------|-------------|
| 1 | İkisi de 0 → Exception fırlat | ai_evaluator.py:246-253 |
| 2 | Biri 0+ diğeri 0 → MAX_RETRIES=3 ile retry | ai_evaluator.py:255-280 |
| 3 | Retry sonrası hala tek pozitif → OpenAI fallback | ai_evaluator.py:290-307 |
| 4 | Fark > 15 → Claude arbitration (mevcut, korundu) | ai_evaluator.py:175 |
| 5 | Orchestrator pattern | evaluate() fonksiyonu |

### Yapılan Değişiklikler

1. **MAX_RETRIES = 3** (satır 178)
   - Eski: 1, Yeni: 3

2. **gemini_ok/hermes_ok total_score > 0 kontrolü** (satır 230-238)
   - `total_score is not None and total_score > 0` eklendi

3. **İkisi de 0 kontrolü** (satır 246-253)
   - `both_zero` durumunda Exception fırlatılıyor

4. **Retry helper fonksiyonları** (satır 412-470)
   - `_retry_zero_score_model()`: Hermes için
   - `_retry_gemini_zero_score()`: Gemini için
   - MAX_RETRIES kadar deneme, her deneme sonrası total_score > 0 kontrolü

5. **OpenAI fallback güncelleme** (satır 316-321)
   - `total_score > 0` kontrolü eklendi

### Etkilenen Adaylar
- candidate_id: 450, 462, 383 (V3 Anomaly analizi sonucu)

### Dosyalar
- `api/core/scoring_v3/ai_evaluator.py`: +80 satır (helper + logic)

---

## ✅ TAMAMLANAN GÖREV: V3 Weighted Average Rescore Fix

**Tarih:** 2026-03-20

### Sorun
Title onayı (approve-titles G8) ve rescore fonksiyonları sadece V2 skoru yazıyordu, V3 weighted average (60%V3+40%V2) hesaplanmıyordu. Bu durum `candidate_positions.match_score` alanının yanlış (V2 only) değer içermesine neden oluyordu.

### Kök Neden
3 kritik fonksiyon V2 only yazıyordu:
- `approve-titles G8` (pools.py:1556-1641)
- `rescore_candidate()` (pools.py:2089-2237)
- `rescore_position_candidates()` (pools.py:2475-2612)

### Çözüm (4 Golden Rule)

1. **DB Migration:**
   - `candidate_positions.calculation_metadata` (TEXT)
   - `candidate_positions.updated_at` (DATETIME)
   - `matches.calculation_metadata` (TEXT)
   - `system_settings` tablosu (v3_weight=0.60, v2_weight=0.40)

2. **Helper Fonksiyonlar (pools.py:106-285):**
   - `get_scoring_weights()`: Config'den ağırlıkları al (Rule 2: CONFIG)
   - `calculate_weighted_score()`: V3 weighted average + JSON metadata (Rule 3 & 4)
   - `batch_v3_evaluate()`: ThreadPoolExecutor ile paralel V3 (Rule 1: ASYNC/BULK)
   - `update_score_with_metadata()`: Tablolara metadata ile güncelleme

3. **Güncellenen Fonksiyonlar:**
   - `approve-titles G8`: Batch V3 + weighted average + metadata
   - `rescore_candidate()`: Single V3 + weighted average + metadata
   - `rescore_position_candidates()`: Batch V3 + weighted average + metadata

### 4 Golden Rule Uyumu
| Rule | Açıklama | Durum |
|------|----------|-------|
| Rule 1 | ASYNC/BULK - ThreadPoolExecutor batch processing | ✅ |
| Rule 2 | CONFIG - system_settings tablosundan ağırlık çekme | ✅ |
| Rule 3 | METADATA - JSON calculation_metadata kayıt | ✅ |
| Rule 4 | FALLBACK - V3 yoksa V2'ye düşme | ✅ |

### Değişen Dosyalar
- `api/routes/pools.py`: +381 satır (helper + 3 fonksiyon)

### Backup
- `talentflow.db.backup_v3_20260320_020406` (10.4 MB)

---

## ✅ TAMAMLANAN GÖREV: Akıllı Havuz Başlıkları - Tam Düzeltme

**Tarih:** 2026-03-19

### Tespit Edilen Sorunlar

1. **Backend Mapping Bug:**
   - AI prompt `exact` ve `close` döndürüyor
   - Frontend `exact`, `similar`, `related` bekliyor
   - Backend'de `close` mapping YOKTU → otomatik `related`'a düşüyordu

2. **AI Prompt Eksikliği:**
   - Title önerileri için sadece 1 kural vardı (kural 7)
   - Diploma/eğitim gereksinimleri pozisyon olarak öneriliyordu
   - Sektör isimleri pozisyon olarak öneriliyordu
   - Farklı seviye pozisyonlar öneriliyordu

3. **Frontend Build Eksik:**
   - Türkçe etiketler kaynak kodda vardı ama build güncellenmemişti

### Çözümler

1. **Backend Mapping Fix (pools.py:1117-1175):**
   - `get_approved_titles()`: `close` → `similar` mapping eklendi
   - `get_pending_titles()`: `close` → `similar` mapping eklendi
   - `level_mapping = {"exact": "exact", "close": "similar", "similar": "similar", "related": "related"}`

2. **AI Prompt Güncelleme (pools.py:2056-2072):**
   - Kural 7 genişletildi: `ek_titlelar KURALLARI (KRİTİK)`
   - 7a: exact tanımı + örnek (birebir TR/EN çevirileri, max 4)
   - 7b: close tanımı + örnek (aynı işi yapan alternatif pozisyonlar, max 6)
   - 7c: YASAK listesi (diploma, sektör, farklı seviye, araç/beceri, departman)
   - 7d: KONTROL sorusu ("Bu başlıkla ayrı iş ilanı açsam, AYNI işi yapan aday başvurur mu?")
   - 7e: Boş liste senaryosu (uygun başlık yoksa [] döndür, zorlama yapma)

3. **Frontend Türkçe Etiketler (havuzlar/index.tsx:1152-1189):**
   - 🎯 Tam (exact)
   - 🔄 Benzer (close/similar)
   - 🔗 İlişkili (related/partial)
   - Badge'da Türkçe label gösterimi

4. **CLAUDE.md Kuralları Eklendi (satır 979-1024):**
   - ek_titlelar kuralları (7a-7e) dokümante edildi
   - Backend mapping dokümante edildi
   - UI etiketleri dokümante edildi
   - Sistem KİLİTLİ olarak işaretlendi

5. **Frontend Build + PM2 Restart:**
   - `npm run build` çalıştırıldı
   - `pm2 restart hylilabs-frontend` yapıldı

### Değişen Dosyalar
- `api/routes/pools.py`: Backend mapping + AI prompt kuralları (7a-7e)
- `src/features/havuzlar/index.tsx`: Türkçe badge etiketleri
- `CLAUDE.md`: Akıllı Havuz Başlıkları kuralları bölümü

### Commitler (Tümü)
| Commit | Mesaj |
|--------|-------|
| `5d2b64d` | fix: smart pool titles close→similar mapping + prompt rules |
| `39c727e` | fix: pending titles badge Turkish labels |
| `91bb6df` | docs: update activeContext with title badge fix |
| `eb88330` | feat: add 7e rule for empty list scenario |
| `3314448` | docs: add smart pool titles rules to CLAUDE.md |

### Final Kontrol
| Bileşen | Durum |
|---------|-------|
| AI Prompt (7a-7e) | ✅ |
| Backend Mapping | ✅ |
| Frontend Etiketler | ✅ |
| CLAUDE.md | ✅ |
| Frontend Build | ✅ (19.03.2026 20:21) |

### 21.03.2026 - AI Model Skorları Ortalama Fix
- ✅ **Aday Detay Modal: Ortalama AI skoru hesaplanıp gösteriliyor**
  - `avg_ai_score` (backend'de yok) yerine frontend'de dinamik hesaplama
  - Aktif model sayısına göre ortalama (0'dan büyük skorlar)
  - Hiç skor yoksa `-%` gösterimi

### 21.03.2026 - Skor Detayı Bölümü
- ✅ **Aday Detay Modal: Skor Detayı bölümü eklendi**
  - V2 (Keyword) x0.4, V3 (AI) x0.6, Final skor kartları
  - Final skoru hesaplanıyor: (v2×0.4)+(v3×0.6)
  - Kelime Skoru / Toplam Puan eski bölümü kaldırıldı

---

- **Sunucu:** hylilabs.com (PM2 ile çalışıyor)
- **Domain:** https://hylilabs.com (Nginx + SSL aktif, 14.03.2026)
- **Son commit:** PM2 ENV reload script + docs (19.03.2026)
- **Backend:** FastAPI + SQLite (WAL mode)
- **Frontend:** React + TypeScript + Tailwind
- **Puanlama:** 100 puan sistemi v2.1 + V3 weighted (60%V3+40%V2) aktif

## Aktif Kullanıcılar

- Adnan Bey (İK Direktörü) — test + onay
- 3 şirket, ~50 aday, 5 pozisyon

## ✅ TAMAMLANAN GÖREV: Kariyer.net URL Parse Bug Fix

**Tarih:** 2026-03-19

### Sorun
Kariyer.net URL analiz edildiğinde pozisyon adı, firma ve lokasyon "Belirtilmemiş" dönüyordu.

### Kök Neden
`scrape_kariyer_net()` fonksiyonu metni "İş İlanı Hakkında" marker'ından itibaren kesiyordu.
Ancak pozisyon adı, firma ve lokasyon bilgileri bu marker'ın **ÖNÜNDE** (sayfa header/title bölümünde) yer alıyor.

**Örnek HTML yapısı:**
```
TOR Holding İş Geliştirme Uzmanı İş İlanı ... İstanbul(Avr.) (Esenyurt) ...
[İş İlanı Hakkında]  <-- marker burada, önceki bilgiler kesiliyor
GENEL NİTELİKLER ...
```

### Çözüm
1. **scrape_kariyer_net() Güncellendi:**
   - Header bölümünü (ilk 600 karakter) `[HEADER]...[/HEADER]` olarak sakla
   - Ana içerikle birleştir
   - AI'a hem header hem içerik gönder

2. **AI Prompt Güncellendi:**
   - `[HEADER]` tag'i açıklaması eklendi
   - Pozisyon adı/firma/lokasyon için HEADER'a bakması söylendi

### Değişen Dosya
- `api/job_scraper.py`: satır 48-81 (scraper), satır 118-124 (prompt)

---

## ✅ TAMAMLANAN GÖREV: PM2 ENV Cache Kalıcı Çözüm + Git Hook

**Tarih:** 2026-03-19

### Sorun
PM2, process başlatıldığında .env dosyasını CACHE'ler. `pm2 restart` komutu ENV değişikliklerini YUKLEMEZ.
Bu sebeple .env'de yapılan değişiklikler (örn: API key güncelleme) etkili olmaz.

### Çözüm
1. **Helper Script Oluşturuldu:** `scripts/pm2-reload-env.sh`
   - Kritik ENV değerlerini maskeleyerek gösterir
   - pm2 delete + pm2 start yaparak ENV'yi yeniler
   - API health check yapar
   - Kullanım: `./scripts/pm2-reload-env.sh` (backend), `./scripts/pm2-reload-env.sh all` (tümü)

2. **Git Post-Merge Hook Eklendi:** `/var/www/hylilabs/.git/hooks/post-merge`
   - git pull sonrası .env veya ecosystem.config.cjs değiştiyse otomatik çalışır
   - pm2-reload-env.sh'ı tetikler
   - Manuel müdahale gerekmez

3. **ecosystem.config.cjs Güncellendi:**
   - Dosya başına ENV cache uyarı yorumu eklendi
   - Script referansı eklendi

4. **CLAUDE.md Güncellendi:**
   - Kural #20: Script referansı eklendi
   - Kural #34: Git hook kuralı eklendi

### Tespit Edilen ENV Değişkenleri
- API Keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, HERMES_API_KEY
- Security: JWT_SECRET, SECRET_KEY, EMAIL_ENCRYPTION_KEY
- Config: ENV, DATABASE_PATH, CLAUDE_MODEL
- Email: IMAP_*, SMTP_*, EMAIL_*

---

## ✅ TAMAMLANAN GÖREV: database.py verify_* Connection Type Fix

**Tarih:** 2026-03-19

### Sorun
4 verify_* fonksiyonu sadece SELECT sorgusu yapıyor ama `get_write_connection()` kullanıyordu.
Bu gereksiz WRITE_LOCK alınmasına ve performans darboğazına neden oluyordu.

### Çözüm
4 fonksiyonda `get_write_connection()` → `get_connection()` değiştirildi:

| Fonksiyon | Satır | Değişiklik |
|-----------|-------|------------|
| verify_candidate_ownership | 5750 | get_write_connection → get_connection |
| verify_position_ownership | 5767 | get_write_connection → get_connection |
| verify_email_account_ownership | 5801 | get_write_connection → get_connection |
| verify_interview_ownership | 5818 | get_write_connection → get_connection |

### Not
`verify_department_pool_ownership` (satır 5784) zaten `get_connection()` kullanıyordu (önceki düzeltme).

---

## ✅ TAMAMLANAN GÖREV: synonyms.py Context Manager Bug Fix

**Tarih:** 2026-03-19

### Sorun
`get_connection()` bir `@contextmanager` dekoratörü ile tanımlı. `with` bloğu olmadan çağrıldığında:
- `_GeneratorContextManager` objesi döner (sqlite3 connection DEĞİL)
- `.execute()` metodu yok → `AttributeError` riski
- 500 Internal Server Error potansiyeli

### Çözüm
12 endpoint'te `conn = get_connection()` pattern'ı `with get_connection() as conn:` pattern'a dönüştürüldü:

| Fonksiyon | Eski Satır | Açıklama |
|-----------|------------|----------|
| list_synonyms | 661 | Paginated synonym listesi |
| synonym_audit_report | 1024 | Audit geçmişi |
| synonym_history | 1106 | Tek synonym geçmişi |
| create_synonym | 1201 | Duplicate kontrolü |
| delete_synonym_endpoint | 1348 | Yetki kontrolü |
| get_synonym_detail | 1443 | Detay görüntüleme |
| dictionary_stats | 2951 | Sözlük istatistikleri |
| language_stats | 3026 | Dil istatistikleri |
| ml_model_stats | 3203 | ML model istatistikleri |
| ml_model_history | 3292 | Model geçmişi |
| ml_training_data_stats | 3356 | Eğitim verisi istatistikleri |
| ml_dashboard | 3610 | ML dashboard |

### Silinen Kodlar
- `conn.execute("PRAGMA foreign_keys = ON")` - get_connection() içinde zaten var
- `conn.close()` - context manager otomatik yapıyor

### Dosya
- api/routes/synonyms.py: 360 ekleme, 386 silme (net -26 satır)

---

## ✅ TAMAMLANAN GÖREV: Hybrid Re-entrant Architecture - SQLite Kalıcı Çözüm

**Tarih:** 2026-03-18

### Çözüm Özeti
4 katmanlı mimari ile nested deadlock ve "database is locked" sorunları KALICI olarak çözüldü:

| Katman | Değişiklik | Satır |
|--------|-----------|-------|
| KATMAN 1 | WRITE_LOCK → RLock (nested deadlock koruması) | 38 |
| KATMAN 2 | save_v3_evaluation_to_db conn parametresi (atomiklik) | 13413 |
| KATMAN 3a | verify_department_pool_ownership: get_write → get_connection | 5784 |
| KATMAN 3b | pull_matching ilk SELECT: get_write → get_connection | 7709 |
| KATMAN 4 | pull_matching içinde save_v3 çağrısına conn geçirme | 8001 |

### Teknik Detaylar
- **RLock (Re-entrant Lock):** Aynı thread kilit içindeyken tekrar kilit alabilir
- **conn parametresi:** Nested çağrılarda mevcut bağlantıyı kullanarak deadlock önleme
- **SELECT optimizasyonu:** READ işlemlerinde WRITE_LOCK gereksiz tutulması engellendi

### Önceki Çözümler (Korunuyor)
- ✅ READ/WRITE connection separation (PARÇA 1-6)
- ✅ WAL mode + busy_timeout=30000
- ✅ retry mekanizması (save_v3_evaluation_to_db)

---

## Son 72 Saatte Tamamlananlar

### 21.03.2026 - AI Model Skorları Ortalama Fix
- ✅ **Aday Detay Modal: Ortalama AI skoru hesaplanıp gösteriliyor**
  - `avg_ai_score` (backend'de yok) yerine frontend'de dinamik hesaplama
  - Aktif model sayısına göre ortalama (0'dan büyük skorlar)
  - Hiç skor yoksa `-%` gösterimi

### 17.03.2026 - README Profesyonel Görünüm Güncelleme
- ✅ **README.md GitHub için profesyonel görünüm**
  - Yeni badge'ler: AI Multi-Model, Turkish Market, KVKK Compliant
  - Quick Links navigasyon tablosu
  - "Powered By" bölümü (Gemini, Claude, OpenAI, Hermes badge'leri)
  - "Why HyliLabs?" bölümü (Problem/Solution tablosu)
  - Mermaid.js mimari diyagramı (System Overview)
  - Scoring Flow ASCII diyagramı (V2+V3 akışı)
  - V3 Scoring detayları güncellendi

### 17.03.2026 - Güvenlik Temizliği
- ✅ **Sunucu IP'leri domain ile değiştirildi**
  - 116.203.29.174 → hylilabs.com (14 dosya)
  - 46.224.206.15 referansları silindi
  - SSH komutları SKILLS.md'den temizlendi
  - Git history BFG ile temizlendi
- ✅ **Backup dosyaları temizlendi**
  - src.bak klasörü silindi (238 dosya)
  - 36 .bak/.backup dosyası silindi

### 17.03.2026 - V3 Scoring Düzeltmeleri
- ✅ **Gemini JSON Parse Hatası Düzeltildi** — ai_evaluator.py
  - maxOutputTokens: 4096 → 8192 artırıldı
  - Gemini artık V3 Scoring yanıtı dönüyor
- ✅ **OpenAI Encoding Hatası Düzeltildi** — ai_evaluator.py
  - Accept-Encoding: identity header eklendi (3 yerde)
  - Brotli decoding hatası önlendi
- ✅ **CV Intelligence Tamamlandı** — 87/87 aday
  - Gemini ile kariyer analizi başarılı
- ✅ **V3 Scoring Çalışıyor**
  - Gemini: ✅ Aktif
  - Hermes: ✅ Aktif
  - OpenAI: Fallback olarak bekliyor


### 16.03.2026 - FAZ 17: İnşaat Sektörü ATS Zekası
- ✅ **Kanonik Form Normalizasyonu** — database.py
  - CONSTRUCTION_CANONICAL_MAPPING: 28 kanonik form, 150+ varyasyon
  - normalize_to_canonical(): "site manager" → "şantiye şefi" dönüşümü
  - get_all_variations_for_canonical(): Kanonik için tüm varyasyonlar
- ✅ **Kara Liste (Hard-Block)** — database.py
  - CONSTRUCTION_BLACKLIST: 11 hedef pozisyon, 30+ engelli terim
  - is_blacklisted_match(): "şantiye şefi" ↔ "aşçı şefi" ENGELLENİYOR
  - Bağlam kontrolü: CV'de inşaat terimleri varsa engelleme atlanıyor
- ✅ **Sertifika Kontrolü** — database.py + scoring_v2.py
  - CONSTRUCTION_CERTIFICATES: 8 sertifika tipi (İSG, Vinç, Elektrik, Kaynak vb.)
  - check_certificate_in_cv(): CV'de sertifika arama
  - get_required_certificates_for_position(): Pozisyon için zorunlu sertifikalar
  - calculate_certificate_penalty(): Puan cezası hesaplama
  - calculate_elimination_score(): Sertifika puan kırma (max 10 puan)
- ✅ **Keyword Grupları Genişletme** — database.py
  - EXCLUSIVE_KEYWORD_GROUPS: +10 inşaat alt grubu
  - semantic_domain_compatible(): İnşaat grupları arası uyumluluk
- ✅ **check_title_match() Güncelleme** — database.py
  - Kara liste kontrolü (önce)
  - Kanonik form eşleşmesi (öncelikli)
  - cv_text parametresi eklendi
- ✅ **Test:** 6/6 PASSED
- ✅ **Commit:** 1a0f60c

### 16.03.2026 - Aday Detay Modal Aksiyon Butonları
- ✅ **İşe Al/Arşivle/Elen → Arşiv/Kara Liste/Genel Havuz**
  - Durum bazlı koşullu görünürlük:
    - yeni: Arşivle + Kara Liste
    - pozisyona_atandi/mulakat: Arşivle + Kara Liste + Genel Havuza Taşı
    - arsiv: Genel Havuza Taşı
    - ise_alindi/blacklist: buton yok
  - Kara Liste: neden dialogu (min 5 karakter), POST /api/candidates/{id}/blacklist
  - Genel Havuza Taşı: mevcut elen endpoint kullanıyor
  - Arşivle: mevcut arsivle endpoint kullanıyor
  - Dosya: src/features/candidates/index.tsx

### 16.03.2026 - Havuzlar Değerlendirme Durumu Filtresi
- ✅ **"Tüm Durum" filtresi "Değerlendirme Durumu" ile değiştirildi**
  - STATUS_MAP: 7 eski durum → 6 yeni durum (Mülakat Değerlendirmesi ile uyumlu)
  - DB Migration: candidate_positions.status 'aktif' → 'beklemede' (52 kayıt)
  - Backend: get_position_candidates cp.status SELECT'e eklendi, 'aktif' filtresi kaldırıldı
  - Tüm 'aktif' referansları güncellendi (database.py, interviews.py, scheduler.py)
  - Yeni INSERT'lerde default status='beklemede'

### 16.03.2026 - Mülakat Değerlendirme Durumu Aksiyonları
- ✅ **Değerlendirme durumuna göre aday otomatik taşıma**
  - Frontend: "Sonuç Kararı" → "Değerlendirme Durumu", 6 seçenek (Beklemede, Değerlendirilecek, Genel Havuz, Arşiv, Kara Liste, İşe Alındı)
  - Backend: interviews.py PUT endpoint'e aday taşıma aksiyonu eklendi
  - Genel Havuz: durum='yeni', Genel Havuz'a taşı
  - Arşiv/Kara Liste: durum='arsiv', Arşiv'e taşı
  - İşe Alındı: durum='ise_alindi', tüm havuzlardan çıkar + update_hired_stats
  - Beklemede/Değerlendirilecek: sadece değerlendirme kaydedilir
  - Code Review: company_id izolasyonu, parametrize SQL, guncelleme_tarihi ✅

### 16.03.2026 - Mülakat Takvimi İşlemler Sütunu Sadeleştirildi
- ✅ **Liste görünümü işlem butonları güncellendi**
  - Düzenleme (kalem) ikonu artık openEval() çağırıyor (Değerlendirme penceresi açar)
  - ClipboardCheck (Değerlendir) butonu kaldırıldı
  - XCircle (İptal Et) butonu kaldırıldı
  - Kalan: Edit (değerlendirme açar) + Trash2 (sil)
  - Dosya: mulakat-takvimi/index.tsx

### 14.03.2026 - Durum Label "Yeni" → "Genel Havuzda"
- ✅ **UI'da 'yeni' durum label'ı "Genel Havuzda" olarak güncellendi**
  - dashboard/index.tsx: DURUM_LABELS mapping güncellendi
  - candidates/index.tsx: durumLabel() mapping + filtre dropdown güncellendi
  - Backend 'yeni' değeri DEĞİŞMEDİ (sadece frontend label)

### 17.03.2026 - Landing Page Düzeltme
- ✅ **AI Değerlendirme kartı metin düzeltmesi**
  - "Nous" → "Nous Research" olarak güncellendi
  - Dosya: src/features/landing/index.tsx satır 62

### 14.03.2026 - Favicon + Branding
- ✅ **HyliLabs favicon** — Logo_600x400.png'den oluşturuldu
  - favicon.png (32x32), favicon_light.png, favicon_16.png
  - index.html title + meta tags HyliLabs olarak güncellendi
  - SVG referansları kaldırıldı, sadece PNG kullanılıyor

### 14.03.2026 - Sayfa Başlık İkonları Kaldırıldı
- ✅ **4 sayfadan başlık ikonu kaldırıldı** (tutarlılık için)
  - havuzlar: FolderTree ikonu kaldırıldı
  - mulakat-takvimi: CalendarClock ikonu kaldırıldı
  - email-hesaplari: Mail ikonu kaldırıldı (listede Mail ikonu korundu)
  - synonyms: Languages ikonu kaldırıldı
  - Diğer 5 sayfa zaten ikonsuzdu (adaylar, cv-collect, dashboard, settings, user-management)

### 14.03.2026 - Content Sol Padding
- ✅ **Sidebar-content arası boşluk düzeltmesi**
  - authenticated-layout.tsx: SidebarInset içine `pl-4` wrapper div eklendi
  - Tüm sayfalar için tutarlı sol boşluk sağlandı

### 14.03.2026 - FAZ 15 Nginx + SSL Kurulumu
- ✅ **Nginx reverse proxy + SSL** — hylilabs.com domain aktif
  - Nginx 1.24.0 kuruldu
  - Certbot ile Let's Encrypt SSL sertifikası alındı
  - HTTP → HTTPS otomatik redirect
  - /api/* → FastAPI (8000), /* → Vite (3000)
  - vite.config.ts allowedHosts eklendi (403 fix)
  - Sertifika geçerliliği: 12 Haziran 2026
  - CLAUDE.md FAZ 15 olarak eklendi
- ✅ **CORS ayarları güncellendi** — api/main.py
  - https://hylilabs.com eklendi
  - https://www.hylilabs.com eklendi
  - Development origin korundu
- ✅ **Günlük DB Yedekleme** kuruldu
  - /var/www/hylilabs/backup.sh (cron 03:00)
  - 7 günden eski yedekler otomatik siliniyor

### 14.03.2026 - Sidebar Toggle + Logo
- ✅ **Sidebar tüm sayfalarda açılır/kapanır**
  - Global Header: authenticated-layout.tsx
  - Sidebar durumu cookie ile korunuyor
  - CLAUDE.md kural #38 eklendi
- ✅ **Login + Sidebar logoları PNG ile güncellendi**

### 14.03.2026 - FAZ 13 Layer Scores Sistemi
- ✅ **FAZ 13.1-13.6**: Layer scores analizi + backend + frontend entegrasyonu
  - FAZ 13.1: AI analizi (scores boş kalıyor sorunu)
  - FAZ 13.2: smart_prompt_builder.py ZORUNLU vurgusu
  - FAZ 13.3: ai_evaluator.py scores validation + fallback
  - FAZ 13.4: pools.py scores + layer_scores alias
  - FAZ 13.5: pools.py scoring_info (v2/v3 ağırlıkları)
  - FAZ 13.6: havuzlar/index.tsx loadDetail + Skor Detayı kartı
- ✅ **FAZ 13.7: ScoreBadge match_score Bug Fix**
  - Sorun: "Uyum Değerlendirmesi" badge V3 skoru (92) gösteriyordu, match_score (68) göstermeli
  - Çözüm: v3Evaluation.total_score → c.match_score (tablo), cd.match_score (kart)
  - Dosya: src/features/havuzlar/index.tsx
  - Satır 825 (tablo): score={c.match_score || 0}
  - Satır 979 (kart): score={cd.match_score || 0}

### 13.03.2026 - CV Topla Sekme Birleştirme
- ✅ **Tekli + Toplu Yükleme birleştirildi** → tek "Manuel CV Yükle" sekmesi
  - 4 sekme → 3 sekme: "Manuel CV Yükle", "Email'den Topla", "Toplama Geçmişi"
  - Tek dosya seçildiğinde direkt yükleme (progress UI yok)
  - Çoklu dosya seçildiğinde toplu akış (dosya listesi, progress bar, özet kartı)
  - 20+ dosya engeli korundu, 10+ uyarı kaldırıldı (bulkWarning state silindi)
  - Drag & drop tek zone'da birleşik çalışıyor

### 13.03.2026 - Toplu CV Yükleme (Max 20)
- ✅ **Toplu CV Yükleme** — tek seferde max 20 CV, sıralı işleme
  - Backend: POST /api/cv/bulk-upload endpoint (api/routes/cv.py)
  - Frontend: "Manuel CV Yükle" sekmesi (src/features/cv-collect/index.tsx)
  - Drag & drop desteği, format validasyonu (PDF/DOCX)
  - Sıralı işleme + progress bar + dosya bazlı durum ikonu
  - İptal butonu, özet kartı, hata devam mekanizması
  - KVKK audit log aktif
  - CLAUDE.md kural #36 eklendi

### 13.03.2026 - Landing Page
- ✅ **Neden HyliLabs? bölümü** (Fiyatlandırma kaldırıldı, yerine eklendi)
  - 6 kart: Zaman Tasarrufu, KVKK Uyumlu, Akıllı Eşleştirme, Türkçe Dil Desteği, Otomatik Süreç, Multi-Tenant Güvenlik
  - Büyük rakam/yüzde vurgusu ile özellikler bölümünden farklı tasarım
  - Navbar + Footer linkleri güncellendi
  - plans array kaldırıldı, whyReasons array eklendi
  - 3 yeni ikon: lock, globe, clock
- ✅ **Çözüm Ortaklarımız bölümü** + partner logo güncellemeleri
- ✅ **Landing Page Entegrasyonu** (route yapısı, auth guard, logo entegrasyonu)

### 13.03.2026
- ✅ **FAZ 12: V3 Puanlama Bug Fix** (tamamlandı)
  - **FAZ 12.1**: ai_evaluator.py düzeltmeleri
    - Hermes/model skorları max 100 cap eklendi (satır 873)
    - Claude 0 fallback koşulu eklendi (satır 1023)
    - Claude 0 uyarı logu + notes_for_hr eklendi
  - **FAZ 12.2**: database.py retry mekanizması
    - save_v3_evaluation_to_db() 3 retry + exponential backoff (0.5s, 1s, 1.5s)
    - "database is locked" hatası için otomatik yeniden deneme
  - **FAZ 12.3**: DB hatalı verileri düzeltildi
    - Hermes > 100 olanlar 100'e cap edildi (1 kayıt)
    - Aday 447: V3=93, Match=82 hesaplandı (hermes+openai ortalaması)
    - Aday 397: V3=41, Match=42 hesaplandı (hermes+openai ortalaması)
  - **FAZ 12.3.1**: V2 skorları düzeltildi (19 kayıt)
    - Tersine hesaplama: v2 = (match - (v3 × 0.60)) / 0.40
    - Aday 447: V2=66, Aday 397: V2=44
    - V2=0 kalan kayıt: 0
  - **FAZ 12.4**: Frontend match_score gösterimi düzeltildi
    - Tablo skor kolonu: v3Evaluation.total_score → c.match_score (satır 803)
    - Kart detay skoru: v3Evaluation.total_score → cd.match_score (satır 947)
    - v3Evaluation: Sadece AI model detayları için kullanılıyor (Gemini, Hermes, OpenAI)
    - TypeScript build: OK
  - **FAZ 12.4.2**: Detail endpoint düzeltildi (pools.py)
    - SELECT: match_score, v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
    - candidate objesine 7 yeni alan eklendi
    - Aday kartı artık doğru match_score gösteriyor
  - **FAZ 12.6**: Genel Havuz tutarsızlığı düzeltildi
    - 17 orphan aday Genel Havuz'a taşındı (V3 < 40 ile elenenler)
    - 2 adayın durumu pozisyona_atandi yapıldı
    - database.py:7261-7285 V3 eleme sonrası Genel Havuz sync eklendi
    - Artık V3 < 40 ile elenen adaylar otomatik Genel Havuz'a dönüyor
  - **FAZ 12.6.1**: candidate_pool_assignments sync düzeltildi
    - 18 eksik aday kaydı candidate_pool_assignments tablosuna eklendi
    - V3 eleme sonrası candidate_pool_assignments INSERT eklendi (database.py:7281)
    - Frontend Genel Havuz artık 58 aday gösteriyor (40 yerine)
  - **FAZ 12.8**: ai_evaluations kozmetik düzeltme
    - 15 kayıt düzeltildi (consensus_method='claude_decision' + total_score=0)
    - 5 kayıt: average_fallback (Hermes+OpenAI ortalaması)
    - 10 kayıt: single_model_fallback (sadece Hermes)
    - 2 tek model aday analizi: OpenAI sigorta öncesi değerlendirme (beklenen davranış)
- ✅ **FAZ 11: V3 Skor Frontend Entegrasyonu**
  - **FAZ 11.1**: candidate_positions tablosuna 6 yeni kolon eklendi
    - v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
  - **FAZ 11.2**: Mevcut V3 veriler ai_evaluations'dan migrate edildi (19 kayıt)
  - **FAZ 11.2.1**: match_score weighted average güncellendi (17 kayıt v3_weighted)
  - **FAZ 11.3**: add_candidate_to_position() ve ilgili fonksiyonlar güncellendi
    - Yeni parametreler: v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
    - match_single_candidate_to_positions() V3 skorları ile çağırıyor
    - pull_matching_candidates_to_position() UPDATE V3 skorları ekliyor
  - **FAZ 11.4**: get_position_candidates() V3 kolonları döndürüyor
  - **FAZ 11.5**: Frontend loadCandidates() v3Evaluation state'ini otomatik dolduruyor
  - V3 skorları artık sayfa yüklendiğinde görünür (Değerlendir tıklamaya gerek yok)
- ✅ **FAZ 10.1: V3 Sync Değerlendirme Entegrasyonu**
  - pull_matching_candidates_to_position fonksiyonuna V3 eklendi
  - Weighted average formülü: Final = (V3 × 0.60) + (V2 × 0.40)
  - save_v3_evaluation_to_db() fonksiyonu eklendi (satır 12317)
  - V3 değerlendirme sonucu ai_evaluations tablosuna kaydediliyor
  - final_score < 40 → aday pozisyondan çıkarılıyor
  - match_reason: "V3 weighted (60%V3+40%V2)" gösteriliyor
- ✅ **Gemini Maliyet Optimizasyonu** (69c41f6)
  - gemini-2.5-pro → gemini-2.5-flash değişti
  - Thinking mode (thinkingConfig) kaldırıldı
  - Beklenen maliyet düşüşü: %95
  - ai_evaluator.py ve cv_intelligence.py güncellendi

### 12.03.2026
- ✅ **FAZ 6: Demo Test + Dokümantasyon Tamamlandı**
  - Demo raporu oluşturuldu (TOP 10 aday, havuz özeti, V3 istatistikleri)
  - Frontend erişilebilir (HTTP 200)
- ✅ **FAZ 5: Production Hazırlık Tamamlandı**
  - DB backup: backup_pre_demo_20260312_120510.db (77 MB)
  - Sunucu: 24 gün uptime, %27 disk, 825 MB RAM
  - PM2 startup: enabled
- ✅ **FAZ 4: Bug Fix + Polish Tamamlandı**
  - Error log: Temiz (hata yok)
  - DB tutarlılık: 81 aday, 28 V3 eval, 0 orphan
  - API health: OK
- ✅ **FAZ 3: V3 Batch Değerlendirme Tamamlandı**
  - 28 aday V3 ile değerlendirildi
  - Mükemmel (85-100): 8, İyi (70-84): 3, Orta (55-69): 2
  - Zayıf (40-54): 2, Uyumsuz (0-39): 13
  - Eligible: 20 (%71), Not Eligible: 8 (%29)
  - Consensus: average (19), claude_decision (9)
- ✅ **Scoring V3 batch_evaluate.py Fix** (1255f71)
  - `layer_scores` AttributeError düzeltildi (attribute yok)
  - `openai_score`, `models_used`, `scores` eklendi (getattr fallback)
  - Verbose output: consensus_method, claude_used gösteriliyor
  - Analiz: Sistem doğru çalışıyor (Claude hakim kararı)
- ✅ **OpenAI Sigorta Sistemi** (6efa98d - 11.03.2026)
  - Gemini/Hermes başarısız olunca OpenAI fallback
  - ai_evaluator.py: 3 model paralel + consensus
  - CandidateEvaluationResponse: openai_score, models_used

### 10.03.2026
- ✅ **Havuz Düzenle modal scroll fix** (7ab8e62)
  - Uzun içeriklerde Kaydet butonuna ulaşılabiliyor
  - max-h-[90vh], overflow-y-auto, sticky footer

### 09.03.2026
- ✅ **HyliLabs Logo Ekleme** (cf3841a)
  - PNG optimize: 1.45 MB → 222 KB (%85 küçültme)
  - logo.tsx: PNG kullanan img bileşeni
  - Sidebar: Logo + "HyliLabs" / "AI HR Platform"
  - Login: Logo + "HyliLabs"
- ✅ **Progress UI Step 4: API + Frontend Progress Bar** (ab71c7a)
  - GET /api/cv/processing-status endpoint
  - processingStatus state + 5sn polling
  - Progress bar UI (Email sekmesinde)
  - Aktif taramalar gerçek zamanlı izlenebilir
- ✅ **Progress UI Step 3: Worker Progress Entegrasyonu** (56d065d)
  - Başlangıç log: durum='devam_ediyor' ile kayıt oluştur
  - Progress update: Her 25 CV'de bir update
  - Bitiş: update_email_collection_log ile final durum
  - Fallback: log_id yoksa yeni kayıt oluştur
- ✅ **Progress UI Step 2: update_email_collection_log fonksiyonu** (f6c4a04)
  - database.py'ye update_email_collection_log() eklendi
  - Dinamik UPDATE sorgusu (sadece non-None alanlar)
  - bitis_zamani otomatik güncelleme
  - with get_connection() context manager kullanımı
- ✅ **Progress UI Step 1: log_email_collection entegrasyonu**
  - email_worker.py'ye log_email_collection import eklendi
  - check_emails_for_account() sonunda log çağrısı eklendi
  - Scheduler-triggered taramalar artık DB'ye loglanacak
  - Durum tespiti: tamamlandi/kismi_basarili/bos/basarisiz
- ✅ **Keyword double encoding fix** (9f79fe0)
  - handleUpdatePool: editKeywords array kullanılıyor
  - Çift JSON encoding sorunu çözüldü
- ✅ **Keyword parse bug fix** (f45979c)
  - Havuz düzenle modalında anahtar kelimeler doğru görünüyor
  - json.loads ile JSON string parse, split fallback korundu
- ✅ **Manuel Giriş sekmesi kaldırıldı** (723bcc9)
  - Pozisyon ekleme: Sadece "URL ile Ekle" ve "Dokümandan Ekle" kaldı
  - grid-cols-3 → grid-cols-2, 30 satır TabsContent silindi
- ✅ **Email CV check scheduler.py'ye taşındı** (67253b7)
  - Saat başı çalışma (00:00-23:00), APScheduler CronTrigger
  - email_worker.py'den schedule döngüsü kaldırıldı
  - Fonksiyonlar korundu (check_all_emails, check_emails_for_account)
- ✅ **CLAUDE.md 3-Katmanlı Mimari** (fe210fe)
  - MİMARİ PRENSİPLER bölümü eklendi
  - 3-Katmanlı Sistem: Directive, Orchestration, Execution
  - Self-Annealing Döngüsü: hata → düzeltme → öğrenme
  - Execution Mapping tablosu
- ✅ **Pozisyon sil→aday kaybı FIX TAM** (f872d62 + 53d2419)
  - Kısım 1: CV Çek sadece durum='yeni' tarıyor (f872d62)
  - Kısım 2: Pozisyon silinince TÜM adaylar Genel Havuz'a (53d2419)
  - 30 gün arşiv mantığı kaldırıldı
- ✅ **Otomatik arşivleme kuralı güncellendi** (9f8ca0b)
  - 30→90 gün, eşleşme kontrolü eklendi (candidate_positions)
  - candidates.durum güncelleme bug'ı düzeltildi
- ✅ **Kara Liste UI İyileştirmeleri** — TAM (4de9ddb)
  - Havuzlar: "Durum" kolonu → "Kara Liste" kolonu
  - Ban ikonu tıklanabilir (kara listede değilse)
  - "Kara Listede" badge (kara listedeyse)
  - Duplicate Ban butonu kaldırıldı
  - Blacklist info kartı (neden, ekleyen, tarih)
  - "Kara Listeden Çıkar" butonu + modal
  - loadDetail'de blacklist info fetch
  - DELETE API: body → query param
- ✅ **Kara Liste Badge + Info** — havuzlar + candidates (d43b22e)
  - Durum badge blacklist önceliği
  - Kara liste bilgi kartı
  - Çıkarma modalları

### 08.03.2026
- ✅ **Kara Liste Sistemi TAM** — database + API + frontend (16aee37)
  - blacklisted_candidates tablosu (15 kolon, 3 index)
  - candidates.is_blacklisted + blacklist_id kolonları
  - create_candidate() blacklist check + cv.py handling
  - 4 DB fonksiyon + 3 API endpoint
  - get_all_candidates() + get_candidates_count() blacklist filtresi
  - havuzlar: Ban butonu, dialog, kırmızı satır
  - candidates: durum dropdown, badge, kırmızı satır
- ✅ AI Evaluation prompt TAM güncelleme — 16 yeni değişken, Türkçe (3a9f1b6)
- ✅ critical_matched dict→string dönüşüm fix (ad98978)
- ✅ .claudeignore oluşturuldu (0e7c03b)
- ✅ CLAUDE.md güncellendi — puanlama, fazlar, savunma sistemleri (a3308e1)
- ✅ activeContext.md temizliği

### 07.03.2026
- ✅ Görev Tanımı Upload Response Fix (6264245)
- ✅ 100 Puan Sistemi Rescore (2a53de5)
- ✅ Frontend Seniority Score Gösterimi (906cd98)
- ✅ AI Evaluation Prompt Fix (0004039)
- ✅ Dil Seviyesi 2. Katman Savunma (2580726)
- ✅ FAZ D: 110→100 Puan Rebalance (4378a26)
- ✅ [object Object] Render Fix (c3560c5)
- ✅ DB Lock Kalıcı Çözüm (8dfa5e7)
- ✅ Toast X Butonu Fix
- ✅ Duplicate Teknik Beceri Temizlik

### 06.03.2026
- ✅ FAZ B: Görev Tanımı Upload (backend + frontend)
- ✅ FAZ C: Görev Eşleşmesi + 15 Puan Task Kategorisi
- ✅ CV Parser İyileştirmeleri

## Geçmiş Hafta Özeti

| Tarih | Görev Sayısı | Ana Konular |
|-------|--------------|-------------|
| 05.03 | 8 | FAZ A tamamlandı, G1 title threshold |
| 04.03 | 10 | Mülakat sistemi, puanlama |
| 03.03 | 17 | Dashboard, CV, arama |
| 02.03 | 4 | FAZ 10 |
| 01.03 | 11 | FAZ 7-8, keyword lifecycle |
| 28.02 | 6 | FAZ 5-6, security audit |

## Devam Eden / Açık Görevler

### 🟠 ORTA
1. **Generic keyword temizliği** — üç aylık, quarterly gibi terimler

### 🟡 DÜŞÜK
2. **Görev tanımı duplicate uyarısı** — aynı pozisyona 2. yüklemede uyarı

### ⏸️ BEKLEYEN
3. **Görev eşleşmesi karar raporu** — A/B/C seçenek onayı bekliyor
4. **Kariyer Sayfası** — güvenlik taraması sonrası
5. **FAZ 7.6 Data Cleanup** — corrupted keywords, orphaned synonyms

## Tamamlanan Büyük Özellikler

### FAZ 15 - Production Deployment ✅ (14.03.2026)

**Tamamlanan İşler:**
- [x] Domain: hylilabs.com DNS ayarları yapılandırıldı
- [x] Nginx 1.24.0 kurulumu + reverse proxy (3000→frontend, 8000→backend)
- [x] SSL: Let's Encrypt sertifikası (12 Haziran 2026'ya kadar geçerli)
- [x] HTTP → HTTPS redirect (301)
- [x] CORS: hylilabs.com + www.hylilabs.com eklendi
- [x] Frontend API URL: .env.production (VITE_API_URL=https://hylilabs.com)
- [x] 16 dosyada hardcoded URL → import.meta.env.VITE_API_URL
- [x] Branding: Title, meta tags, favicon (HyliLabs)
- [x] Vite allowedHosts fix

**Commitler:**
- a58d11f: Nginx + SSL kurulumu
- 61888c7: CORS güncelleme
- fcb86fd: Favicon + branding

**Konfigürasyon Dosyaları:**
- /etc/nginx/sites-available/hylilabs
- /var/www/hylilabs/.env.production
- /var/www/hylilabs/.env.development

**Erişim:**
- Production: https://hylilabs.com
- Development: http://localhost:3000

### Pozisyon Sil→Aday Kaybı Fix ✅ (09.03.2026)
- [x] CV Çek sadece durum='yeni' tarıyor (f872d62)
- [x] Pozisyon silinince TÜM adaylar Genel Havuz'a (53d2419)
- [x] Otomatik arşivleme 30→90 gün + eşleşme kontrolü (9f8ca0b)

### Kara Liste Sistemi ✅ (08-09.03.2026)
- [x] Database layer (blacklisted_candidates tablosu)
- [x] Backend API endpoints (routes/candidates.py)
- [x] Frontend UI (havuzlar + candidates)
- [x] Blacklist info kartı + çıkarma modalı (4de9ddb)
- [x] Deploy ve test (sunucuda)

## Sonraki Hedef

### Bekleyen Görevler
1. **Görev Tanımı sekmesi** — Manuel Giriş yerine Görev Tanımı (pozisyon ekleme)
2. **Generic keyword temizliği**
3. **Kariyer Sayfası** (Security taraması önce)

## Notlar

- CLAUDE.md'de tüm kalıcı kurallar mevcut (909 satır, FAZ 15 eklendi)
- progress.md güncellenmeli (17 gün eski)
- .claudeignore aktif (~2.6 GB filtreleniyor)
