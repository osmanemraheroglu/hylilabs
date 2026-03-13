#!/usr/bin/env python3
"""
Genel Havuzdaki adayları V3 ile değerlendirip pozisyonlara eşleştirir.
Background'da çalışır, progress log tutar, kaldığı yerden devam edebilir.

Kullanım:
    nohup python3 sync_general_pool.py > sync_pool.log 2>&1 &
    tail -f sync_pool.log
"""

import sys
import os
import time
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, '/var/www/hylilabs/api')
sys.path.insert(0, '/var/www/hylilabs/api/core')

# Sabitler
DB_PATH = '/var/www/hylilabs/api/data/talentflow.db'
PROGRESS_FILE = '/var/www/hylilabs/api/scripts/sync_progress.json'
BATCH_SIZE = 10
RATE_LIMIT_SECONDS = 2
COMPANY_ID = 1
GENEL_HAVUZ_ID = 13  # department_pools id for Genel Havuz

def log(message):
    """Timestamp ile log yaz."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}", flush=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def load_progress():
    """Önceki ilerlemeyi yükle."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'processed_candidates': [], 'stats': {'total': 0, 'matched': 0, 'skipped': 0, 'errors': 0}}

def save_progress(progress):
    """İlerlemeyi kaydet."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def get_pending_candidates(processed_ids):
    """Henüz işlenmemiş Genel Havuz adaylarını getir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if processed_ids:
        placeholders = ','.join(['?'] * len(processed_ids))
        query = f"""
            SELECT c.id, c.ad_soyad, c.mevcut_pozisyon 
            FROM candidates c
            JOIN candidate_pool_assignments cpa ON c.id = cpa.candidate_id
            WHERE cpa.department_pool_id = ?
            AND c.company_id = ?
            AND c.id NOT IN ({placeholders})
            ORDER BY c.id
        """
        params = [GENEL_HAVUZ_ID, COMPANY_ID] + processed_ids
    else:
        query = """
            SELECT c.id, c.ad_soyad, c.mevcut_pozisyon 
            FROM candidates c
            JOIN candidate_pool_assignments cpa ON c.id = cpa.candidate_id
            WHERE cpa.department_pool_id = ?
            AND c.company_id = ?
            ORDER BY c.id
        """
        params = [GENEL_HAVUZ_ID, COMPANY_ID]
    
    cursor.execute(query, params)
    candidates = cursor.fetchall()
    conn.close()
    
    return candidates

def get_active_positions():
    """Aktif pozisyonları getir."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name 
        FROM department_pools 
        WHERE pool_type = 'position' 
        -- durum filter removed
        AND company_id = ?
    """, (COMPANY_ID,))
    
    positions = cursor.fetchall()
    conn.close()
    
    return positions

def process_candidate(candidate_id):
    """
    Tek bir adayı V3 ile değerlendir ve eşleştir.
    match_single_candidate_to_positions kullanır (V3 entegrasyonlu).
    """
    from database import match_single_candidate_to_positions
    
    try:
        result = match_single_candidate_to_positions(candidate_id, COMPANY_ID)
        return result
    except Exception as e:
        log(f"  HATA aday {candidate_id}: {e}")
        return {'error': str(e), 'transferred': 0}

def main():
    log("=" * 60)
    log("GENEL HAVUZ V3 EŞLEŞTİRME BAŞLADI")
    log("=" * 60)
    
    # Progress yükle
    progress = load_progress()
    processed_ids = progress['processed_candidates']
    stats = progress['stats']
    
    log(f"Önceki ilerleme: {len(processed_ids)} aday işlenmiş")
    
    # Bekleyen adayları al
    candidates = get_pending_candidates(processed_ids)
    log(f"İşlenecek aday: {len(candidates)}")
    
    if not candidates:
        log("Tüm adaylar zaten işlenmiş!")
        return
    
    # Pozisyonları al
    positions = get_active_positions()
    log(f"Aktif pozisyon: {len(positions)}")
    for p in positions:
        log(f"  - {p['name']} (ID: {p['id']})")
    
    # Her adayı işle
    batch_count = 0
    for i, row in enumerate(candidates, 1):
        cand_id = row['id']
        ad_soyad = row['ad_soyad'] or 'İsimsiz'
        pozisyon = row['mevcut_pozisyon']
        
        log(f"\n[{i}/{len(candidates)}] Aday {cand_id}: {ad_soyad}")
        log(f"  Mevcut pozisyon: {pozisyon or 'Belirtilmemiş'}")
        
        # V3 değerlendirme ve eşleştirme
        result = process_candidate(cand_id)
        
        if 'error' in result:
            log(f"  ❌ HATA: {result['error']}")
            stats['errors'] += 1
        else:
            transferred = result.get('transferred', 0)
            matched_positions = result.get('matched_positions', [])
            
            if transferred > 0:
                for pos_info in matched_positions:
                    v3_eval = pos_info.get('v3_evaluated', False)
                    log(f"  ✅ EŞLEŞTİ: {pos_info.get('name', 'N/A')} (Skor: {pos_info.get('score', 'N/A')}, V3: {v3_eval})")
                stats['matched'] += 1
            else:
                log(f"  ⏭️ Eşleşme yok (Final < 40 veya title match yok)")
                stats['skipped'] += 1
        
        stats['total'] += 1
        
        # Progress kaydet
        processed_ids.append(cand_id)
        progress['processed_candidates'] = processed_ids
        progress['stats'] = stats
        save_progress(progress)
        
        # Rate limiting
        time.sleep(RATE_LIMIT_SECONDS)
        
        # Batch kontrolü - her 10 adayda özet
        batch_count += 1
        if batch_count >= BATCH_SIZE:
            batch_count = 0
            log(f"\n--- BATCH ÖZET: {stats['total']} işlendi, {stats['matched']} eşleşti, {stats['errors']} hata ---\n")
            time.sleep(5)  # Batch arası dinlenme
    
    # Final rapor
    log("\n" + "=" * 60)
    log("GENEL HAVUZ V3 EŞLEŞTİRME TAMAMLANDI")
    log("=" * 60)
    log(f"Toplam işlenen: {stats['total']}")
    log(f"Eşleştirilen: {stats['matched']}")
    log(f"Eşleşmeyen: {stats['skipped']}")
    log(f"Hata: {stats['errors']}")
    
    # Progress dosyasını tamamlandı olarak işaretle
    if os.path.exists(PROGRESS_FILE):
        os.rename(PROGRESS_FILE, PROGRESS_FILE + '.completed')
    
    log("Bitti!")

if __name__ == '__main__':
    main()
