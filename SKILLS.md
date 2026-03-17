# HyliLabs — Özel Yetenekler

## Deploy

Deploy komutları sunucuya SSH ile bağlanarak çalıştırılır.
Detaylar için deployment dokümantasyonuna bakınız.

```bash
# Backend restart
pm2 restart hylilabs-api

# Frontend build + restart
npm run build && pm2 restart hylilabs-frontend

# Her ikisi
pm2 restart all
```

## Git Workflow
```bash
# Geliştirme
git checkout dev
# ... değişiklik yap ...
git add -A && git commit -m "feat: açıklama"
git checkout main && git merge dev
git push origin main

# Sunucuda
cd /var/www/hylilabs && git pull
```

## Database
- Konum: /var/www/hylilabs/api/data/talentflow.db (SQLite, 41MB)
- Backup: cp data/talentflow.db data/talentflow_backup_$(date +%Y%m%d).db
- Tablo listesi: 37 tablo (candidates, positions, department_pools, companies, users, matches, ...)
- Pool tablosu: department_pools (pools değil!)

## Test
```bash
cd /var/www/hylilabs/api
python3 test_core.py
```

## CV Parse
- Claude API ile parse ediliyor (cv_parser.py)
- ANTHROPIC_API_KEY .env'de
- Parse sonucu candidates tablosuna yazılır
- Otomatik matching: CV parse sonrası scoring_v2 çalışır

## Email CV Toplama
- IMAP ile email okuma (email_reader.py)
- CV ekleri otomatik parse (email_worker.py)
- Cron ile periyodik kontrol
