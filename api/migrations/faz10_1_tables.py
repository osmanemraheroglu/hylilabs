#!/usr/bin/env python3
"""
FAZ 10.1: Multiple Confidence Source - Migration Script
Creates tables and columns for confidence scoring system
"""

import sqlite3
import os

DB_PATH = "/var/www/hylilabs/api/data/talentflow.db"

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. synonym_usage_stats tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synonym_usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                synonym TEXT NOT NULL,
                company_id INTEGER,
                cv_occurrence_count INTEGER DEFAULT 0,
                match_count INTEGER DEFAULT 0,
                hired_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(keyword, synonym, company_id)
            )
        """)
        print("synonym_usage_stats tablosu oluşturuldu")

        # 2. synonym_match_history tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synonym_match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                position_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                matched_term TEXT NOT NULL,
                method TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                company_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("synonym_match_history tablosu oluşturuldu")

        # 3. keyword_synonyms tablosuna confidence_score kolonu ekle
        cursor.execute("PRAGMA table_info(keyword_synonyms)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'confidence_score' not in columns:
            cursor.execute("""
                ALTER TABLE keyword_synonyms
                ADD COLUMN confidence_score REAL DEFAULT 0.58
            """)
            print("confidence_score kolonu eklendi")
        else:
            print("confidence_score kolonu zaten mevcut")

        # 4. İndeksler
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_stats_keyword
            ON synonym_usage_stats(keyword, company_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_match_history_candidate
            ON synonym_match_history(candidate_id, position_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_match_history_keyword
            ON synonym_match_history(keyword, company_id)
        """)
        print("İndeksler oluşturuldu")

        conn.commit()
        print("\nFAZ 10.1 migration başarıyla tamamlandı!")
        return True

    except Exception as e:
        print(f"Migration hatası: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
