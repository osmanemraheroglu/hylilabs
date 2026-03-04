"""
FAZ 0.3 - Scoring Baseline Test

Bu test Boubekeur Bouakkaz (ID: 392) adayının
Bütçe ve Maliyet Kontrol Şefi (ID: 7792) pozisyonu için
mevcut scoring puanını doğrular.

AMAÇ: Bug fix öncesi mevcut puanı kayıt altına almak.
Bu test daha sonra regression testi olarak kullanılacak.

TEST KURALI (Kural 26 - AAA Pattern):
- ARRANGE: DB'den aday ve pozisyon verilerini al
- ACT: scoring fonksiyonunu çağır
- ASSERT: Beklenen puanları doğrula
"""

import sys
import os

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
    """DB'den pozisyon verilerini al"""
    conn = sqlite3.connect('data/talentflow.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM department_pools WHERE id = ?", (position_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        # pozisyon_adi yerine name kullanılıyor
        result = dict(row)
        result['pozisyon_adi'] = result.get('name', '')
        return result
    return None


class TestScoringBaseline:
    """Scoring v2 baseline testleri"""
    
    # Test sabitleri
    CANDIDATE_ID = 392  # Boubekeur Bouakkaz
    POSITION_ID = 7792  # Bütçe ve Maliyet Kontrol Şefi
    
    # Beklenen puanlar (mevcut bug'lu sistem)
    EXPECTED_TOTAL = 65
    EXPECTED_POSITION = 8
    EXPECTED_TECHNICAL = 37
    EXPECTED_GENERAL = 20
    
    def test_boubekeur_baseline_score(self):
        """
        Boubekeur Bouakkaz (ID: 392) için mevcut puanı doğrula.
        
        Bu test bug fix ÖNCESİ mevcut puanı kaydeder.
        Bug fix SONRASI bu test FAILED olmalı (puan artacak).
        """
        # ARRANGE: DB'den aday ve pozisyon verilerini al
        candidate = get_candidate_data(self.CANDIDATE_ID)
        position = get_position_data(self.POSITION_ID)
        
        assert candidate is not None, f"Aday bulunamadı: ID={self.CANDIDATE_ID}"
        assert position is not None, f"Pozisyon bulunamadı: ID={self.POSITION_ID}"
        
        # Aday bilgilerini doğrula
        assert candidate['ad_soyad'] == 'Boubekeur Bouakkaz', "Aday adı eşleşmiyor"
        assert position['name'] == 'Bütçe ve Maliyet Kontrol Şefi', "Pozisyon adı eşleşmiyor"
        
        # ACT: Scoring fonksiyonunu çağır
        from scoring_v2 import calculate_match_score_v2
        
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
        assert position['name'] == 'Bütçe ve Maliyet Kontrol Şefi'
        assert position['gerekli_deneyim_yil'] == 7.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
