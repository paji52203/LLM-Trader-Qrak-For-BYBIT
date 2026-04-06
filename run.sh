#!/bin/bash

# Folder environment
VENV_DIR=".venv"

echo "🔄 Memeriksa Virtual Environment..."
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Membuat Virtual Environment baru..."
    python3.11 -m venv $VENV_DIR
    echo "📥 Install dependensi..."
    source $VENV_DIR/bin/activate
    pip3 install -r requirements.txt
fi

# 1. Bunuh instance lama jika dulu dijalankan manual (tanpa PM2)
pkill -f "python3 start.py" 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
sleep 1

# 2. Cek apakah bot sudah berjalan di PM2
if pm2 list 2>/dev/null | grep -q "bybit-bot"; then
    echo "🔄 Bot sudah ada di PM2. Merestart bybit-bot agar update..."
    pm2 restart bybit-bot
else
    echo "🚀 Meluncurkan bybit-bot pertama kali via PM2 (Background)..."
    pm2 start "$(pwd)/$VENV_DIR/bin/python3 start.py" \
      --name 'bybit-bot' \
      --cwd "$(pwd)" \
      --log "$(pwd)/logs/pm2.log" \
      --error "$(pwd)/logs/pm2_error.log" \
      --restart-delay 5000 \
      --max-restarts 10
    pm2 save
fi

echo ""
echo "✅ Bot sekarang berjalan AMAN di latar belakang (Background)!"
echo "--------------------------------------------------------"
echo "➡️  Cek log langsung : pm2 logs bybit-bot"
echo "➡️  Hentikan bot     : pm2 stop bybit-bot"
echo "➡️  Restart bot      : pm2 restart bybit-bot"
echo "➡️  Status bot       : pm2 status"
echo "--------------------------------------------------------"
