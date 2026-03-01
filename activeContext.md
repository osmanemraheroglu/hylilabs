# HyliLabs — Aktif Baglam
Son guncelleme: 01.03.2026

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

## Kilitli Sistemler — DOKUNULMAZLAR (28 sistem)
1. v2 eslestirme: Fuzzy 70->85, 85->92. Max 1 pozisyon/aday. DEGISMEZ.
2. Scoring v2.1: Dynamic knockout(%50), junior/senior penalti, egitim kademeli. DEGISMEZ.
3. Claude CV parsing: %100 basarili. Parse sistemi bozulmamali.
4. categorize_and_save(): Pozisyon ekleme akisina entegre. DEGISMEZ.
5. Akilli Havuz Onerisi v2: approved_title_mappings tablosu. DEGISMEZ.
6. DB CASCADE DELETE: 16 tablo, 24 FK CASCADE. KALDIRILMAZ.
7. company_id guvenlik katmani: Tum tablolarda. ZORUNLU.
8. CV dosya izolasyonu: /data/cvs/{company_id}/. GERI DONULEMEZ.
9. Firma login kontrolu: verify_user() aktiflik kontrolu. DEGISMEZ.
10. Ayarlar sayfasi: Sadece 3 sekme. KILITLI.
11. Aday Durum Akisi Senkronizasyonu: candidates.durum + pool_assignments birlikte guncellenir.
12. Dashboard Visibility Refresh: fetchDashboardData() + visibilitychange.
13. Genel Havuzdan Silme Engeli: 400 HTTPException + toast.error().
14. Pool Assignments Veri Kurallari: Her durum icin havuz kurali.
15. Pozisyon Havuzu Sorgu Yönlendirmesi: pool_type=="position" → candidate_positions tablosu.

## Son 72 Saatte Tamamlananlar
### 01.03.2026 - FAZ 8.1.7 Reject Stats Rapor Endpoint
- GET /api/synonyms/reject_stats endpoint eklendi
- database.py: get_reject_stats() fonksiyonu eklendi
- Response:
  - reason_distribution: [{reason, label, count, percentage}]
  - source_distribution: [{source, count}]
  - top_rejected_keywords: [{keyword, count}]
  - totals: {rejected, with_reason, no_reason}
- Frontend gösterimi FAZ 8.2'de yapılacak

### 01.03.2026 - FAZ 8.1.4-8.1.6 Reject Dialog ve API
- Backend:
  - GET /api/synonyms/reject_reasons endpoint eklendi (REJECT_REASONS döndürür)
  - POST /api/synonyms/reject güncellendi: reject_reason (zorunlu) + reject_note (opsiyonel)
  - database.py reject_synonyms() güncellendi: reject_reason ve reject_note parametreleri
  - SynonymRejectRequest Pydantic modeli eklendi
- Frontend:
  - RejectDialog komponenti eklendi (Select dropdown + Textarea)
  - loadRejectReasons() API fonksiyonu eklendi
  - openRejectDialog(), closeRejectDialog(), confirmReject() fonksiyonları
  - Dialog: Red sebebi seçimi (7 kategori) + opsiyonel not alanı
- Dosyalar:
  - api/routes/synonyms.py (endpoint + request model)
  - api/database.py (reject_synonyms güncellendi)
  - src/features/synonyms/index.tsx (RejectDialog UI)

### 01.03.2026 - FAZ 8.1.2-8.1.3 DB Kolonları
- keyword_synonyms tablosuna 2 yeni kolon eklendi:
  - reject_reason TEXT: Red kategorisi kodu (REJECT_REASONS key)
  - reject_note TEXT: Opsiyonel açıklama notu
- Yedek: talentflow_backup_faz812_20260301_191648.db
- Sonraki adım: reject endpoint güncelleme + frontend entegrasyonu

### 01.03.2026 - FAZ 8.1.1 REJECT_REASONS Kategorileri
- synonyms.py'ye REJECT_REASONS dict eklendi (satır 46-91)
- 7 red kategorisi tanımlandı:
  - too_general: Çok Genel
  - technically_wrong: Teknik Olarak Yanlış
  - out_of_context: Bağlam Dışı
  - duplicate: Tekrar
  - meaningless: Anlamsız
  - different_concept: Farklı Kavram
  - other: Diğer
- Her kategori için: code, label_tr, label_en, description
- REJECT_REASON_CODES basit liste eklendi
- Sonraki adım: DB'ye reject_reason kolonu, API endpoint, frontend entegrasyonu

### 01.03.2026 - AI Synonym Limit Değişikliği (Max 4 → Max 3)
- filter_ai_synonyms(): len(filtered) >= 4 → >= 3
- SYNONYM_PROMPT_BATCH_V2: MAX 4 → MAX 3
- SYNONYM_PROMPT_SINGLE_V2: MAX 4 → MAX 3
- HR inceleme yükü %25 azaldı
- Commit: 234d56d

### 01.03.2026 - FAZ 7.7 AI Synonym Kalite Sistemi v2
- synonyms.py'ye kalite kontrol sistemi eklendi:
  - SYNONYM_BLACKLIST (57 kelime) - Soft skills, kişilik özellikleri, genel iş terimleri
  - GENERAL_WORDS (25 kelime) - Çok genel kelimeler
  - SYNONYM_PROMPT_BATCH_V2 - Yeni prompt (confidence score, teknik odaklı)
  - SYNONYM_PROMPT_SINGLE_V2 - Yeni prompt (confidence score, teknik odaklı)
  - filter_ai_synonyms() fonksiyonu - AI çıktısını filtreler
- Filtre kuralları:
  - Blacklist kontrolü (soft skills, kişilik özellikleri filtrelenir)
  - General words kontrolü (çok genel terimler filtrelenir)
  - Confidence threshold: 0.7 (altındakiler filtrelenir)
  - Max 4 synonym limiti
  - "variation" tipi kaldırıldı (sadece turkish, english, abbreviation)
- _generate_synonyms_batch_internal() güncellendi:
  - SYNONYM_PROMPT_BATCH_V2 kullanıyor
  - filter_ai_synonyms() çağrısı eklendi
- generate_synonyms() endpoint güncellendi:
  - SYNONYM_PROMPT_SINGLE_V2 kullanıyor
  - filter_ai_synonyms() çağrısı eklendi
  - Tüm öneriler filtrelenirse "kalite filtresinden geçemedi" mesajı
- SONUÇ: AI synonym üretimi artık soft skill ve genel terim üretmiyor

### 01.03.2026 - FAZ 7.6 Data Cleanup (Bozuk Veri Temizliği)
- 15 bozuk keyword silindi (ID 1314-1328, JSON escape hataları)
- 24 rejected synonym silindi
- 1 test keyword synonym silindi (test_keyword)
- 36 değerli keyword eklendi (veri analizi, yazılım geliştirme, machine learning, vs.)
- Yetim synonym sorunu çözüldü (123 → 0)
- Yeni durum: 240 keyword, 286 synonym (212 approved, 74 pending)
- Usage count dağılımı: 213 seed (0), 27 aktif (1)

### 01.03.2026 - FAZ 7.3 Usage Count Sistemi
- database.py'ye 3 fonksiyon eklendi (satır 1130-1287):
  - increment_keyword_usage(keywords, source): usage_count +1, yoksa oluştur
  - decrement_keyword_usage(keywords): usage_count -1 (min 0)
  - get_pool_keywords(pool_id): Pozisyonun keyword listesini döndür
- pools.py save_parsed_position'da increment çağrısı (satır 775-782)
- database.py delete_department_pool'da decrement çağrısı (satır 5098-5105)
- Log: "[save-parsed] USAGE: X güncellendi, Y oluşturuldu"
- Log: "[delete-pool] USAGE: pool_id=X, Y keyword azaltıldı"
- Pozisyon oluşturulunca keyword usage_count +1
- Pozisyon silinince keyword usage_count -1
- usage_count = 0 olan keyword'ler ileride temizlenebilir

### 28.02.2026 - FAZ 7.2 Smart Synonym (AI Skip if Approved)
- database.py'ye get_approved_synonym_count() fonksiyonu eklendi (satır 1093-1127)
  - Keyword için onaylı synonym sayısını döndürür
  - company_id filtresi: firma + global birleşik
  - Exception handling: try/except, 0 döner
- synonyms.py _generate_synonyms_batch_internal() güncellendi:
  - skipped_has_approved = [] scope için erken tanımlama (satır 392)
  - Smart synonym kontrolü: get_approved_synonym_count() çağrısı (satır 407-414)
  - Onaylı synonym varsa AI çağrısı atlanır, keyword keywords_to_process'e eklenmez
  - Tüm return ifadelerine skipped_has_approved alanı eklendi (9 return)
  - Başarılı return mesajına "(X keyword onaylı synonym nedeniyle atlandı)" eklendi
- MALİYET TASARRUFU: Her batch'te mevcut onaylı synonym'ler için Claude API çağrısı yapılmaz
- Response alanları: skipped_has_approved listesi eklendi

### 28.02.2026 - FAZ 7.1 BLACKLIST Keyword Filtresi
- pools.py'ye KEYWORD_BLACKLIST seti eklendi (~57 terim)
- filter_keywords() fonksiyonu eklendi
- save_parsed_position'da filtre uygulandı (satır 767-772)
- Soft skill'ler (iletişim, koordinasyon, takım çalışması, vb.) pozisyonlara EKLENMİYOR
- Teknik terimler (excel, python, autocad, proje, analiz, vb.) KORUNUYOR
- Log: "[save-parsed] BLACKLIST: X keyword filtrelendi, kalan: Y"
- Fonksiyon konumu: satır 77-99

### 28.02.2026 - FAZ 6.4 Frontend Toast Bildirimi (FAZ 6 TAMAMLANDI)
- havuzlar/index.tsx handleSaveParsed fonksiyonu güncellendi
- Backend'den gelen synonym_result toast'ta gösteriliyor
- Başarılı: "X aday eşleştirildi. Y synonym üretildi (onay bekliyor)."
- Optional chaining (?.) ile null safety
- Sonner toast description özelliği kullanıldı
- Fonksiyon konumu: satır 299-309

### 28.02.2026 - FAZ 6.3 Pozisyon Kaydetme Synonym Entegrasyonu
- pools.py save_parsed_position endpoint'ine synonym üretimi eklendi
- Pozisyon kaydedilince keyword'ler için otomatik synonym üretimi
- _generate_synonyms_batch_internal() çağrısı (routes.synonyms import)
- user_id parametresi current_user["id"]'den alınıyor
- Error handling: try/except ile ana fonksiyon korunuyor
- Response'a synonym_result alanı eklendi
- Fonksiyon konumu: satır 735-748

### 28.02.2026 - FAZ 6.2 Batch Synonym Üretim Fonksiyonu
- synonyms.py'ye _generate_synonyms_batch_internal() fonksiyonu eklendi
- Tek Claude API çağrısı ile çoklu keyword işleme
- Rate limit entegrasyonu (check_synonym_batch_generate_limit)
- Error handling ve logging
- Mevcut generate_synonyms endpoint'i KORUNDU
- Fonksiyon konumu: satır 363-610

### 28.02.2026 - FAZ 6.1 Batch Rate Limit
- rate_limiter.py'ye batch synonym üretimi için rate limit eklendi
- SYNONYM_BATCH_GENERATE_MAX = 5 (sabitler)
- SYNONYM_BATCH_GENERATE_WINDOW_MINUTES = 60
- check_synonym_batch_generate_limit(user_id) fonksiyonu
- record_synonym_batch_generate(user_id) fonksiyonu
- Pozisyon oluşturulurken toplu synonym üretimi için limit kontrolü

### 28.02.2026 - FAZ 5 Frontend Synonym Yönetimi
- ADIM 5.1: Route + Sidebar Entegrasyonu
  - src/routes/_authenticated/synonyms/index.tsx (YENİ)
  - src/features/synonyms/index.tsx (YENİ - placeholder)
  - sidebar-data.ts: Languages icon import, synonymlar menu item eklendi
  - company_admin ve user rollerine 'synonymlar' eklendi
  - URL: /synonyms, Menü: "Eş Anlamlılar"
- ADIM 5.2: Ana sayfa iskelet + Tab yapısı (493 satır)
  - 4 Tab: pending, all, generate, manual
  - State'ler: pendingList, synonymList, selectedIds, generateKeyword, manualKeyword, etc.
  - API fonksiyonları placeholder (TODO: sonraki adımlarda)
  - Helper fonksiyonlar: toggleSelect, getStatusBadge, getTypeBadge
  - UI: Tabs, Card, Table, Checkbox, Input, Select, Button, Badge
- ADIM 5.3: Tab 1 - Onay Bekleyenler API implementasyonu
  - loadPendingCount(): GET /api/synonyms/pending/count
  - loadPendingList(): GET /api/synonyms/pending
  - handleApprove(): POST /api/synonyms/approve
  - handleReject(): POST /api/synonyms/reject
  - Toast mesajları Türkçe, error handling, loading state
- ADIM 5.4: Tab 2 - Tüm Eş Anlamlılar API implementasyonu
  - handleSearch(): GET /api/synonyms?keyword={keyword}
    - encodeURIComponent ile Türkçe karakter desteği
    - Boş sonuç için toast.success mesajı
  - handleDelete(): DELETE /api/synonyms/{id}
    - confirm() ile silme onayı
    - Başarılı silme sonrası liste + pendingCount güncelleme
- ADIM 5.5: Tab 3 - AI Üretimi API implementasyonu
  - handleGenerate(): POST /api/synonyms/generate
    - Loading state: setGenerateLoading(true/false)
    - Sonuç gösterimi: setGeneratedSynonyms(synonymTexts)
    - inserted/skipped sayısı ile detaylı mesaj
    - Pending count güncelleme: loadPendingCount()
    - Rate limit hatası yakalama (429)
- ADIM 5.6: Tab 4 - Manuel Ekleme API implementasyonu
  - handleManualAdd(): POST /api/synonyms
    - Loading state: setManualLoading(true/false)
    - Lowercase dönüşüm: keyword ve synonym
    - auto_approve: false (onay beklemeli)
    - Form temizleme: başarı sonrası sıfırla
    - Duplicate/self-reference hata yakalama
    - Pending count güncelleme: loadPendingCount()

### 28.02.2026 - Keyword Synonym Yönetim Sistemi (ADIM 1.1 + 1.2 + 2.1 + 2.2)
- AMAÇ: AI + İK onay sistemli synonym yönetimi için altyapı
- ADIM 1.1: keyword_synonyms tablosu oluşturuldu (database.py:678-703)
  - 11 kolon: id, company_id, keyword, synonym, synonym_type, source, status, created_by, approved_by, created_at, approved_at
  - 4 index: company, keyword, status, lookup (composite)
  - UNIQUE(company_id, keyword, synonym) constraint
  - source: 'ai'/'manual'/'migrated', status: 'pending'/'approved'/'rejected'
- ADIM 1.2: KEYWORD_SYNONYMS dict migration (database.py:705-789)
  - _migrate_keyword_synonyms(cursor) fonksiyonu eklendi
  - detect_synonym_type() iç fonksiyonu: turkish/english/abbreviation/variation
  - 81 keyword, ~193 synonym (self-reference hariç) migrate edilecek
  - source='migrated', status='approved', company_id=NULL (global)
  - Idempotent: Zaten migrate edilmişse tekrar çalışmaz
- ADIM 2.1: get_synonyms_for_keyword() fonksiyonu (database.py:1034-1093)
  - İmza: get_synonyms_for_keyword(keyword: str, company_id: int = None) -> list[str]
  - Status filtresi: sadece 'approved'
  - Company_id filtresi: firma + global birleşik
  - Self-reference kontrolü: keyword != synonym
  - Exception handling: try/except, boş liste döner
- ADIM 2.2: 9 CRUD fonksiyonu eklendi (database.py:1096-1570)
  - save_generated_synonyms() - AI synonym kaydet (1096-1162)
  - get_pending_synonyms() - Onay bekleyenleri listele (1165-1210)
  - get_pending_synonyms_count() - Pending sayısı badge (1213-1245)
  - approve_synonyms() - Toplu onay (1248-1303)
  - reject_synonyms() - Toplu red (1306-1355)
  - add_manual_synonym() - İK manuel ekle (1358-1413)
  - delete_synonym() - Synonym sil (1416-1460)
  - get_keyword_synonyms() - Keyword synonym listesi (1463-1519)
  - check_synonym_exists() - Duplicate kontrolü (1522-1570)
  - Tüm fonksiyonlarda: turkish_lower(), logger, try/except, company_id güvenliği
- SONRAKI: candidate_matcher.py entegrasyonu ve cache

### 27.02.2026 - CV Çek Batch İşleme (Bellek Optimizasyonu)
- AMAÇ: 1000+ aday için bellek sorununu önle
- database.py: pull_matching_candidates_to_position fonksiyonuna batch işleme eklendi
  - BATCH_SIZE = 100 (her seferde 100 aday işlenir)
  - Eski: fetchall() ile TÜM adaylar belleğe (O(n) bellek)
  - Yeni: LIMIT/OFFSET ile parça parça (O(100) sabit bellek)
  - stats['batches_processed'] eklendi
  - Her 5 batch'te ilerleme logu
- AKIŞ: COUNT → WHILE (LIMIT/OFFSET) → SIRALA → LİMİTLE → INSERT
- Mevcut skor hesaplama kodu (scoring_v2) korundu

### 27.02.2026 - Pozisyon Eşleşme Limiti (CV Çek)
- AMAÇ: CV Çek yapıldığında en yüksek skorlu TOP N aday gelsin
- database.py: pull_matching_candidates_to_position fonksiyonu refactor edildi
  - limit parametresi eklendi (varsayılan 50, -1 = sınırsız)
  - Adaylar önce toplanıyor, sonra match_score'a göre sıralanıyor (DESC)
  - Limit uygulanıp sadece TOP N aday ekleniyor
  - stats['limit_applied'] response'a eklendi
- pools.py: pull-candidates endpoint'ine limit Query parametresi eklendi
  - Query(default=50, ge=1, le=500)
  - Response mesajına limit bilgisi eklendi
- Diğer çağrı noktaları (save-parsed, approve-titles) varsayılan 50 kullanıyor

### 27.02.2026 - AI Günlük Kullanım Limiti (Plan Bazlı)
- AMAÇ: Maliyet kontrolü için plan bazlı günlük AI limiti
- DB: plans tablosuna daily_ai_limit kolonu eklendi
  - trial: 10, starter: 50, professional: 200, enterprise: -1 (sınırsız)
- database.py: 3 yeni fonksiyon eklendi
  - get_company_daily_ai_limit() → Plan bazlı limit
  - get_daily_ai_usage() → Bugünkü kullanım sayısı
  - check_ai_daily_limit() → Limit kontrolü (izin, mesaj, kalan)
- pools.py: evaluate_candidate'de limit kontrolü
  - Cache kontrolünden SONRA, API çağrısından ÖNCE
  - Limit aşıldığında 429 + Türkçe hata mesajı

### 27.02.2026 - Login ve CV Upload Rate Limit Aktivasyonu
- AMAÇ: Brute force saldırıları ve spam koruması
- FIX 1: auth.py login endpoint rate limit eklendi
  - check_login_limit() → 5 deneme / 15 dakika
  - Başarısız giriş → record_login_attempt()
  - Başarılı giriş → clear_login_attempts()
  - 429 status code ile Türkçe hata mesajı
- FIX 2: cv.py upload endpoint rate limit eklendi
  - check_cv_upload_limit() → 20 dosya / saat
  - Başarılı upload → record_cv_upload()
  - 429 status code ile Türkçe hata mesajı
- rate_limiter.py fonksiyonları aktifleştirildi

### 27.02.2026 - AI Değerlendirme Tekrar Kontrolü
- SORUN: evaluate_candidate her çağrıda Claude API kullanıyordu (maliyet + gereksiz)
- ÇÖZÜM: Mevcut değerlendirme kontrolü eklendi - her aday+pozisyon için sadece 1 kere AI çağrılır
- FIX: pools.py evaluate_candidate endpoint'ine get_ai_evaluation() kontrolü eklendi
  - Mevcut değerlendirme varsa → cache'den döndürülür (API çağrısı yapılmaz)
  - Response'a "cached": true ekleniyor (frontend'de cache göstergesi olabilir)
- BEKLİYOR: ai_evaluations tablosuna UNIQUE INDEX (sunucu bağlantısı sonrası)
  - CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_eval_candidate_position ON ai_evaluations(candidate_id, position_id)

### 27.02.2026 - Manuel Aday Ata Sistemik Tutarlılık Fix
- BUG: Manuel "Aday Ata" sadece candidate_positions INSERT yapıyordu
- SORUN: candidates.durum ve havuz güncellenmiyordu, Genel Havuz kaydı silinmiyordu
- ETKİ: Dashboard ve Adaylar sayfasında tutarsız veriler
- FIX: add_candidate_to_position fonksiyonu tamamlandı:
  1. candidates.durum = "pozisyona_atandi" UPDATE
  2. candidates.havuz = "pozisyona_aktarilan" UPDATE
  3. Genel Havuz DELETE
  4. Arşiv DELETE
  5. matches INSERT (manuel_atama notu ile)
- CLAUDE.md Pool Assignments kurallarına uygun hale getirildi
- Commit: 6596f6b

### 26.02.2026 - Bug Fix: v2_result UnboundLocalError
- Sorun: PM2 PYTHONPATH eksik → candidate_matcher import hata → v2_result tanımsız → 500 Error
- Kısa vadeli fix: database.py except bloğuna v2_result = None eklendi
- Uzun vadeli fix: scoring_v2.py, email_worker.py, workflows.py import guard eklendi
- CLAUDE.md: 3 yeni kural eklendi (19, 20, 21) 
- PM2: delete+start ile PYTHONPATH yüklendi
- Etkilenen: Tüm yeni pozisyonlara aday atanamıyordu (Position 7782 dahil)
- Çözüm: Kapsamlı fix uygulandı, test edildi

### 25.02.2026 - Puanlama Duzeltmesi (7 Adim)
- ADIM 1: UNIQUE constraint (idx_matches_candidate_position)
- ADIM 2: matches v2_result kayit (42cf5b0)
- ADIM 3: KEYWORD_SYNONYMS 40 key (af6edc2)
- ADIM 4: Migration 13 aday rescore
- ADIM 5: ai_evaluations 7 kayit
- ADIM 6: Yeniden Hesapla butonu (cc2a339)
- ADIM 7: Dokumantasyon
Sonuc: Serkan 14→41, matches 0→13, TR↔EN calisiyor
- ADIM 6: Yeniden Hesapla Butonu:
  - Backend: POST /{pool_id}/candidates/{candidate_id}/rescore endpoint (pools.py satır 1253)
  - calculate_match_score_v2 kullanarak v2 skorunu yeniden hesaplar
  - candidate_positions.match_score, matches.uyum_puani, ai_evaluations.v2_score güncellenir
  - Frontend: rescoring state (satır 115), handleRescore fonksiyonu (satır 443)
  - RefreshCw butonu mavi renkte (satır 725)
  - Commit: cc2a339
- ADIM 5: ai_evaluations.v2_score Migration:
  - 10 kayıt analiz edildi, hepsi v2_score=0
  - Root cause: Kayıtlar ADIM 4 migration'dan önce oluşturulmuş
  - UPDATE ile matches.uyum_puani ai_evaluations.v2_score'a kopyalandı
  - 7 kayıt güncellendi, 3 orphan kayıt (matches kaydı yok) 0 kaldı
  - Serkan'ın v2_score: 41 (doğrulandı)
- KEYWORD_SYNONYMS TR↔EN Genişletme (ADIM 3):
  - candidate_matcher.py'de 40 yeni synonym eklendi (toplam 78 key)
  - Bakım/Onarım: bakım-onarım, önleyici bakım, periyodik bakım, arıza takibi
  - Makina/Ekipman: iş makineleri, ekipman yönetimi, makine mühendisliği
  - Yönetim: koordinasyon, planlama, takım çalışması, takım liderliği
  - Kalite/Güvenlik: kalite kontrol, kalite güvence, iş güvenliği
  - Finans: maliyet analizi, satın alma, stok yönetimi
  - Çift yönlü EN→TR: maintenance, heavy equipment, troubleshooting, teamwork
- Matches Tablosu v2 Skorlama Fix (2 ADIM):
  - ADIM 1: matches tablosuna UNIQUE(candidate_id, position_id) constraint eklendi
  - ADIM 2: pull_matching_candidates_to_position fonksiyonuna matches INSERT eklendi
  - v2_result JSON olarak detayli_analiz kolonuna kaydediliyor
  - UI/Rapor artık gerçek v2 skorları gösterecek (0 yerine)
  - Korunan sistemlere dokunulmadı (scoring_v2.py, eval_report_v2.py, pools.py)
- Havuz Pydantic Model Fix:
  - models.py satır 46: havuz: str → havuz: Optional[str] = "genel_havuz"
  - ise_alindi adaylar (havuz=NULL) artık Pydantic hatasına yol açmaz
  - Adaylar sayfası artık düzgün açılıyor
- CV Topla İstatistik Düzeltmeleri:
  - database.py get_email_collection_stats(): toplam_cv ve toplam_basarili artık candidates tablosundan
  - cv_parser.py get_cv_storage_stats(): company_id parametresi + rglob ile recursive dosya sayma
  - cv.py /stats endpoint: get_cv_storage_stats(company_id=company_id) çağrısı
  - Önceki değerler: toplam_cv=331, storage.count=2 (yanlış)
  - Yeni değerler: toplam_cv=56, storage.count=59 (doğru)
  - 36 yetim log kaydı silindi (company_id=NULL)
- Havuz Tutarlılığı Fix (5 parça):
  - PARÇA A: Veri temizliği - 3 aday düzeltildi (395, 428, 431)
  - PARÇA B: candidates.py ise_al endpoint - havuz=NULL eklendi
  - PARÇA C: interviews.py mülakat iptal - candidate_positions kontrolü + ise_alindi/arsiv koruması
  - PARÇA D: interviews.py mülakat silme - candidate_positions kontrolü + ise_alindi/arsiv koruması
  - PARÇA E: CLAUDE.md güncellendi - Mülakat-Aday Durum Senkronizasyonu kuralı genişletildi
- Türkçe Hata Mesajları Fix (59 mesaj, 9 dosya):
  - PARÇA A: pools.py UNIQUE constraint yakalama (409 hatası)
  - PARÇA A: approved_title_mappings INSERT OR IGNORE (race condition önlemi)
  - PARÇA B: admin.py, auth.py, candidates.py, companies.py, cv.py düzeltildi
  - PARÇA B: emails.py, interviews.py, pools.py, database.py düzeltildi
  - bulunamadı, güncellendi, oluşturuldu, kullanılıyor, başarıyla vb. düzeltildi
- Durum Downgrade Koruması (3 Katmanlı Savunma):
  - FIX 1A/1B: SELECT filtreleri (ise_alindi/arsiv hariç)
  - FIX 2A/2B: INSERT öncesi durum kontrolü
  - FIX 3: UPDATE güvenliği
- "Pozisyon" sütun başlığı "CV'de Belirtilen Unvan" olarak güncellendi:
  - candidates/index.tsx satır 266: Tablo başlığı
  - candidates/index.tsx satır 350: Detay görünümü label
  - havuzlar/index.tsx satır 674: Tablo başlığı
- Dashboard widget başlığı güncellendi:
  - "Son Email Başvuruları" → "Son Eklenen Adaylar"
  - "Email ile gelen son başvurular" → "Son eklenen adaylar"
- FIX 7: Application kaydı oluşturma düzeltildi
  - cv.py upload endpoint: create_application() eklendi (kaynak: cv_yukleme)
  - cv.py scan-emails endpoint: create_application() eklendi (kaynak: email)
  - Duplicate kontrolü her iki endpoint'te de eklendi
  - database.py get_recent_applications(): candidates tablosundan çekiyor (applications değil)
  - Dashboard "Son Başvurular" widget'ı artık tüm yeni adayları gösteriyor

### 24.02.2026
- 6 BUG FIX: Dashboard istatistikleri ve aday filtreleme düzeltildi
  - FIX 1: Bugün Başvuru → candidates.olusturma_tarihi (applications değil)
  - FIX 2: Bu Ay İşe Alınan → candidates.durum + guncelleme_tarihi
  - FIX 3: Toplam Aday → durum != 'ise_alindi' hariç tutuluyor
  - FIX 4: Pozisyona atama → Genel Havuz'dan otomatik DELETE
  - FIX 5: Departman filtresi → candidate_positions tablosu kullanıyor
  - FIX 6: Pozisyon filtresi → candidate_positions tablosu kullanıyor
- DB Cleanup: 4 aday Genel Havuz'dan silindi (399, 406, 412, 417) - pozisyona atanmış ama Genel Havuz'da kalmışlardı
- CLAUDE.md: Kural 12 güncellendi (candidate_positions tablosu), Pool Assignments kuralı güncellendi
- CLAUDE.md: Kritik kural eklendi — Mevcut çalışan sistemleri bozma
  - interviews.py, pools.py, eval_report_v2.py KİLİTLİ
  - Yeni özellik eklerken mevcut fonksiyonlara dokunma kuralı
- interviews.py: Mülakat formu aday dropdown düzeltildi (551 satır)
  - dropdown-data endpoint yanlış tablo sorguluyordu
  - candidate_pool_assignments → candidate_positions tablosuna düzeltildi
  - cp.status = 'aktif' filtresi eklendi
  - Pozisyon seçilince adaylar artık görünüyor
- eval_report_v2.py: Radar SVG tam label'lar (v10 - 351 satır)
  - "Poz"→"Pozisyon", "Tek"→"Teknik", "Den"→"Deneyim", "Eği"→"Eğitim", "Ele"→"Eleme"
  - font-size="7" küçültüldü (sığması için)
  - Label pozisyonları radar dışına taşındı (y=8, y=52, y=185)
- eval_report_v2.py: Kompakt yan yana layout (v9 - 351 satır)
  - Radar ve progress bar'lar tekrar YAN YANA (flex-direction: row)
  - Radar: 120px genişlik, SVG viewBox 200x200, display 120x120
  - Progress bar: label 55px, score 30px - kompakt
  - Skor ve verdict radar altında (radar-box içinde)
  - .rpt container'da overflow:hidden KALDIRILDI
  - 1 A4 sayfaya sığan kompakt layout
- eval_report_v2.py: Radar ve bar ALT ALTA layout (v8 - 358 satır)
  - .top: flex-direction:column - radar üstte, bar'lar altta
  - .scores-box: width:100% - full genişlik
  - Radar 160x160, ortalanmış
  - Progress bar'lar kesilmeden tam görünüyor
- eval_report_v2.py: Radar ve progress bar düzeltmesi (v7 - 358 satır)
  - Radar chart: 140x140 → 180x180 (daha büyük, okunabilir)
  - Progress bar label: width:60px, skor: width:34px
  - "PUAN DAĞILIMI" başlığı kaldırıldı (sadece bar'lar)
  - Tam label'lar: Pozisyon, Teknik, Deneyim, Eğitim, Eleme
  - .scores-box'a min-width:0 eklendi
- eval_report_v2.py: 2 kozmetik bug düzeltildi (v6 - 360 satır)
  - BUG 1: Progress bar tek satır flex layout (label + bar + skor yan yana)
  - BUG 2: Radar SVG "Tek" → "Teknik" tam yazıldı, x="135" text-anchor="end"
- eval_report_v2.py: Metin kesme sorunu düzeltildi (v5 - 361 satır)
  - Python slice kaldırıldı: item[:55] → {item}, item[:18] → {item}
  - Güçlü yönler ve eksiklikler listelerinde tam metin gösteriliyor
- eval_report_v2.py: 2 son bug düzeltildi (v4 - 361 satır)
  - BUG 1: overflow:hidden metin container'larından kaldırıldı, sadece .rpt ve .radar-box'ta
  - BUG 2: Progress bar görünür - background:#e8e8ec;border-radius:3px;height:5px;
  - Tüm metin alanlarında: word-break:break-word; overflow-wrap:break-word;
- eval_report_v2.py: TAMAMEN yeniden yazıldı (v3 - 358 satır)
  - Layout: .top flex row - radar (140px) + progress bar'lar yan yana
  - CSS: max-width 800px, font-size 0.65-0.7rem, padding max 10px
  - Progress bar height: 5px
  - Tüm container: overflow:hidden; word-break:break-word;
  - Kaldırılan: "Puan Dağılımı" ayrı kart, "Detaylar" kartı
  - Parser: 'zayıf' → eksik, 'öneri' → alternatif eklendi
  - Genel değerlendirme max 320 karakter
- eval_report_v2.py: 3 yeni bug düzeltildi (v2)
  - Bug 1: ** markdown temizleme - line.replace('**', '').strip()
  - Bug 2: Header tespiti 3 koşul - liste öğesi değil + <50 karakter + : ile biter
  - Bug 3: Overflow fix - .left-col, .right-col, .card, .tags-section, .ai-text overflow:hidden
- _parse_ai_sections() fonksiyonu ayrı fonksiyon olarak eklendi (test edilebilir)
- eval_report_v2.py: 3 bug düzeltildi (v1)
  - Bug 1: CSS overflow fix - word-break:break-word 13 yerde eklendi
  - Bug 2: Genel Değerlendirme parse fix - 'degerlendirme' (g ile) kontrol
  - Bug 3: Eksik yetkinlik tag'leri - AI metninden parantez içi beceri ayıklama
- extract_skills_from_text() fonksiyonu eklendi (regex ile parantez parse)
- eval_report_v2.py: Modern infographic tasarımlı AI değerlendirme raporu oluşturuldu
- SVG radar chart (5 boyut), progress bar'lar, verdict card'lar, yetkinlik tag'leri
- pools.py: eval_report_v2 import edildi, yeni rapor aktif
- CLAUDE.md: Sistem #28 kilitlendi - Pozisyon Havuzu Sorgu Yönlendirmesi

### 23.02.2026
- BUG FIX: Pozisyon havuzlarinda aday gorunmuyordu (0 aday) - pools.py route'a pool_type kontrol eklendi
- get_position_candidates() fonksiyonu guncellendi: c.* donuyor, frontend ile uyumlu
- candidate_positions tablosu pozisyonlar icin kullaniliyor (candidate_pool_assignments degil)
- CLAUDE.md: 4 yeni sistem kilitlendi (#24-27) - Durum senkronizasyonu, dashboard refresh, pool kurallari
- Genel Havuz'dan silme icin kullanici dostu toast mesaji (havuzlar frontend)
- COMMIT D: havuzdan silme durum guncelleme + dashboard visibility refresh
- COMMIT C: ise-al endpoint pool_assignments temizleme eklendi + DB fix (ID:434)
- COMMIT B: elen endpoint pool_assignments senkronizasyonu eklendi
- COMMIT A FIX: Duplicate pool assignments duzeltildi (430,431 Genel Havuz'dan silindi, sadece Arsiv'de)
- COMMIT A: 2 yetim aday (411,423) Genel Havuz'a eklendi (candidate_pool_assignments: 51->53->51)
- dashboard.py labels'a "yeni" eklendi (pie chart icin)
- 3 arsivli aday (430,431,432) Arsiv havuzuna eklendi (candidate_pool_assignments)
- arsivle endpoint duzeltildi: candidate_pool_assignments'a Arsiv havuzu atamasi eklendi
- Mevcut arsivli aday (ID=432) Arsiv havuzuna eklendi
- Havuzlar frontend cift sayim duzeltildi: totalCandidates artik backend'den geliyor
- TreeData interface'e total_candidates eklendi
- totalCandidates hesaplamasi basitlestirildi (tree?.total_candidates || 0)
- Backend /api/pools/hierarchical endpoint'ine total_candidates eklendi
- window.alert() kaldirildi, sonner toast bildirimleri eklendi (3 dosya, 33 alert)
- email-hesaplari, firma-yonetimi, havuzlar sayfalarinda toast.success/error kullaniliyor
- PYTHONPATH fix: ecosystem.config.cjs'e core/ path eklendi
- candidate_matcher ve cv_parser import hatalari cozuldu
- v2 scoring artik duzgun calisiyor (fallback'e dusmuyor)
- Auth yonlendirme duzeltildi: token yoksa /sign-in'e yonlendir
- /api/auth/me endpoint'i: aktif=0 kullanici -> 401, aktif=0 firma -> 403
- Login endpoint'i: pasif kullanici/firma icin ozel hata mesajlari
- Frontend initAuth(): 401/403 durumunda token silip /sign-in'e yonlendiriyor
- Token varken /sign-in'e gelince /'e (dashboard) yonlendiriyor
- Firma Yonetimi: Aktif/Pasif toggle ve Kalici Silme ayrildi
- PATCH /api/companies/{id}/toggle-status: aktif<->pasif toggle
- DELETE /api/companies/{id}: Kalici silme (hard delete) - tum veriler silinir
- hard_delete_company(): 10 tablo sirayla siliniyor (candidates, users, interviews, vs.)
- Silme onay dialogu: "Bu islem GERI ALINAMAZ" uyarisi
- URL Parse frontend duzeltildi: res.basarili -> res.success, res.pozisyon_adi -> res.data.pozisyon_adi
- save-parsed endpoint detayli loglama eklendi (debug icin)
- save-parsed endpoint test edildi: calisiyor (pool olusturma, categorize_and_save, pull_matching)
- URL Parse sonuc render crash duzeltildi: SelectItem value="" -> value="none" (3 yer)
- Select value guard eklendi: value={x || "none"} + onValueChange none->empty string ceviri
- KRITIK BUG FIX: Eslestirme calismiyordu - approve_titles sadece position_title_mappings guncelliyordu
- approved_title_mappings senkronizasyonu eklendi (pools.py approve_titles endpoint)

### 22.02.2026
- Mulakat olusturulunca aday durumu otomatik 'mulakat' olarak guncelleniyor
- Mulakat iptal edilince baska aktif mulakat yoksa aday durumu 'pozisyona_atandi' olarak geri aliniyor
- Mulakat silinince baska aktif mulakat yoksa aday durumu 'pozisyona_atandi' olarak geri aliniyor
- Dashboard "Mulakat Bekleyen" ve Takvim "Planlanmis" senkronizasyonu saglandi
- Dashboard "Bekleyen" karti duzeltildi: position_pools.durum='beklemede' -> candidates.durum='yeni'
- Plan dropdown kaldirildi (firma-yonetimi sayfasindan)
- CV yuklemede max_aday limiti kontrolu eklendi (403 hatasi donuyor)
- CV Topla sayfasinda aday limiti gostergesi eklendi (X / Y Aday + progress bar)
- /api/companies/me endpoint'i eklendi (kullanicinin firmasini getir)
- create_company() eksik parametreler eklendi (yetkili_adi, yetkili_email, yetkili_telefon, max_kullanici, max_aday)
- Firma olusturulunca yetkili emaile otomatik kullanici hesabi ve sifre emaili gonderiliyor
- Firma kullanici olusturma kolon adi duzeltildi (sifre -> password_hash)
- Firma silme fonksiyonu duzeltildi (durum kolonu yok, rowcount fix)
- Login sayfasi HyliLabs markasi ve Turkce (Shadcn Admin -> HyliLabs, Sign in -> Giris Yap)
- Teams dropdown kaldirildi (sol ust logo artik tiklanabilir degil)
- Sidebar "Firma Yonetimi" -> "Firma Yönetimi" Turkce duzeltme
- Dashboard "Mulakat Bekleyen" -> "Mülakat Bekleyen" Turkce duzeltme

### 20.02.2026
- pm2 kurulumu ve yapilandirilmasi (ecosystem.config.cjs)
- systemd -> pm2 gecisi (frontend + backend)
- DEPLOYMENT.md olusturuldu (yeni sunucu rehberi)
- Mulakat Takvimi pozisyon dropdown duzeltildi (positions -> department_pools)
- Mulakat Takvimi Turkce karakter duzeltmeleri (20+ kelime)
- Mulakat Takvimi tarih formati GG.AA.YYYY (toLocaleDateString tr-TR)
- Mulakat Form sirasi degistirildi: Pozisyon (opsiyonel) -> Aday (zorunlu)
- Mulakat Form pozisyon secilince aday filtreleme (positionCandidates)
- Mulakat Form pozisyonsuz aday uyarisi eklendi
- Mulakat Form SelectItem value="" crash duzeltildi (value="none")
- Mulakat Form tarih input placeholder="GG.AA.YYYY" eklendi
- Mulakat olusturulunca adaya email gonderme ozelligi eklendi
- Mulakat email onizleme akisi eklendi (Kaydet -> Onizle -> Gonder)
- Backend: email-preview ve send-email endpointleri (/api/interviews/{id}/email-preview, /api/interviews/{id}/send-email)
- email_sender.py: generate_interview_invite_content helper fonksiyonu eklendi
- Frontend: Email onizleme dialog'u (duzenlenebilir alici email, konu/icerik onizleme)
- Email preview dialog DOM crash fix (setTimeout 150ms delay between dialogs)
- Email preview dialog state fix (reorder state updates, loadInterviews en sona alindi)
- Email gonderimi: veritabani hesabi kullanimi (email_accounts tablosu, varsayilan_gonderim=1)
- send_interview_invite() account parametresi eklendi
- Mulakat onaylama linki sistemi: token uretimi, public /confirm/{token} endpoint, email'de onay linki
- Mulakat formu onay suresi secimi eklendi (1/3/7/14/30 gun, varsayilan 3)

### 21.02.2026
- Mulakat formu onay suresi Select alani eklendi (frontend)
- Backend: onay_suresi parametresi aliniyor, token suresi dinamik
- Email taslagi dinamik onay_suresi kullanimi (hardcoded 7 gun -> parametrik)
- Email icerik Turkce karakter duzeltmeleri (25+ kelime)
- Email tarih formati Turkce (22 Subat 2026)
- NOTLAR bolumu kosullu (not yoksa gizle)
- Sirket adi dinamik (companies tablosundan)
- Otomatik hatirlatma email sistemi (APScheduler)
- scheduler.py: send_reminder_emails() her gun 09:00
- is_reminder parametresi eklendi (email konu + icerik farkli)
- interviews tablosuna onay_suresi kolonu eklendi
- Email sender_name dinamik: sirket_adi > account.sender_name > 'HyliLabs'
- Mulakat takvimi onay durumu badge (confirmed/pending)
- Onay durumu filtre dropdown eklendi
- Stats kart sayisi 4->5 (Onaylandi eklendi)
- Email UTF-8 encoding fix (Header + formataddr)
- Keyword Istatistikleri menuden kaldirildi
- Dashboard Eksik Beceriler widget'i kaldirildi (veri altyapisi hazir degil)
- Profil dropdown: Faturalama ve Yeni Takim secenekleri kaldirildi
- Profil dropdown: Turkce ceviri (Profile->Profil, Settings->Ayarlar, Sign out->Oturumu Kapat)
- Frontend Turkce karakter duzeltmeleri (9 dosya, 150+ kelime):
  - settings/password/index.tsx: Sifre -> Şifre, vs.
  - settings/theme/index.tsx: Acik -> Açık, Guncelle -> Güncelle
  - settings/index.tsx: Gelismis -> Gelişmiş
  - user-management/index.tsx: Kullanici -> Kullanıcı, Sifre -> Şifre, vs.
  - havuzlar/index.tsx: Duzenle -> Düzenle, Iptal -> İptal, Egitim -> Eğitim, vs.
  - admin-panel/index.tsx: Istatistikler -> İstatistikler, Kullanici -> Kullanıcı
  - firma-yonetimi/index.tsx: Firma Yonetimi -> Yönetimi, Olustur -> Oluştur
  - email-hesaplari/index.tsx: Gonderim -> Gönderim, Saglayici -> Sağlayıcı
  - dashboard/index.tsx: once -> önce, bakis -> bakış
- Ek Turkce karakter duzeltmeleri (4 dosya, 40+ duzeltme):
  - dashboard/index.tsx: Bugün, Başvuru, Değerlendirme, Dağılımı, göre, etc.
  - candidates/index.tsx: önce, yıl, Değerlendirmede, Mülakat, Arşiv, Yükleme, Şirket, Eğitim, etc.
  - settings-page/index.tsx: Firma Adı, Kullanıcı, Günlük, Bağlantı hatası, görüntülemek için, etc.
  - havuzlar/index.tsx: Mülakat, dosyaları, başarıyla, tamamlandı, yıl, yüklenemedi, Henüz, başlık, etc.
- cv-collect/index.tsx Turkce karakter duzeltmeleri (30+ duzeltme):
  - Manuel Yükle, CV Yükle, Başarılı, Başarı Oranı, Toplama Geçmişi
  - seçmek için tıklayın, sürükleyin, dosyaları desteklenir
  - hesabı bulunamadı, Hesapları sayfasından, Hesabı Seçimi
  - Klasör Seçimi, klasörleri yükleyin, Klasörleri Yükle, yüklenmedi
  - Tarama Ayarları, okunmamış, işlenir, Taranıyor, işlemini başlatın
- sidebar-data.ts Turkce karakter duzeltmeleri:
  - Mülakat Takvimi, Email Hesapları, Kullanıcı Yönetimi
- cv-collect/index.tsx durum badge Turkce etiketler:
  - getDurumLabel() fonksiyonu eklendi
  - tamamlandi->Tamamlandı, basarili->Başarılı, kismi_basarili->Kısmi Başarılı, basarisiz->Başarısız, devam_ediyor->Devam Ediyor
- dashboard/index.tsx pie chart Turkce etiketler:
  - DURUM_LABELS map eklendi
  - yeni->Yeni, pozisyona_atandi->Pozisyona Atandı, mulakatta->Mülakata Çağrıldı, arsiv->Arşiv, reddedildi->Reddedildi, ise_alindi->İşe Alındı
- havuzlar/index.tsx kalan Turkce duzeltmeleri:
  - havuzlarini -> havuzlarını, Arsiv -> Arşiv

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
- interviews tablosu CASCADE DELETE eklendi (3 FK)
- create_interview() company_id guvenlik eklendi
- create_application() SQL hatasi duzeltildi (5 kolon 6 placeholder -> 6/6) + company_id
- transfer_candidates_to_position() company_id eklendi (candidate'dan turetiliyor)
- 9 tabloya CASCADE DELETE eklendi (ai_analyses, hr_evaluations, position_requirements, position_sector_preferences, position_title_mappings, candidate_merge_logs, company_settings, email_accounts, email_templates)
- audit_logs INSERT'e company_id eklendi
- email_templates 56.544 duplike kayit silindi (56.550 -> 6)
- email_templates UNIQUE(company_id, sablon_kodu) constraint eklendi
- email_templates INSERT OR IGNORE company_id=1 olarak duzeltildi

## Son Commitler
2eb11a9 - perf: CV Çek batch işleme eklendi (bellek optimizasyonu)
4b16983 - feat: Pozisyon eşleşme limiti eklendi (varsayılan 50, skor sıralı)
abd3f05 - feat: AI günlük kullanım limiti eklendi (plan bazlı)
3683ce5 - feat: Login ve CV upload rate limit aktifleştirildi
b4bcafd - feat: AI değerlendirme tekrar kontrolü - mevcut değerlendirme cache sistemi
8cdb600 - refactor: havuzlar UI temizliği - gereksiz butonlar kaldırıldı + aday ata pool_type fix
cc2a339 - feat: Yeniden Hesapla butonu - ADIM 6 (pools.py rescore endpoint + frontend RefreshCw button)
8394118 - fix: havuz alanı Optional yapıldı - ise_alindi adaylar için NULL kabul eder
df118eb - fix: CV Topla istatistik düzeltmeleri - gerçek aday sayıları ve dosya istatistikleri
1a41071 - fix: havuz tutarlılığı - veri temizliği + ise_al havuz=NULL + mülakat iptal/silme mantık düzeltmesi
70fa8b2 - fix: Türkçe karakter düzeltme (59 mesaj) + UNIQUE constraint yakalama (pools.py)
7a6d7e9 - fix: durum downgrade koruması - ise_alindi/arsiv adaylar 3 katmanlı savunma
6c4410b - fix: havuzlar frontend cift sayim duzeltildi - totalCandidates artik backendden geliyor
9d28dd0 - ui: window.alert kaldirildi, toast bildirimleri eklendi
c56a09c - fix: PYTHONPATH core/ eklendi - candidate_matcher ve cv_parser import sorunu cozuldu
e0a669f - fix: eslestirme calismiyordu - approved_title_mappings senkronizasyonu eklendi
e32c1a4 - fix: URL parse sonuc render SelectItem value crash duzeltildi
fec1e45 - debug: save-parsed endpoint detayli loglama
275682b - fix: URL parse frontend response handling duzeltmesi
52b7a7f - security: IDOR duzeltmesi, audit log, mulakat izolasyon dogrulama
df4b16c - docs: security sistemi CLAUDE.md kilitlendi
aab1e57 - security: JWT secret zorunlu, rate limiting public endpoint hazirlik
b5c8dfa - fix: auth yonlendirme duzeltmesi - pasif kullanici ve route guard
84967de - fix: teams dropdown kaldirildi, menu ve dashboard Turkce duzeltme
7d4126d - fix: login sayfasi HyliLabs markasi ve Turkce duzeltmesi
cf31959 - fix: firma email gonderi ve silme hatasi duzeltildi
14a2aef - feat: firma olusturulunca yetkili email otomatik kullanici ve sifre emaili
875bea8 - fix: create_company() eksik parametreler eklendi
a149447 - feat: plan dropdown kaldirildi, max_aday limiti ve gosterge eklendi
525a132 - fix: dashboard bekleyen karti - yanlis tablo duzeltildi, candidates.durum=yeni
7480780 - fix: mulakat olusturulunca aday durumu guncelleniyor + update activeContext
4c185c2 - fix: frontend turkce karakter duzeltmeleri - ek dosyalar (4 dosya, 40+)
1fe9af5 - fix: settings/advanced Turkce karakter duzeltmesi - sadece UI metinleri
577ef45 - fix: frontend turkce karakter duzeltmeleri (9 dosya)
c9dfa57 - feat: keyword sayfasi menuden kaldirildi, eksik beceriler dashboard widget
dbbbe75 - feat: takvimde onaylandi badge ve filtre
951abf2 - feat: email sender_name dinamik sirket adi destegi
4928766 - feat: mulakat onaylama linki - token sistemi ve public endpoint
536e950 - fix: email gonderiminde veritabani hesabini kullan (email/sifre kolonlari)
2cbf52b - fix: email preview dialog state fix - reorder state updates and API calls
90de6f9 - fix: email preview dialog DOM crash - add setTimeout delay between dialogs
4e3a926 - feat: email onizleme akisi eklendi (Kaydet -> Onizle -> Gonder)
a35032c - feat: mulakat olusturulunca adaya email gonder
8aaf655 - fix: tarih input placeholder GG.AA.YYYY eklendi
ef71d87 - fix: SelectItem empty value crash - use 'none' instead of empty string
0fa0186 - docs: update activeContext.md - mulakat form improvements

## Sonraki Gorev
FAZ 7 Keyword Yönetimi: ✅ TAMAMLANDI
- ✅ FAZ 7.1: BLACKLIST Keyword Filtresi (pools.py)
- ✅ FAZ 7.2: Smart Synonym (AI skip if approved exists)
- ✅ FAZ 7.3: Usage Count System (database.py, pools.py)
- ✅ FAZ 7.6: Data Cleanup (bozuk keyword, yetim synonym temizliği)
- ✅ FAZ 7.7: AI Synonym Kalite Sistemi v2 (synonyms.py)

FAZ 6 Pozisyon Kaydetme Otomatik Synonym Üretimi: ✅ TAMAMLANDI
- ✅ FAZ 6.1: Batch Rate Limit (rate_limiter.py)
- ✅ FAZ 6.2: Batch Synonym Üretim Fonksiyonu (synonyms.py)
- ✅ FAZ 6.3: save_parsed_position Entegrasyonu (pools.py)
- ✅ FAZ 6.4: Frontend Toast Bildirimi (havuzlar)
- ✅ FAZ 6.5: Production Test

FAZ 5 Frontend Synonym Yönetimi TAMAMLANDI:
- ✅ ADIM 5.1: Route + Sidebar Entegrasyonu
- ✅ ADIM 5.2: Ana sayfa iskelet + Tab yapısı
- ✅ ADIM 5.3: Tab 1 - Onay Bekleyenler
- ✅ ADIM 5.4: Tab 2 - Tüm Eş Anlamlılar + Arama
- ✅ ADIM 5.5: Tab 3 - AI Üretimi
- ✅ ADIM 5.6: Tab 4 - Manuel Ekleme
- ✅ ADIM 5.7: Test + Bug fix (deferred - production test)

## Bilinen Acik Konular
- SSL henuz yok (HTTP)
- Company Switcher henuz yapilmadi

## Son Security Duzeltmeleri (23.02.2026)
- IDOR zafiyeti duzeltildi (pools.py: 4 sorguya company_id filtresi eklendi)
- Super Admin audit log eklendi (firma olusturma, silme, durum degisikligi)
- JWT_SECRET fallback kaldirildi, .env zorunlu
- Public endpoint rate limiting hazir (check_public_apply_limit, check_public_positions_limit)
- Mulakat izolasyonu dogrulandi (0 NULL company_id kayit)

### 26.02.2026 - CV Çek Tutarsızlığı Fix
- BUG: X aday eşleşti mesajı ile tabloda görünen aday sayısı uyuşmuyordu
- KÖK NEDEN: stats[matched]++ korumalı durum kontrolünden ÖNCE çalışıyordu
- FIX: stats[matched]++ satırı 3861den 3933e taşındı (INSERTten hemen önce)
- Artık korumalı adaylar (ise_alindi/arsiv) matched sayısına dahil edilmiyor

### 26.02.2026 - Aday Ata Combobox
- SORUN: Modal Aday ID soruyordu, kullanıcı ID bilmiyordu
- ÇÖZÜM: Command + Popover Combobox ile ad soyad araması
- Backend: candidates.py limit kısıtlaması kaldırıldı (le=200 → sınırsız)
- Frontend: Combobox implementasyonu (havuzlar/index.tsx)
  - İsim ile arama yapılabiliyor
  - Mevcut pozisyon bilgisi gösteriliyor
  - ise_alindi adaylar listede gösterilmiyor (frontend filtre)
  - shadcn/ui Command + Popover bileşenleri kullanıldı

### 27.02.2026 - Havuzlar UI Temizliği
- GÖREV 4: Gereksiz butonlar ve UI elementleri kaldırıldı
- KALDIRILANLAR:
  - Üstteki "CV İndir" butonu (işlevsiz - zip download)
  - Transfer ve Durum toplu işlem butonları
  - Tablo header ve satır checkbox'ları
  - Transfer ve Status dialog'ları
  - selectedCandidates, allPools state'leri
  - toggleCandidate, toggleAllCandidates, handleTransfer, handleStatusUpdate, handleDownloadPoolCVs fonksiyonları
  - loadAllPools fonksiyonu
  - ArrowRightLeft import
- KORUNANLAR:
  - CSV export butonu (handleExport)
  - Aday detay CV butonu (handleViewCV)
  - Akıllı Havuz başlık onayı için Checkbox
- SONUÇ: 1236 → 1145 satır (~90 satır temizlendi)

### 26.02.2026 - Aday Ata Bug Fix (Pozisyon Tablosu)
- BUG: API 200 döndürüyordu ama aday pozisyona eklenmiyordu
- KÖK NEDEN: assign_candidate endpoint HEP candidate_pool_assignments tablosuna yazıyordu
  - Ama pozisyon havuzları candidate_positions tablosundan okunuyor
  - İKİ FARKLI TABLO → veri tutarsızlığı
- FIX: pools.py endpoint'te pool_type kontrolü eklendi
  - pool_type == "position" → add_candidate_to_position() (candidate_positions)
  - Diğer → assign_candidate_to_department_pool() (candidate_pool_assignments)
- GÜNCELLENEN DOSYALAR:
  - database.py: add_candidate_to_position() fonksiyonu güncellendi
    - arsiv kontrolü kaldırıldı (sadece ise_alindi engeller)
    - company_id parametresi eklendi (güvenlik)
    - Dict döndürüyor (detaylı hata mesajları)
  - pools.py: assign_candidate endpoint pool_type kontrolü eklendi

## İLERİDE YAPILACAKLAR

### PM2 → SYSTEMD GEÇİŞİ
- **Sorun:** PM2 "waiting" gösteriyor (Uvicorn child process spawn ediyor)
- **Risk:** Auto-restart çalışmayabilir, crash durumunda manuel müdahale gerekebilir
- **Çözüm:** systemd service'e geçiş
- **Ne zaman:** Domain/alan adı bağlandıktan sonra
- **Öncelik:** Orta
