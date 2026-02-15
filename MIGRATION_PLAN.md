# HyliLabs Göç Planı — TalentFlow (Streamlit) → HyliAI (React + FastAPI)

**Tarih:** 15 Şubat 2026
**Hazırlayan:** Planlama oturumu (Claude Opus + EMRAHFC)
**Kural:** Küçük adımlar, her adım test edilir, korunan sistemlere DOKUNULMAZ.

---

## 1. MEVCUT SİSTEM HARİTASI

### 1.1 Sunucular

| Sunucu | IP | Amaç |
|--------|-----|------|
| TalentFlow (Production) | ***REMOVED*** | Mevcut çalışan sistem (Streamlit) |
| HyliLabs (Dev/Test) | ***REMOVED*** | Yeni React frontend |

### 1.2 Mevcut Dosya Yapısı (TalentFlow)

```
/var/www/talentflow/
├── app.py                 (467KB, 9700+ satır) — TÜM UI KODU
├── database.py            (324KB, 8700+ satır) — TÜM DB FONKSİYONLARI
├── scoring_v2.py          (38KB) — ⛔ KORUNAN: Puanlama sistemi
├── candidate_matcher.py   (74KB) — ⛔ KORUNAN: Eşleştirme motoru
├── cv_parser.py           (36KB) — ⛔ KORUNAN: CV okuma/parse
├── keyword_stats.py       (16KB) — ⛔ KORUNAN: Keyword istatistikleri
├── email_worker.py        (16KB) — Email toplama worker
├── email_reader.py        (13KB) — Email okuma
├── email_sender.py        (13KB) — Email gönderme
├── email_automation.py    (21KB) — Email otomasyonu
├── workflows.py           (37KB) — İş akışları
├── audit_logger.py        (25KB) — Denetim kayıtları
├── validators.py          (11KB) — Doğrulama kuralları
├── config.py              (19KB) — Yapılandırma
├── models.py              (4KB)  — Veri modelleri
├── events.py              (7KB)  — Olay sistemi
├── rate_limiter.py        (10KB) — Hız sınırlama
├── ai_agents.py           (27KB) — AI agent fonksiyonları
├── create_pdf_report.py   (27KB) — PDF rapor oluşturma
├── rapor_olustur.py       (22KB) — Rapor oluşturma
├── eval_report.py         (5KB)  — Değerlendirme raporu
├── job_scraper.py         (15KB) — İş ilanı çekme
├── seed_data.py           (10KB) — Örnek veri
├── cron_archive.py        (0.5KB)— Arşiv cron
├── setup_cron.py          (5KB)  — Cron kurulumu
│
├── MIGRATION/TEST DOSYALARI (Taşınmayacak):
│   ├── migrate_matches_fk.py
│   ├── migrate_positions_to_v2.py
│   ├── scoring_v2_migration.py
│   ├── debug_match_issue.py
│   ├── re_match_all_candidates.py
│   ├── test_*.py (4 adet)
│
└── data/
    └── talentflow.db      — SQLite veritabanı (36 tablo)
```

### 1.3 Veritabanı Tabloları (36 adet)

**Çekirdek tablolar (kesinlikle taşınacak):**
- candidates, candidate_positions, candidate_pool_assignments
- companies, users, plans
- department_pools, position_pools, positions
- matches, position_keywords_v2, position_criteria
- keyword_dictionary, approved_title_mappings, job_titles

**İşlevsel tablolar (taşınacak):**
- email_accounts, email_collection_logs, email_logs, email_templates
- interviews, ai_evaluations, ai_analyses, hr_evaluations
- audit_logs, api_usage_logs, rate_limits
- company_settings, applications

**Yardımcı tablolar (gerekirse taşınacak):**
- candidate_merge_logs, matches_backup, password_reset_tokens
- department_templates, position_templates
- position_requirements, position_sector_preferences
- position_title_mappings

### 1.4 Sayfa Haritası (app.py)

| # | Sayfa | Fonksiyon | Satır Aralığı | Boyut | Zorluk | Rol |
|---|-------|-----------|---------------|-------|--------|-----|
| 1 | Dashboard | show_dashboard() | 3017-3350 | ~330 | Düşük | Herkes |
| 2 | CV Topla | show_cv_collector() | 8054-8418 | ~360 | Orta | Admin+ |
| 3 | Adaylar | show_candidates() | 3350-4822 | ~1470 | Yüksek | Herkes |
| 4 | Havuzlar | show_pools() | 4822-7408 | ~2590 | Çok Yüksek | Herkes |
| 5 | Mülakat Takvimi | show_interviews() | 8418-8847 | ~430 | Orta | Herkes |
| 6 | Keyword İstatistikleri | show_keyword_stats() | 9423-9584 | ~160 | Düşük | Herkes |
| 7 | Email Hesapları | show_email_accounts() | 7448-8054 | ~600 | Orta | Company Admin |
| 8 | Kullanıcı Yönetimi | show_company_users() | 9214-9423 | ~210 | Düşük | Company Admin |
| 9 | Ayarlar | show_settings() | 9584-son | ~135 | Düşük | Company Admin |
| 10 | Firma Yönetimi | show_company_management() | 8847-9100 | ~250 | Düşük | Super Admin |
| 11 | Tüm Kullanıcılar | show_all_users() | 9100-9214 | ~110 | Düşük | Super Admin |
| 12 | Admin Paneli | show_admin_panel() | 1724-3017 | ~1290 | Yüksek | Super Admin |
| 13 | Login | show_login_page() | 1560-1643 | ~83 | Düşük | Public |

### 1.5 Menü Yapısı (Role Göre)

**Super Admin:**
Dashboard, Firma Yönetimi, Tüm Kullanıcılar, Admin Paneli, Ayarlar

**Company Admin:**
Dashboard, CV Topla, Adaylar, Havuzlar, Mülakat Takvimi, Keyword İstatistikleri, Email Hesapları, Kullanıcı Yönetimi, Ayarlar

**Normal User:**
Dashboard, CV Topla, Adaylar, Havuzlar, Mülakat Takvimi, Keyword İstatistikleri

### 1.6 Cron Jobs

| Zamanlama | İş | Dosya |
|-----------|-----|-------|
| Her gece 00:00 | Email'den CV topla | email_worker.py |
| Her gece 03:00 | 30 gün eski → Arşiv | cron_archive.py |

---

## 2. ⛔ DOKUNULMAZ / KORUNAN SİSTEMLER

**BU DOSYALAR AYNEN TAŞINACAK, İÇERİKLERİ DEĞİŞTİRİLMEYECEK:**

| Dosya | Ne Yapıyor | Neden Korunan |
|-------|-----------|---------------|
| scoring_v2.py | v2.1 puanlama — dynamic knockout(%50), junior/senior penaltı, eğitim kademeli, hibrit must_have | %100 doğruluk sağlandı, değiştirilmemeli |
| candidate_matcher.py | Fuzzy:85/92 eşik, max 5 pozisyon/aday, AI prompt max 5 başlık | %100 doğruluk, değiştirilmemeli |
| cv_parser.py | Claude API ile CV parse, %100 başarılı | Bozulmamalı |
| keyword_stats.py | Keyword istatistik sistemi | Çalışıyor, dokunma |
| database.py fonksiyonları | pull_matching_candidates_to_position, approved_title_mappings sorguları | Çalışan havuz sistemi |

**KURAL:** Bu dosyalar backend'e olduğu gibi kopyalanır. Sadece üzerine API endpoint wrapper yazılır. İç mantığa dokunulmaz.

---

## 3. YENİ SİSTEM MİMARİSİ

### 3.1 Hedef Yapı

```
HyliLabs Sunucu (***REMOVED***)
├── /var/www/hylilabs/          ← React Frontend (Shadcn Admin)
│   └── src/
│       ├── pages/              ← Her sayfa bir component
│       ├── components/         ← Ortak UI parçaları
│       ├── api/                ← API çağrı fonksiyonları
│       └── auth/               ← Login/session
│
└── /var/www/hylilabs-api/      ← FastAPI Backend (Python)
    ├── main.py                 ← FastAPI app
    ├── routes/                 ← API endpoint dosyaları
    │   ├── auth.py
    │   ├── dashboard.py
    │   ├── candidates.py
    │   ├── pools.py
    │   ├── cv_collect.py
    │   ├── interviews.py
    │   ├── keywords.py
    │   ├── email_accounts.py
    │   ├── users.py
    │   ├── companies.py
    │   └── settings.py
    ├── core/                   ← ⛔ KORUNAN DOSYALAR (aynen kopyalanır)
    │   ├── scoring_v2.py
    │   ├── candidate_matcher.py
    │   ├── cv_parser.py
    │   └── keyword_stats.py
    ├── database.py             ← Mevcut fonksiyonlar (aynen)
    ├── models.py
    ├── config.py
    └── requirements.txt
```

### 3.2 İletişim Akışı

```
Kullanıcı → React (port 3000) → API call → FastAPI (port 8000) → database.py → SQLite/PostgreSQL
                                                                 → scoring_v2.py
                                                                 → candidate_matcher.py
                                                                 → cv_parser.py
```

---

## 4. TAŞIMA SIRASI VE ADIMLARI

### ⚠️ ALTIN KURALLAR
1. Her adım MAX 1 dosya veya 1 endpoint grubu
2. Her adımdan sonra TEST edilir
3. Streamlit KAPANMAZ, paralel çalışır
4. Korunan dosyalara DOKUNULMAZ
5. Antigravity'ye her seferinde KÜÇÜK görev verilir

---

### FAZ 0 — Backend İskeleti (1-2 gün)

**Amaç:** FastAPI projesini oluştur, korunan dosyaları kopyala, DB bağlantısını kur.

#### Adım 0.1 — FastAPI projesi oluştur
```
Antigravity'ye görev:
─────────────────────
HyliLabs sunucusunda (***REMOVED***) FastAPI backend oluştur.

Konum: /var/www/hylilabs-api/

Dosya yapısı:
/var/www/hylilabs-api/
├── main.py          ← FastAPI app, CORS ayarları (localhost:3000 izinli)
├── requirements.txt ← fastapi, uvicorn, python-multipart, anthropic
├── routes/          ← boş klasör
└── core/            ← boş klasör

main.py içeriği:
- FastAPI app
- CORS middleware (origins: ["http://***REMOVED***:3000"])
- GET /api/health → {"status": "ok"}

Test: curl http://localhost:8000/api/health → {"status": "ok"}

Sadece bu kadar. Başka hiçbir şey ekleme.
Commit: "feat: FastAPI backend iskeleti"
```

#### Adım 0.2 — Korunan dosyaları kopyala
```
Antigravity'ye görev:
─────────────────────
TalentFlow GitHub reposundan şu dosyaları /var/www/hylilabs-api/core/ altına kopyala:

git clone https://github.com/osmanemraheroglu/talentflow.git /tmp/talentflow
cp /tmp/talentflow/scoring_v2.py /var/www/hylilabs-api/core/
cp /tmp/talentflow/candidate_matcher.py /var/www/hylilabs-api/core/
cp /tmp/talentflow/cv_parser.py /var/www/hylilabs-api/core/
cp /tmp/talentflow/keyword_stats.py /var/www/hylilabs-api/core/
cp /tmp/talentflow/database.py /var/www/hylilabs-api/
cp /tmp/talentflow/config.py /var/www/hylilabs-api/
cp /tmp/talentflow/models.py /var/www/hylilabs-api/
cp /tmp/talentflow/validators.py /var/www/hylilabs-api/
cp /tmp/talentflow/audit_logger.py /var/www/hylilabs-api/
cp /tmp/talentflow/email_reader.py /var/www/hylilabs-api/
cp /tmp/talentflow/email_sender.py /var/www/hylilabs-api/
cp /tmp/talentflow/email_worker.py /var/www/hylilabs-api/
cp /tmp/talentflow/email_automation.py /var/www/hylilabs-api/
cp /tmp/talentflow/workflows.py /var/www/hylilabs-api/
cp /tmp/talentflow/rate_limiter.py /var/www/hylilabs-api/
cp /tmp/talentflow/events.py /var/www/hylilabs-api/
cp /tmp/talentflow/cron_archive.py /var/www/hylilabs-api/

⛔ BU DOSYALARIN İÇERİĞİNİ DEĞİŞTİRME. SADECE KOPYALA.

Commit: "feat: TalentFlow backend dosyaları kopyalandı"
```

#### Adım 0.3 — DB bağlantısını test et
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs-api/main.py dosyasına test endpoint ekle:

GET /api/test/db → database.py'den get_connection() çağır,
candidates tablosundan COUNT(*) döndür.

⛔ database.py dosyasını DEĞİŞTİRME. Sadece import et ve kullan.

Test: curl http://localhost:8000/api/test/db → {"candidate_count": X}

Commit: "test: DB bağlantısı doğrulandı"
```

**FAZ 0 BİTİŞ TESTİ:**
- [ ] /api/health çalışıyor
- [ ] /api/test/db veritabanından veri dönüyor
- [ ] core/ klasöründe 4 korunan dosya var
- [ ] Hiçbir dosya değiştirilmedi

---

### FAZ 1 — Auth Sistemi (1-2 gün)

#### Adım 1.1 — Login API endpoint
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs-api/routes/auth.py oluştur.

Mevcut database.py'deki şu fonksiyonları kullan (DEĞİŞTİRME):
- verify_user_login(email, password)
- get_user_by_id(user_id)

Endpoint'ler:
POST /api/auth/login
  Body: {"email": "...", "password": "..."}
  Başarılı → JWT token döndür
  Başarısız → 401

GET /api/auth/me (Authorization: Bearer token gerekli)
  → Kullanıcı bilgilerini döndür (id, ad_soyad, email, role, company_id)

JWT secret: config.py'den al veya .env dosyasından oku.

⛔ database.py fonksiyonlarını DEĞİŞTİRME. Sadece import et.

Test:
1. curl -X POST /api/auth/login -d '{"email":"admin@test.com","password":"..."}'
2. Token ile: curl -H "Authorization: Bearer TOKEN" /api/auth/me

Commit: "feat: Auth API - login + JWT"
```

#### Adım 1.2 — React Login sayfası
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs/ React projesinde login sayfası oluştur.

Shadcn Admin template'inde zaten login sayfası var.
Sadece form submit'i /api/auth/login endpoint'ine bağla.

1. Email + şifre formu
2. POST /api/auth/login çağır
3. Başarılı → token'ı localStorage'a kaydet, /dashboard'a yönlendir
4. Başarısız → hata mesajı göster

⛔ Template'in diğer dosyalarına DOKUNMA. Sadece login sayfasını düzenle.

Test: Tarayıcıda login ol, token alınsın.

Commit: "feat: React login sayfası"
```

**FAZ 1 BİTİŞ TESTİ:**
- [ ] Login API çalışıyor
- [ ] React'ta login olunabiliyor
- [ ] JWT token dönüyor ve saklanıyor

---

### FAZ 2 — Dashboard (2-3 gün)

#### Adım 2.1 — Dashboard API endpoint'leri
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs-api/routes/dashboard.py oluştur.

Önce TalentFlow'da show_dashboard() fonksiyonunu oku (app.py satır 3017-3350).
Bu fonksiyonun çağırdığı database.py fonksiyonlarını bul.

Endpoint'ler:
GET /api/dashboard/stats
  → Toplam aday, aktif pozisyon, bugün başvuru, bekleyen,
    mülakat bekleyen, bu ay işe alınan

GET /api/dashboard/pool-distribution
  → Havuz dağılımı (pasta grafik verisi)

GET /api/dashboard/recent-activities
  → Son 10 aktivite (aday adı, tarih, işlem)

⛔ database.py fonksiyonlarını DEĞİŞTİRME. Sadece import et ve çağır.

Her endpoint'i test et:
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/dashboard/stats

Commit: "feat: Dashboard API endpoint'leri"
```

#### Adım 2.2 — React Dashboard sayfası
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs/ React projesinde Dashboard sayfası oluştur.

Shadcn Admin template'indeki dashboard component'lerini kullan.

Gösterilecekler:
1. Üstte 6 metrik kartı (stats endpoint'inden)
2. Aday Havuz Dağılımı pasta grafik (pool-distribution endpoint'inden)
3. Son Aktiviteler tablosu (recent-activities endpoint'inden)

API çağrıları /api/dashboard/* endpoint'lerine yapılacak.
Token'ı header'a ekle: Authorization: Bearer TOKEN

⛔ Template'in sidebar, header gibi layout kısımlarına DOKUNMA.
Sadece dashboard içerik alanını doldur.

Test: Sayfada veriler görünüyor mu?

Commit: "feat: React Dashboard sayfası"
```

#### Adım 2.3 — Dashboard karşılaştırma testi
```
Streamlit Dashboard ile React Dashboard'u yan yana aç.
Aynı sayılar görünüyor mu kontrol et:
- Toplam aday sayısı aynı mı?
- Havuz dağılımı aynı mı?
- Son aktiviteler aynı mı?
```

**FAZ 2 BİTİŞ TESTİ:**
- [ ] Dashboard API 3 endpoint çalışıyor
- [ ] React'ta metrik kartları doğru gösteriyor
- [ ] Streamlit ile aynı veriler
- [ ] Grafik çalışıyor

---

### FAZ 3 — Keyword İstatistikleri (1 gün) — EN KOLAY SAYFA

#### Adım 3.1 — Keyword API
```
Antigravity'ye görev:
─────────────────────
/var/www/hylilabs-api/routes/keywords.py oluştur.

Mevcut keyword_stats.py ve database.py fonksiyonlarını kullan.
show_keyword_stats() fonksiyonunu oku (app.py satır 9423-9584).

GET /api/keywords/stats
  → Keyword listesi, kullanım sayıları, kategori dağılımı

⛔ keyword_stats.py'yi DEĞİŞTİRME.

Commit: "feat: Keyword İstatistikleri API"
```

#### Adım 3.2 — React Keyword sayfası
```
React'ta Keyword İstatistikleri sayfası oluştur.
Bar chart + tablo gösterimi.
Commit: "feat: React Keyword İstatistikleri sayfası"
```

---

### FAZ 4 — Kullanıcı Yönetimi + Ayarlar (1-2 gün) — KÜÇÜK SAYFALAR

#### Adım 4.1 — Users API
```
GET /api/users → Firma kullanıcıları listesi
POST /api/users → Yeni kullanıcı ekle
PUT /api/users/:id → Kullanıcı güncelle
DELETE /api/users/:id → Kullanıcı sil
```

#### Adım 4.2 — Settings API
```
GET /api/settings → Firma ayarları
PUT /api/settings → Ayarları güncelle
```

#### Adım 4.3 — React sayfaları
```
Kullanıcı Yönetimi ve Ayarlar React sayfalarını oluştur.
```

---

### FAZ 5 — CV Topla (2-3 gün)

#### Adım 5.1 — CV Upload API
```
POST /api/cv/upload → Manuel CV yükleme (dosya + parse)
GET /api/cv/email-status → Email toplama durumu
POST /api/cv/collect-emails → Email'den CV toplamayı tetikle

⛔ cv_parser.py'yi DEĞİŞTİRME. Import et, çağır.
```

#### Adım 5.2 — React CV Topla sayfası

---

### FAZ 6 — Adaylar (3-5 gün) — BÜYÜK SAYFA

#### Adım 6.1 — Candidates API (CRUD)
```
GET /api/candidates → Aday listesi (filtreleme, sıralama, pagination)
GET /api/candidates/:id → Aday detayı
PUT /api/candidates/:id → Aday güncelle
DELETE /api/candidates/:id → Aday sil
GET /api/candidates/:id/cv → CV görüntüle
GET /api/candidates/:id/positions → Adayın pozisyonları
POST /api/candidates/:id/evaluate → AI değerlendirme
GET /api/candidates/export → Excel export
```

#### Adım 6.2 — React Adaylar listesi
#### Adım 6.3 — React Aday detay
#### Adım 6.4 — Karşılaştırma testi

---

### FAZ 7 — Mülakat Takvimi (2 gün)

#### Adım 7.1 — Interviews API
```
GET /api/interviews → Mülakat listesi
POST /api/interviews → Yeni mülakat
PUT /api/interviews/:id → Güncelle
DELETE /api/interviews/:id → Sil
```

#### Adım 7.2 — React Mülakat sayfası

---

### FAZ 8 — Email Hesapları (2 gün)

#### Adım 8.1 — Email Accounts API
#### Adım 8.2 — React Email Hesapları sayfası

---

### FAZ 9 — Havuzlar (5-7 gün) — EN ZOR SAYFA, EN SON YAPILIR

#### Adım 9.1 — Pools API (temel)
```
GET /api/pools/departments → Departman listesi
GET /api/pools/department/:id → Departman detay + pozisyonlar
GET /api/pools/system → Sistem havuzları (Genel, Arşiv)
```

#### Adım 9.2 — Pools API (pozisyon işlemleri)
```
GET /api/pools/position/:id → Pozisyon detay + adaylar
POST /api/pools/position/:id/pull → CV Çek
  ⛔ pull_matching_candidates_to_position() kullan, DEĞİŞTİRME
POST /api/pools/position → Yeni pozisyon oluştur
```

#### Adım 9.3 — Pools API (eşleştirme)
```
GET /api/pools/position/:id/potential → Potansiyel adaylar
GET /api/pools/position/:id/approved-titles → Onaylı eşdeğer pozisyonlar
POST /api/pools/position/:id/approve-title → Başlık onayla/reddet

⛔ candidate_matcher.py ve scoring_v2.py'yi DEĞİŞTİRME.
```

#### Adım 9.4 — React Havuzlar sayfası (ağaç yapısı)
#### Adım 9.5 — React Pozisyon detay
#### Adım 9.6 — React Sistem havuzları
#### Adım 9.7 — KAPSAMLI KARŞILAŞTIRMA TESTİ

---

### FAZ 10 — Super Admin Sayfaları (2-3 gün)

#### Adım 10.1 — Companies API
#### Adım 10.2 — Admin Panel API
#### Adım 10.3 — React Super Admin sayfaları

---

### FAZ 11 — Sidebar + Role Bazlı Menü (1 gün)

```
Antigravity'ye görev:
─────────────────────
Tüm sayfalar hazır olduktan sonra sidebar menüsünü düzenle.

3 rol seviyesi:
- super_admin: Dashboard, Firma Yönetimi, Tüm Kullanıcılar, Admin Paneli, Ayarlar
- company_admin: Dashboard, CV Topla, Adaylar, Havuzlar, Mülakat Takvimi,
  Keyword İstatistikleri, Email Hesapları, Kullanıcı Yönetimi, Ayarlar
- user: Dashboard, CV Topla, Adaylar, Havuzlar, Mülakat Takvimi, Keyword İstatistikleri

Login olan kullanıcının rolüne göre menü filtrelenecek.
```

---

### FAZ 12 — Final Test + Streamlit Kapatma (2-3 gün)

```
1. Tüm sayfalar tek tek test
2. Streamlit ile yan yana karşılaştırma
3. Cron job'ları yeni sisteme taşı
4. DNS güncelle (talentflow.com.tr → yeni sistem)
5. Streamlit'i kapat
```

---

## 5. TAŞINMAYACAK DOSYALAR (Ölü Kod)

| Dosya | Neden |
|-------|-------|
| migrate_matches_fk.py | Tek seferlik migration, tamamlandı |
| migrate_positions_to_v2.py | Tek seferlik migration, tamamlandı |
| scoring_v2_migration.py | Tek seferlik migration, tamamlandı |
| debug_match_issue.py | Debug aracı, artık gerekli değil |
| re_match_all_candidates.py | Tek seferlik düzeltme |
| test_*.py dosyaları | Eski testler, yeni testler yazılacak |
| seed_data.py | Demo veri, production'da gereksiz |
| job_scraper.py | Kullanılmıyor (TODO olarak kalmış) |

---

## 6. ZAMAN TAHMİNİ

| Faz | İş | Süre |
|-----|-----|------|
| Faz 0 | Backend iskeleti + dosya kopyalama | 1-2 gün |
| Faz 1 | Auth sistemi (API + React login) | 1-2 gün |
| Faz 2 | Dashboard (API + React) | 2-3 gün |
| Faz 3 | Keyword İstatistikleri | 1 gün |
| Faz 4 | Kullanıcı Yönetimi + Ayarlar | 1-2 gün |
| Faz 5 | CV Topla | 2-3 gün |
| Faz 6 | Adaylar (en büyük 2. sayfa) | 3-5 gün |
| Faz 7 | Mülakat Takvimi | 2 gün |
| Faz 8 | Email Hesapları | 2 gün |
| Faz 9 | Havuzlar (EN ZOR, en son) | 5-7 gün |
| Faz 10 | Super Admin sayfaları | 2-3 gün |
| Faz 11 | Sidebar + rol menüsü | 1 gün |
| Faz 12 | Final test + geçiş | 2-3 gün |
| **TOPLAM** | | **~25-38 gün** |

---

## 7. ANTİGRAVİTY / CLAUDE CODE KULLANIM KURALLARI

### Her Görevde Söylenecek Başlangıç
```
⛔ ÖNCE /var/www/hylilabs-api/core/ klasöründeki dosyaları oku.
Bu dosyalar KORUNAN dosyalardır. İÇERİKLERİNİ DEĞİŞTİRME.
Sadece import edip kullanabilirsin.

⛔ database.py fonksiyonlarını DEĞİŞTİRME. Yeni fonksiyon EKLEME.
Mevcut fonksiyonları olduğu gibi çağır.
```

### Görev Boyutu Kuralı
- Tek seferde MAX 1 endpoint dosyası VEYA 1 React sayfası
- Asla "tüm endpoint'leri yaz" deme
- Asla "tüm sayfaları oluştur" deme
- Her görev: yaz → test et → commit → sonraki görev

### Commit Mesajı Formatı
```
feat: Dashboard API endpoint'leri
feat: React Dashboard sayfası
fix: Dashboard aday sayısı düzeltmesi
test: Dashboard Streamlit karşılaştırma OK
```

---

## 8. ACİL DURUMLAR

**Bir şey bozulursa:**
1. Streamlit hâlâ çalışıyor (***REMOVED***:8501) — kullanıcılar etkilenmez
2. git revert ile son commit'i geri al
3. Bana (Claude Opus) sor

**Korunan dosya yanlışlıkla değiştirildiyse:**
```bash
cd /tmp/talentflow
git checkout -- scoring_v2.py candidate_matcher.py cv_parser.py keyword_stats.py
cp scoring_v2.py candidate_matcher.py cv_parser.py keyword_stats.py /var/www/hylilabs-api/core/
```

---

## 9. BAŞLANGIÇ KOMUTU

Her şey hazır olduğunda, ilk komut:

```bash
ssh root@***REMOVED***
mkdir -p /var/www/hylilabs-api/routes /var/www/hylilabs-api/core
```

Sonra Antigravity'ye Adım 0.1'i ver. Başlıyoruz!
