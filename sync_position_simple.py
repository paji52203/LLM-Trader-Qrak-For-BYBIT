#!/usr/bin/env python3
"""Simple position sync using CCXT directly"""
import asyncio
import json
import os
import ccxt.async_support as ccxt

async def sync_position():
    print("Starting position sync (simple)...")
    
    api_key = os.getenv('BYBIT_API_KEY', '')
    api_secret = os.getenv('BYBIT_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("❌ Error: BYBIT_API_KEY or BYBIT_API_SECRET not set in .env")
        return
    
    print(f"Using API Key: {api_key[:8]}...")
    
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
            'accountType': 'unified',
        },
    })
    
    try:
        await exchange.load_markets()
        positions = await exchange.fetch_positions(symbols=['BTC/USDT:USDT'])
        
        print(f"Found {len(positions)} position record(s) from Bybit")
        
        # Filter: hanya posisi yang benar-benar terbuka (size > 0 dan side valid)
        open_positions = []
        for pos in positions:
            side = pos.get('side')
            contracts = pos.get('contracts', 0)
            
            if side and contracts and contracts > 0:
                open_positions.append(pos)
                print(f"  ✅ OPEN: Side={side}, Size={contracts}, Entry=${pos.get('entryPrice')}, PNL=${pos.get('unrealizedPnl')}")
            else:
                print(f"  ℹ️  EMPTY: No open position (side={side}, contracts={contracts})")
        
        if open_positions:
            pos = open_positions[0]
            position_data = {
                'symbol': 'BTC/USDT:USDT',
                'side': pos.get('side', 'N/A'),
                'size': pos.get('contracts', 0),
                'entry_price': pos.get('entryPrice', 0),
                'unrealized_pnl': pos.get('unrealizedPnl', 0),
            }
            
            os.makedirs('data/trading', exist_ok=True)
            filepath = 'data/trading/current_position.json'
            with open(filepath, 'w') as f:
                json.dump(position_data, f, indent=2)
            
            print(f"\n✅ Position saved to {filepath}")
        else:
            filepath = 'data/trading/current_position.json'
            if os.path.exists(filepath):
                os.remove(filepath)
                print("\n✅ Cleared stale position file.")
            else:
                print("\n✅ No position file exists (clean state).")
    
    except Exception as e:
        print(f"❌ Position sync failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()
    
    print("Position sync completed.")

if __name__ == '__main__':
    asyncio.run(sync_position())
