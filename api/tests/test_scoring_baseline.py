"""
FAZ 0.3 - Scoring Baseline Test

Bu test Boubekeur Bouakkaz (ID: 392) adayının
Bütçe ve Maliyet Kontrol Şefi (ID: 7792) pozisyonu için
mevcut scoring puanını doğrular.

AMAÇ: FAZ 2.2 global synonyms sonrası puanı kayıt altına almak.
Bu test regression testi olarak kullanılacak.

TEST KURALI (Kural 26 - AAA Pattern):
- ARRANGE: DB'den aday ve pozisyon verilerini al
- ACT: scoring fonksiyonunu çağır
- ASSERT: Beklenen puanları doğrula

9 TEST:
1. test_candidate_exists - Aday DB'de var mı
2. test_position_keywords_exist - Pozisyon v2 keyword'leri var mı
3. test_boubekeur_technical_score_none - company_id=None ile teknik puan
4. test_boubekeur_technical_score_company1 - company_id=1 ile teknik puan
5. test_boubekeur_total_score - Toplam puan doğrulama (71)
6. test_company_id_parameter_exists - check_keyword_match company_id parametresi
7. test_three_layer_layer1_dict - Katman 1: KEYWORD_SYNONYMS dict
8. test_three_layer_layer2_db_global - Katman 2: DB global synonym
9. test_three_layer_layer3_db_company - Katman 3: DB firma synonym
"""

import sys
import os
import json

# API dizinini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3


def get_candidate_data(candidate_id: int) -> dict:
    """DB'den aday verilerini al"""
    conn = sqlite3.connect('data/talentflow.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_position_data(position_id: int) -> dict:
    """DB'den pozisyon verilerini al - scoring_v2 ile uyumlu format
    
    NOT: Position dict'te 'baslik' kullanılmalı, 'name' EKLENMEMELİ.
    'name' eklenirse scoring farklı sonuç veriyor (65 vs 71).
    """
    conn = sqlite3.connect('data/talentflow.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, company_id, name as baslik, keywords, description, gerekli_deneyim_yil, 
               gerekli_egitim, lokasyon, aranan_nitelikler, is_tanimi
        FROM department_pools 
        WHERE id = ? AND pool_type = "position"
    ''', (position_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        result = dict(row)
        # Keywords JSON array ise string'e cevir
        kw = result.get('keywords', '')
        if kw and kw.startswith('['):
            try:
                kw_list = json.loads(kw)
                result['keywords'] = ', '.join(kw_list)
            except:
                pass
        return result
    return None


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri normalize et ve küçük harfe çevir"""
    if not text:
        return ""
    return text.replace('İ', 'i').replace('I', 'ı').lower()


class TestScoringBaseline:
    """Scoring v2 baseline testleri - 9 test"""
    
    # Test sabitleri
    CANDIDATE_ID = 392  # Boubekeur Bouakkaz
    POSITION_ID = 7792  # Bütçe ve Maliyet Kontrol Şefi
    
    # Beklenen puanlar (G5 sonrası: scoring_v2.py senkronize edildi)
    EXPECTED_TOTAL = 71
    EXPECTED_POSITION = 14
    EXPECTED_TECHNICAL = 37
    EXPECTED_GENERAL = 20
    
    # =========================================================================
    # TEST 1: test_candidate_exists
    # =========================================================================
    def test_candidate_exists(self):
        """Aday verisinin DB'de var olduğunu doğrula"""
        candidate = get_candidate_data(self.CANDIDATE_ID)
        
        assert candidate is not None, f"Aday bulunamadı: ID={self.CANDIDATE_ID}"
        assert candidate['ad_soyad'] == 'Boubekeur Bouakkaz'
        assert candidate['mevcut_pozisyon'] == 'Cost Control Engineer'
    
    # =========================================================================
    # TEST 2: test_position_keywords_exist
    # =========================================================================
    def test_position_keywords_exist(self):
        """Pozisyon için v2 keyword'lerin var olduğunu doğrula"""
        conn = sqlite3.connect('data/talentflow.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as cnt FROM position_keywords_v2 
            WHERE position_id = ?
        ''', (self.POSITION_ID,))
        row = cursor.fetchone()
        conn.close()
        
        assert row['cnt'] > 0, f"Pozisyon {self.POSITION_ID} için v2 keyword bulunamadı"
    
    # =========================================================================
    # TEST 3: test_boubekeur_technical_score_none
    # =========================================================================
    def test_boubekeur_technical_score_none(self):
        """company_id=None ile teknik puan hesaplama"""
        from scoring_v2 import calculate_technical_score, get_v2_keywords
        
        candidate = get_candidate_data(self.CANDIDATE_ID)
        position = get_position_data(self.POSITION_ID)
        v2_keywords = get_v2_keywords(self.POSITION_ID)
        
        # company_id=None ile hesapla
        result = calculate_technical_score(candidate, position, v2_keywords, None)
        
        assert 'technical_score' in result
        assert result['technical_score'] >= 0
        # Global synonyms ile en az 30 puan bekliyoruz
        assert result['technical_score'] >= 30, f"Teknik puan çok düşük: {result['technical_score']}"
    
    # =========================================================================
    # TEST 4: test_boubekeur_technical_score_company1
    # =========================================================================
    def test_boubekeur_technical_score_company1(self):
        """company_id=1 ile teknik puan hesaplama (firma synonym'ları dahil)"""
        from scoring_v2 import calculate_technical_score, get_v2_keywords
        
        candidate = get_candidate_data(self.CANDIDATE_ID)
        position = get_position_data(self.POSITION_ID)
        v2_keywords = get_v2_keywords(self.POSITION_ID)
        
        # company_id=1 ile hesapla
        result = calculate_technical_score(candidate, position, v2_keywords, 1)
        
        assert 'technical_score' in result
        assert result['technical_score'] == self.EXPECTED_TECHNICAL, \
            f"Teknik puan eşleşmiyor: Beklenen={self.EXPECTED_TECHNICAL}, Gerçek={result['technical_score']}"
    
    # =========================================================================
    # TEST 5: test_boubekeur_total_score
    # =========================================================================
    def test_boubekeur_total_score(self):
        """
        Boubekeur toplam puan doğrulama.

        G5 sonrası: Total=71, Position=14, Technical=37, General=20
        """
        from scoring_v2 import calculate_match_score_v2
        
        candidate = get_candidate_data(self.CANDIDATE_ID)
        position = get_position_data(self.POSITION_ID)
        
        # company_id = 1 (matches tablosundaki değer ile tutarlı)
        candidate['company_id'] = 1
        
        result = calculate_match_score_v2(candidate, position)
        
        # Sonuçları yazdır (debug için)
        print(f"\n=== SCORING SONUÇLARI ===")
        print(f"Toplam: {result.get('total', 'N/A')}")
        print(f"Pozisyon: {result.get('position_score', 'N/A')}")
        print(f"Teknik: {result.get('technical_score', 'N/A')}")
        print(f"Genel: {result.get('general_score', 'N/A')}")
        print(f"========================\n")
        
        assert result is not None, "Scoring sonucu None döndü"
        assert result.get('version') == 'v2', "Scoring versiyonu v2 olmalı"
        
        assert result.get('total') == self.EXPECTED_TOTAL, \
            f"Toplam puan eşleşmiyor: Beklenen={self.EXPECTED_TOTAL}, Gerçek={result.get('total')}"
        
        assert result.get('position_score') == self.EXPECTED_POSITION, \
            f"Pozisyon puanı eşleşmiyor: Beklenen={self.EXPECTED_POSITION}, Gerçek={result.get('position_score')}"
        
        assert result.get('technical_score') == self.EXPECTED_TECHNICAL, \
            f"Teknik puan eşleşmiyor: Beklenen={self.EXPECTED_TECHNICAL}, Gerçek={result.get('technical_score')}"
        
        assert result.get('general_score') == self.EXPECTED_GENERAL, \
            f"Genel puan eşleşmiyor: Beklenen={self.EXPECTED_GENERAL}, Gerçek={result.get('general_score')}"
    
    # =========================================================================
    # TEST 6: test_company_id_parameter_exists
    # =========================================================================
    def test_company_id_parameter_exists(self):
        """check_keyword_match fonksiyonunun company_id parametresi var mı"""
        from core.candidate_matcher import check_keyword_match
        import inspect
        
        sig = inspect.signature(check_keyword_match)
        param_names = list(sig.parameters.keys())
        
        assert 'company_id' in param_names, \
            f"check_keyword_match'te company_id parametresi yok. Mevcut: {param_names}"
    
    # =========================================================================
    # TEST 7: test_three_layer_layer1_dict
    # =========================================================================
    def test_three_layer_layer1_dict(self):
        """Katman 1: KEYWORD_SYNONYMS dict'ten synonym bulma"""
        from core.candidate_matcher import check_keyword_match, KEYWORD_SYNONYMS
        
        # Dict'te 'python' -> ['py', 'python3'] var mı kontrol et
        assert 'python' in KEYWORD_SYNONYMS, "python KEYWORD_SYNONYMS'da yok"
        
        # python keyword'ü için 'py' ile eşleşme bul
        keyword = 'python'
        search_text = 'py developer with experience'
        skills_text = ''
        
        found, matched, source = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        
        assert found == True, "Katman 1 (dict) eşleşmesi bulunamadı"
        assert source == 'synonym', f"Kaynak synonym olmalı, {source} geldi"
    
    # =========================================================================
    # TEST 8: test_three_layer_layer2_db_global
    # =========================================================================
    def test_three_layer_layer2_db_global(self):
        """Katman 2: DB global synonym (company_id IS NULL)"""
        from core.candidate_matcher import check_keyword_match
        
        # DB'de global synonym var mı kontrol et
        conn = sqlite3.connect('data/talentflow.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT keyword, synonym FROM keyword_synonyms 
            WHERE company_id IS NULL AND is_active = 1
            LIMIT 1
        ''')
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None, "DB'de global synonym bulunamadı"
        
        keyword = row[0]
        synonym = row[1]
        
        # Bu synonym ile eşleşme bul
        search_text = f"experience with {synonym}"
        skills_text = ''
        
        found, matched, source = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        
        # Global synonym her iki durumda da bulunmalı
        assert found == True, f"Katman 2 (DB global) eşleşmesi bulunamadı: {keyword} -> {synonym}"
    
    # =========================================================================
    # TEST 9: test_three_layer_layer3_db_company
    # =========================================================================
    def test_three_layer_layer3_db_company(self):
        """Katman 3: DB firma synonym (company_id = N)"""
        from core.candidate_matcher import check_keyword_match
        
        # s4hana keyword'ü için erp synonym'u (company_id=1)
        # Bu FAZ 2.1'de firma bazlı kaldı
        keyword = 's4hana'
        search_text = 'erp sistemleri deneyimi'
        skills_text = ''
        
        # company_id=1 ile bulmalı
        found_1, matched_1, source_1 = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=1
        )
        
        # company_id=None ile bulmamalı (firma bazlı synonym)
        found_none, matched_none, source_none = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        
        assert found_1 == True, "Katman 3 (DB firma) eşleşmesi bulunamadı: s4hana -> erp (company_id=1)"
        assert found_none == False, "company_id=None ile firma synonym'u bulunmamalı"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
