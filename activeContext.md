# Aktif Context

## Son Güncelleme: 18 Şubat 2026 (Akşam)

## Bugün Tamamlanan (18 Şubat 2026)

### Özellikler
- Data Reset sistemi — 3 kademe (candidates/pools/full), şifre+SIFIRLA onay, otomatik backup
- CV ZIP Download — Adaylar + Havuzlar sayfası, filtre-bağımlı indirme
- Şifre Değiştir — PUT /api/auth/change-password endpoint + UI
- Tema seçimi — Sadeleştirilmiş Açık/Koyu tema sayfası

### Bug Fix
- Adaylar filtre sistemi — departman/pozisyon/arsiv artık doğru çalışıyor
- CV İndir butonu — Seçili havuz filtresine göre indirme
- Duplicate CV kontrolü — create_candidate() içinde email+telefon kontrolü

### Refactor
- Ayarlar sayfası temizliği — 6 sekmeden 3'e düşürüldü (Şifre, Tema, Gelişmiş)

### Kilitleme
- 13 kilitli kural (CLAUDE.md)
- 14 kilitli dosya (LOCKED_FILES.md)
- Duplicate kontrolü, filtre mantığı, reset-data güvenliği kilitlendi

## Bugünkü Commit'ler (12 adet)
- e9c164e refactor: clean settings page - keep password/theme/advanced
- 11dd0ff lock: duplicate CV check in create_candidate
- 5a9f608 fix: add duplicate check to create_candidate
- 545d9e6 lock: 18.02.2026 - data management features locked
- b373b60 fix: CV download respects filter + add arsiv filter
- 039bfea fix: candidates filter - departman/pozisyon queries
- 8f3ecf3 feat: add pool CV download ZIP button to havuzlar page
- a7214e4 feat: add CV download ZIP button to candidates page
- 16efbf8 feat: add Gelismis (Advanced) settings tab
- d45abf2 feat: add CV download as ZIP endpoint
- d6cddfd feat: add reset-data endpoint with backup + password validation
- ec03569 feat: Memory Bank sistemi kuruldu

## Sonraki Session İçin Açık Konular
1. Company Switcher — 3 görev planlandı
2. Production altyapı — SSL, DNS, Nginx, Türkiye VPS
3. Kariyer Sayfası — Dış başvuru formu, llms.txt
4. Eski route dosyaları temizliği — profile, account, notifications, display (dosyalar duruyor, sidebar'dan kaldırıldı)
5. Kariyer.net Cloudflare 403 — Brightdata proxy bekliyor

## Bugün Dokunma
- Kilitli 14 dosya (güncel liste LOCKED_FILES.md'de)
- Scoring v2.1 sistemi
- Akıllı Havuz Önerisi v2
- Reset-data endpoint güvenlik mantığı
- Adaylar filtre JOIN mantığı
- create_candidate() duplicate kontrolü
