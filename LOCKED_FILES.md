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

## DOĞRULAMA SİSTEMİ (3x Kontrol)
Dosya kilitlenmeden önce:
1. Fonksiyon eşleşmesi — TalentFlow ile birebir aynı mı?
2. Çalışma testi — API + Frontend doğru çalışıyor mu?
3. Entegrasyon testi — Diğer modüllerle bağlantı sorunsuz mu?

## CLAUDE CODE TALİMATI
- Kilitli dosyada değişiklik talebi → "Bu dosya kilitli, EMRAHFC onayı gerekli" de ve DUR.
- Yeni kilit talebi → 3x kontrol yap, raporla, onay bekle.
