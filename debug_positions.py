#!/usr/bin/env python3
import asyncio
import os
import ccxt.async_support as ccxt
import json

async def debug():
    api_key = os.getenv('BYBIT_API_KEY', '')
    api_secret = os.getenv('BYBIT_API_SECRET', '')
    
    print(f"API Key: {api_key[:8]}...")
    print(f"API Secret: {api_secret[:8]}...")
    
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
        
        # Fetch all positions
        positions = await exchange.fetch_positions()
        
        print(f"\nTotal positions returned: {len(positions)}")
        
        for i, pos in enumerate(positions):
            print(f"\n--- Position {i+1} ---")
            print(f"Symbol: {pos.get('symbol', 'N/A')}")
            print(f"Full data: {json.dumps(pos, indent=2, default=str)}")
        
        # Also try specific symbol
        print("\n\n=== Fetching BTC/USDT:USDT specifically ===")
        btc_positions = await exchange.fetch_positions(symbols=['BTC/USDT:USDT'])
        print(f"BTC positions count: {len(btc_positions)}")
        for i, pos in enumerate(btc_positions):
            print(f"\n--- BTC Position {i+1} ---")
            print(f"Symbol: {pos.get('symbol', 'N/A')}")
            print(f"Full data: {json.dumps(pos, indent=2, default=str)}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()

asyncio.run(debug())
