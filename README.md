# LLM Trader Qrak for BYBIT 🚀

An advanced, AI-driven, fully autonomous futures trading bot specifically adapted for **Bybit Unified Trading Account (UTA) V5**. 

This is a heavily modified and modernized fork of the original [qrak / LLM_trader](https://github.com/qrak/LLM_trader). We've taken the brilliant LLM processing foundation and re-architected the execution, risk management, and live dashboard systems for serious Bybit futures scalping.

*Adapted and optimized for Bybit V5 by **Antigravity** (Main Contributor for Bybit Fork).*

---

## 🌟 What makes this Fork different?

While the original `LLM_trader` offers a great starting point for algorithmic crypto analysis, **LLM Trader Qrak for BYBIT** introduces several enterprise-grade features necessary for live, high leverage futures trading:

1. **CCXT Bybit V5 Live Execution Pipeline**
   - Removed Indodax/Tokocrypto mock dependencies.
   - Fully integrated live `Marketable Limit` Long/Short execution on Bybit Futures.
   - Dynamic API leverage assignment.

2. **Fee-Awareness AI Guardrails**
   - The AI is structurally injected with knowledge of Maker/Taker round-trip fees (0.12%+).
   - Prevents the bot from prematurely closing profitable positions that would otherwise be eaten by exchange fees (Micro-profit avoidance).

3. **Dynamic Structural Trailing Stop-Loss**
   - Uses Stealth **Soft-Stops** (Stop limits hidden securely in your VPS database to prevent Bybit market makers from *stop-hunting*).
   - Real-time `UPDATE` signals allow the AI to actively trail the Stop Loss into deep profit as the market structure changes.

4. **[Emergency] 1-Second WebSocket Alarm**
   - *The Blindspot Fix:* Standard LLM bots sleep heavily between candle intervals (e.g., 15 minutes). If a flash crash occurs at minute 8, you lose.
   - We integrated a continuous Bybit WebSocket connection that acts as a 1-second radar. If prices violently spike through your Soft Stop, the WebSocket emergency interrupts the bot's sleep and executes an immediate Market Close.

5. **Modernized Sticky Dashboard**
   - Re-designed the frontend live web dashboard (`http://your-vps:8000`).
   - Sticky header, Countdown timers, and real-time PNL visualization syncing via Websockets.

---

## 🛠️ Quick Start & Installation

We provide an automated installation script that securely provisions a virtual Python environment and installs dependencies.

```bash
# 1. Clone this repository
git clone https://github.com/yourusername/LLM-Trader-Qrak-For-BYBIT.git
cd LLM-Trader-Qrak-For-BYBIT

# 2. Run the automated installer
./install.sh

# 3. Configure your API Keys
nano .env 
# (Insert your Bybit API keys & LLM Provider keys here)

# 4. Start the Bot manually to verify
source .venv/bin/activate
python start.py
```

### Background Execution (VPS / 24-7 Running)
For production trading, it's highly recommended to use `pm2` so the bot stays alive when you disconnect SSH.

```bash
# Ensure pm2 is installed: npm install -g pm2
pm2 start start.py --name bybit-bot --interpreter .venv/bin/python
pm2 logs bybit-bot
```

## 📜 Credits & Acknowledgements
- **Original Architecture & AI Logic:** Huge thanks to **[@qrak](https://github.com/qrak/LLM_trader)** for the foundational LLM RAG trading conceptualization.
- **Bybit V5 Execution, WebSocket, & Advanced Risk System Architect:** **Antigravity**.

*Disclaimer: Cryptocurrency trading is extremely risky. Use this bot at your own peril. Do not test with live money without understanding leverage and API risk mechanics.*
