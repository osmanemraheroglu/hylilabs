# HyliLabs — Aktif Bağlam

Son güncelleme: 09.03.2026

## Mevcut Sistem Durumu

- **Sunucu:** ***REMOVED*** (PM2 ile çalışıyor)
- **Son commit:** 9f79fe0 (09.03.2026)
- **Backend:** FastAPI + SQLite (WAL mode)
- **Frontend:** React + TypeScript + Tailwind
- **Puanlama:** 100 puan sistemi v2.1 aktif

## Aktif Kullanıcılar

- Adnan Bey (İK Direktörü) — test + onay
- 3 şirket, ~50 aday, 5 pozisyon

## Son 72 Saatte Tamamlananlar

### 09.03.2026
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
