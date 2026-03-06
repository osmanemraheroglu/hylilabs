#!/usr/bin/env python3
"""
FAZ C RESCORE - Tüm Pozisyonlar
Puan sabitleri değişti, DB'deki puanları yeniden hesapla.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json

DB_PATH = 'data/talentflow.db'

def main():
    from scoring_v2 import calculate_match_score_v2

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout = 60000")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Tüm pozisyonları al
    cursor.execute("""
        SELECT id, name, company_id, gerekli_deneyim_yil, gerekli_egitim, lokasyon, is_tanimi
        FROM department_pools WHERE pool_type = 'position'
    """)
    positions = cursor.fetchall()
    print(f"İşlenecek pozisyon: {len(positions)}\n")

    total_rescored = 0
    total_increased = 0
    total_decreased = 0
    total_unchanged = 0

    for pos in positions:
        pool_id = pos['id']
        pos_name = pos['name']
        company_id = pos['company_id']

        # Keywords
        cursor.execute("""
            SELECT keyword, category FROM position_keywords_v2 WHERE position_id = ?
        """, (pool_id,))
        kws = cursor.fetchall()

        position_dict = {
            'id': pool_id,
            'baslik': pos_name,
            'name': pos_name,
            'gerekli_deneyim_yil': pos['gerekli_deneyim_yil'] or 0,
            'gerekli_egitim': pos['gerekli_egitim'] or '',
            'lokasyon': pos['lokasyon'] or '',
            'is_tanimi': pos['is_tanimi'] or '',
            'keywords': {},
            'company_id': company_id
        }
        for kw in kws:
            position_dict['keywords'].setdefault(kw['category'], []).append(kw['keyword'])

        # Adaylar
        cursor.execute("""
            SELECT cp.candidate_id, cp.match_score as old_score
            FROM candidate_positions cp
            WHERE cp.position_id = ?
        """, (pool_id,))
        candidates = cursor.fetchall()

        if not candidates:
            print(f"[{pool_id}] {pos_name}: 0 aday (ATLA)")
            continue

        pos_rescored = 0
        pos_increased = 0
        pos_decreased = 0
        pos_unchanged = 0

        for cand in candidates:
            cid = cand['candidate_id']
            old_score = cand['old_score'] or 0

            cursor.execute("""
                SELECT id, ad_soyad, teknik_beceriler, mevcut_pozisyon,
                       deneyim_detay, toplam_deneyim_yil, egitim, lokasyon,
                       mevcut_sirket, cv_raw_text, diller, sertifikalar, deneyim_aciklama
                FROM candidates WHERE id = ?
            """, (cid,))
            r = cursor.fetchone()
            if not r:
                continue

            candidate_dict = {
                'id': r['id'],
                'ad_soyad': r['ad_soyad'] or '',
                'teknik_beceriler': r['teknik_beceriler'] or '',
                'mevcut_pozisyon': r['mevcut_pozisyon'] or '',
                'deneyim_detay': r['deneyim_detay'] or '',
                'toplam_deneyim_yil': r['toplam_deneyim_yil'] or 0,
                'egitim': r['egitim'] or '',
                'lokasyon': r['lokasyon'] or '',
                'mevcut_sirket': r['mevcut_sirket'] or '',
                'cv_raw_text': r['cv_raw_text'] or '',
                'diller': r['diller'] or '',
                'sertifikalar': r['sertifikalar'] or '',
                'deneyim_aciklama': r['deneyim_aciklama'] or '',
                'company_id': company_id
            }

            v2_result = calculate_match_score_v2(candidate_dict, position_dict)
            if v2_result:
                new_score = v2_result.get('total', 0)

                cursor.execute("""
                    UPDATE matches SET uyum_puani = ?, detayli_analiz = ?
                    WHERE candidate_id = ? AND position_id = ?
                """, (new_score, json.dumps(v2_result, ensure_ascii=False), cid, pool_id))

                cursor.execute("""
                    UPDATE candidate_positions SET match_score = ?
                    WHERE candidate_id = ? AND position_id = ?
                """, (new_score, cid, pool_id))

                pos_rescored += 1
                if new_score > old_score:
                    pos_increased += 1
                elif new_score < old_score:
                    pos_decreased += 1
                else:
                    pos_unchanged += 1

        conn.commit()

        print(f"[{pool_id}] {pos_name[:40]}: {pos_rescored} aday | ↑{pos_increased} ↓{pos_decreased} ={pos_unchanged}")

        total_rescored += pos_rescored
        total_increased += pos_increased
        total_decreased += pos_decreased
        total_unchanged += pos_unchanged

    conn.close()

    print(f"\n{'='*60}")
    print(f"TOPLAM: {total_rescored} rescore | ↑{total_increased} ↓{total_decreased} ={total_unchanged}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
