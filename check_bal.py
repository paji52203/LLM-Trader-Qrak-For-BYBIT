import asyncio
import ccxt.async_support as ccxt
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
        # Check Spot 
        exchange.options['defaultType'] = 'spot'
        spot_bal = await exchange.fetch_balance()
        spot_usdt = spot_bal.get('USDT', {}).get('free', 0.0)
        
        # Check Futures (UTA)
        exchange.options['defaultType'] = 'swap'
        swap_bal = await exchange.fetch_balance()
        swap_usdt = swap_bal.get('USDT', {}).get('free', 0.0)
        
        print('===============================================')
        print(f'SALDO LAMA (Spot): $ {spot_usdt:,.2f} USDT')
        print(f'SALDO BARU (Futures Margin): $ {swap_usdt:,.2f} USDT')
        print('===============================================')
    except Exception as e:
        print('ERROR:', e)
    finally:
        await exchange.close()

asyncio.run(main())
