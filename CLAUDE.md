# HyliLabs — Claude Kurallari

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
12. Adaylar filtre sistemi (genel/departman/pozisyon/arsiv) candidate_pool_assignments JOIN mantigi korunmali
13. create_candidate() duplicate kontrolu (email + telefon) kaldirilmaz
14. CV dosyalari firma bazli izole: /data/cvs/{company_id}/. save_cv_file() company_id zorunlu. validate_cv_access() okuma kontrolu zorunlu. Flat yapiya geri donulemez. 2x3 guvenlik kontrolu DEGISTIRILEMEZ
15. DB CASCADE DELETE aktif: applications, matches, candidate_pool_assignments, position_pools, ai_evaluations -> candidates ON DELETE CASCADE. position_keywords_v2 -> department_pools ON DELETE CASCADE. interviews -> candidates, department_pools, companies ON DELETE CASCADE. PRAGMA foreign_keys=ON her connectionda zorunlu. Tablo yapilari DEGISTIRILEMEZ. CASCADE kaldirilmaz.

## Stil
- Fonksiyon ve degisken: snake_case (Python), camelCase (TypeScript)
- API response: {"success": true, "data": ...} veya {"detail": "hata mesaji"}
- Frontend: shadcn/ui + Tailwind
- Hata mesajlari Turkce

## SQL Kurali
JOIN iceren tum SQL sorgularinda company_id her zaman tablo prefixiyle yazilmali (orn: c.company_id, a.company_id). Prefixsiz AND company_id = ? kullanimi yasaktir.
