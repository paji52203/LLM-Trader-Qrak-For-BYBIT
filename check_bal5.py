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
        'options': {'defaultType': 'linear'}
    })
    
    try:
        # What happens when we call fetch_balance with no params vs swap?
        print('FETCH NO PARAMS:')
        data = await exchange.fetch_balance()
        print('Total:', data.get('total', {}).get('USDT'))
        print('INFO:', data.get('info', {}))
        
        print('\nFETCH PARAMS type=swap:')
        data2 = await exchange.fetch_balance({'type': 'swap'})
        print('Total:', data2.get('total', {}).get('USDT'))
        print('INFO:', data2.get('info', {}))
    except Exception as e:
        print('ERROR:', e)
    finally:
        await exchange.close()

asyncio.run(main())
