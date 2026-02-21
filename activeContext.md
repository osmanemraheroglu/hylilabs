# HyliLabs — Aktif Baglam
Son guncelleme: 21.02.2026

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

## Kilitli Sistemler — DOKUNULMAZLAR
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

## Son 72 Saatte Tamamlananlar
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
Frontend Turkce karakter duzeltmeleri tamamlandi ve deploy edildi.

## Bilinen Acik Konular
- SSL henuz yok (HTTP)
- Company Switcher henuz yapilmadi
