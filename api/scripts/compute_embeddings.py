#!/usr/bin/env python3
"""
FAZ 10.2: Mevcut tüm keyword ve synonymler için embedding hesapla
Kullanım: python3 scripts/compute_embeddings.py
"""
import sys
import os
sys.path.insert(0, '/var/www/hylilabs/api')
os.chdir('/var/www/hylilabs/api')

from dotenv import load_dotenv
load_dotenv('/var/www/hylilabs/api/.env')

import sqlite3
import time

# Database path
DB_PATH = '/var/www/hylilabs/api/data/talentflow.db'

def main():
    # Import after env loaded
    from database import save_keyword_embedding, save_synonym_embedding
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Unique keyword'leri al
    cursor.execute('SELECT DISTINCT keyword FROM keyword_synonyms')
    keywords = [row[0] for row in cursor.fetchall()]
    print(f'\nToplam {len(keywords)} unique keyword bulundu')
    
    # Keyword embeddings
    success_kw = 0
    for i, kw in enumerate(keywords):
        if save_keyword_embedding(kw):
            success_kw += 1
        print(f'\r[{i+1}/{len(keywords)}] Keyword işleniyor...', end='', flush=True)
        time.sleep(0.05)  # Rate limit
    print(f'\nKeyword embeddings: {success_kw}/{len(keywords)} başarılı')
    
    # Synonym embeddings
    cursor.execute('SELECT keyword, synonym FROM keyword_synonyms')
    synonyms = cursor.fetchall()
    print(f'\nToplam {len(synonyms)} synonym bulundu')
    
    success_syn = 0
    for i, (kw, syn) in enumerate(synonyms):
        if save_synonym_embedding(syn, kw):
            success_syn += 1
        print(f'\r[{i+1}/{len(synonyms)}] Synonym işleniyor...', end='', flush=True)
        time.sleep(0.05)  # Rate limit
    print(f'\nSynonym embeddings: {success_syn}/{len(synonyms)} başarılı')
    
    conn.close()
    
    print('\n=== TAMAMLANDI ===')
    print(f'Keyword: {success_kw}/{len(keywords)}')
    print(f'Synonym: {success_syn}/{len(synonyms)}')

if __name__ == '__main__':
    main()
