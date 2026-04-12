#!/usr/bin/env python3
"""Position sync script - fetches actual positions from Bybit and updates bot state"""
import asyncio
import json
import os
import sys

# Add project to path
sys.path.insert(0, '/root/bot_bybit')

from src.platforms.exchange_manager import ExchangeManager

async def sync_position():
    """Sync bot's internal position state with actual Bybit positions"""
    print("Starting position sync...")
    
    exchange_manager = ExchangeManager()
    await exchange_manager.initialize()
    
    try:
        # Fetch actual positions from Bybit
        positions = await exchange_manager.get_open_positions(symbol='BTC/USDT:USDT')
        
        print(f"Found {len(positions)} open position(s) on Bybit:")
        
        if positions:
            for pos in positions:
                side = pos.get('side', 'N/A')
                size = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                print(f"  - Side: {side}, Size: {size}, Entry: ${entry}, PNL: ${pnl}")
            
            # Save to current_position.json for bot to read
            position_data = {
                'symbol': 'BTC/USDT:USDT',
                'side': positions[0].get('side', 'N/A'),
                'size': positions[0].get('contracts', 0),
                'entry_price': positions[0].get('entry_price', 0),
                'unrealized_pnl': positions[0].get('unrealized_pnl', 0),
            }
            
            os.makedirs('data/trading', exist_ok=True)
            filepath = 'data/trading/current_position.json'
            with open(filepath, 'w') as f:
                json.dump(position_data, f, indent=2)
            
            print(f"\n✅ Position saved to {filepath}")
        else:
            print("No open positions found on Bybit.")
            # Clear any stale position file
            filepath = 'data/trading/current_position.json'
            if os.path.exists(filepath):
                os.remove(filepath)
                print("Cleared stale position file.")
    
    except Exception as e:
        print(f"❌ Position sync failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange_manager.close()
    
    print("Position sync completed.")

if __name__ == '__main__':
    asyncio.run(sync_position())
