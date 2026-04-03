import asyncio
from datetime import datetime
from typing import Dict, Optional, Set, Tuple, Any, TYPE_CHECKING

import ccxt.async_support as ccxt
import aiohttp

from src.logger.logger import Logger
from src.utils.decorators import retry_async

if TYPE_CHECKING:
    from src.config.protocol import ConfigProtocol


class ExchangeManager:
    def __init__(self, logger: Logger, config: "ConfigProtocol"):
        """Initialize ExchangeManager with logger and self.config.

        Args:
            logger: Logger instance
            config: ConfigProtocol instance for exchange settings

        Raises:
            ValueError: If config is None
        """


        self.logger = logger
        self.config = config
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.symbols_by_exchange: Dict[str, Set[str]] = {}
        self.exchange_last_loaded: Dict[str, datetime] = {}
        self._update_task: Optional[asyncio.Task] = None
        self._shutdown_in_progress = False
        self.exchange_config: Dict[str, Any] = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        }
        self.exchange_names = self.config.SUPPORTED_EXCHANGES
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize the session for exchanges - no longer loads all exchanges upfront"""
        self.logger.debug("Initializing ExchangeManager with lazy loading")
        # Create a single session for all exchanges to share
        self.session = aiohttp.ClientSession()
        self.exchange_config['session'] = self.session

        # Start periodic update task, but it will only update already loaded exchanges
        self._update_task = asyncio.create_task(self._periodic_update())
        self._update_task.add_done_callback(self._handle_update_task_done)

    def _handle_update_task_done(self, task):
        if task.exception() and not self._shutdown_in_progress:
            self.logger.error("Periodic update task failed: %s", task.exception())

    async def shutdown(self) -> None:
        """Close all exchanges and stop periodic updates"""
        self._shutdown_in_progress = True

        if self._update_task:
            self.logger.info("Cancelling periodic update task")
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.exception("Error during update task cancellation: %s", e)
            finally:
                self._update_task = None

        self.logger.info("Closing exchange connections")
        for exchange_id, exchange in list(self.exchanges.items()):
            try:
                await exchange.close()
                self.logger.debug("Closed %s connection", exchange_id)
            except Exception as e:
                self.logger.error("Error closing %s connection: %s", exchange_id, e)

        # Close the shared session last, after all exchanges have been closed
        if self.session:
            try:
                self.logger.debug("Closing shared aiohttp session")
                await self.session.close()
            except Exception as e:
                self.logger.error("Error closing shared aiohttp session: %s", e)
            finally:
                self.session = None

        self.exchanges.clear()
        self.symbols_by_exchange.clear()
        self.exchange_last_loaded.clear()
        self.logger.info("ExchangeManager shutdown complete")

    @retry_async()
    async def _load_exchange(self, exchange_id: str) -> Optional[ccxt.Exchange]:
        """Load a single exchange and its markets"""
        self.logger.debug("Loading %s markets", exchange_id)
        try:
            # Create exchange instance with the shared session
            try:
                exchange_class = ccxt.__dict__[exchange_id]
            except KeyError:
                self.logger.error("Failed to load %s: Not found in ccxt", exchange_id)
                return None
            exchange_config = self.exchange_config.copy()

            # Add the session to the config
            if self.session:
                exchange_config['session'] = self.session

            # Authenticate Tokocrypto 
            if exchange_id == "tokocrypto":
                if self.config.TOKOCRYPTO_API_KEY and self.config.TOKOCRYPTO_API_SECRET:
                    exchange_config['apiKey'] = self.config.TOKOCRYPTO_API_KEY
                    exchange_config['secret'] = self.config.TOKOCRYPTO_API_SECRET
                    self.logger.info("Tokocrypto API Keys loaded successfully")
                else:
                    self.logger.warning("Tokocrypto API keys missing. Only public endpoints will work.")
                # Tokocrypto (Binance-based): market buy uses USDT cost, not BTC quantity
                # recvWindow 10000ms agar tidak rejected di laptop lambat (default 5000ms)
                exchange_config['options'] = {
                    'createMarketBuyOrderRequiresPrice': False,
                    'recvWindow': 10000,
                }

            # Authenticate Indodax
            if exchange_id == "indodax":
                if self.config.INDODAX_API_KEY and self.config.INDODAX_API_SECRET:
                    exchange_config['apiKey'] = self.config.INDODAX_API_KEY
                    exchange_config['secret'] = self.config.INDODAX_API_SECRET
                    self.logger.info("Indodax API Keys loaded successfully")
                else:
                    self.logger.warning("Indodax API keys missing. Only public endpoints will work.")

            # Authenticate Bybit
            if exchange_id == "bybit":
                exchange_config['hostname'] = 'bytick.com' # Bypass ISP block
                exchange_config['options'] = {'defaultType': 'swap'} # Linear Perpetual Futures
                if self.config.BYBIT_API_KEY and self.config.BYBIT_API_SECRET:
                    exchange_config['apiKey'] = self.config.BYBIT_API_KEY
                    exchange_config['secret'] = self.config.BYBIT_API_SECRET
                    self.logger.info("Bybit API Keys loaded successfully (Futures Mode)")
                else:
                    self.logger.warning("Bybit API keys missing. Only public endpoints will work.")

            exchange = exchange_class(exchange_config)

            # Enable sandbox / testnet if configured
            if getattr(self.config, 'EXCHANGE_SANDBOX', False):
                if exchange_id == "tokocrypto":
                    self.logger.warning("Tokocrypto does not support Sandbox. Skipping set_sandbox_mode(True).")
                else:
                    self.logger.warning(f"Simulating {exchange_id} in Sandbox/Testnet Environment!")
                    exchange.set_sandbox_mode(True)

            # Patch CCXT Tokocrypto URLs to bypass Indonesian ISP blocking of api.binance.com
            if exchange_id == "tokocrypto" and getattr(exchange, 'urls', {}).get('api'):
                api_urls = exchange.urls['api']
                if 'binance' in api_urls:
                    api_urls['binance'] = 'https://data-api.binance.vision/api/v3'
                if 'rest' in api_urls and 'binance' in api_urls['rest']:
                    api_urls['rest']['binance'] = 'https://data-api.binance.vision/api/v3'

            # Load markets
            await exchange.load_markets()

            # Update tracking
            self.exchanges[exchange_id] = exchange
            self.symbols_by_exchange[exchange_id] = set(exchange.symbols)
            self.exchange_last_loaded[exchange_id] = datetime.now()
            self.logger.debug("Loaded %s with %s symbols", exchange_id, len(exchange.symbols))

            return exchange
        except Exception as e:
            self.logger.error("Failed to load %s markets: %s", exchange_id, e)
            return None

    async def _ensure_exchange_loaded(self, exchange_id: str) -> Optional[ccxt.Exchange]:
        """Ensure exchange is loaded and markets are up to date"""
        now = datetime.now()

        # Check if exchange is already loaded
        if exchange_id in self.exchanges:
            last_loaded = self.exchange_last_loaded.get(exchange_id)

            # Check if refresh is needed (based on MARKET_REFRESH_HOURS)
            if last_loaded and (now - last_loaded).total_seconds() < self.config.MARKET_REFRESH_HOURS * 3600:
                # self.logger.debug("Using cached %s markets", exchange_id)
                return self.exchanges[exchange_id]
            else:
                self.logger.info("Refreshing %s markets (last loaded: %s)", exchange_id, last_loaded)
                await self._refresh_exchange_markets(exchange_id)
                return self.exchanges.get(exchange_id)
        else:
            # Load exchange for the first time
            return await self._load_exchange(exchange_id)

    async def _refresh_exchange_markets(self, exchange_id: str) -> None:
        """Refresh markets for a single exchange"""
        if exchange_id not in self.exchanges:
            return

        exchange = self.exchanges[exchange_id]
        try:
            self.logger.debug("Refreshing %s markets", exchange_id)
            await exchange.load_markets(reload=True)
            self.symbols_by_exchange[exchange_id] = set(exchange.symbols)
            self.exchange_last_loaded[exchange_id] = datetime.now()
            self.logger.info("Refreshed %s with %s symbols", exchange_id, len(exchange.symbols))
        except Exception as e:
            self.logger.error("Failed to refresh %s markets: %s", exchange_id, e)
            # Try to reconnect if refresh fails
            try:
                # Close old exchange connection first
                try:
                    await exchange.close()
                except Exception as e_close:
                    self.logger.warning("Error closing old %s connection: %s", exchange_id, e_close)

                # Create new exchange instance
                new_exchange = await self._load_exchange(exchange_id)
                if not new_exchange:
                    # Remove failed exchange from dicts to avoid using a dead instance
                    self.exchanges.pop(exchange_id, None)
                    self.symbols_by_exchange.pop(exchange_id, None)
                    self.exchange_last_loaded.pop(exchange_id, None)
            except Exception as reconnect_err:
                self.logger.error("Failed to reconnect to %s: %s", exchange_id, reconnect_err)
                # Remove failed exchange from dicts to avoid using a dead instance
                self.exchanges.pop(exchange_id, None)
                self.symbols_by_exchange.pop(exchange_id, None)
                self.exchange_last_loaded.pop(exchange_id, None)

    async def _periodic_update(self) -> None:
        """Periodically refresh markets for loaded exchanges only"""
        while not self._shutdown_in_progress:
            try:
                # Only refresh exchanges that are already loaded
                loaded_exchanges = list(self.exchanges.keys())
                if loaded_exchanges:
                    self.logger.info("Checking %s loaded exchanges for periodic refresh", len(loaded_exchanges))

                    for exchange_id in loaded_exchanges:
                        await self._refresh_exchange_markets(exchange_id)
                else:
                    pass
                    # self.logger.debug("No exchanges loaded yet, skipping periodic refresh")

                # Wait for next update cycle
                sleep_hours = self.config.MARKET_REFRESH_HOURS
                self.logger.debug("Next periodic update in %s hours", sleep_hours)
                await asyncio.sleep(sleep_hours * 3600)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in periodic update: %s", e)
                await asyncio.sleep(300)  # Wait 5 minutes before retrying on error

    async def find_symbol_exchange(self, symbol: str) -> Tuple[Optional[ccxt.Exchange], Optional[str]]:
        """Find the first exchange that supports the given symbol using lazy loading"""
        # self.logger.debug("Looking for symbol %s across exchanges", symbol)

        for exchange_id in self.exchange_names:
            try:
                # Check if we already have this exchange loaded and symbol cached
                if exchange_id in self.symbols_by_exchange and symbol in self.symbols_by_exchange[exchange_id]:
                    exchange = self.exchanges.get(exchange_id)
                    if exchange:
                        self.logger.debug("Found %s in cached %s markets", symbol, exchange_id)
                        return exchange, exchange_id

                # Try to load/refresh the exchange to check for the symbol
                exchange = await self._ensure_exchange_loaded(exchange_id)
                if exchange and exchange_id in self.symbols_by_exchange:
                    if symbol in self.symbols_by_exchange[exchange_id]:
                        self.logger.info("Found %s on %s", symbol, exchange_id)
                        return exchange, exchange_id
                    else:
                        # self.logger.debug("Symbol %s not found on %s", symbol, exchange_id)
                        pass

            except Exception as e:
                self.logger.error("Error checking %s for symbol %s: %s", exchange_id, symbol, e)
                continue

        self.logger.warning("Symbol %s not found on any supported exchange", symbol)
        return None, None

    def get_all_symbols(self) -> Set[str]:
        """Get all unique symbols across all loaded exchanges"""
        all_symbols = set()
        for symbols in self.symbols_by_exchange.values():
            all_symbols.update(symbols)
        return all_symbols

    async def fetch_wallet_balance(self, exchange_id: str, currency: str) -> float:
        """Fetch real free balance for a specific currency."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return 0.0
            if not getattr(exchange, 'apiKey', None):
                self.logger.warning(f"Cannot fetch balance on {exchange_id}: API keys not set.")
                return 0.0

            # Bybit V5 Unified Trading Account (UTA) support
            params = {}
            if exchange_id == "bybit":
                params['accountType'] = 'UNIFIED'
                # Note: 'category' is usually not needed for fetch_balance in UTA, 
                # but 'accountType' is mandatory for V5.
                
            balance = await exchange.fetch_balance(params)
            
            # Check for UTA specific structure or standard CCXT structure
            if currency in balance and 'free' in balance[currency]:
                return float(balance[currency]['free'])
            
            # Fallback for total balance if 'free' is not populated as expected in UTA
            if currency in balance and 'total' in balance[currency]:
                return float(balance[currency]['total'])
                
            return 0.0
        except Exception as e:
            self.logger.error("Failed to fetch balance: %s", e)
            return 0.0

    async def get_balance(self, currency: str) -> float:
        """Convenience alias used by app.py to fetch wallet balance from the primary exchange."""
        primary_exchange = self.exchange_names[0] if self.exchange_names else "bybit"
        return await self.fetch_wallet_balance(primary_exchange, currency)

    def _get_market_limits(self, exchange: Any, symbol: str) -> tuple:
        """Return (min_amount, min_notional) from market info, with safe fallbacks.

        Returns:
            (min_amount, min_notional): floats. min_amount is minimum qty,
            min_notional is minimum USDT order value.
        """
        try:
            markets = getattr(exchange, 'markets', {})
            market = markets.get(symbol, {})
            limits = market.get('limits', {})
            min_amount   = limits.get('amount', {}).get('min') or 0.00001
            min_notional = limits.get('cost',   {}).get('min') or 10.0  # 10 USDT fallback
            return float(min_amount), float(min_notional)
        except Exception:
            return 0.00001, 10.0

    async def create_market_buy_order(
        self, exchange_id: str, symbol: str, amount: float, quote_amount: float = 0.0
    ) -> Optional[Dict]:
        """Execute a REAL live market buy order. WARNING: SPENDS ACTUAL FUNDS."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            # 1. Tentukan Biaya (Cost) yang akan divalidasi
            if exchange_id == "tokocrypto":
                cost = quote_amount if quote_amount > 0 else amount
            else:
                # Bybit (Futures): amount adalah Qty BTC.
                if quote_amount > 0:
                    cost = quote_amount
                else:
                    ticker = await exchange.fetch_ticker(symbol)
                    price = float(ticker.get('last', 0))
                    cost = amount * price

            # 2. Validasi minimum order value (min notional)
            _, min_notional = self._get_market_limits(exchange, symbol)
            if cost < min_notional:
                self.logger.warning(
                    f"BUY skipped: Order value ${cost:.2f} USDT is below exchange minimum "
                    f"${min_notional:.2f} USDT for {symbol}. Increase capital allocation."
                )
                return None

            # 3. Eksekusi
            self.logger.critical(f"LIVE EXECUTION: Creating Market BUY {amount} of {symbol} on {exchange_id}")
            
            params = {}
            if exchange_id == "bybit":
                params['category'] = 'linear'
            
            order = await exchange.create_market_buy_order(symbol, amount, params)
            self.logger.info(f"Live BUY order filled: {order.get('id', 'N/A')} @ avg {order.get('average', 'N/A')}")
            return order
        except Exception as e:
            self.logger.error("Live BUY order failed: %s", e)
            return None

    async def create_limit_buy_order(self, exchange_id: str, symbol: str, amount: float, price: float) -> Optional[Dict]:
        """Execute a REAL live limit buy order."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            # Validasi minimum order value (qty * price)
            cost = amount * price
            _, min_notional = self._get_market_limits(exchange, symbol)
            
            if cost < min_notional:
                self.logger.warning(f"LIMIT BUY skipped: Value ${cost:.2f} USDT is below minimum ${min_notional:.2f} USDT")
                return None

            self.logger.critical(f"LIVE EXECUTION: Creating Limit BUY {amount} {symbol} @ ${price:.2f} on {exchange_id}")
            
            params = {'category': 'linear'} if exchange_id == "bybit" else {}
            order = await exchange.create_limit_buy_order(symbol, amount, price, params)
            self.logger.info(f"Live Limit BUY order placed: {order.get('id', 'N/A')}")
            return order
        except Exception as e:
            self.logger.error("Live Limit BUY failed: %s", e)
            return None

    async def create_market_sell_order(self, exchange_id: str, symbol: str, amount: float) -> Optional[Dict]:
        """Execute a REAL live market sell order."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None
            
            is_futures = exchange.options.get('defaultType') in ['future', 'swap', 'linear']
            
            if not is_futures:
                # Cek saldo base currency (BTC) sebelum jual di SPOT
                base_currency = symbol.split('/')[0]
                available = await self.fetch_wallet_balance(exchange_id, base_currency)
                if available <= 0:
                    self.logger.warning(f"SELL skipped: No {base_currency} balance to sell on {exchange_id}.")
                    return None
                sell_amount = min(amount, available * 0.999)
            else:
                sell_amount = amount

            # Validasi minimum Qty
            min_amount, _ = self._get_market_limits(exchange, symbol)
            if sell_amount < min_amount:
                self.logger.warning(f"SELL skipped: {sell_amount:.8f} < min {min_amount}")
                return None

            self.logger.critical(f"LIVE EXECUTION: Creating Market SELL for {sell_amount:.8f} {symbol} on {exchange_id}")
            
            params = {'category': 'linear'} if exchange_id == "bybit" else {}
            order = await exchange.create_market_sell_order(symbol, sell_amount, params)
            self.logger.info(f"Live SELL order filled: {order.get('id', 'N/A')}")
            return order
        except Exception as e:
            self.logger.error("Live SELL order failed: %s", e)
            return None

    async def create_limit_sell_order(self, exchange_id: str, symbol: str, amount: float, price: float) -> Optional[Dict]:
        """Execute a REAL live limit sell order."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            self.logger.critical(f"LIVE EXECUTION: Creating Limit SELL {amount:.8f} {symbol} @ ${price:.2f} on {exchange_id}")
            
            params = {'category': 'linear'} if exchange_id == "bybit" else {}
            order = await exchange.create_limit_sell_order(symbol, amount, price, params)
            self.logger.info(f"Live Limit SELL placed: {order.get('id', 'N/A')}")
            return order
        except Exception as e:
            self.logger.error("Live Limit SELL failed: %s", e)
            return None

    async def set_leverage(self, exchange_id: str, symbol: str, leverage: int) -> bool:
        """
        Set leverage for a specific symbol on Bybit Futures.
        
        CRITICAL GUARDRAILS:
        1. Ensures Isolated Margin mode.
        2. Prevents leverage change if a position is already open.
        3. Handles LeverageNotModified exception.
        """
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange or exchange_id != "bybit":
                return False

            # Ensure symbol format for Bybit Linear Futures (V5 requires category=linear)
            # CCXT usually maps BTC/USDT to BTCUSDT or BTC/USDT:USDT for futures
            market = exchange.market(symbol)
            is_linear = market.get('linear', True)
            category = 'linear' if is_linear else 'inverse'

            # GUARDRAIL 1: Ensure Isolated Margin mode
            try:
                # Bybit V5: set_margin_mode('ISOLATED', symbol, {'category': category, 'leverage': leverage})
                await exchange.set_margin_mode('ISOLATED', symbol, {'category': category, 'leverage': leverage})
                self.logger.info(f"Enforced Isolated Margin for {symbol} on Bybit ({category})")
            except Exception as e:
                # Often fails if already isolated, we check the message
                if "already in isolated margin" in str(e).lower() or "margin mode not modified" in str(e).lower():
                    self.logger.debug(f"Margin mode already isolated or no change for {symbol}")
                else:
                    self.logger.warning(f"Could not explicitly set margin mode: {e}")

            # GUARDRAIL 2: Check for existing open positions
            # In Bybit, we cannot change leverage if there is an active position
            try:
                # V5 requires category
                positions = await exchange.fetch_positions([symbol], {'category': category})
                for pos in positions:
                    size = float(pos.get('contracts', 0) or pos.get('size', 0))
                    if size > 0:
                        self.logger.warning(
                            f"LEVERAGE GUARDRAIL: Open position detected for {symbol} (size={size}). "
                            "Refusing to change leverage to avoid liquidation risk."
                        )
                        return False
            except Exception as e:
                self.logger.error(f"Failed to check positions before setting leverage: {e}")

            # ACTUAL LEVERAGE UPDATE
            self.logger.info(f"Setting leverage for {symbol} to {leverage}x (category={category})...")
            await exchange.set_leverage(leverage, symbol, {'category': category})
            self.logger.info(f"Leverage successfully set to {leverage}x for {symbol}")
            return True

        except Exception as e:
            msg = str(e).lower()
            # GUARDRAIL 3: Handle LeverageNotModified
            if "leverage not modified" in msg or "not changed" in msg:
                self.logger.info(f"Leverage for {symbol} is already {leverage}x. No update needed.")
                return True
            else:
                self.logger.error(f"Failed to set leverage for {symbol}: {e}")
                return False

