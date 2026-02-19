# HyliLabs — Yeni Sunucu Kurulum Rehberi

## Gereksinimler
- Ubuntu 22.04+
- Node.js 18+
- Python 3.10+
- Git

## Kurulum Adimlari

### 1. Repo'yu cek
```bash
git clone https://github.com/osmanemraheroglu/hylilabs.git /var/www/hylilabs
cd /var/www/hylilabs
```

### 2. Python bagimliliklari
```bash
pip install -r requirements.txt
```

### 3. Frontend bagimliliklari ve build
```bash
npm install
npm run build
```

### 4. pm2 kur ve servisleri baslat
```bash
npm install -g pm2
pm2 start ecosystem.config.cjs
pm2 startup
# Cikan komutu kopyala ve calistir
pm2 save
```

### 5. Dogrula
```bash
pm2 list
# hylilabs-frontend (port 3000) online olmali
# hylilabs-backend (port 8000) online olmali

curl http://localhost:3000  # HTTP 200
curl http://localhost:8000  # HTTP 401 (normal, auth gerekli)
```

## Onemli Notlar
- DB dosyasi: `/var/www/hylilabs/api/data/talentflow.db`
- CV dosyalari: `/var/www/hylilabs/api/data/cvs/`
- Bu iki klasor yeni sunucuya manuel tasinmali (git'te yok)
- KVKK uyumu icin Turkiye lokasyonlu sunucu zorunlu

## Servis Yonetimi
| Komut | Aciklama |
|-------|----------|
| `pm2 list` | Servisleri gor |
| `pm2 logs` | Loglari gor |
| `pm2 restart hylilabs-frontend` | Frontend restart |
| `pm2 restart hylilabs-backend` | Backend restart |
| `pm2 stop all` | Tum servisleri durdur |
| `pm2 start ecosystem.config.cjs` | Tum servisleri baslat |

## Sunucu Gereksinimleri
- Min 2GB RAM
- Min 20GB disk
- Port 3000 ve 8000 acik olmali
