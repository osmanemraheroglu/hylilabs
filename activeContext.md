# HyliLabs — Aktif Baglam
Son guncelleme: 19.02.2026

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
6. DB CASCADE DELETE: 6 tablo, 10 FK, 16 index. KALDIRILMAZ.
7. company_id guvenlik katmani: Tum tablolarda. ZORUNLU.
8. CV dosya izolasyonu: /data/cvs/{company_id}/. GERI DONULEMEZ.
9. Firma login kontrolu: verify_user() aktiflik kontrolu. DEGISMEZ.
10. Ayarlar sayfasi: Sadece 3 sekme. KILITLI.

## Son 72 Saatte Tamamlananlar
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

## Son Commitler
f11aeac - ui: clarify date labels and add relative time tooltip
2627a12 - docs: add .cursorrules with SQL company_id prefix rule
4311074 - fix: resolve SQL ambiguous column error in dashboard stats
ea98465 - fix: restore user session on page refresh via /api/auth/me
47a97ac - fix: clean super admin panel

## Sonraki Gorev
Mulakat Takvimi menusu incelenecek. Once kesif raporu alinacak.

## Bilinen Acik Konular
- pm2 kurulu degil, vite preview ile calisiyor
- SSL henuz yok (HTTP)
- Company Switcher henuz yapilmadi
