# HyliLabs — Aktif Baglam
Son guncelleme: 23.02.2026

## Mevcut Sistem Durumu
- Frontend: React + Vite, port 3000
- Backend: FastAPI + Uvicorn, port 8000
- DB: SQLite (/var/www/hylilabs/api/data/talentflow.db)
- GitHub: https://github.com/osmanemraheroglu/hylilabs.git
- Branch: main

## Aktif Kullanicilar
- admin@talentflow.com -> super_admin -> aktif
- demo@demo.com -> company_admin -> aktif (sifre: demo123)
- test@test.com -> user -> PASIF (aktif=0, GERI ALINAMAZ)

## Kilitli Sistemler — DOKUNULMAZLAR (27 sistem)
1. v2 eslestirme: Fuzzy 70->85, 85->92. Max 1 pozisyon/aday. DEGISMEZ.
2. Scoring v2.1: Dynamic knockout(%50), junior/senior penalti, egitim kademeli. DEGISMEZ.
3. Claude CV parsing: %100 basarili. Parse sistemi bozulmamali.
4. categorize_and_save(): Pozisyon ekleme akisina entegre. DEGISMEZ.
5. Akilli Havuz Onerisi v2: approved_title_mappings tablosu. DEGISMEZ.
6. DB CASCADE DELETE: 16 tablo, 24 FK CASCADE. KALDIRILMAZ.
7. company_id guvenlik katmani: Tum tablolarda. ZORUNLU.
8. CV dosya izolasyonu: /data/cvs/{company_id}/. GERI DONULEMEZ.
9. Firma login kontrolu: verify_user() aktiflik kontrolu. DEGISMEZ.
10. Ayarlar sayfasi: Sadece 3 sekme. KILITLI.
11. Aday Durum Akisi Senkronizasyonu: candidates.durum + pool_assignments birlikte guncellenir.
12. Dashboard Visibility Refresh: fetchDashboardData() + visibilitychange.
13. Genel Havuzdan Silme Engeli: 400 HTTPException + toast.error().
14. Pool Assignments Veri Kurallari: Her durum icin havuz kurali.

## Son 72 Saatte Tamamlananlar
### 23.02.2026
- CLAUDE.md: 4 yeni sistem kilitlendi (#24-27) - Durum senkronizasyonu, dashboard refresh, pool kurallari
- Genel Havuz'dan silme icin kullanici dostu toast mesaji (havuzlar frontend)
- COMMIT D: havuzdan silme durum guncelleme + dashboard visibility refresh
- COMMIT C: ise-al endpoint pool_assignments temizleme eklendi + DB fix (ID:434)
- COMMIT B: elen endpoint pool_assignments senkronizasyonu eklendi
- COMMIT A FIX: Duplicate pool assignments duzeltildi (430,431 Genel Havuz'dan silindi, sadece Arsiv'de)
- COMMIT A: 2 yetim aday (411,423) Genel Havuz'a eklendi (candidate_pool_assignments: 51->53->51)
- dashboard.py labels'a "yeni" eklendi (pie chart icin)
- 3 arsivli aday (430,431,432) Arsiv havuzuna eklendi (candidate_pool_assignments)
- arsivle endpoint duzeltildi: candidate_pool_assignments'a Arsiv havuzu atamasi eklendi
- Mevcut arsivli aday (ID=432) Arsiv havuzuna eklendi
- Havuzlar frontend cift sayim duzeltildi: totalCandidates artik backend'den geliyor
- TreeData interface'e total_candidates eklendi
- totalCandidates hesaplamasi basitlestirildi (tree?.total_candidates || 0)
- Backend /api/pools/hierarchical endpoint'ine total_candidates eklendi
- window.alert() kaldirildi, sonner toast bildirimleri eklendi (3 dosya, 33 alert)
- email-hesaplari, firma-yonetimi, havuzlar sayfalarinda toast.success/error kullaniliyor
- PYTHONPATH fix: ecosystem.config.cjs'e core/ path eklendi
- candidate_matcher ve cv_parser import hatalari cozuldu
- v2 scoring artik duzgun calisiyor (fallback'e dusmuyor)
- Auth yonlendirme duzeltildi: token yoksa /sign-in'e yonlendir
- /api/auth/me endpoint'i: aktif=0 kullanici -> 401, aktif=0 firma -> 403
- Login endpoint'i: pasif kullanici/firma icin ozel hata mesajlari
- Frontend initAuth(): 401/403 durumunda token silip /sign-in'e yonlendiriyor
- Token varken /sign-in'e gelince /'e (dashboard) yonlendiriyor
- Firma Yonetimi: Aktif/Pasif toggle ve Kalici Silme ayrildi
- PATCH /api/companies/{id}/toggle-status: aktif<->pasif toggle
- DELETE /api/companies/{id}: Kalici silme (hard delete) - tum veriler silinir
- hard_delete_company(): 10 tablo sirayla siliniyor (candidates, users, interviews, vs.)
- Silme onay dialogu: "Bu islem GERI ALINAMAZ" uyarisi
- URL Parse frontend duzeltildi: res.basarili -> res.success, res.pozisyon_adi -> res.data.pozisyon_adi
- save-parsed endpoint detayli loglama eklendi (debug icin)
- save-parsed endpoint test edildi: calisiyor (pool olusturma, categorize_and_save, pull_matching)
- URL Parse sonuc render crash duzeltildi: SelectItem value="" -> value="none" (3 yer)
- Select value guard eklendi: value={x || "none"} + onValueChange none->empty string ceviri
- KRITIK BUG FIX: Eslestirme calismiyordu - approve_titles sadece position_title_mappings guncelliyordu
- approved_title_mappings senkronizasyonu eklendi (pools.py approve_titles endpoint)

### 22.02.2026
- Mulakat olusturulunca aday durumu otomatik 'mulakat' olarak guncelleniyor
- Mulakat iptal edilince baska aktif mulakat yoksa aday durumu 'pozisyona_atandi' olarak geri aliniyor
- Mulakat silinince baska aktif mulakat yoksa aday durumu 'pozisyona_atandi' olarak geri aliniyor
- Dashboard "Mulakat Bekleyen" ve Takvim "Planlanmis" senkronizasyonu saglandi
- Dashboard "Bekleyen" karti duzeltildi: position_pools.durum='beklemede' -> candidates.durum='yeni'
- Plan dropdown kaldirildi (firma-yonetimi sayfasindan)
- CV yuklemede max_aday limiti kontrolu eklendi (403 hatasi donuyor)
- CV Topla sayfasinda aday limiti gostergesi eklendi (X / Y Aday + progress bar)
- /api/companies/me endpoint'i eklendi (kullanicinin firmasini getir)
- create_company() eksik parametreler eklendi (yetkili_adi, yetkili_email, yetkili_telefon, max_kullanici, max_aday)
- Firma olusturulunca yetkili emaile otomatik kullanici hesabi ve sifre emaili gonderiliyor
- Firma kullanici olusturma kolon adi duzeltildi (sifre -> password_hash)
- Firma silme fonksiyonu duzeltildi (durum kolonu yok, rowcount fix)
- Login sayfasi HyliLabs markasi ve Turkce (Shadcn Admin -> HyliLabs, Sign in -> Giris Yap)
- Teams dropdown kaldirildi (sol ust logo artik tiklanabilir degil)
- Sidebar "Firma Yonetimi" -> "Firma Yönetimi" Turkce duzeltme
- Dashboard "Mulakat Bekleyen" -> "Mülakat Bekleyen" Turkce duzeltme

### 20.02.2026
- pm2 kurulumu ve yapilandirilmasi (ecosystem.config.cjs)
- systemd -> pm2 gecisi (frontend + backend)
- DEPLOYMENT.md olusturuldu (yeni sunucu rehberi)
- Mulakat Takvimi pozisyon dropdown duzeltildi (positions -> department_pools)
- Mulakat Takvimi Turkce karakter duzeltmeleri (20+ kelime)
- Mulakat Takvimi tarih formati GG.AA.YYYY (toLocaleDateString tr-TR)
- Mulakat Form sirasi degistirildi: Pozisyon (opsiyonel) -> Aday (zorunlu)
- Mulakat Form pozisyon secilince aday filtreleme (positionCandidates)
- Mulakat Form pozisyonsuz aday uyarisi eklendi
- Mulakat Form SelectItem value="" crash duzeltildi (value="none")
- Mulakat Form tarih input placeholder="GG.AA.YYYY" eklendi
- Mulakat olusturulunca adaya email gonderme ozelligi eklendi
- Mulakat email onizleme akisi eklendi (Kaydet -> Onizle -> Gonder)
- Backend: email-preview ve send-email endpointleri (/api/interviews/{id}/email-preview, /api/interviews/{id}/send-email)
- email_sender.py: generate_interview_invite_content helper fonksiyonu eklendi
- Frontend: Email onizleme dialog'u (duzenlenebilir alici email, konu/icerik onizleme)
- Email preview dialog DOM crash fix (setTimeout 150ms delay between dialogs)
- Email preview dialog state fix (reorder state updates, loadInterviews en sona alindi)
- Email gonderimi: veritabani hesabi kullanimi (email_accounts tablosu, varsayilan_gonderim=1)
- send_interview_invite() account parametresi eklendi
- Mulakat onaylama linki sistemi: token uretimi, public /confirm/{token} endpoint, email'de onay linki
- Mulakat formu onay suresi secimi eklendi (1/3/7/14/30 gun, varsayilan 3)

### 21.02.2026
- Mulakat formu onay suresi Select alani eklendi (frontend)
- Backend: onay_suresi parametresi aliniyor, token suresi dinamik
- Email taslagi dinamik onay_suresi kullanimi (hardcoded 7 gun -> parametrik)
- Email icerik Turkce karakter duzeltmeleri (25+ kelime)
- Email tarih formati Turkce (22 Subat 2026)
- NOTLAR bolumu kosullu (not yoksa gizle)
- Sirket adi dinamik (companies tablosundan)
- Otomatik hatirlatma email sistemi (APScheduler)
- scheduler.py: send_reminder_emails() her gun 09:00
- is_reminder parametresi eklendi (email konu + icerik farkli)
- interviews tablosuna onay_suresi kolonu eklendi
- Email sender_name dinamik: sirket_adi > account.sender_name > 'HyliLabs'
- Mulakat takvimi onay durumu badge (confirmed/pending)
- Onay durumu filtre dropdown eklendi
- Stats kart sayisi 4->5 (Onaylandi eklendi)
- Email UTF-8 encoding fix (Header + formataddr)
- Keyword Istatistikleri menuden kaldirildi
- Dashboard Eksik Beceriler widget'i kaldirildi (veri altyapisi hazir degil)
- Profil dropdown: Faturalama ve Yeni Takim secenekleri kaldirildi
- Profil dropdown: Turkce ceviri (Profile->Profil, Settings->Ayarlar, Sign out->Oturumu Kapat)
- Frontend Turkce karakter duzeltmeleri (9 dosya, 150+ kelime):
  - settings/password/index.tsx: Sifre -> Şifre, vs.
  - settings/theme/index.tsx: Acik -> Açık, Guncelle -> Güncelle
  - settings/index.tsx: Gelismis -> Gelişmiş
  - user-management/index.tsx: Kullanici -> Kullanıcı, Sifre -> Şifre, vs.
  - havuzlar/index.tsx: Duzenle -> Düzenle, Iptal -> İptal, Egitim -> Eğitim, vs.
  - admin-panel/index.tsx: Istatistikler -> İstatistikler, Kullanici -> Kullanıcı
  - firma-yonetimi/index.tsx: Firma Yonetimi -> Yönetimi, Olustur -> Oluştur
  - email-hesaplari/index.tsx: Gonderim -> Gönderim, Saglayici -> Sağlayıcı
  - dashboard/index.tsx: once -> önce, bakis -> bakış
- Ek Turkce karakter duzeltmeleri (4 dosya, 40+ duzeltme):
  - dashboard/index.tsx: Bugün, Başvuru, Değerlendirme, Dağılımı, göre, etc.
  - candidates/index.tsx: önce, yıl, Değerlendirmede, Mülakat, Arşiv, Yükleme, Şirket, Eğitim, etc.
  - settings-page/index.tsx: Firma Adı, Kullanıcı, Günlük, Bağlantı hatası, görüntülemek için, etc.
  - havuzlar/index.tsx: Mülakat, dosyaları, başarıyla, tamamlandı, yıl, yüklenemedi, Henüz, başlık, etc.
- cv-collect/index.tsx Turkce karakter duzeltmeleri (30+ duzeltme):
  - Manuel Yükle, CV Yükle, Başarılı, Başarı Oranı, Toplama Geçmişi
  - seçmek için tıklayın, sürükleyin, dosyaları desteklenir
  - hesabı bulunamadı, Hesapları sayfasından, Hesabı Seçimi
  - Klasör Seçimi, klasörleri yükleyin, Klasörleri Yükle, yüklenmedi
  - Tarama Ayarları, okunmamış, işlenir, Taranıyor, işlemini başlatın
- sidebar-data.ts Turkce karakter duzeltmeleri:
  - Mülakat Takvimi, Email Hesapları, Kullanıcı Yönetimi
- cv-collect/index.tsx durum badge Turkce etiketler:
  - getDurumLabel() fonksiyonu eklendi
  - tamamlandi->Tamamlandı, basarili->Başarılı, kismi_basarili->Kısmi Başarılı, basarisiz->Başarısız, devam_ediyor->Devam Ediyor
- dashboard/index.tsx pie chart Turkce etiketler:
  - DURUM_LABELS map eklendi
  - yeni->Yeni, pozisyona_atandi->Pozisyona Atandı, mulakatta->Mülakata Çağrıldı, arsiv->Arşiv, reddedildi->Reddedildi, ise_alindi->İşe Alındı
- havuzlar/index.tsx kalan Turkce duzeltmeleri:
  - havuzlarini -> havuzlarını, Arsiv -> Arşiv

### 18.02.2026
- Data Reset endpoint + UI (3 kademe)
- CV ZIP Download endpoint + UI
- Filtre fix (departman/pozisyon/arsiv)
- Duplicate CV kontrolu
- Ayarlar sayfasi 6->3 sekme
- Sifre degistir backend + UI
- Tema sadelestirme (Light/Dark)
- Firma login kontrolu (pasif firma bloklama)
- CV dosya izolasyonu (2x3 guvenlik)
- 5 tabloya company_id eklendi
- 240 yetim kayit temizlendi
- DB CASCADE DELETE (6 tablo yeniden olusturuldu)

### 19.02.2026
- Super Admin dropdown temizligi
- Eski route/feature dosyalari silindi (11 dosya, 1059 satir)
- Admin panel 500 hatasi duzeltildi -> commit 47a97ac
- test@test.com pasif edildi (aktif=0) -> GERI ALINAMAZ
- Auth session bug duzeltildi (initAuth + /api/auth/me) -> commit ea98465
- Dashboard SQL ambiguous column bug duzeltildi -> commit 4311074
- .cursorrules SQL kurali eklendi -> commit 2627a12
- Dashboard "Son Email Basvurulari" etiketi + tooltip -> commit f11aeac
- Adaylar "CV Yukleme Tarihi" etiketi + tooltip -> commit f11aeac
- interviews tablosu CASCADE DELETE eklendi (3 FK)
- create_interview() company_id guvenlik eklendi
- create_application() SQL hatasi duzeltildi (5 kolon 6 placeholder -> 6/6) + company_id
- transfer_candidates_to_position() company_id eklendi (candidate'dan turetiliyor)
- 9 tabloya CASCADE DELETE eklendi (ai_analyses, hr_evaluations, position_requirements, position_sector_preferences, position_title_mappings, candidate_merge_logs, company_settings, email_accounts, email_templates)
- audit_logs INSERT'e company_id eklendi
- email_templates 56.544 duplike kayit silindi (56.550 -> 6)
- email_templates UNIQUE(company_id, sablon_kodu) constraint eklendi
- email_templates INSERT OR IGNORE company_id=1 olarak duzeltildi

## Son Commitler
6c4410b - fix: havuzlar frontend cift sayim duzeltildi - totalCandidates artik backendden geliyor
9d28dd0 - ui: window.alert kaldirildi, toast bildirimleri eklendi
c56a09c - fix: PYTHONPATH core/ eklendi - candidate_matcher ve cv_parser import sorunu cozuldu
e0a669f - fix: eslestirme calismiyordu - approved_title_mappings senkronizasyonu eklendi
e32c1a4 - fix: URL parse sonuc render SelectItem value crash duzeltildi
fec1e45 - debug: save-parsed endpoint detayli loglama
275682b - fix: URL parse frontend response handling duzeltmesi
52b7a7f - security: IDOR duzeltmesi, audit log, mulakat izolasyon dogrulama
df4b16c - docs: security sistemi CLAUDE.md kilitlendi
aab1e57 - security: JWT secret zorunlu, rate limiting public endpoint hazirlik
b5c8dfa - fix: auth yonlendirme duzeltmesi - pasif kullanici ve route guard
84967de - fix: teams dropdown kaldirildi, menu ve dashboard Turkce duzeltme
7d4126d - fix: login sayfasi HyliLabs markasi ve Turkce duzeltmesi
cf31959 - fix: firma email gonderi ve silme hatasi duzeltildi
14a2aef - feat: firma olusturulunca yetkili email otomatik kullanici ve sifre emaili
875bea8 - fix: create_company() eksik parametreler eklendi
a149447 - feat: plan dropdown kaldirildi, max_aday limiti ve gosterge eklendi
525a132 - fix: dashboard bekleyen karti - yanlis tablo duzeltildi, candidates.durum=yeni
7480780 - fix: mulakat olusturulunca aday durumu guncelleniyor + update activeContext
4c185c2 - fix: frontend turkce karakter duzeltmeleri - ek dosyalar (4 dosya, 40+)
1fe9af5 - fix: settings/advanced Turkce karakter duzeltmesi - sadece UI metinleri
577ef45 - fix: frontend turkce karakter duzeltmeleri (9 dosya)
c9dfa57 - feat: keyword sayfasi menuden kaldirildi, eksik beceriler dashboard widget
dbbbe75 - feat: takvimde onaylandi badge ve filtre
951abf2 - feat: email sender_name dinamik sirket adi destegi
4928766 - feat: mulakat onaylama linki - token sistemi ve public endpoint
536e950 - fix: email gonderiminde veritabani hesabini kullan (email/sifre kolonlari)
2cbf52b - fix: email preview dialog state fix - reorder state updates and API calls
90de6f9 - fix: email preview dialog DOM crash - add setTimeout delay between dialogs
4e3a926 - feat: email onizleme akisi eklendi (Kaydet -> Onizle -> Gonder)
a35032c - feat: mulakat olusturulunca adaya email gonder
8aaf655 - fix: tarih input placeholder GG.AA.YYYY eklendi
ef71d87 - fix: SelectItem empty value crash - use 'none' instead of empty string
0fa0186 - docs: update activeContext.md - mulakat form improvements

## Sonraki Gorev
Kariyer Sayfasi guvenlik taramasi ve gelistirme.

## Bilinen Acik Konular
- SSL henuz yok (HTTP)
- Company Switcher henuz yapilmadi

## Son Security Duzeltmeleri (23.02.2026)
- IDOR zafiyeti duzeltildi (pools.py: 4 sorguya company_id filtresi eklendi)
- Super Admin audit log eklendi (firma olusturma, silme, durum degisikligi)
- JWT_SECRET fallback kaldirildi, .env zorunlu
- Public endpoint rate limiting hazir (check_public_apply_limit, check_public_positions_limit)
- Mulakat izolasyonu dogrulandi (0 NULL company_id kayit)
