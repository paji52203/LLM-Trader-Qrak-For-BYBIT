"""Exchange Manager — Bybit Futures (USDT Perpetual / Linear) edition."""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Set, Tuple, Any, List, TYPE_CHECKING

import ccxt.async_support as ccxt
import aiohttp

from src.logger.logger import Logger
from src.utils.decorators import retry_async

if TYPE_CHECKING:
    from src.config.protocol import ConfigProtocol


class ExchangeManager:
    def __init__(self, logger: Logger, config: "ConfigProtocol"):
        self.logger = logger
        self.config = config
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.symbols_by_exchange: Dict[str, Set[str]] = {}
        self.exchange_last_loaded: Dict[str, datetime] = {}
        self._update_task: Optional[asyncio.Task] = None
        self._shutdown_in_progress = False
        self.exchange_config: Dict[str, Any] = {
            'enableRateLimit': True,
        }
        self.exchange_names = self.config.SUPPORTED_EXCHANGES
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        self.logger.debug("Initializing ExchangeManager (Bybit Futures mode)")
        self.session = aiohttp.ClientSession()
        self.exchange_config['session'] = self.session
        self._update_task = asyncio.create_task(self._periodic_update())
        self._update_task.add_done_callback(self._handle_update_task_done)

    def _handle_update_task_done(self, task):
        if task.exception() and not self._shutdown_in_progress:
            self.logger.error("Periodic update task failed: %s", task.exception())

    async def shutdown(self) -> None:
        self._shutdown_in_progress = True
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            finally:
                self._update_task = None

        for exchange_id, exchange in list(self.exchanges.items()):
            try:
                await exchange.close()
            except Exception as e:
                self.logger.error("Error closing %s: %s", exchange_id, e)

        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                self.logger.error("Error closing session: %s", e)
            finally:
                self.session = None

        self.exchanges.clear()
        self.symbols_by_exchange.clear()
        self.exchange_last_loaded.clear()
        self.logger.info("ExchangeManager shutdown complete")

    @retry_async()
    async def _load_exchange(self, exchange_id: str) -> Optional[ccxt.Exchange]:
        self.logger.debug("Loading %s markets", exchange_id)
        try:
            try:
                exchange_class = ccxt.__dict__[exchange_id]
            except KeyError:
                self.logger.error("Exchange not found in ccxt: %s", exchange_id)
                return None

            exchange_config = self.exchange_config.copy()
            if self.session:
                exchange_config['session'] = self.session

            # ── Bybit Futures (USDT Linear Perpetual) ──
            if exchange_id == "bybit":
                if self.config.BYBIT_API_KEY and self.config.BYBIT_API_SECRET:
                    exchange_config['apiKey'] = self.config.BYBIT_API_KEY
                    exchange_config['secret'] = self.config.BYBIT_API_SECRET
                    self.logger.info("Bybit API Keys loaded successfully")
                else:
                    self.logger.warning("Bybit API keys missing — public data only")

                exchange_config['options'] = {
                    'defaultType': 'linear',   # USDT perpetual futures
                    'recvWindow': 10000,
                }

            exchange = exchange_class(exchange_config)
            await exchange.load_markets()

            self.exchanges[exchange_id] = exchange
            self.symbols_by_exchange[exchange_id] = set(exchange.symbols)
            self.exchange_last_loaded[exchange_id] = datetime.now()
            self.logger.debug("Loaded %s with %s symbols", exchange_id, len(exchange.symbols))
            return exchange

        except Exception as e:
            self.logger.error("Failed to load %s: %s", exchange_id, e)
            return None

    async def _ensure_exchange_loaded(self, exchange_id: str) -> Optional[ccxt.Exchange]:
        now = datetime.now()
        if exchange_id in self.exchanges:
            last_loaded = self.exchange_last_loaded.get(exchange_id)
            if last_loaded and (now - last_loaded).total_seconds() < self.config.MARKET_REFRESH_HOURS * 3600:
                return self.exchanges[exchange_id]
            else:
                self.logger.info("Refreshing %s markets", exchange_id)
                await self._refresh_exchange_markets(exchange_id)
                return self.exchanges.get(exchange_id)
        return await self._load_exchange(exchange_id)

    async def _refresh_exchange_markets(self, exchange_id: str) -> None:
        if exchange_id not in self.exchanges:
            return
        exchange = self.exchanges[exchange_id]
        try:
            await exchange.load_markets(reload=True)
            self.symbols_by_exchange[exchange_id] = set(exchange.symbols)
            self.exchange_last_loaded[exchange_id] = datetime.now()
        except Exception as e:
            self.logger.error("Failed to refresh %s: %s", exchange_id, e)
            self.exchanges.pop(exchange_id, None)
            self.symbols_by_exchange.pop(exchange_id, None)
            self.exchange_last_loaded.pop(exchange_id, None)

    async def _periodic_update(self) -> None:
        while not self._shutdown_in_progress:
            try:
                for exchange_id in list(self.exchanges.keys()):
                    await self._refresh_exchange_markets(exchange_id)
                await asyncio.sleep(self.config.MARKET_REFRESH_HOURS * 3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in periodic update: %s", e)
                await asyncio.sleep(300)

    async def find_symbol_exchange(self, symbol: str) -> Tuple[Optional[ccxt.Exchange], Optional[str]]:
        for exchange_id in self.exchange_names:
            try:
                if exchange_id in self.symbols_by_exchange and symbol in self.symbols_by_exchange[exchange_id]:
                    exchange = self.exchanges.get(exchange_id)
                    if exchange:
                        return exchange, exchange_id

                exchange = await self._ensure_exchange_loaded(exchange_id)
                if exchange and exchange_id in self.symbols_by_exchange:
                    if symbol in self.symbols_by_exchange[exchange_id]:
                        self.logger.info("Found %s on %s", symbol, exchange_id)
                        return exchange, exchange_id
            except Exception as e:
                self.logger.error("Error checking %s for %s: %s", exchange_id, symbol, e)
                continue

        self.logger.warning("Symbol %s not found on any exchange", symbol)
        return None, None

    def get_all_symbols(self) -> Set[str]:
        all_symbols = set()
        for symbols in self.symbols_by_exchange.values():
            all_symbols.update(symbols)
        return all_symbols

    # ─────────────────────── BALANCE & MARGIN ──────────────────────────

    async def fetch_wallet_balance(self, exchange_id: str, currency: str) -> float:
        """Fetch free balance for a currency (spot fallback)."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return 0.0
            if not getattr(exchange, 'apiKey', None):
                return 0.0
            balance = await exchange.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0.0) or 0.0)
        except Exception as e:
            self.logger.error("fetch_wallet_balance failed: %s", e)
            return 0.0

    async def fetch_available_margin(self, exchange_id: str = "bybit", currency: str = "USDT") -> float:
        """Fetch available margin for futures (Bybit UTA)."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange or not getattr(exchange, 'apiKey', None):
                return 0.0
            balance = await exchange.fetch_balance({'type': 'swap'})
            free = balance.get(currency, {}).get('free', 0.0)
            if not free:
                # UTA fallback
                free = balance.get('total', {}).get(currency, 0.0)
            result = float(free or 0.0)
            self.logger.info("Available margin: %.4f %s", result, currency)
            return result
        except Exception as e:
            self.logger.error("fetch_available_margin failed: %s", e)
            return 0.0

    async def get_balance(self, currency: str) -> float:
        """Alias used by app.py — fetches Bybit margin."""
        return await self.fetch_available_margin("bybit", currency)

    # ─────────────────────── POSITIONS ─────────────────────────────────

    async def get_open_positions(self, exchange_id: str = "bybit", symbol: str = None) -> List[Dict]:
        """Return list of open futures positions (non-zero size)."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange or not getattr(exchange, 'apiKey', None):
                return []
            symbols = [symbol] if symbol else None
            positions = await exchange.fetch_positions(symbols)
            open_pos = [p for p in positions if abs(float(p.get('contracts', 0) or 0)) > 0]
            return open_pos
        except Exception as e:
            self.logger.error("get_open_positions failed: %s", e)
            return []

    # ─────────────────────── LEVERAGE ──────────────────────────────────

    async def set_leverage(self, exchange_id: str, symbol: str, leverage: int) -> bool:
        """Set leverage for a futures symbol before placing order."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return False
            await exchange.set_leverage(leverage, symbol)
            self.logger.info("Leverage set to %dx for %s on %s", leverage, symbol, exchange_id)
            return True
        except Exception as e:
            self.logger.warning("set_leverage failed (may already be set): %s", e)
            return False

    # ─────────────────────── FUTURES ORDERS ────────────────────────────

    def _get_dynamic_params(self, confidence_str: Any) -> Tuple[float, int]:
        """Return (position_size_pct, leverage) based on LLM confidence.
        
        Scale:
          >= 90% → 50% margin, 50x leverage
          >= 75% → 40% margin, 20x leverage
          >= 60% → 30% margin, 15x leverage
           < 60% → 20% margin, 10x leverage  (minimum to meet Bybit min notional)
        """
        try:
            conf = float(str(confidence_str).replace('%', '').strip())
        except (ValueError, TypeError):
            conf = 60.0

        if conf >= 90:
            return 0.50, 50
        elif conf >= 75:
            return 0.40, 20
        elif conf >= 60:
            return 0.30, 15
        else:
            return 0.20, 10

    async def create_futures_long(
        self,
        exchange_id: str,
        symbol: str,
        qty: float,
        leverage: int = 10,
        current_price: Optional[float] = None
    ) -> Optional[Dict]:
        """Open a LONG (buy) futures position.
        Uses Marketable Limit Order (current_price + 0.05%) to avoid wild slippage.
        """
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            await self.set_leverage(exchange_id, symbol, leverage)
            
            # Marketable Limit setup
            if current_price:
                limit_price = current_price * 1.0005 # 0.05% offset higher for LONG
                self.logger.critical("LIVE FUTURES LONG (Limit): %s qty=%.6f lev=%dx price=%.4f on %s", symbol, qty, leverage, limit_price, exchange_id)
                order = await exchange.create_order(
                    symbol, 'limit', 'buy', qty, limit_price,
                    params={'reduceOnly': False, 'timeInForce': 'IOC'}
                )
            else:
                self.logger.critical("LIVE FUTURES LONG (Market): %s qty=%.6f lev=%dx on %s", symbol, qty, leverage, exchange_id)
                order = await exchange.create_order(
                    symbol, 'market', 'buy', qty,
                    params={'reduceOnly': False}
                )
                
            self.logger.info("LONG order filled: %s", order.get('id', 'N/A'))
            return order
        except Exception as e:
            self.logger.error("create_futures_long failed: %s", e)
            return None

    async def create_futures_short(
        self,
        exchange_id: str,
        symbol: str,
        qty: float,
        leverage: int = 10,
        current_price: Optional[float] = None
    ) -> Optional[Dict]:
        """Open a SHORT (sell) futures position.
        Uses Marketable Limit Order (current_price - 0.05%) to avoid wild slippage.
        """
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            await self.set_leverage(exchange_id, symbol, leverage)
            
            # Marketable Limit setup
            if current_price:
                limit_price = current_price * 0.9995 # -0.05% offset lower for SHORT
                self.logger.critical("LIVE FUTURES SHORT (Limit): %s qty=%.6f lev=%dx price=%.4f on %s", symbol, qty, leverage, limit_price, exchange_id)
                order = await exchange.create_order(
                    symbol, 'limit', 'sell', qty, limit_price,
                    params={'reduceOnly': False, 'timeInForce': 'IOC'}
                )
            else:
                self.logger.critical("LIVE FUTURES SHORT (Market): %s qty=%.6f lev=%dx on %s", symbol, qty, leverage, exchange_id)
                order = await exchange.create_order(
                    symbol, 'market', 'sell', qty,
                    params={'reduceOnly': False}
                )
                
            self.logger.info("SHORT order filled: %s", order.get('id', 'N/A'))
            return order
        except Exception as e:
            self.logger.error("create_futures_short failed: %s", e)
            return None

    async def close_futures_position(
        self,
        exchange_id: str,
        symbol: str,
        direction: str,
        qty: float,
        current_price: Optional[float] = None
    ) -> Optional[Dict]:
        """Close an existing futures position (reduce-only)."""
        try:
            exchange = await self._ensure_exchange_loaded(exchange_id)
            if not exchange:
                return None

            # To close LONG → sell at -0.05% offset from current price
            # To close SHORT → buy at +0.05% offset from current price
            side = 'sell' if direction.upper() == 'LONG' else 'buy'
            
            if current_price:
                limit_price = current_price * 0.9995 if side == 'sell' else current_price * 1.0005
                self.logger.critical(
                    "LIVE FUTURES CLOSE %s (Limit): %s qty=%.6f price=%.4f (%s)",
                    direction, symbol, qty, limit_price, side
                )
                order = await exchange.create_order(
                    symbol, 'limit', side, qty, limit_price,
                    params={'reduceOnly': True, 'timeInForce': 'IOC'}
                )
            else:
                self.logger.critical(
                    "LIVE FUTURES CLOSE %s (Market): %s qty=%.6f (%s)",
                    direction, symbol, qty, side
                )
                order = await exchange.create_order(
                    symbol, 'market', side, qty,
                    params={'reduceOnly': True}
                )
            
            self.logger.info("CLOSE order filled: %s", order.get('id', 'N/A'))
            return order
        except Exception as e:
            self.logger.error("close_futures_position failed: %s", e)
            return None

    # ─── Legacy compat wrappers (used by old trading_strategy.py calls) ──

    async def create_market_buy_order(
        self, exchange_id: str, symbol: str, amount: float, quote_amount: float = 0.0
    ) -> Optional[Dict]:
        """Legacy wrapper — routes to create_futures_long."""
        qty = amount  # amount here is already the qty in base currency
        return await self.create_futures_long(exchange_id, symbol, qty, leverage=10)

    async def create_market_sell_order(
        self, exchange_id: str, symbol: str, amount: float
    ) -> Optional[Dict]:
        """Legacy wrapper — routes to create_futures_short."""
        return await self.create_futures_short(exchange_id, symbol, amount, leverage=10)
