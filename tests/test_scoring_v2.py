"""
Scoring V2 - company_id desteği doğrulama testi
FAZ 1B sonrası regresyon testi
"""
import sys
sys.path.insert(0, '/var/www/hylilabs/api')

import sqlite3
from scoring_v2 import calculate_technical_score, get_v2_keywords

def get_candidate(candidate_id):
    conn = sqlite3.connect('/var/www/hylilabs/api/data/talentflow.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM candidates WHERE id = ?', (candidate_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def test_company_id_parameter():
    """
    calculate_technical_score fonksiyonunun company_id parametresini kabul ettiğini test et
    """
    candidate = get_candidate(392)  # Boubekeur Bouakkaz
    assert candidate is not None, 'Aday bulunamadı: 392'
    
    # Mock position (sadece ID gerekli)
    position = {'id': 7792}
    
    # V2 keywords al
    v2_keywords = get_v2_keywords(7792)
    assert v2_keywords, 'V2 keywords bulunamadı'
    
    print(f"V2 Keywords: {v2_keywords}")
    
    # company_id=None ile çağır (eski davranış)
    result1 = calculate_technical_score(candidate, position, v2_keywords, company_id=None)
    print(f"company_id=None ile skor: {result1['technical_score']}")
    
    # company_id=1 ile çağır (firma özel sinonimler)
    result2 = calculate_technical_score(candidate, position, v2_keywords, company_id=1)
    print(f"company_id=1 ile skor: {result2['technical_score']}")
    
    # Her iki çağrı da çalışmalı
    assert 'technical_score' in result1, 'technical_score eksik (company_id=None)'
    assert 'technical_score' in result2, 'technical_score eksik (company_id=1)'
    
    print()
    print('✓ company_id parametresi çalışıyor!')
    print(f'  company_id=None: {result1["technical_score"]} puan')
    print(f'  company_id=1: {result2["technical_score"]} puan')
    
    # Detay bilgileri
    print()
    print('Critical matched (None):', result1.get('critical_matched', []))
    print('Critical matched (1):', result2.get('critical_matched', []))
    
    return True

if __name__ == '__main__':
    test_company_id_parameter()
    print()
    print('TEST BAŞARILI!')
