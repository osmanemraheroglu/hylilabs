# HyliLabs — Claude Kurallari

## KRİTİK KURAL — MEVCUT ÇALIŞAN SİSTEMLERİ BOZMA

Herhangi bir dosyada değişiklik yaparken, o dosyadaki MEVCUT ÇALIŞAN FONKSİYONLARI BOZMA.
Özellikle şu dosyalar KİLİTLİ — değişiklik yaparken çalışan kodu koruma altına al:

- api/routes/interviews.py — Mülakat Takvimi sistemi (dropdown-data, confirm endpoint, CRUD). DEĞİŞMEZ.
- api/routes/pools.py — Pozisyon havuzu sorgu yönlendirmesi (pool_type kontrolü). DEĞİŞMEZ.
- api/eval_report_v2.py — Değerlendirme raporu v10. DEĞİŞMEZ.

Yeni özellik eklerken:
1. Mevcut fonksiyonlara DOKUNMA
2. Yeni fonksiyonları AYRI ekle
3. Mevcut import'ları değiştirme
4. Mevcut SQL sorgularını değiştirme
5. Değişiklik sonrası TÜM mevcut endpoint'leri test et

---

## ZORUNLU KURAL — HER GOREV SONU

Her gorev tamamlandiginda, committen ONCE:

1. activeContext.md guncelle:
   - "Son Tamamlananlar" bolumune yeni is ekle
   - "Son Commitler" bolumunu guncelle
   - "Sonraki Gorev" bolumunu guncelle

2. Guncellemeyi commite dahil et:
   git add activeContext.md
   git commit -m "gorev commit mesaji + update activeContext"

BU KURAL ATLANAMAZLAR. activeContext.md guncellenmeden gorev bitmez.

---

## Proje
HyliLabs: AI destekli HR recruitment platformu. React + FastAPI + SQLite. Turkiye pazari, KVKK uyumlu.

## Sunucular
- Production: ***REMOVED*** (React:3000, FastAPI:8000)
- Eski TalentFlow: ***REMOVED*** (Streamlit, artik guncellenmeyecek)

## Roller
- Claude Opus: Planlama, mimari kararlar, strateji
- Antigravity/Cursor: Kod yazma, implementasyon
- Claude Code: Sunucuda calistirma, git commit, deploy

## Kod Kurallari
- Dil: Python backend, TypeScript frontend
- Her degisiklik dev branchte yapilir, test edilir, sonra maine merge
- commit mesajlari: fix:, feat:, security:, lock:, refactor: prefix kullan
- Turkce degisken/tablo adlari backendde OK (baslik, departman vb.)
- .env ASLA gite eklenmez
- Her yeni dosya ARCHITECTURE.mdye eklenir

## KILITLI DOSYALAR — DOKUNMA
Bu dosyalar 3+ kez dogrulanmis, DEGISTIRILEMEZ:
1. scoring_v2.py — Eslestirme motoru
2. job_scraper.py — Kariyer.net parser
3. eval_report.py — AI degerlendirme
4. email_worker.py — Email CV worker
5. email_reader.py — IMAP reader
6. core/cv_parser.py — CV parser (Claude API)
7. routes/cv.py — CV upload + auto-match
8. routes/emails.py — Email yonetimi
9. routes/candidates.py — CASCADE delete
10. cv-collect/index.tsx — CV toplama UI
11. routes/admin.py — reset-data endpoint
12. settings/advanced/index.tsx — Gelismis ayarlar UI

## KILITLI KURALLAR — IHLAL ETME
1. SECRET_KEY her zaman os.getenv() ile okunmali
2. FastAPI docs productionda None olmali
3. Security headers middleware kaldirilmamali
4. .env dosyasi ASLA gite eklenmemeli
5. API endpointleri auth olmadan erisilemez (public haric)
6. v2 eslestirme: Fuzzy 70->85, 85->92. Partial devre disi. Max 1 pozisyon/aday. DEGISMEMELI
7. Akilli Havuz Onerisi v2 korunmali, degistirilmemeli
8. Scoring v2.1: dynamic knockout(%50), junior/senior penalti, egitim kademeli. DEGISMEMELI
9. Ayarlar Gelismis sekmesi 3 kart yapisi korunmali
10. CV Indir butonlari filtre-bagimli calismali (Adaylar + Havuzlar)
11. Reset-data endpoint guvenlik kontrolleri (sifre + SIFIRLA + role) degistirilmemeli
12. Adaylar filtre sistemi: Pozisyon/departman filtreleri candidate_positions tablosunu kullanir. candidate_pool_assignments sadece Genel Havuz ve Arsiv icin
13. create_candidate() duplicate kontrolu (email + telefon) kaldirilmaz
14. CV dosyalari firma bazli izole: /data/cvs/{company_id}/. save_cv_file() company_id zorunlu. validate_cv_access() okuma kontrolu zorunlu. Flat yapiya geri donulemez. 2x3 guvenlik kontrolu DEGISTIRILEMEZ
15. DB CASCADE DELETE aktif: applications, matches, candidate_pool_assignments, position_pools, ai_evaluations -> candidates ON DELETE CASCADE. position_keywords_v2 -> department_pools ON DELETE CASCADE. interviews -> candidates, department_pools, companies ON DELETE CASCADE. ai_analyses, hr_evaluations -> candidates, positions. position_requirements, position_sector_preferences, position_title_mappings -> department_pools. candidate_merge_logs -> candidates. company_settings, email_accounts, email_templates -> companies. PRAGMA foreign_keys=ON her connectionda zorunlu. Tablo yapilari DEGISTIRILEMEZ. CASCADE kaldirilmaz.

## Stil
- Fonksiyon ve degisken: snake_case (Python), camelCase (TypeScript)
- API response: {"success": true, "data": ...} veya {"detail": "hata mesaji"}
- Frontend: shadcn/ui + Tailwind
- Hata mesajlari Turkce

## SQL Kurali
JOIN iceren tum SQL sorgularinda company_id her zaman tablo prefixiyle yazilmali (orn: c.company_id, a.company_id). Prefixsiz AND company_id = ? kullanimi yasaktir.

---

## KILITLI SISTEMLER (21.02.2026)

### Mulakat Takvimi UI — DEGISMEZ
- src/features/mulakat-takvimi/index.tsx
- Pozisyon -> Aday sirasi ve filtreleme
- Email onizleme dialog (Kaydet -> Onizle -> Gonder akisi)
- Onay suresi secimi (1/3/7/14/30 gun, varsayilan 3 gun)

### Email Onizleme Sistemi — DEGISMEZ
- api/email_sender.py — send_interview_invite(), generate_interview_invite_content()
- Alici email degistirilebilir
- Turkce karakter duzeltmeleri yapildi
- Not yoksa NOTLAR bolumu gizlenir
- Tarih Turkce format (TURKCE_AYLAR dict)

### Mulakat Onaylama Linki — DEGISMEZ
- interviews tablosu: confirm_token, confirm_token_expires, confirmed_at, confirmation_status
- GET /api/interviews/confirm/{token} — public endpoint (auth gerektirmez)
- Token suresi IK tarafindan belirlenir
- Onay sayfasi HTML response doner

### pm2 Deployment — DEGISMEZ
- ecosystem.config.cjs — frontend port 3000, backend port 8000
- start-backend.sh — uvicorn baslatma scripti
- systemd devre disi, pm2 tek process manager
- DEPLOYMENT.md — yeni sunucu kurulum rehberi

### Otomatik Hatirlatma Email Sistemi — DEGISMEZ
- api/scheduler.py — APScheduler, her gun 09:00 Europe/Istanbul
- Son gunu olan pending mulakatlari bulur, hatirlatma emaili gonderir
- hatirlatma_gonderildi kolonu ile tekrar gonderimi onler
- api/main.py lifespan ile baslatiliyor
- is_reminder=True ile farkli email icerigi

### Email UTF-8 Encoding — DEGISMEZ
- api/email_sender.py: formataddr + Header ile UTF-8 encoding
- Turkce karakterler destekleniyor (s,g,u,o,i,c vb.)
- msg["From"] = formataddr((str(Header(sender_name, 'utf-8')), email_addr))
- msg["Subject"] = Header(subject, 'utf-8')
- DEGISTIRME

### Türkçe Metin Kuralı — DEGISMEZ
Tüm frontend UI metinleri doğru Türkçe karakter kullanmalı.
ş, ğ, ü, ö, ı, ç, İ, Ş, Ğ, Ü, Ö, Ç
- Yeni bileşen yazarken Türkçe karakterleri doğru kullan
- Mevcut metinleri düzenlerken Türkçe karakterleri koru
- Asla "Kullanici", "Sifre", "Guncelle", "Iptal", "Yukleniyor" gibi karaktersiz yazma
- DB'den gelen değerleri frontend'de Türkçe'ye çevir (getDurumLabel pattern)

### Dashboard Bekleyen Kartı (22.02.2026) — DEGISMEZ
- api/database.py — candidates.durum = 'yeni' sorgusu
- position_pools tablosu degil, candidates tablosu kullaniliyor
- DEGISTIRME

### Türkçe Karakter Sistemi (22.02.2026) — DEGISMEZ
- Tüm frontend UI metinleri doğru Türkçe karakter kullanır
- DB'den gelen değerler getDurumLabel() pattern ile Türkçe'ye çevrilir
- Dashboard pie chart, CV Topla badge, Toplama Geçmişi badge dahil
- DEGISTIRME

### Mülakat-Aday Durum Senkronizasyonu (22.02.2026) — DEGISMEZ
- Mülakat oluşturulunca candidates.durum = 'mulakat' otomatik güncellenir
- Mülakat iptal/silinince başka aktif mülakat yoksa durum geri alınır
- api/routes/interviews.py — DEGISTIRME

### Max Aday Limit Sistemi (22.02.2026) — DEGISMEZ
- Plan dropdown kaldırıldı, max_aday manuel belirlenir
- CV yüklemede api/routes/cv.py'de limit kontrolü yapılır
- Limit dolunca kullanıcı dostu hata mesajı gösterilir
- CV Topla sayfasında progress bar ile limit göstergesi var
- DEGISTIRME

### Firma Otomatik Kullanıcı Sistemi (22.02.2026) — DEGISMEZ
- Firma oluşturulunca yetkili email'e otomatik company_admin hesabı açılır
- Geçici şifre oluşturulur ve email ile gönderilir
- api/routes/companies.py — DEGISTIRME

### Auth Route Guard (23.02.2026) — DEGISMEZ
- Token yoksa → /sign-in'e yönlendir
- aktif=0 kullanıcı → 401, login engeli
- Pasif firma kullanıcısı → 403, login engeli
- Token varken /sign-in'e gelince → /dashboard'a yönlendir
- src/stores/auth-store.ts + api/routes/auth.py — DEGISTIRME

### Takvimde Onaylama Badge Sistemi (21.02.2026) — DEGISMEZ
- interviews tablosunda confirmation_status, confirmed_at alanları
- Takvimde yeşil ✓ badge, listede "✓ Onaylandı" / "⏳ Bekliyor"
- Onay durumu filtre dropdown
- Commit: dbbbe75 — DEGISTIRME

### Firma Kalıcı Silme Sistemi (23.02.2026) — DEGISMEZ
- hard_delete_company() - 14 tablo cascade silme
- Var olan tablolar sqlite_master ile kontrol edilir
- Her DELETE try/except ile sarılı
- api/database.py — DEGISTIRME

### Security Sistemi (23.02.2026) — DEGISMEZ
- JWT_SECRET .env'den zorunlu, fallback yok - RuntimeError fırlatır
- Public endpoint rate limiting hazır:
  - check_public_apply_limit() → 10 istek/saat/IP
  - check_public_positions_limit() → 60 istek/dakika/IP
- api/rate_limiter.py + api/routes/auth.py — DEGISTIRME

### IDOR Koruması (23.02.2026) — DEGISMEZ
- pools.py satır 852, 859, 1007, 1012
- Tüm candidate/pool sorgularında AND company_id = ? zorunlu
- Commit 52b7a7f — DEGISTIRME

### Super Admin Audit Log (23.02.2026) — DEGISMEZ
- audit_logger.py — COMPANY_CREATE, COMPANY_DELETE, COMPANY_STATUS_CHANGE
- Firma oluşturma, silme, durum değişikliği loglanıyor
- Commit 52b7a7f — DEGISTIRME

### PYTHONPATH Konfigürasyonu (23.02.2026) — DEGISMEZ
- ecosystem.config.cjs'de PYTHONPATH=/var/www/hylilabs/api/core:/var/www/hylilabs/api
- candidate_matcher ve cv_parser core/ altında, PYTHONPATH ile erişiliyor
- Kilitli dosyalar (scoring_v2.py, email_worker.py, job_scraper.py) core. prefix'siz import ediyor
- PYTHONPATH sayesinde import hataları çözüldü
- DEGISTIRME

### URL Parse Frontend Fix (23.02.2026) — DEGISMEZ
- src/features/havuzlar/index.tsx
- res.başarılı → res.success && res.data kontrolü
- res.pozisyon_adi → res.data.pozisyon_adi erişimi
- Commit 275682b — DEGISTIRME

### Radix UI Select Fix (23.02.2026) — DEGISMEZ
- SelectItem value="" → value="none" (3 yerde: satır 901, 986, 1019)
- Select value={x || "none"}, onChange: "none" → "" dönüşümü
- Commit e32c1a4 — DEGISTIRME

### Eşleştirme Senkronizasyon Fix (23.02.2026) — DEGISMEZ
- approved_title_mappings tablosu pozisyon onayında senkronize ediliyor
- Onay: is_approved=1, Red: kayıt siliniyor — her iki tabloda
- Commit e0a669f — DEGISTIRME

### Toast Bildirim Sistemi (23.02.2026) — DEGISMEZ
- 33 window.alert() kaldırıldı (3 dosya)
- sonner toast kullanılıyor: toast.success() + toast.error()
- Dosyalar: havuzlar, firma-yonetimi, email-hesaplari
- Commit dc8592b — DEGISTIRME

### Aday Durum Akışı Senkronizasyonu (23.02.2026) — DEGISMEZ
Her aday aksiyonu candidates.durum VE candidate_pool_assignments'ı birlikte günceller:
- arsivle: durum=arsiv, Arşiv havuzuna taşı
- elen: durum=yeni, Genel Havuza taşı
- ise-al: durum=ise_alindi, tüm havuzlardan sil
- havuzdan sil (Arşiv): durum=yeni, Genel Havuza taşı
- havuzdan sil (Genel): 400 ENGEL
Dosyalar:
- api/routes/candidates.py (elen:195-212, arsivle:220-260, ise-al:287-296)
- api/routes/pools.py (remove_candidate:282-326)
Commit: e289c20, 96df97c, 1268b20 — DEGISTIRME

### Dashboard Visibility Refresh (23.02.2026) — DEGISMEZ
- src/features/dashboard/index.tsx
- fetchDashboardData() fonksiyonu ayrıştırıldı
- visibilitychange event listener ile sayfa görünür olunca otomatik yenileme
- Commit 1268b20 — DEGISTIRME

### Genel Havuzdan Silme Engeli (23.02.2026) — DEGISMEZ
- Backend: pools.py remove_candidate → Genel Havuz için 400 HTTPException
- Frontend: havuzlar/index.tsx → 400 response için toast.error()
- Genel Havuzdan manuel aday silme engellendi
- Adayı kaldırmak için Arşivle butonu kullanılmalı
- Commit 96105f0 — DEGISTIRME

### Pool Assignments Veri Kuralları (23.02.2026) — DEGISMEZ
Her aday her zaman şu kurallarla havuzda olmalı:
- durum='yeni' → Genel Havuzda
- durum='arsiv' → Arşiv havuzunda
- durum='mulakat' → Genel Havuzda (değişmez)
- durum='pozisyona_atandi' → Genel Havuzda DEGIL (candidate_positions tablosunda, Genel Havuz'dan silinir)
- durum='ise_alindi' → Hiçbir havuzda değil
- Hiçbir aday 2 havuzda aynı anda olamaz
DEGISTIRME

### Pozisyon Havuzu Sorgu Yönlendirmesi (24.02.2026) — DEGISMEZ
- pools.py route'unda pool_type kontrolü:
  - pool_type == "position" → get_position_candidates() çağrılır (candidate_positions tablosu)
  - pool_type == "department" veya diğer → get_department_pool_candidates() çağrılır (candidate_pool_assignments tablosu)
- get_position_candidates() fonksiyonu c.* ile tüm aday alanlarını döndürür
- Dosyalar: api/routes/pools.py (satır 215-216), api/database.py (satır 8577-8599)
- Commit: 6641c11 — DEGISTIRME
