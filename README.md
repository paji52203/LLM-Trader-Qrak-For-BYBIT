# Bybit Trading Bot: Execution Fix (Notional & Real-time)

This repository contains the fixed files to resolve the Bybit Futures trading issues including the $10 notional validation and real-time trade tracking.

## 🚀 Key Fixes
1.  **Bybit WebSocket**: Real-time price tracking using the `bytick.com` domain (ISP bypass).
2.  **Notional Validation**: Corrected the BTC quantity vs USDT threshold comparison.
3.  **Marketable Limit Orders**: Replaced market orders with limit orders (0.05% offset) for better fill rates.
4.  **Graceful Shutdown**: Added proper WebSocket cleanup on exit.

## 🏃 How to Apply (to VPS)
1.  **Clone this repo** somewhere on your VPS:
    `git clone https://github.com/paji52203/bybit-execution-fix.git ~/bybit-fix`
2.  **Run the apply script** (it will backup your files first):
    `cd ~/bybit-fix && chmod +x apply_fixes.sh && ./apply_fixes.sh /path/to/your/main/bot/folder`
