#!/usr/bin/env python3
"""Günlük otomatik arşiv - 30 gün geçmiş + pozisyona atanmamış adayları arşive taşı"""
import sys
sys.path.insert(0, '/var/www/talentflow')

from database import auto_archive_old_candidates, get_all_companies

def main():
    companies = get_all_companies()
    for company in companies:
        result = auto_archive_old_candidates(company['id'])
        if result['archived'] > 0:
            print(f"[{company['name']}] {result['archived']} aday arşive taşındı")

if __name__ == '__main__':
    main()
