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
1. scoring_v2.py — FAZ 9.5 weight + FAZ 10.1 save_match_details entegrasyonu. FAZ 1B TAMAMLANDI (05.03.2026): check_keyword_match() company_id parametresi eklendi. Commit: 0538f36. DEĞİŞMEYEN: Puanlama mantığı, fuzzy eşikler (85/92), ağırlıklar (33/47/20), BLACKLIST. KİLİTLİ.
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
16. KEYWORD_SYNONYMS: candidate_matcher.py dict KORUNMALI (migration kaynağı). check_keyword_match() synonym'ları DB'den okuyor (get_synonyms_for_keyword, cache'li). check_keyword_match_weighted() FAZ 9.5 + FAZ 10.1 log_synonym_usage entegrasyonu. keyword_synonyms tablosu: 387 synonym, FAZ 1-10.3 tamamlandı. API: 18 endpoint /api/synonyms/* (list, pending, create, delete, approve, reject, generate, update-confidence, confidence-stats, check-semantic, semantic-duplicates, semantic-search, normalize, translate, dictionary-stats, add-translation, language-stats). FAZ 1B (05.03.2026): check_keyword_match() 3 katmanlı synonym arama: Katman 1: KEYWORD_SYNONYMS dict (candidate_matcher.py, DEĞİŞTİRİLEMEZ), Katman 2: DB global synonym (company_id IS NULL), Katman 3: DB firma synonym (company_id = N) — FAZ 1B eklendi. Commit: 0538f36 + 0086a16, KİLİTLİ.
17. matches v2_result: database.py sync INSERT kodu DEGISMEZ (commit 42cf5b0)
18. rescore_candidate: pools.py:1253 DEGISMEZ (commit cc2a339)
22. HTTP filename kuralı: Content-Disposition header'ında filename kullanırken RFC 5987 encoding (quote + filename*=UTF-8) kullanılmalı. Türkçe karakterler latin-1'de encode edilemez. DEĞİŞMEZ.
19. try-except değişken kuralı: try içinde tanımlanan değişkenler try bloğu dışında kullanılacaksa MUTLAKA except bloğunda veya try öncesi None/default değer tanımlanmalı. Aksi halde UnboundLocalError riski. DEGISMEZ.
20. PM2 restart kuralı: ecosystem.config.cjs env değişikliğinde sadece pm2 restart YETERSİZ. pm2 delete + pm2 start kullanılmalı. DEGISMEZ.
21. Import guard kuralı: core/ altındaki modüller import edilirken try-except ile fallback yazılmalı (from X except: from core.X). DEGISMEZ.
23. CV PDF-Only Mimarisi: CV dosyaları SADECE PDF olarak saklanır. DOCX/DOC yüklendiğinde save_cv_file() otomatik PDF'e çevirir (LibreOffice headless). convert_to_pdf() fonksiyonu fcntl lock ile thread-safe. Orijinal DOCX'ler _originals/ klasöründe saklanır. Sistemde aktif DOCX CV OLMAMALI. DEĞİŞMEZ.
25. Duplicate Mülakat Engeli (04.03.2026): Aktif mülakatı olan adaya ikinci mülakat oluşturulamaz. interviews CREATE endpoint'te candidate_id + durum='planlanmis' + company_id kontrolü. 400 HTTPException Türkçe hata mesajı. DEĞİŞMEZ.
26. Onaylanmamış Mülakat Arşivleme (04.03.2026): auto_cancel sonrası onaylamayan adaylar arşive taşınır, Genel Havuz'a değil. Manuel iptal davranışı farklı (Genel Havuz). DEĞİŞMEZ.
27. Mülakat Sonuç Değerlendirme (04.03.2026): interviews tablosunda degerlendirme_notu(degerlendirme), puan(1-10), sonuc_karari(olumlu/olumsuz/beklemede), degerlendiren alanları. Tamamlanan mülakatlar için İK değerlendirmesi. DEĞİŞMEZ.

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

### Mülakat-Aday Durum Senkronizasyonu (22.02.2026, güncelleme 25.02.2026) — DEGISMEZ
- Mülakat oluşturulunca candidates.durum = 'mulakat' otomatik güncellenir
- Mülakat iptal/silinince başka aktif mülakat yoksa:
  - ise_alindi/arsiv adaylar → durum DEĞİŞTİRİLMEZ (korumalı)
  - candidate_positions kaydı varsa → durum='pozisyona_atandi', havuz='pozisyona_aktarilan'
  - candidate_positions kaydı yoksa → durum='yeni', havuz='genel_havuz'
- ise_al endpoint: durum='ise_alindi', havuz=NULL
- api/routes/interviews.py, api/routes/candidates.py — DEGISTIRME

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

### Sistem Limitleri (27.02.2026) — DEĞİŞTİRİLMEMELİ

1. **AI Tekrar Kontrolü**: Her aday+pozisyon için Claude API sadece 1 kere çağrılır.
   - ai_evaluations tablosunda UNIQUE(candidate_id, position_id)
   - Mevcut değerlendirme varsa cache'den döner
   - pools.py evaluate_candidate'de kontrol var

2. **Rate Limitler**:
   - Login: 5 deneme / 15 dk (check_login_limit)
   - CV Upload: 20 dosya / saat (check_cv_upload_limit)
   - rate_limiter.py fonksiyonları aktif

3. **AI Günlük Limit** (plan bazlı):
   - trial: 10, starter: 50, professional: 200, enterprise: sınırsız
   - plans.daily_ai_limit kolonu
   - check_ai_daily_limit() fonksiyonu

4. **CV Çek Limitleri**:
   - Pozisyon başına varsayılan 50 aday (max 500)
   - match_score DESC sıralı
   - BATCH_SIZE=100 ile bellek optimizasyonu
   - pull_matching_candidates_to_position(limit=50)

Bu limitler DEĞİŞTİRİLMEMELİ.

### FAZ 8 Synonym Quality System (01.03.2026) — DEGISMEZ

#### FAZ 8.1 HR Feedback Loop (8/8)
Dosyalar:
- routes/synonyms.py: REJECT_REASONS sabiti, reject endpoint, reject_stats endpoint
- database.py: blacklist_candidates tablosu, check_and_suggest_blacklist()
- keyword_synonyms: reject_reason, reject_note kolonları
Commit'ler: e18099d, 8edd06e, e1cccdc, a2556b9, 5f54651

#### FAZ 8.2 Dinamik Max Limit (5/5)
Dosyalar:
- routes/synonyms.py: HIGH_COVERAGE_KEYWORDS (93 keyword), get_max_synonym_limit()
- database.py: keyword_importance tablosu, get_keyword_importance()
- filter_ai_synonyms() dinamik limit kullanıyor
Commit'ler: ca62f80, 9cd0997

#### FAZ 8.3 Match Weight (4/4)
Dosyalar:
- routes/synonyms.py: SYNONYM_TYPE_WEIGHTS sabiti
- database.py: _get_weight() fonksiyonu
- keyword_synonyms: match_weight kolonu (387 kayıt)

### FAZ 9 Advanced Synonym System (02.03.2026) — DEGISMEZ

#### FAZ 9.1 6 Synonym Tipi (7/7)
Dosyalar:
- routes/synonyms.py: SYNONYM_TYPES sabiti (6 tip)
- keyword_synonyms: synonym_type kolonu
Tipler: exact_synonym(1.0), abbreviation(0.95), english(0.90), turkish(0.85), broader_term(0.70), narrower_term(0.60)

#### FAZ 9.2 Çakışma Kontrolü (6/6)
Dosyalar:
- database.py: check_synonym_conflict() fonksiyonu
- synonym_primary_mapping tablosu
- keyword_synonyms: ambiguity_score kolonu

#### FAZ 9.3 İki Seviyeli Blacklist (7/7)
Dosyalar:
- routes/synonyms.py: GLOBAL_BLACKLIST, CONTEXTUAL_BLACKLIST, SECTOR_BLACKLISTS
- routes/synonyms.py: is_contextually_allowed() fonksiyonu
- database.py: blacklist_candidates tablosu

#### FAZ 9.4 Versiyonlama ve Audit (9/9)
Dosyalar:
- keyword_synonyms: version, model_version, updated_by, updated_at, is_active kolonları
- keyword_synonyms_history tablosu
- database.py: log_synonym_change() fonksiyonu

#### FAZ 9.5 Skorlama Entegrasyonu (6/6)
Dosyalar:
- core/candidate_matcher.py:250 - check_keyword_match_weighted()
- core/scoring_v2.py - weight bazlı skorlama (4 çağrı noktası)
- database.py: get_synonyms_with_weights()
Formül: effective_weight = match_weight * (1 - ambiguity * 0.3)
Commit: 3646dce

### FAZ 10.1 Multiple Confidence Source (02.03.2026) — DEGISMEZ

Aşağıdaki dosyalar FAZ 10.1 için güncellendi, KORUNMALI:

1. **database.py** - Yeni fonksiyonlar (satır 1673-1950):
   - calculate_corpus_relevance() - CV sıklığı skoru
   - calculate_historical_precision() - Geçmiş başarı oranı
   - calculate_final_confidence() - Formula: (0.4*AI) + (0.3*corpus) + (0.3*historical)
   - log_synonym_usage() - UPSERT synonym_usage_stats
   - save_match_details() - INSERT synonym_match_history
   - update_hired_stats() - hired_count güncelleme

2. **scoring_v2.py** - save_match_details entegrasyonu
   - calculate_match_score_v2 içinde match detayları kaydediliyor

3. **candidate_matcher.py** - log_synonym_usage entegrasyonu
   - check_keyword_match_weighted içinde synonym kullanımı loglanıyor

4. **routes/candidates.py** - update_hired_stats entegrasyonu
   - ise_al_candidate içinde hired istatistikleri güncelleniyor

5. **routes/synonyms.py** - Yeni endpointler:
   - POST /update-confidence (satır 1902)
   - GET /confidence-stats (satır 1950)

6. **Tablolar** (DEGISTIRILEMEZ):
   - synonym_usage_stats (10 kolon, 3 index)
   - synonym_match_history (10 kolon, 2 index)
   - keyword_synonyms.confidence_score kolonu (default 0.58)

7. **Frontend** - src/features/synonyms/index.tsx
   - Confidence badge (emerald/amber/red renkleri)
   - getConfidenceBadge() fonksiyonu

Commit: b7d4c10 — DEGISTIRME

### FAZ 10.2 Semantic Similarity (02.03.2026) — DEGISMEZ

OpenAI Embeddings ile semantic benzerlik sistemi. KORUNMALI:

1. **database.py** - Semantic fonksiyonlar:
   - get_openai_client() - Lazy initialization OpenAI client
   - get_embedding(text) - OpenAI text-embedding-3-small (1536 boyut)
   - semantic_similarity(emb1, emb2) - Cosine similarity (numpy)
   - save_keyword_embedding(keyword) - Keyword embedding kaydet
   - save_synonym_embedding(synonym, keyword) - Synonym embedding kaydet
   - check_semantic_similarity(keyword, synonym) - Benzerlik kontrol (threshold 0.70)
   - find_semantic_duplicates(threshold) - Potansiyel duplicate'ları bul
   - SEMANTIC_THRESHOLD = 0.70

2. **routes/synonyms.py** - 3 yeni endpoint:
   - POST /check-semantic - Keyword-synonym benzerlik kontrolü
   - GET /semantic-duplicates - Potansiyel duplicate listesi
   - POST /semantic-search - Semantik arama (threshold + limit)
   - create_synonym() semantic validation + auto-save embedding

3. **Tablolar** (DEGISTIRILEMEZ):
   - keyword_embeddings: keyword, embedding (BLOB), model_version
   - synonym_embeddings: synonym, keyword, embedding (BLOB), model_version

4. **scripts/compute_embeddings.py** - Pre-compute scripti
   - 125 keyword + 387 synonym embedding hesaplandı

5. **Bağımlılıklar**:
   - openai==2.24.0
   - numpy==2.4.2

Commit: 9dbb301 — DEGISTIRME

### FAZ 10.3 Çoklu Dil Normalizasyonu (02.03.2026) — DEGISMEZ

TR/EN teknik terim çevirisi ve normalizasyon sistemi. KORUNMALI:

1. **database.py** - Sözlükler ve fonksiyonlar:
   - TRANSLATION_DICTIONARY: 53 TR->EN teknik terim (yapay zeka, makine öğrenmesi, vb.)
   - ENGLISH_CANONICAL: 21 kısaltma->tam form (ML, AI, JS, K8S, vb.)
   - detect_language(): Dil algılama (tr/en/de/fr/es/it)
   - stem_word(): Snowball stemmer (cached)
   - translate_to_canonical(): Öncelikli çeviri (DB->statik->kısaltma)
   - normalize_keyword(): Tam normalizasyon + opsiyonel stemming

2. **routes/synonyms.py** - 5 yeni endpoint:
   - POST /normalize - Keyword normalizasyonu
   - POST /translate - Çeviri
   - GET /dictionary-stats - Sözlük istatistikleri
   - POST /add-translation - Yeni çeviri ekle (DB sözlük)
   - GET /language-stats - Dil dağılım raporu

3. **Tablolar** (DEGISTIRILEMEZ):
   - translation_dictionary: source_term, source_lang, canonical_term, sector, verified

4. **Bağımlılıklar**:
   - langdetect==1.0.9
   - snowballstemmer==3.0.1

NOT: 10.3.7 (Google Translate) ve 10.3.8 (DeepL) opsiyonel, statik sözlük yeterli

Commit: 4541477 — DEGISTIRME

### FAZ 10.4 ML-Based Auto-Learning (02.03.2026) — DEGISMEZ

RandomForest ile synonym onay tahmin sistemi. KORUNMALI:

1. **database.py** - ML fonksiyonları:
   - SKLEARN_AVAILABLE: Scikit-learn yüklü mü kontrolü
   - FEATURE_NAMES: 15 özellik listesi
   - AUTO_APPROVE_THRESHOLD = 0.95
   - AUTO_REJECT_THRESHOLD = 0.20
   - extract_synonym_features(): 15 özellik çıkarımı (keyword_length, semantic_similarity, etc.)
   - prepare_training_data(): Eğitim verisi hazırlama (approved/rejected synonym'lar)
   - train_synonym_model(): RandomForestClassifier eğitimi + joblib kayıt
   - load_active_model(): Aktif model yükleme (cache)
   - predict_approval_probability(): Onay olasılığı tahmini + DB kayıt
   - auto_process_synonym(): Otomatik onay/red işlemi
   - start_ab_test(): A/B test başlatma
   - get_ab_test_results(): A/B test sonuçları
   - end_ab_test(): A/B test bitirme + kazanan seçimi
   - check_retraining_needed(): Retraining gerekliliği kontrolü (yeni sample, accuracy düşüşü)
   - run_retraining_job(): Retraining job çalıştırma

2. **routes/synonyms.py** - 11 yeni endpoint:
   - POST /ml/predict - ML tahmini
   - POST /ml/train - Model eğitimi
   - GET /ml/model-stats - Aktif model istatistikleri
   - GET /ml/model-history - Model geçmişi
   - GET /ml/training-data - Eğitim verisi istatistikleri
   - GET /ml/retraining-status - Retraining gerekliliği
   - POST /ml/retrain - Manuel retraining
   - GET /ml/ab-test - A/B test durumu
   - POST /ml/ab-test/start - A/B test başlat
   - POST /ml/ab-test/end - A/B test bitir
   - GET /ml/dashboard - Tüm ML metrikleri

3. **create_synonym() entegrasyonu**:
   - ML otomatik onay (prob >= 0.95 → auto_approve=True)
   - ML düşük olasılık uyarısı (prob <= 0.20 → warning)
   - Response'a ml_prediction alanı eklendi

4. **Tablolar** (DEGISTIRILEMEZ):
   - ml_models: model_name, model_version, accuracy, precision_score, recall_score, f1_score, is_active, is_ab_test
   - ml_predictions: keyword, synonym, probability, prediction, actual_result, is_correct
   - ml_retraining_jobs: job_type, status, trigger_reason, old_model_id, new_model_id

5. **Dosyalar** (DEGISTIRILEMEZ):
   - /var/www/hylilabs/api/models/ dizini (.joblib model dosyaları)

6. **Bağımlılıklar**:
   - scikit-learn==1.8.0
   - joblib==1.5.3

Commit: e02992c — DEGISTIRME

### Dashboard Kart Başlıkları (03.03.2026) — DEGISMEZ
- src/features/dashboard/index.tsx
- "Toplam Aday" → "Toplam Başvuru" (satır 165)
- "Sistemdeki tüm adaylar" → "Sistemde kayıtlı tüm başvurular" (satır 170)
- "Aktif Pozisyon" → "Açık Pozisyon" (satır 176)
- "Aday Havuz Dağılımı" → "Aday Durum Dağılımı" (satır 235)
- "Durumlara göre aday dağılımı" → "Süreç aşamalarına göre aday oranı" (satır 236)
- "Bekleyen" → "Bekleyen Başvuru" (satır 198)
- "Değerlendirme bekleyen" → "Açık pozisyonlarla eşleşemeyen başvurular" (satır 203)
- Commit: b0924e7, 697ab0d, 9fcde9f, a307d17 — DEGISTIRME

### Türkçe Karakter Duyarsız Arama (03.03.2026) — DEGISMEZ
- api/database.py: turkish_lower() helper fonksiyonu (İ→i, I→ı dönüşümü)
- api/database.py: get_connection() içinde TURKISH_LOWER SQLite custom function
- get_all_candidates() ve get_candidates_count() arama sorguları TURKISH_LOWER() kullanıyor
- Büyük/küçük harf + Türkçe karakter duyarsız arama (İ↔i, I↔ı, Ö↔ö, Ü↔ü, Ş↔ş, Ğ↔ğ, Ç↔ç)
- Commit: ba28821 — DEGISTIRME

### Havuzlar Türkçe Karakter Duyarsız Arama (03.03.2026) — DEGISMEZ
- src/features/havuzlar/index.tsx satır 479-480
- .toLowerCase() → .toLocaleLowerCase('tr-TR') (ad_soyad, email, mevcut_pozisyon)
- Frontend tarafında Türkçe karakter duyarsız filtreleme
- Commit: 20dcde4 — DEGISTIRME
### guncelleme_tarihi Senkronizasyonu (03.03.2026) — DEGISMEZ
- candidates.durum değiştiren TÜM UPDATE sorgularında guncelleme_tarihi = datetime('now') zorunlu
- 13 UPDATE sorgusu 4 dosyada düzeltildi:
  - candidates.py: elen, arsivle, ise_al (3 sorgu)
  - pools.py: remove_candidate Arşiv ve Pozisyon/Departman (2 sorgu)
  - interviews.py: create, cancel, delete mülakatlar (5 sorgu)
  - database.py: pull_matching, add_to_position, on_position_delete (4 sorgu)
- Dashboard "Bu Ay İşe Alınan" kartı bu alana bağlı (strftime('%Y-%m', guncelleme_tarihi))
- Yeni durum değiştiren UPDATE sorgusu eklenirse guncelleme_tarihi DAHİL EDİLMELİ
- Commit: 48743f2 — DEGISTIRME

24. CV parser lokasyon kuralı: Sadece adayın İKAMET adresi/şehri çıkarılır. İş deneyimindeki şehir lokasyon DEĞİLDİR. Eğitim şehri lokasyon DEĞİLDİR. Açık adres yoksa null döner. Tahmin/çıkarım YASAK. DEĞİŞMEZ.
25. CODE REVIEW KURALI: Her dosya yaziminda otomatik kontrol listesi uygula: (1) company_id izolasyonu - her DB sorgusu company_id filtresi icermeli (2) SQL injection - f-string ile SQL YASAK, parametrize query zorunlu (3) Turkce karakter - UI metinleri s,g,u,o,i,c kullanmali, HTTP header'larda Turkce YASAK (RFC 5987) (4) CV guvenligi - validate_cv_access() zorunlu, dosyalar /data/cvs/{company_id}/ yapisinda (5) Auth kontrolu - her endpoint JWT + role kontrolu icermeli (6) Error handling - except: pass YASAK, hatalar loglanmali (7) Kilitli fonksiyonlara dokunma - save_cv_file, validate_cv_access, convert_to_pdf, scoring_v2, eval_report_v2 DEGISTIRILEMEZ (8) BLACKLIST/keyword - 5 katmanli QA, usage count korumasi (9) KVKK audit - kisisel veri ve CV erisiminde audit log (10) Rate limiting - public endpoint'lerde limit kontrolu (11) Frontend - useEffect deps, key prop, error boundary. Sorun bulunursa DURDUR, raporla, onay bekle. DEGISMEZ.
26. TEST YAZARI KURALI: Test yazarken kontrol listesi uygula: (1) company_id izolasyon testi ZORUNLU - 2 sirket olustur, capraz erisim dene (2) Turkce karakter test verisi ZORUNLU (3) Durum korumasi - ise_alindi/arsiv adaylar degistirilemez (4) CV guvenligi - path traversal, dosya formati, boyut limiti (5) Auth testi - role kontrolu, devre disi kullanici, expired token (6) Mock stratejisi - Claude API ve LibreOffice mocklanmali, test edilen fonksiyon ASLA mocklanmamali (7) Regresyon - gecmis her bug icin en az 1 test (8) AAA pattern - Arrange/Act/Assert yapisi zorunlu (9) pytest fixture ile temiz DB - her test bagimsiz. DEGISMEZ.
27. API TASARIM KURALI: Yeni endpoint eklerken kontroller: (1) URL pattern - /api/{resource} cogul isim, snake_case/kebab YOK (2) Auth - Depends(get_current_user) zorunlu, public ise neden acikla (3) company_id - her DB sorgusunda filtre, public'te slug kullan ID gosterme (4) Response format - {"success": true, "data": {...}} veya {"detail": "Turkce mesaj"} (5) Hata mesajlari - Turkce, sistem bilgisi sizdirma (6) SQL - parametrize zorunlu, SELECT * yasak (7) Public endpoint - rate limiting + input validation + KVKK onay + CORS + bilgi sizintisi kontrolu (8) Mevcut pagination pattern koru - ?page=&limit=&search=&sort_by=&sort_order=. DEGISMEZ.
28. KVKK KURALI: Kisisel veri isleyen her ozellikte kontroller: (1) Aydinlatma metni - yeni veri toplama noktasinda ZORUNLU (2) Acik riza - checkbox isaretlenmeden form gonderilemez, riza tarihi+IP kaydedilmeli (3) Audit log - kisisel veri goruntuleme, degistirme, silme loglanmali (4) Veri minimizasyonu - gereksiz kisisel veri toplamama (5) Saklama suresi - her veri kategorisinin saklama suresi belirli olmali (6) Yurt disi aktarim - Claude API'ye veri gonderiliyorsa acik riza gerekli (7) Silme hakki - adayin verilerini silme/anonimleştirme mekanizmasi olmali. DEGISMEZ.
