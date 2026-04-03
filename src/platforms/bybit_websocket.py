import logging
import threading
from typing import Optional, Dict, Any
from pybit.unified_trading import WebSocket

class BybitWebSocketManager:
    """
    Manages real-time data from Bybit V5 WebSocket.
    Focuses on the 'trade' topic to provide the absolute latest market price.
    """
    
    def __init__(self, logger: logging.Logger, symbol: str = "BTCUSDT", testnet: bool = False):
        self.logger = logger
        self.symbol = symbol.replace("/", "").split(":")[0]  # Convert BTC/USDT:USDT to BTCUSDT
        self.testnet = testnet
        
        self.latest_price: Optional[float] = None
        self.last_side: Optional[str] = None
        self.last_tick_direction: Optional[str] = None
        self._lock = threading.Lock()
        
        self.ws: Optional[WebSocket] = None
        self._active = False

    def start(self):
        """Start the WebSocket connection and subscribe to trades."""
        if self._active:
            return
            
        try:
            self.logger.info(f"Starting Bybit WebSocket for {self.symbol}...")
            self.ws = WebSocket(
                testnet=self.testnet,
                channel_type="linear",
                domain="bytick"
            )
            
            self.ws.trade_stream(
                symbol=self.symbol,
                callback=self._handle_message
            )
            self._active = True
            self.logger.info(f"Subscribed to trade stream for {self.symbol}")
        except Exception as e:
            self.logger.error(f"Failed to start Bybit WebSocket: {e}")

    def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming trade messages from Bybit V5."""
        try:
            data_list = message.get("data", [])
            if not data_list:
                return
                
            # Process the latest trade in the bundle
            latest_trade = data_list[-1]
            
            # Filter Block Trades (BT) to avoid price outliers for retail bot
            if latest_trade.get("BT", False):
                return

            with self._lock:
                self.latest_price = float(latest_trade.get("p", self.latest_price))
                self.last_side = latest_trade.get("S") # 'Buy' or 'Sell'
                self.last_tick_direction = latest_trade.get("L") # e.g. PlusTick
                
        except Exception as e:
            self.logger.error(f"Error processing Bybit WS message: {e}")

    def get_latest_price(self) -> Optional[float]:
        """Thread-safe access to the latest trade price."""
        with self._lock:
            return self.latest_price

    def stop(self):
        """Stop the WebSocket connection and cleanup pybit resources."""
        if self.ws:
            self.logger.info("Closing Bybit WebSocket connection (pybit.exit)...")
            try:
                self._active = False
                # The official way to close pybit V5 WebSocket
                self.ws.exit()
                self.logger.info("Bybit WebSocket successfully exited.")
            except Exception as e:
                self.logger.error(f"Error stopping Bybit WebSocket: {e}")
