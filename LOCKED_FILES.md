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
