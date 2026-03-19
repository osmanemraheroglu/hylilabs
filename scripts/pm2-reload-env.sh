#!/bin/bash
# ============================================================================
# PM2 ENV Reload Script - HyliLabs
# ============================================================================
# PM2, process baslatildiginda .env dosyasini CACHE'ler.
# "pm2 restart" ENV degisikliklerini YUKLEMEZ.
# Bu script pm2 delete + pm2 start yaparak ENV'yi yeniler.
#
# Kullanim:
#   ./scripts/pm2-reload-env.sh           # Sadece backend
#   ./scripts/pm2-reload-env.sh all       # Frontend + Backend
#   ./scripts/pm2-reload-env.sh test      # ENV test (reload yok)
# ============================================================================

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Dizin
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
API_DIR="$PROJECT_DIR/api"
ENV_FILE="$API_DIR/.env"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   PM2 ENV Reload Script - HyliLabs${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# .env dosyasi kontrol
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}HATA: .env dosyasi bulunamadi: $ENV_FILE${NC}"
    exit 1
fi

# Kritik ENV degiskenleri listesi
CRITICAL_ENVS=(
    "ANTHROPIC_API_KEY"
    "OPENAI_API_KEY"
    "GEMINI_API_KEY"
    "HERMES_API_KEY"
    "JWT_SECRET"
    "SECRET_KEY"
    "ENV"
)

# ENV degerlerini goster (maskelemeli)
show_env_values() {
    echo -e "${YELLOW}Kritik ENV Degiskenleri (.env dosyasindan):${NC}"
    echo ""
    for var in "${CRITICAL_ENVS[@]}"; do
        value=$(grep "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
        if [ -n "$value" ]; then
            # Ilk 8 ve son 4 karakteri goster, ortasi ***
            if [ ${#value} -gt 16 ]; then
                masked="${value:0:8}***${value: -4}"
            else
                masked="${value:0:4}***"
            fi
            echo -e "  ${GREEN}$var${NC} = $masked"
        else
            echo -e "  ${RED}$var${NC} = (tanimlanmamis)"
        fi
    done
    echo ""
}

# PM2 durumunu goster
show_pm2_status() {
    echo -e "${YELLOW}PM2 Process Durumu:${NC}"
    pm2 list 2>/dev/null || echo "  PM2 calistirmada hata"
    echo ""
}

# Test modu
if [ "$1" == "test" ]; then
    echo -e "${BLUE}[TEST MODU] ENV degerleri gosteriliyor, reload yapilmayacak${NC}"
    echo ""
    show_env_values
    show_pm2_status
    exit 0
fi

# Reload islemleri
reload_backend() {
    echo -e "${YELLOW}[1/3] Backend process siliniyor...${NC}"
    pm2 delete hylilabs-backend 2>/dev/null || echo "  (Process zaten yok)"

    echo -e "${YELLOW}[2/3] Backend baslatiliyor (yeni ENV ile)...${NC}"
    cd "$PROJECT_DIR"
    pm2 start ecosystem.config.cjs --only hylilabs-backend

    echo -e "${YELLOW}[3/3] Backend API testi...${NC}"
    sleep 3

    # Health check
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
    if [ "$response" == "200" ]; then
        echo -e "  ${GREEN}Backend basariyla basladi (HTTP 200)${NC}"
    else
        echo -e "  ${RED}UYARI: Backend yanit vermiyor (HTTP $response)${NC}"
        echo -e "  ${YELLOW}Log kontrol: pm2 logs hylilabs-backend --lines 20${NC}"
    fi
}

reload_frontend() {
    echo -e "${YELLOW}[1/2] Frontend process siliniyor...${NC}"
    pm2 delete hylilabs-frontend 2>/dev/null || echo "  (Process zaten yok)"

    echo -e "${YELLOW}[2/2] Frontend baslatiliyor...${NC}"
    cd "$PROJECT_DIR"
    pm2 start ecosystem.config.cjs --only hylilabs-frontend

    sleep 2
    echo -e "  ${GREEN}Frontend baslatildi${NC}"
}

# Islem secimi
echo -e "${YELLOW}Mevcut ENV degerleri:${NC}"
show_env_values

if [ "$1" == "all" ]; then
    echo -e "${BLUE}Tum processler reload ediliyor...${NC}"
    echo ""
    reload_backend
    echo ""
    reload_frontend
else
    echo -e "${BLUE}Sadece backend reload ediliyor...${NC}"
    echo ""
    reload_backend
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Reload tamamlandi${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
show_pm2_status

echo -e "${YELLOW}Faydali komutlar:${NC}"
echo "  pm2 logs hylilabs-backend --lines 50    # Backend loglari"
echo "  pm2 monit                                # Canli izleme"
echo "  curl http://localhost:8000/api/health   # API testi"
echo ""
