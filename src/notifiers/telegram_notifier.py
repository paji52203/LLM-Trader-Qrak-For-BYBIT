"""
Telegram Notifier - Lightweight notification service using Telegram Bot API.
Sends AI trading analysis to Telegram with Markdown formatting.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, List, Dict, Any

from aiohttp import ClientSession, ClientError

from src.utils.decorators import retry_async
from .base_notifier import BaseNotifier

if TYPE_CHECKING:
    from src.config.protocol import ConfigProtocol
    from src.parsing.unified_parser import UnifiedParser
    from src.utils.format_utils import FormatUtils

ENTRY_ACTIONS = {'BUY', 'SELL'}


class TelegramNotifier(BaseNotifier):
    """Async Telegram notifier using aiohttp."""

    def __init__(self, logger: logging.Logger, config: "ConfigProtocol", unified_parser: "UnifiedParser", formatter: "FormatUtils") -> None:
        """Initialize TelegramNotifier.

        Args:
            logger: Logger instance
            config: ConfigProtocol instance for Telegram settings
            unified_parser: UnifiedParser for JSON extraction
            formatter: FormatUtils instance for value formatting
        """
        super().__init__(logger, config, unified_parser, formatter)
        self.session: Optional[ClientSession] = None
        self._api_url = f"https://api.telegram.org/bot{self.config.get_env('BOT_TOKEN_TELEGRAM')}/"
        self.chat_id = self.config.get_env('TELEGRAM_CHAT_ID')
        self.is_initialized = False

    async def start(self) -> None:
        """Start the Telegram notifier session."""
        if not self.config.get_env('BOT_TOKEN_TELEGRAM'):
            self.logger.error("Telegram Notifier: BOT_TOKEN_TELEGRAM not configured.")
            return
        
        if not self.session or self.session.closed:
            self.session = ClientSession()
        
        # Verify token and chat id
        try:
            url = f"{self._api_url}getMe"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.info("Telegram Notifier: Logged in as %s", data['result']['username'])
                    self.is_initialized = True
                else:
                    self.logger.error("Telegram Notifier: Invalid token or API error: %s", response.status)
        except Exception as e:
            self.logger.error("Telegram Notifier: Initialization error: %s", e)

    async def wait_until_ready(self) -> None:
        """Wait for initialization."""
        # Simple check, since this doesn't use a persistent bot instance like discord.py
        while not self.is_initialized and self.config.get_env('BOT_TOKEN_TELEGRAM'):
            await asyncio.sleep(0.5)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        if self.session and not self.session.closed:
            await self.session.close()

    async def close(self) -> None:
        """Close the Telegram notifier session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("Telegram Notifier: Closed session.")

    @retry_async(max_retries=3, initial_delay=1)
    async def send_message(
            self,
            message: str,
            channel_id: Optional[int] = None,
            expire_after: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a text message to Telegram.

        Args:
            message: Message text (MarkdownV2)
            channel_id: Ignored (uses chat_id from config)
            expire_after: Ignored for Telegram
        """
        if not self.is_initialized or not self.chat_id:
            return None

        # Basic escaping for MarkdownV2 if not already escaped
        # (For simplicity, we'll assume the caller provides valid Markdown/Text)
        
        url = f"{self._api_url}sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown" # Using basic Markdown for better compatibility
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.text()
                    self.logger.error("Telegram send_message error (%s): %s", response.status, error_data)
        except ClientError as e:
            self.logger.error("Telegram network error: %s", e)
        return None

    async def send_trading_decision(self, decision: Any, channel_id: Optional[int] = None) -> None:
        """Send a trading decision to Telegram."""
        try:
            color_key, emoji = self.get_action_styling(decision.action)
            
            msg = [
                f"{emoji} *TRADING DECISION: {decision.action}*",
                f"━━━━━━━━━━━━━━━━━━━",
                f"*Symbol:* `{decision.symbol}`",
                f"*Price:* `${decision.price:,.2f}`",
                f"*Confidence:* `{decision.confidence}`",
            ]

            if decision.stop_loss:
                msg.append(f"*Stop Loss:* `${decision.stop_loss:,.2f}`")
            if decision.take_profit:
                msg.append(f"*Take Profit:* `${decision.take_profit:,.2f}`")
            if decision.position_size:
                msg.append(f"*Position Size:* `{decision.position_size * 100:.2f}%`")
            if decision.quote_amount:
                msg.append(f"*Invested:* `${decision.quote_amount:,.2f}`")
            if decision.quantity:
                msg.append(f"*Quantity:* `{self.formatter.fmt(decision.quantity)}`")
            
            msg.append(f"━━━━━━━━━━━━━━━━━━━")
            if decision.reasoning:
                msg.append(f"*Reasoning:*")
                msg.append(f"_{decision.reasoning[:1000]}_") # Truncate if too long
            
            msg.append(f"\n🕙 `{decision.timestamp.strftime('%Y-%m-%d %H:%M:%S')}`")

            await self.send_message("\n".join(msg))
        except Exception as e:
            self.logger.error("Error sending Telegram trading decision: %s", e)

    async def send_analysis_notification(
            self,
            result: dict,
            symbol: str,
            timeframe: str,
            channel_id: Optional[int] = None
    ) -> None:
        """Send analysis notification to Telegram."""
        try:
            analysis = result.get("analysis")
            if not analysis:
                return

            raw_response = result.get("raw_response", "")
            reasoning = self.unified_parser.extract_text_before_json(raw_response) if raw_response else ""
            
            signal = analysis.get('signal', 'HOLD')
            _, emoji = self.get_action_styling(signal)

            msg = [
                f"📊 *Analysis: {symbol} ({timeframe})*",
                f"Signal: {emoji} *{signal}*",
                f"Confidence: `{analysis.get('confidence', 0)}%`",
                f"━━━━━━━━━━━━━━━━━━━",
            ]

            if analysis.get('entry_price'):
                msg.append(f"Target Entry: `${analysis['entry_price']:,.2f}`")
            if analysis.get('stop_loss'):
                msg.append(f"Stop Loss: `${analysis['stop_loss']:,.2f}`")
            if analysis.get('take_profit'):
                msg.append(f"Take Profit: `${analysis['take_profit']:,.2f}`")
            
            if reasoning:
                msg.append(f"\n*AI Insights:*")
                msg.append(f"_{reasoning[:1000]}_")

            await self.send_message("\n".join(msg))
        except Exception as e:
            self.logger.error("Error sending Telegram analysis: %s", e)

    async def send_position_status(
            self,
            position: Any,
            current_price: float,
            channel_id: Optional[int] = None
    ) -> None:
        """Send current position status to Telegram."""
        try:
            pnl_pct, pnl_quote = self.calculate_position_pnl(position, current_price)
            _, emoji = self.get_pnl_styling(pnl_pct)
            
            msg = [
                f"{emoji} *Position Status: {position.symbol}*",
                f"*Dir:* `{position.direction}` | *PnL:* `{pnl_pct:+.2f}%` (`${pnl_quote:+,.2f}`)",
                f"━━━━━━━━━━━━━━━━━━━",
                f"Entry: `${position.entry_price:,.2f}`",
                f"Current: `${current_price:,.2f}`",
                f"Size: `{self.formatter.fmt(position.size)}`",
                f"Stop: `${position.stop_loss:,.2f}`",
                f"Target: `${position.take_profit:,.2f}`",
                f"\n🕙 Time held: `{self.calculate_time_held(position.entry_time):.1f}h`"
            ]

            await self.send_message("\n".join(msg))
        except Exception as e:
            self.logger.error("Error sending Telegram position status: %s", e)

    async def send_performance_stats(
            self,
            trade_history: List[Dict[str, Any]],
            symbol: str,
            channel_id: Optional[int] = None
    ) -> None:
        """Send performance stats to Telegram."""
        try:
            stats = self.calculate_performance_stats(trade_history)
            if not stats:
                return

            emoji = "📈" if stats['net_pnl'] > 0 else "📉"
            
            msg = [
                f"{emoji} *Performance: {symbol}*",
                f"━━━━━━━━━━━━━━━━━━━",
                f"*Win Rate:* `{stats['win_rate']:.1f}%`",
                f"*Trades:* `{stats['closed_trades']}` (`{stats['winning_trades']}` Wins)",
                f"*Total PnL:* `{stats['total_pnl_pct']:+.2f}%` (`${stats['total_pnl_quote']:+,.2f}`)",
                f"*Net PnL:* `${stats['net_pnl']:+,.2f}` (After Fees)",
                f"*Avg PnL:* `{stats['avg_pnl_pct']:+.2f}%`"
            ]

            await self.send_message("\n".join(msg))
        except Exception as e:
            self.logger.error("Error sending Telegram performance stats: %s", e)
