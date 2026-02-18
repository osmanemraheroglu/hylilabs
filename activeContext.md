# Aktif Context

## Son Güncelleme: 18 Şubat 2026

## Şu An Üzerinde Çalışıyoruz
- Production'a geçiş hazırlığı
- Company Switcher planlandı (3 görev, henüz başlanmadı)

## Bugün Tamamlanan (18 Şubat 2026)
- Data Reset sistemi (backend + UI) — 3 kademe: candidates/pools/full
- CV ZIP Download (backend + UI) — Adaylar + Havuzlar sayfası
- Filtre bug fix — departman/pozisyon/arsiv filtreleri düzeltildi
- Kilitleme güncellendi — LOCKED_FILES.md, CLAUDE.md
- Duplicate CV kontrolü eklendi (create_candidate scope, tüm entry point korumalı)
- Taner Baransel duplicate temizlendi (51 aday)

## Bugünkü Commit'ler
- d6cddfd feat: add reset-data endpoint with backup + password validation
- d45abf2 feat: add CV download as ZIP endpoint
- 16efbf8 feat: add Gelismis (Advanced) settings tab
- a7214e4 feat: add CV download ZIP button to candidates page
- 8f3ecf3 feat: add pool CV download ZIP button to havuzlar page
- 039bfea fix: candidates filter - departman/pozisyon queries
- b373b60 fix: CV download respects filter + add arsiv filter

## Son Yapılanlar (17 Şubat)
- JWT secret .env'e taşındı (89a6f2d)
- Swagger/ReDoc production'da kapatıldı (6370d84)
- Security headers eklendi (6370d84)
- LOCKED_FILES güvenlik kontrolleri eklendi (dba6dfd)

## Açık Sorunlar
1. Template sekmeler temizliği — Profile/Account/Appearance/Notifications/Display gereksiz
2. SSL sorunu — HTTP indirme uyarısı (HTTPS gerekli)
3. Kariyer.net Cloudflare 403 — Brightdata proxy bekliyor
4. Company Switcher — 3 görev planlandı
5. Production altyapı — DNS, SSL, Nginx, Türkiye VPS

## Bugün Dokunma
- Kilitli 12 dosya (güncel liste LOCKED_FILES.md'de)
- Scoring v2.1 sistemi
- Akıllı Havuz Önerisi v2
- Reset-data endpoint güvenlik mantığı
- Adaylar filtre JOIN mantığı
