# HyliLabs — Aktif Bağlam

Son güncelleme: 13.03.2026

## Mevcut Sistem Durumu

- **Sunucu:** ***REMOVED*** (PM2 ile çalışıyor)
- **Son commit:** dbe06b0 (FAZ 12.6.1: candidate_pool_assignments sync)
- **Backend:** FastAPI + SQLite (WAL mode)
- **Frontend:** React + TypeScript + Tailwind
- **Puanlama:** 100 puan sistemi v2.1 + V3 weighted (60%V3+40%V2) aktif

## Aktif Kullanıcılar

- Adnan Bey (İK Direktörü) — test + onay
- 3 şirket, ~50 aday, 5 pozisyon

## Son 72 Saatte Tamamlananlar

### 13.03.2026 - HyliLabs Landing Page
- ✅ **Çözüm Ortaklarımız Bölümü** (tamamlandı)
  - "Nasıl Çalışır" ile "Fiyatlandırma" arasına eklendi
  - 5 logo: Anthropic, Claude, Gemini, Google, Hetzner
  - Grayscale + opacity efekti, hover'da renkli
  - RevealSection scroll animasyonu
- ✅ **Landing Page Logo Entegrasyonu** (tamamlandı)
  - Navbar: Logo_400x120.png (height: 56px)
  - Footer: footer_logo_600x400.png (beyaz yazılı, koyu arka plan, height: 80px)
  - Logo dosyaları: public/images/Logo_400x120.png, public/images/Logo_600x400.png
- ✅ **Landing Page Entegrasyonu** (tamamlandı)
  - `/` = Landing page (public), `/sign-in` = Giriş sayfası, `/dashboard` = Dashboard (auth)
  - Landing page bileşeni: `src/features/landing/index.tsx`
  - Bölümler: Navbar, Hero, Özellikler (6 kart), Nasıl Çalışır (4 adım), Fiyatlandırma (3 plan), İletişim (form), Footer
  - Route yapısı: `src/routes/index.tsx` (public root), `src/routes/_authenticated/dashboard/index.tsx` (dashboard)
  - Auth guard güncellendi: `initAuth()` public paths listesi eklendi (/, /sign-in, /sign-up vb.)
  - Login sonrası redirect: `/` → `/dashboard`
  - Sidebar dashboard linki: `/` → `/dashboard`
  - Değişen dosyalar:
    - YENİ: `src/features/landing/index.tsx`, `src/routes/index.tsx`, `src/routes/_authenticated/dashboard/index.tsx`
    - SİLİNEN: `src/routes/_authenticated/index.tsx`
    - GÜNCELLENEN: `auth-store.ts`, `user-auth-form.tsx`, `sidebar-data.ts`, `otp-form.tsx`, 4 error sayfası

### 13.03.2026
- ✅ **FAZ 12: V3 Puanlama Bug Fix** (tamamlandı)
  - **FAZ 12.1**: ai_evaluator.py düzeltmeleri
    - Hermes/model skorları max 100 cap eklendi (satır 873)
    - Claude 0 fallback koşulu eklendi (satır 1023)
    - Claude 0 uyarı logu + notes_for_hr eklendi
  - **FAZ 12.2**: database.py retry mekanizması
    - save_v3_evaluation_to_db() 3 retry + exponential backoff (0.5s, 1s, 1.5s)
    - "database is locked" hatası için otomatik yeniden deneme
  - **FAZ 12.3**: DB hatalı verileri düzeltildi
    - Hermes > 100 olanlar 100'e cap edildi (1 kayıt)
    - Aday 447: V3=93, Match=82 hesaplandı (hermes+openai ortalaması)
    - Aday 397: V3=41, Match=42 hesaplandı (hermes+openai ortalaması)
  - **FAZ 12.3.1**: V2 skorları düzeltildi (19 kayıt)
    - Tersine hesaplama: v2 = (match - (v3 × 0.60)) / 0.40
    - Aday 447: V2=66, Aday 397: V2=44
    - V2=0 kalan kayıt: 0
  - **FAZ 12.4**: Frontend match_score gösterimi düzeltildi
    - Tablo skor kolonu: v3Evaluation.total_score → c.match_score (satır 803)
    - Kart detay skoru: v3Evaluation.total_score → cd.match_score (satır 947)
    - v3Evaluation: Sadece AI model detayları için kullanılıyor (Gemini, Hermes, OpenAI)
    - TypeScript build: OK
  - **FAZ 12.4.2**: Detail endpoint düzeltildi (pools.py)
    - SELECT: match_score, v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
    - candidate objesine 7 yeni alan eklendi
    - Aday kartı artık doğru match_score gösteriyor
  - **FAZ 12.6**: Genel Havuz tutarsızlığı düzeltildi
    - 17 orphan aday Genel Havuz'a taşındı (V3 < 40 ile elenenler)
    - 2 adayın durumu pozisyona_atandi yapıldı
    - database.py:7261-7285 V3 eleme sonrası Genel Havuz sync eklendi
    - Artık V3 < 40 ile elenen adaylar otomatik Genel Havuz'a dönüyor
  - **FAZ 12.6.1**: candidate_pool_assignments sync düzeltildi
    - 18 eksik aday kaydı candidate_pool_assignments tablosuna eklendi
    - V3 eleme sonrası candidate_pool_assignments INSERT eklendi (database.py:7281)
    - Frontend Genel Havuz artık 58 aday gösteriyor (40 yerine)
- ✅ **FAZ 11: V3 Skor Frontend Entegrasyonu**
  - **FAZ 11.1**: candidate_positions tablosuna 6 yeni kolon eklendi
    - v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
  - **FAZ 11.2**: Mevcut V3 veriler ai_evaluations'dan migrate edildi (19 kayıt)
  - **FAZ 11.2.1**: match_score weighted average güncellendi (17 kayıt v3_weighted)
  - **FAZ 11.3**: add_candidate_to_position() ve ilgili fonksiyonlar güncellendi
    - Yeni parametreler: v2_score, v3_score, gemini_score, hermes_score, openai_score, score_version
    - match_single_candidate_to_positions() V3 skorları ile çağırıyor
    - pull_matching_candidates_to_position() UPDATE V3 skorları ekliyor
  - **FAZ 11.4**: get_position_candidates() V3 kolonları döndürüyor
  - **FAZ 11.5**: Frontend loadCandidates() v3Evaluation state'ini otomatik dolduruyor
  - V3 skorları artık sayfa yüklendiğinde görünür (Değerlendir tıklamaya gerek yok)
- ✅ **FAZ 10.1: V3 Sync Değerlendirme Entegrasyonu**
  - pull_matching_candidates_to_position fonksiyonuna V3 eklendi
  - Weighted average formülü: Final = (V3 × 0.60) + (V2 × 0.40)
  - save_v3_evaluation_to_db() fonksiyonu eklendi (satır 12317)
  - V3 değerlendirme sonucu ai_evaluations tablosuna kaydediliyor
  - final_score < 40 → aday pozisyondan çıkarılıyor
  - match_reason: "V3 weighted (60%V3+40%V2)" gösteriliyor
- ✅ **Gemini Maliyet Optimizasyonu** (69c41f6)
  - gemini-2.5-pro → gemini-2.5-flash değişti
  - Thinking mode (thinkingConfig) kaldırıldı
  - Beklenen maliyet düşüşü: %95
  - ai_evaluator.py ve cv_intelligence.py güncellendi

### 12.03.2026
- ✅ **FAZ 6: Demo Test + Dokümantasyon Tamamlandı**
  - Demo raporu oluşturuldu (TOP 10 aday, havuz özeti, V3 istatistikleri)
  - Frontend erişilebilir (HTTP 200)
- ✅ **FAZ 5: Production Hazırlık Tamamlandı**
  - DB backup: backup_pre_demo_20260312_120510.db (77 MB)
  - Sunucu: 24 gün uptime, %27 disk, 825 MB RAM
  - PM2 startup: enabled
- ✅ **FAZ 4: Bug Fix + Polish Tamamlandı**
  - Error log: Temiz (hata yok)
  - DB tutarlılık: 81 aday, 28 V3 eval, 0 orphan
  - API health: OK
- ✅ **FAZ 3: V3 Batch Değerlendirme Tamamlandı**
  - 28 aday V3 ile değerlendirildi
  - Mükemmel (85-100): 8, İyi (70-84): 3, Orta (55-69): 2
  - Zayıf (40-54): 2, Uyumsuz (0-39): 13
  - Eligible: 20 (%71), Not Eligible: 8 (%29)
  - Consensus: average (19), claude_decision (9)
- ✅ **Scoring V3 batch_evaluate.py Fix** (1255f71)
  - `layer_scores` AttributeError düzeltildi (attribute yok)
  - `openai_score`, `models_used`, `scores` eklendi (getattr fallback)
  - Verbose output: consensus_method, claude_used gösteriliyor
  - Analiz: Sistem doğru çalışıyor (Claude hakim kararı)
- ✅ **OpenAI Sigorta Sistemi** (6efa98d - 11.03.2026)
  - Gemini/Hermes başarısız olunca OpenAI fallback
  - ai_evaluator.py: 3 model paralel + consensus
  - CandidateEvaluationResponse: openai_score, models_used

### 10.03.2026
- ✅ **Havuz Düzenle modal scroll fix** (7ab8e62)
  - Uzun içeriklerde Kaydet butonuna ulaşılabiliyor
  - max-h-[90vh], overflow-y-auto, sticky footer

### 09.03.2026
- ✅ **HyliLabs Logo Ekleme** (cf3841a)
  - PNG optimize: 1.45 MB → 222 KB (%85 küçültme)
  - logo.tsx: PNG kullanan img bileşeni
  - Sidebar: Logo + "HyliLabs" / "AI HR Platform"
  - Login: Logo + "HyliLabs"
- ✅ **Progress UI Step 4: API + Frontend Progress Bar** (ab71c7a)
  - GET /api/cv/processing-status endpoint
  - processingStatus state + 5sn polling
  - Progress bar UI (Email sekmesinde)
  - Aktif taramalar gerçek zamanlı izlenebilir
- ✅ **Progress UI Step 3: Worker Progress Entegrasyonu** (56d065d)
  - Başlangıç log: durum='devam_ediyor' ile kayıt oluştur
  - Progress update: Her 25 CV'de bir update
  - Bitiş: update_email_collection_log ile final durum
  - Fallback: log_id yoksa yeni kayıt oluştur
- ✅ **Progress UI Step 2: update_email_collection_log fonksiyonu** (f6c4a04)
  - database.py'ye update_email_collection_log() eklendi
  - Dinamik UPDATE sorgusu (sadece non-None alanlar)
  - bitis_zamani otomatik güncelleme
  - with get_connection() context manager kullanımı
- ✅ **Progress UI Step 1: log_email_collection entegrasyonu**
  - email_worker.py'ye log_email_collection import eklendi
  - check_emails_for_account() sonunda log çağrısı eklendi
  - Scheduler-triggered taramalar artık DB'ye loglanacak
  - Durum tespiti: tamamlandi/kismi_basarili/bos/basarisiz
- ✅ **Keyword double encoding fix** (9f79fe0)
  - handleUpdatePool: editKeywords array kullanılıyor
  - Çift JSON encoding sorunu çözüldü
- ✅ **Keyword parse bug fix** (f45979c)
  - Havuz düzenle modalında anahtar kelimeler doğru görünüyor
  - json.loads ile JSON string parse, split fallback korundu
- ✅ **Manuel Giriş sekmesi kaldırıldı** (723bcc9)
  - Pozisyon ekleme: Sadece "URL ile Ekle" ve "Dokümandan Ekle" kaldı
  - grid-cols-3 → grid-cols-2, 30 satır TabsContent silindi
- ✅ **Email CV check scheduler.py'ye taşındı** (67253b7)
  - Saat başı çalışma (00:00-23:00), APScheduler CronTrigger
  - email_worker.py'den schedule döngüsü kaldırıldı
  - Fonksiyonlar korundu (check_all_emails, check_emails_for_account)
- ✅ **CLAUDE.md 3-Katmanlı Mimari** (fe210fe)
  - MİMARİ PRENSİPLER bölümü eklendi
  - 3-Katmanlı Sistem: Directive, Orchestration, Execution
  - Self-Annealing Döngüsü: hata → düzeltme → öğrenme
  - Execution Mapping tablosu
- ✅ **Pozisyon sil→aday kaybı FIX TAM** (f872d62 + 53d2419)
  - Kısım 1: CV Çek sadece durum='yeni' tarıyor (f872d62)
  - Kısım 2: Pozisyon silinince TÜM adaylar Genel Havuz'a (53d2419)
  - 30 gün arşiv mantığı kaldırıldı
- ✅ **Otomatik arşivleme kuralı güncellendi** (9f8ca0b)
  - 30→90 gün, eşleşme kontrolü eklendi (candidate_positions)
  - candidates.durum güncelleme bug'ı düzeltildi
- ✅ **Kara Liste UI İyileştirmeleri** — TAM (4de9ddb)
  - Havuzlar: "Durum" kolonu → "Kara Liste" kolonu
  - Ban ikonu tıklanabilir (kara listede değilse)
  - "Kara Listede" badge (kara listedeyse)
  - Duplicate Ban butonu kaldırıldı
  - Blacklist info kartı (neden, ekleyen, tarih)
  - "Kara Listeden Çıkar" butonu + modal
  - loadDetail'de blacklist info fetch
  - DELETE API: body → query param
- ✅ **Kara Liste Badge + Info** — havuzlar + candidates (d43b22e)
  - Durum badge blacklist önceliği
  - Kara liste bilgi kartı
  - Çıkarma modalları

### 08.03.2026
- ✅ **Kara Liste Sistemi TAM** — database + API + frontend (16aee37)
  - blacklisted_candidates tablosu (15 kolon, 3 index)
  - candidates.is_blacklisted + blacklist_id kolonları
  - create_candidate() blacklist check + cv.py handling
  - 4 DB fonksiyon + 3 API endpoint
  - get_all_candidates() + get_candidates_count() blacklist filtresi
  - havuzlar: Ban butonu, dialog, kırmızı satır
  - candidates: durum dropdown, badge, kırmızı satır
- ✅ AI Evaluation prompt TAM güncelleme — 16 yeni değişken, Türkçe (3a9f1b6)
- ✅ critical_matched dict→string dönüşüm fix (ad98978)
- ✅ .claudeignore oluşturuldu (0e7c03b)
- ✅ CLAUDE.md güncellendi — puanlama, fazlar, savunma sistemleri (a3308e1)
- ✅ activeContext.md temizliği

### 07.03.2026
- ✅ Görev Tanımı Upload Response Fix (6264245)
- ✅ 100 Puan Sistemi Rescore (2a53de5)
- ✅ Frontend Seniority Score Gösterimi (906cd98)
- ✅ AI Evaluation Prompt Fix (0004039)
- ✅ Dil Seviyesi 2. Katman Savunma (2580726)
- ✅ FAZ D: 110→100 Puan Rebalance (4378a26)
- ✅ [object Object] Render Fix (c3560c5)
- ✅ DB Lock Kalıcı Çözüm (8dfa5e7)
- ✅ Toast X Butonu Fix
- ✅ Duplicate Teknik Beceri Temizlik

### 06.03.2026
- ✅ FAZ B: Görev Tanımı Upload (backend + frontend)
- ✅ FAZ C: Görev Eşleşmesi + 15 Puan Task Kategorisi
- ✅ CV Parser İyileştirmeleri

## Geçmiş Hafta Özeti

| Tarih | Görev Sayısı | Ana Konular |
|-------|--------------|-------------|
| 05.03 | 8 | FAZ A tamamlandı, G1 title threshold |
| 04.03 | 10 | Mülakat sistemi, puanlama |
| 03.03 | 17 | Dashboard, CV, arama |
| 02.03 | 4 | FAZ 10 |
| 01.03 | 11 | FAZ 7-8, keyword lifecycle |
| 28.02 | 6 | FAZ 5-6, security audit |

## Devam Eden / Açık Görevler

### 🟠 ORTA
1. **Generic keyword temizliği** — üç aylık, quarterly gibi terimler

### 🟡 DÜŞÜK
2. **Görev tanımı duplicate uyarısı** — aynı pozisyona 2. yüklemede uyarı

### ⏸️ BEKLEYEN
3. **Görev eşleşmesi karar raporu** — A/B/C seçenek onayı bekliyor
4. **Kariyer Sayfası** — güvenlik taraması sonrası
5. **FAZ 7.6 Data Cleanup** — corrupted keywords, orphaned synonyms

## Tamamlanan Büyük Özellikler

### Pozisyon Sil→Aday Kaybı Fix ✅ (09.03.2026)
- [x] CV Çek sadece durum='yeni' tarıyor (f872d62)
- [x] Pozisyon silinince TÜM adaylar Genel Havuz'a (53d2419)
- [x] Otomatik arşivleme 30→90 gün + eşleşme kontrolü (9f8ca0b)

### Kara Liste Sistemi ✅ (08-09.03.2026)
- [x] Database layer (blacklisted_candidates tablosu)
- [x] Backend API endpoints (routes/candidates.py)
- [x] Frontend UI (havuzlar + candidates)
- [x] Blacklist info kartı + çıkarma modalı (4de9ddb)
- [x] Deploy ve test (sunucuda)

## Sonraki Hedef

### Bekleyen Görevler
1. **Görev Tanımı sekmesi** — Manuel Giriş yerine Görev Tanımı (pozisyon ekleme)
2. **Generic keyword temizliği**
3. **Kariyer Sayfası** (Security taraması önce)

## Notlar

- CLAUDE.md'de tüm kalıcı kurallar mevcut (763 satır, 3-katmanlı mimari eklendi)
- progress.md güncellenmeli (17 gün eski)
- .claudeignore aktif (~2.6 GB filtreleniyor)
