# HyliLabs — Aktif Bağlam

Son güncelleme: 09.03.2026

## Mevcut Sistem Durumu

- **Sunucu:** ***REMOVED*** (PM2 ile çalışıyor)
- **Son commit:** 4de9ddb (09.03.2026)
- **Backend:** FastAPI + SQLite (WAL mode)
- **Frontend:** React + TypeScript + Tailwind
- **Puanlama:** 100 puan sistemi v2.1 aktif

## Aktif Kullanıcılar

- Adnan Bey (İK Direktörü) — test + onay
- 3 şirket, ~50 aday, 5 pozisyon

## Son 72 Saatte Tamamlananlar

### 09.03.2026
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

### 🔴 KRİTİK
1. **Pozisyon sil→ekle aday kaybı** — 5 aday → silip ekle → 2 aday sorunu

### 🟠 ORTA
2. **Generic keyword temizliği** — üç aylık, quarterly gibi terimler

### 🟡 DÜŞÜK
3. **Görev tanımı duplicate uyarısı** — aynı pozisyona 2. yüklemede uyarı

### ⏸️ BEKLEYEN
4. **Görev eşleşmesi karar raporu** — A/B/C seçenek onayı bekliyor
5. **Kariyer Sayfası** — güvenlik taraması sonrası
6. **FAZ 7.6 Data Cleanup** — corrupted keywords, orphaned synonyms

## Tamamlanan Büyük Özellikler

### Kara Liste Sistemi ✅ (08-09.03.2026)
- [x] Database layer (blacklisted_candidates tablosu)
- [x] Backend API endpoints (routes/candidates.py)
- [x] Frontend UI (havuzlar + candidates)
- [x] Blacklist info kartı + çıkarma modalı
- [x] Deploy ve test (sunucuda)

## Notlar

- CLAUDE.md'de tüm kalıcı kurallar mevcut (656 satır)
- progress.md güncellenmeli (17 gün eski)
- .claudeignore aktif (~2.6 GB filtreleniyor)
