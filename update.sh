#!/bin/bash
set -e

# Stop all existing bot processes
echo "🛑 Stopping all existing bot processes..."
pkill -9 -f "python3 start.py" 2>/dev/null || true
pkill -9 -f "run.sh" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 2

# Pull latest changes from GitHub (always fast-forward, never fail)
echo "📥 Pulling latest changes from GitHub..."
git config pull.ff only
git fetch origin
git reset --hard origin/master

# Make sure run.sh is executable
chmod +x run.sh

# Open port 8000 if ufw is active (DigitalOcean VPS)
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    echo "🔓 Opening port 8000 in UFW firewall..."
    ufw allow 8000/tcp 2>/dev/null || true
fi

# Start the bot in background
echo "🚀 Starting the bot..."
nohup ./run.sh > nohup.out 2>&1 &
BOT_PID=$!
sleep 3

# Verify bot started
if kill -0 $BOT_PID 2>/dev/null; then
    echo "✅ Bot started (PID: $BOT_PID)"
    echo "📊 Dashboard: http://$(hostname -I | awk '{print $1}'):8000"
    echo "📄 Logs: tail -f logs/Bot/$(date +%Y_%m_%d)/Bot.log"
    echo "📄 nohup log: tail -f nohup.out"
else
    echo "❌ Bot failed to start! Check: cat nohup.out"
    exit 1
fi
