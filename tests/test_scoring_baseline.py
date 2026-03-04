"""
Boubekeur Bouakkaz (ID:392) + Pozisyon (ID:7792) scoring baseline.
FAZ 1B sonrası güncel değerler (05.03.2026).
FAZ 2.1 sonrası: 102 synonym global yapıldı (05.03.2026).
AAA Pattern zorunlu (Kural 26).
"""
import pytest
import inspect
import sys
import sqlite3

sys.path.insert(0, '/var/www/hylilabs/api')

from scoring_v2 import calculate_match_score_v2, calculate_technical_score, get_v2_keywords
from core.candidate_matcher import check_keyword_match, KEYWORD_SYNONYMS

# Turkish lowercase helper (database.py'den)
def turkish_lower(text):
    if not text:
        return ''
    text = str(text)
    text = text.replace('İ', 'i').replace('I', 'ı')
    return text.lower().replace('i̇', 'i')


def get_candidate(candidate_id):
    """DB'den candidate dict al"""
    conn = sqlite3.connect('/var/www/hylilabs/api/data/talentflow.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM candidates WHERE id = ?', (candidate_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


class TestScoringBaseline:
    """Boubekeur Bouakkaz (ID:392) scoring testleri"""

    def test_candidate_exists(self):
        """Aday 392 veritabanında mevcut"""
        # ARRANGE
        conn = sqlite3.connect('/var/www/hylilabs/api/data/talentflow.db')
        c = conn.cursor()
        
        # ACT
        c.execute('SELECT id, ad_soyad FROM candidates WHERE id = 392')
        row = c.fetchone()
        conn.close()
        
        # ASSERT
        assert row is not None, 'Aday 392 veritabanında bulunamadı'
        assert row[1] == 'Boubekeur Bouakkaz', f'Beklenen: Boubekeur Bouakkaz, Gelen: {row[1]}'

    def test_position_keywords_exist(self):
        """Pozisyon 7792 için V2 keywords mevcut"""
        # ARRANGE
        conn = sqlite3.connect('/var/www/hylilabs/api/data/talentflow.db')
        c = conn.cursor()
        
        # ACT
        c.execute('SELECT COUNT(*) FROM position_keywords_v2 WHERE position_id = 7792')
        count = c.fetchone()[0]
        conn.close()
        
        # ASSERT
        assert count > 0, 'Pozisyon 7792 için V2 keywords bulunamadı'

    def test_boubekeur_technical_score_none(self):
        """
        Teknik puan doğrulama (company_id=None, global synonym'ler).
        calculate_technical_score() ile direkt test.
        """
        # ARRANGE
        candidate = get_candidate(392)
        position = {'id': 7792}
        v2_keywords = get_v2_keywords(7792)
        
        # ACT
        result = calculate_technical_score(candidate, position, v2_keywords, company_id=None)
        
        # ASSERT
        assert result['technical_score'] == 35, f'Teknik puan beklenen: 35, gelen: {result["technical_score"]}'
        assert result['must_have_score'] == 20, f'Must-have beklenen: 20, gelen: {result["must_have_score"]}'

    def test_boubekeur_technical_score_company1(self):
        """
        company_id=1 ile teknik puan farkı.
        S4HANA→SAP eşleşmesi sayesinde +2 puan.
        """
        # ARRANGE
        candidate = get_candidate(392)
        position = {'id': 7792}
        v2_keywords = get_v2_keywords(7792)
        
        # ACT
        result = calculate_technical_score(candidate, position, v2_keywords, company_id=1)
        
        # ASSERT
        assert result['technical_score'] == 37, f'Teknik puan beklenen: 37, gelen: {result["technical_score"]}'

    def test_boubekeur_total_score(self):
        """
        calculate_match_score_v2() ile toplam puan doğrulama.
        Boubekeur (392) + Pozisyon (7792), company_id=None (global).
        
        Gerçek değerler (05.03.2026):
        - total: 49
        - position_score: 14
        - technical_score: 35
        - general_score: 0
        """
        # ARRANGE
        candidate = get_candidate(392)
        candidate['company_id'] = None  # Global synonym testi
        position = {'id': 7792}
        
        # ACT
        result = calculate_match_score_v2(candidate, position)
        
        # ASSERT
        assert result is not None, 'calculate_match_score_v2 None döndü'
        assert result['version'] == 'v2', f'Version beklenen: v2, gelen: {result["version"]}'
        assert result['total'] == 49, f'Toplam beklenen: 49, gelen: {result["total"]}'
        assert result['position_score'] == 14, f'Pozisyon beklenen: 14, gelen: {result["position_score"]}'
        assert result['technical_score'] == 35, f'Teknik beklenen: 35, gelen: {result["technical_score"]}'
        assert result['general_score'] == 0, f'Genel beklenen: 0, gelen: {result["general_score"]}'

    def test_company_id_parameter_exists(self):
        """check_keyword_match() company_id parametresi kabul ediyor"""
        # ARRANGE & ACT
        sig = inspect.signature(check_keyword_match)
        
        # ASSERT
        assert 'company_id' in sig.parameters, 'company_id parametresi bulunamadı'
        assert sig.parameters['company_id'].default is None, 'company_id default değeri None olmalı'

    def test_three_layer_synonym_lookup_layer1_dict(self):
        """
        Katman 1: KEYWORD_SYNONYMS dict eşleşmesi.
        'excel' keyword'ü dict'te var, 'microsoft excel' text'te olmalı.
        """
        # ARRANGE
        keyword = 'excel'
        search_text = 'microsoft excel kullanımı'
        skills_text = ''
        
        # ACT
        found, matched_via, method = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        
        # ASSERT
        assert found == True, f'Katman 1 (dict): {keyword} bulunamadı'
        # Dict'te 'excel' key'i var mı kontrol
        assert keyword in KEYWORD_SYNONYMS, f'{keyword} KEYWORD_SYNONYMS dict içinde yok'

    def test_three_layer_synonym_lookup_layer2_db_global(self):
        """
        Katman 2: DB global synonym (company_id IS NULL).
        'ms office' → 'microsoft office' DB'de global olarak tanımlı.
        """
        # ARRANGE
        keyword = 'ms office'
        search_text = 'microsoft office programları'
        skills_text = ''
        
        # ACT
        found, matched_via, method = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        
        # ASSERT
        assert found == True, f'Katman 2 (DB global): {keyword} bulunamadı'

    def test_three_layer_synonym_lookup_layer3_db_company(self):
        """
        Katman 3: DB firma synonym (company_id=1).
        
        FAZ 2.1 sonrası: 's4hana' kullanılıyor (yazılım geliştirme artık global).
        s4hana → erp sadece company_id=1'de var.
        
        Test 3a: company_id=1 → bulmalı
        Test 3b: company_id=None → BULAMAMALI (s4hana için NULL'da erp yok)
        Test 3c: company_id=999 → BULAMAMALI
        """
        # ARRANGE
        keyword = 's4hana'
        search_text = 'erp sistemleri deneyimi'  # synonym: erp
        skills_text = ''
        
        # ACT & ASSERT - Test 3a: company_id=1 ile bulmalı
        found_1, _, _ = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=1
        )
        assert found_1 == True, f'Katman 3a (company_id=1): {keyword} bulunamadı'
        
        # ACT & ASSERT - Test 3b: company_id=None ile BULAMAMALI
        found_none, _, _ = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=None
        )
        assert found_none == False, f'Katman 3b (company_id=None): {keyword} bulunmamalıydı ama bulundu'
        
        # ACT & ASSERT - Test 3c: company_id=999 ile BULAMAMALI
        found_999, _, _ = check_keyword_match(
            keyword, search_text, skills_text, turkish_lower, company_id=999
        )
        assert found_999 == False, f'Katman 3c (company_id=999): {keyword} bulunmamalıydı ama bulundu'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
