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
        swap_bal = await exchange.fetch_balance()
        print('AVAILABLE USDT (free):', swap_bal.get('USDT', {}).get('free'))
        print('TOTAL USDT:', swap_bal.get('total', {}).get('USDT'))
        print('ALL TOTALS:', json.dumps(swap_bal.get('total', {})))
    except Exception as e:
        print('ERROR:', e)
    finally:
        await exchange.close()

asyncio.run(main())
