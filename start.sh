#!/data/data/com.termux/files/usr/bin/bash
# =============================================
# START SCRIPT - Bot Menfess Telegram (Termux)
# =============================================

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BOT_DIR"

# Warna output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🤖 Bot Menfess Telegram${NC}"
echo "================================"

# Cek Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 tidak ditemukan!${NC}"
    echo "Install: pkg install python"
    exit 1
fi

# Cek .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}⚠️  File .env belum ada!${NC}"
        echo "Salin dan edit konfigurasi:"
        echo "  cp .env.example .env"
        echo "  nano .env"
    else
        echo -e "${RED}❌ File .env tidak ditemukan!${NC}"
    fi
    exit 1
fi

# Cek & install dependencies
echo -e "${YELLOW}📦 Mengecek dependencies...${NC}"
if ! python3 -c "import pyrogram" 2>/dev/null; then
    echo "Menginstall dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Gagal install dependencies!${NC}"
        exit 1
    fi
fi

if ! python3 -c "import dotenv" 2>/dev/null; then
    pip install python-dotenv
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"
echo "================================"
echo "Memulai bot... (Ctrl+C untuk stop)"
echo ""

# Jalankan bot
python3 main.py
