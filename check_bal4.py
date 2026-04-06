import asyncio
import ccxt.async_support as ccxt
import json
from src.config.loader import Config

async def main():
    config = Config()
    exchange = ccxt.bybit({
        'apiKey': config.BYBIT_API_KEY,
        'secret': config.BYBIT_API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })
    
    try:
        data = await exchange.fetch_balance()
        print('USDT free:', data.get('USDT', {}).get('free'))
        print('USDT total:', data.get('total', {}).get('USDT'))
    except Exception as e:
        print('ERROR:', e)
    finally:
        await exchange.close()

asyncio.run(main())
