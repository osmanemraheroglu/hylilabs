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


class TestScoringBaseline:
    """Scoring v2 baseline testleri"""
    
    # Test sabitleri
    CANDIDATE_ID = 392  # Boubekeur Bouakkaz
    POSITION_ID = 7792  # Bütçe ve Maliyet Kontrol Şefi
    
    # Beklenen puanlar (FAZ 2.2 sonrası global synonyms ile)
    EXPECTED_TOTAL = 71
    EXPECTED_POSITION = 14
    EXPECTED_TECHNICAL = 37
    EXPECTED_GENERAL = 20
    
    def test_boubekeur_baseline_score(self):
        """
        Boubekeur Bouakkaz (ID: 392) için mevcut puanı doğrula.
        
        Bu test FAZ 2.2 global synonyms sonrası puanı kaydeder.
        DB'deki match kaydı ile tutarlı olmalı (company_id=1).
        """
        # ARRANGE: DB'den aday ve pozisyon verilerini al
        candidate = get_candidate_data(self.CANDIDATE_ID)
        position = get_position_data(self.POSITION_ID)
        
        assert candidate is not None, f"Aday bulunamadı: ID={self.CANDIDATE_ID}"
        assert position is not None, f"Pozisyon bulunamadı: ID={self.POSITION_ID}"
        
        # Aday bilgilerini doğrula
        assert candidate['ad_soyad'] == 'Boubekeur Bouakkaz', "Aday adı eşleşmiyor"
        assert position['baslik'] == 'Bütçe ve Maliyet Kontrol Şefi', "Pozisyon adı eşleşmiyor"
        
        # ACT: Scoring fonksiyonunu çağır
        from scoring_v2 import calculate_match_score_v2
        
        # company_id = 1 (matches tablosundaki değer ile tutarlı)
        candidate['company_id'] = 1
        
        result = calculate_match_score_v2(candidate, position)
        
        # Sonuçları yazdır (debug için)
        print(f"\n=== SCORING SONUÇLARI ===")
        print(f"Toplam: {result.get('total', 'N/A')}")
        print(f"Pozisyon: {result.get('position_score', 'N/A')}")
        print(f"Teknik: {result.get('technical_score', 'N/A')}")
        print(f"Genel: {result.get('general_score', 'N/A')}")
        print(f"Versiyon: {result.get('version', 'N/A')}")
        print(f"========================\n")
        
        # ASSERT: Beklenen puanları doğrula
        assert result is not None, "Scoring sonucu None döndü"
        assert result.get('version') == 'v2', "Scoring versiyonu v2 olmalı"
        
        # Puan doğrulamaları
        actual_total = result.get('total', 0)
        actual_position = result.get('position_score', 0)
        actual_technical = result.get('technical_score', 0)
        actual_general = result.get('general_score', 0)
        
        # Detaylı hata mesajları
        assert actual_total == self.EXPECTED_TOTAL, \
            f"Toplam puan eşleşmiyor: Beklenen={self.EXPECTED_TOTAL}, Gerçek={actual_total}"
        
        assert actual_position == self.EXPECTED_POSITION, \
            f"Pozisyon puanı eşleşmiyor: Beklenen={self.EXPECTED_POSITION}, Gerçek={actual_position}"
        
        assert actual_technical == self.EXPECTED_TECHNICAL, \
            f"Teknik puan eşleşmiyor: Beklenen={self.EXPECTED_TECHNICAL}, Gerçek={actual_technical}"
        
        assert actual_general == self.EXPECTED_GENERAL, \
            f"Genel puan eşleşmiyor: Beklenen={self.EXPECTED_GENERAL}, Gerçek={actual_general}"
    
    def test_candidate_exists(self):
        """Aday verisinin DB'de var olduğunu doğrula"""
        # ARRANGE & ACT
        candidate = get_candidate_data(self.CANDIDATE_ID)
        
        # ASSERT
        assert candidate is not None, f"Aday bulunamadı: ID={self.CANDIDATE_ID}"
        assert candidate['ad_soyad'] == 'Boubekeur Bouakkaz'
        assert candidate['mevcut_pozisyon'] == 'Cost Control Engineer'
    
    def test_position_exists(self):
        """Pozisyon verisinin DB'de var olduğunu doğrula"""
        # ARRANGE & ACT
        position = get_position_data(self.POSITION_ID)
        
        # ASSERT
        assert position is not None, f"Pozisyon bulunamadı: ID={self.POSITION_ID}"
        assert position['baslik'] == 'Bütçe ve Maliyet Kontrol Şefi'
        assert position['gerekli_deneyim_yil'] == 7.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
