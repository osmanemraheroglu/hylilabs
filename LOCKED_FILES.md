# 🔒 HyliLabs — KİLİTLİ DOSYALAR

## KURAL: Bu listedeki dosyalar DEĞİŞTİRİLEMEZ.
## Değiştirmek için EMRAHFC onayı gerekli.
## Her görev başında bu dosyayı oku.

## KİLİTLİ DOSYALAR

### Backend — /var/www/hylilabs/api/
| # | Dosya | Kilit Tarihi | Not |
|---|-------|-------------|-----|
| 1 | scoring_v2.py | 17.02.2026 | Eşleştirme motoru — KESİNLİKLE DOKUNMA |
| 2 | job_scraper.py | 17.02.2026 | Kariyer.net URL parse |
| 3 | eval_report.py | 17.02.2026 | AI değerlendirme raporu |
| 4 | email_worker.py | 17.02.2026 | Email CV toplama cron — 3x doğrulandı |
| 5 | email_reader.py | 17.02.2026 | IMAP email okuma + klasör decode — 3x doğrulandı |
| 6 | core/cv_parser.py | 17.02.2026 | CV parse (Claude API) — 3x doğrulandı |

### Routes — /var/www/hylilabs/api/routes/
| # | Dosya | Kilit Tarihi | Not |
|---|-------|-------------|-----|
| 7 | routes/cv.py | 17.02.2026 | CV upload + scan-emails + auto-match — 6x doğrulandı |
| 8 | routes/emails.py | 17.02.2026 | Email hesap CRUD + folders endpoint — 3x doğrulandı |
| 9 | routes/candidates.py | 17.02.2026 | CASCADE delete + orphan onleme — 3x dogrulandi |

### Frontend — /var/www/hylilabs/src/features/
| # | Dosya | Kilit Tarihi | Not |
|---|-------|-------------|-----|
| 10 | cv-collect/index.tsx | 17.02.2026 | 3 sekmeli CV Topla sayfası — 3x doğrulandı |

## DOĞRULAMA SİSTEMİ (3x Kontrol)
Dosya kilitlenmeden önce:
1. Fonksiyon eşleşmesi — TalentFlow ile birebir aynı mı?
2. Çalışma testi — API + Frontend doğru çalışıyor mu?
3. Entegrasyon testi — Diğer modüllerle bağlantı sorunsuz mu?

## CLAUDE CODE TALİMATI
- Kilitli dosyada değişiklik talebi → "Bu dosya kilitli, EMRAHFC onayı gerekli" de ve DUR.
- Yeni kilit talebi → 3x kontrol yap, raporla, onay bekle.

---

## GÜVENLİK KONTROLLERİ (17.02.2026)

### 1. GitLeaks — Secret/Key Sızıntı Taraması ✅
- **Araç:** Manuel 8 nokta tarama scripti
- **Sonuç:** 3 bulgu tespit, 3/3 düzeltildi
- **Düzeltme 1:** JWT SECRET_KEY hardcoded → os.getenv("JWT_SECRET") — Commit: 89a6f2d
- **Düzeltme 2:** admin123/demo123 → production'da değiştirilecek (seed data)
- **Dosya:** api/routes/auth.py (SECRET_KEY satırı KİLİTLİ — tekrar hardcoded yapılmamalı)
- **Kontroller:** .env git'te yok ✅, API key kodda yok ✅, DB git'te yok ✅, hassas dosya yok ✅

### 2. Nikto — Sunucu/Nginx Güvenlik Taraması ✅
- **Araç:** Nikto v2 (localhost:3000 + localhost:8000)
- **Sonuç:** 7 bulgu tespit, 7/7 düzeltildi
- **Düzeltme:** Security headers middleware eklendi — Commit: 6370d84
- **Düzeltme:** Swagger UI, ReDoc, OpenAPI JSON production'da kapatıldı — Commit: 6370d84
- **Dosya:** api/main.py (FastAPI docs_url=None + security headers middleware KİLİTLİ)
- **Headers:** X-Frame-Options ✅, X-Content-Type-Options ✅, X-XSS-Protection ✅, Referrer-Policy ✅, Permissions-Policy ✅

### 3. OWASP ZAP — API Güvenlik Taraması ✅
- **Araç:** OWASP ZAP Baseline Scan + Manuel kontroller
- **Sonuç:** 0 High, 0 Medium, 0 Low, 0 Informational
- **Rapor:** /var/www/hylilabs/zap_report.html
- **Kontroller:** Auth koruması ✅, CORS ✅, 404 temiz ✅, Stack trace yok ✅, Docs kapalı ✅

### KİLİTLENEN GÜVENLİK KURALLARI
> ⚠️ Aşağıdaki kurallar ASLA değiştirilmemeli:
> 1. SECRET_KEY her zaman os.getenv() ile okunmalı, ASLA hardcoded olmamalı
> 2. FastAPI docs_url, redoc_url, openapi_url production'da None olmalı
> 3. Security headers middleware kaldırılmamalı veya zayıflatılmamalı
> 4. .env dosyası ASLA git'e eklenmemeli
> 5. API endpoint'leri auth olmadan erişilebilir olmamalı (public endpoint'ler hariç)

---

## 18.02.2026 — Data Management & Bug Fixes

### Yeni Kilitli Endpoint'ler
| # | Endpoint | Kilit Tarihi | Not |
|---|----------|-------------|-----|
| 11 | POST /api/admin/reset-data | 18.02.2026 | 3 kademeli veri sıfırlama (candidates/pools/full). Şifre + "SIFIRLA" onayı zorunlu. Otomatik backup. Bu endpoint'in güvenlik kontrolleri DEĞİŞTİRİLMEMELİ. |
| 12 | GET /api/candidates/export/download-cvs | 18.02.2026 | CV toplu indirme (ZIP). Parametreler: all, ids, pool_id, havuz. 100MB limit. Auth zorunlu. Bu endpoint DEĞİŞTİRİLMEMELİ. |

### Yeni Kilitli Kurallar
| # | Kural | Not |
|---|-------|-----|
| 9 | Ayarlar > Gelişmiş sekmesi | 3 kart yapısı (Aday Sıfırla, Havuz Sıfırla, Tam Sıfırla). super_admin kartı role kontrolü frontend'de de yapılmalı. DEĞİŞTİRİLMEMELİ. |
| 10 | CV İndir butonu (Adaylar) | Seçili havuz filtresine göre indirme. Filtre parametresi backend'e gönderilmeli. DEĞİŞTİRİLMEMELİ. |
| 11 | CV İndir butonu (Havuzlar) | pool_id parametresi ile havuz bazlı indirme. DEĞİŞTİRİLMEMELİ. |
| 12 | Adaylar filtre sistemi | genel_havuz, departman_havuzu, pozisyon_havuzu, arsiv filtreleri candidate_pool_assignments JOIN ile çalışır. database.py'deki bu filtre mantığı DEĞİŞTİRİLMEMELİ. |

### Yeni Kilitli Dosyalar
| # | Dosya | Kilit Tarihi | Not |
|---|-------|-------------|-----|
| 13 | src/features/settings/advanced/index.tsx | 18.02.2026 | Gelişmiş ayarlar (veri sıfırlama UI) |
| 14 | src/routes/_authenticated/settings/advanced.tsx | 18.02.2026 | Gelişmiş route |

### Commit'ler (18.02.2026)
- d6cddfd feat: add reset-data endpoint with backup + password validation
- d45abf2 feat: add CV download as ZIP endpoint (append only, locked file)
- 16efbf8 feat: add Gelismis (Advanced) settings tab with data reset functionality
- a7214e4 feat: add CV download ZIP button to candidates page
- 8f3ecf3 feat: add pool CV download ZIP button to havuzlar page
- 039bfea fix: candidates filter - departman/pozisyon now queries pool assignments
- b373b60 fix: CV download respects filter + add arsiv filter option

---

## 18.02.2026 — Duplicate CV Kontrolü

### Yeni Kilitli Kural
| # | Kural | Not |
|---|-------|-----|
| 13 | create_candidate() duplicate kontrolü | Email + telefon ile duplicate kontrol. Company_id scope'unda çalışır. TÜM giriş noktalarını korur (upload, scan-emails, workflows). DEĞİŞTİRİLMEMELİ, KALDIRILMAMALI. |

### Commit
- 5a9f608 fix: add duplicate check to create_candidate + clean existing duplicate
