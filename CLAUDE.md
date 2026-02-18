# HyliLabs — Claude Kuralları

## Proje
HyliLabs: AI destekli HR recruitment platformu. React + FastAPI + SQLite. Türkiye pazarı, KVKK uyumlu.

## Sunucular
- Production: ***REMOVED*** (React:3000, FastAPI:8000)
- Eski TalentFlow: ***REMOVED*** (Streamlit, artık güncellenmeyecek)

## Roller
- Claude Opus: Planlama, mimari kararlar, strateji
- Antigravity/Cursor: Kod yazma, implementasyon
- Claude Code: Sunucuda çalıştırma, git commit, deploy

## Kod Kuralları
- Dil: Python backend, TypeScript frontend
- Her değişiklik dev branch'te yapılır, test edilir, sonra main'e merge
- commit mesajları: fix:, feat:, security:, lock:, refactor: prefix kullan
- Türkçe değişken/tablo adları backend'de OK (baslik, departman vb.)
- .env ASLA git'e eklenmez
- Her yeni dosya ARCHITECTURE.md'ye eklenir

## KİLİTLİ DOSYALAR — DOKUNMA
Bu dosyalar 3+ kez doğrulanmış, DEĞİŞTİRİLMEZ:
1. scoring_v2.py — Eşleştirme motoru
2. job_scraper.py — Kariyer.net parser
3. eval_report.py — AI değerlendirme
4. email_worker.py — Email CV worker
5. email_reader.py — IMAP reader
6. core/cv_parser.py — CV parser (Claude API)
7. routes/cv.py — CV upload + auto-match
8. routes/emails.py — Email yönetimi
9. routes/candidates.py — CASCADE delete
10. cv-collect/index.tsx — CV toplama UI

## KİLİTLİ KURALLAR — İHLAL ETME
1. SECRET_KEY her zaman os.getenv() ile okunmalı
2. FastAPI docs production'da None olmalı
3. Security headers middleware kaldırılmamalı
4. .env dosyası ASLA git'e eklenmemeli
5. API endpoint'leri auth olmadan erişilemez (public hariç)
6. v2 eşleştirme: Fuzzy 70→85, 85→92. Partial devre dışı. Max 1 pozisyon/aday. DEĞİŞMEMELİ
7. Akıllı Havuz Önerisi v2 korunmalı, değiştirilmemeli
8. Scoring v2.1: dynamic knockout(%50), junior/senior penaltı, eğitim kademeli. DEĞİŞMEMELİ

## Stil
- Fonksiyon ve değişken: snake_case (Python), camelCase (TypeScript)
- API response: {"success": true, "data": ...} veya {"detail": "hata mesajı"}
- Frontend: shadcn/ui + Tailwind
- Hata mesajları Türkçe
