"""Risk Manager for converting signals into actionable trade parameters."""

import json
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
from src.logger.logger import Logger
from src.contracts.risk_contract import RiskManagerProtocol

if TYPE_CHECKING:
    from src.config.protocol import ConfigProtocol
    from src.trading.data_models import RiskAssessment

class RiskManager(RiskManagerProtocol):
    """
    Manages risk calculations including position sizing, stop-loss/take-profit dynamic adjustment,
    and circuit breakers.
    """

    def __init__(self, logger: Logger, config: "ConfigProtocol"):
        self.logger = logger
        self.config = config

    def validate_signal(self, signal: str) -> bool:
        """Validate if a signal is actionable."""
        return signal in ("BUY", "SELL", "CLOSE", "CLOSE_LONG", "CLOSE_SHORT")

    def calculate_dynamic_leverage(self, confidence: str, volatility_pct: float) -> int:
        """
        Calculate optimal leverage based on AI confidence and market volatility.
        
        Logic: High Confidence + Low Volatility = Higher Leverage.
        GUARDRAIL: Max leverage is strictly capped at 25x.
        """
        conf_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(confidence.upper(), 1)
        
        # Volatility multiplier (inverse relationship: lower volatility allows higher leverage)
        if volatility_pct < 1.0:
            vol_mult = 8
        elif volatility_pct < 2.5:
            vol_mult = 5
        else:
            vol_mult = 3
            
        leverage = conf_score * vol_mult
        
        # CRITICAL GUARDRAIL: Strict cap at 25x
        return int(min(leverage, 25))

    def calculate_entry_parameters(
        self,
        signal: str,
        current_price: float,
        capital: float,
        confidence: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[float] = None,
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> "RiskAssessment":
        """
        Calculate all risk parameters for a new position entry.
        """
        from src.trading.data_models import RiskAssessment
        market_conditions = market_conditions or {}
        direction = "LONG" if signal == "BUY" else "SHORT"

        # 1. Extract or Default ATR/Volatility
        atr = market_conditions.get("atr", current_price * 0.02)
        atr_pct = market_conditions.get("atr_percentage", (atr / current_price) * 100)

        # Determine volatility level
        if atr_pct > 3:
            volatility_level = "HIGH"
        elif atr_pct < 1.5:
            volatility_level = "LOW"
        else:
            volatility_level = "MEDIUM"

        # 2. Dynamic SL/TP Calculation (Dynamic Defaults)
        # Use 2x ATR for SL, 4x ATR for TP (2:1 R/R default)
        dynamic_sl_distance = atr * 2
        dynamic_tp_distance = atr * 4

        if direction == "LONG":
            dynamic_sl = current_price - dynamic_sl_distance
            dynamic_tp = current_price + dynamic_tp_distance
        else:  # SHORT
            dynamic_sl = current_price + dynamic_sl_distance
            dynamic_tp = current_price - dynamic_tp_distance

        # 2.5 Load Manual Overrides
        overrides = self._get_manual_overrides()
        manual_sl_pct = overrides.get("stop_loss_pct", 0)
        manual_tp_pct = overrides.get("take_profit_pct", 0)

        if manual_sl_pct > 0:
            if direction == "LONG":
                final_sl = current_price * (1 - (manual_sl_pct / 100))
            else:
                final_sl = current_price * (1 + (manual_sl_pct / 100))
            self.logger.info("Using MANUAL SL override: %.2f%% ($%s)", manual_sl_pct, f"{final_sl:,.2f}")
        elif stop_loss and stop_loss > 0:
            final_sl = stop_loss
            self.logger.debug("Using AI-provided SL: $%s", f"{final_sl:,.2f}")
        else:
            final_sl = dynamic_sl
            self.logger.info("Using dynamic SL (2x ATR): $%s", f"{final_sl:,.2f}")

        if manual_tp_pct > 0:
            if direction == "LONG":
                final_tp = current_price * (1 + (manual_tp_pct / 100))
            else:
                final_tp = current_price * (1 - (manual_tp_pct / 100))
            self.logger.info("Using MANUAL TP override: %.2f%% ($%s)", manual_tp_pct, f"{final_tp:,.2f}")
        elif take_profit and take_profit > 0:
            final_tp = take_profit
            self.logger.debug("Using AI-provided TP: $%s", f"{final_tp:,.2f}")
        else:
            final_tp = dynamic_tp
            self.logger.info("Using dynamic TP (4x ATR): $%s", f"{final_tp:,.2f}")

        # 4. Circuit Breakers (Clamp Extreme Values)
        sl_distance_raw = abs(current_price - final_sl) / current_price

        # Clamp SL: min 0.5%, max 10%
        if sl_distance_raw > 0.10:
            self.logger.warning("SL distance %s exceeds 10%% max, clamping", f"{sl_distance_raw:.1%}")
            if direction == "LONG":
                final_sl = current_price * 0.90
            else:
                final_sl = current_price * 1.10
        elif sl_distance_raw < 0.005:
            self.logger.warning("SL distance %s below 0.5%% min, expanding", f"{sl_distance_raw:.1%}")
            if direction == "LONG":
                final_sl = current_price * 0.995
            else:
                final_sl = current_price * 1.005

        # Validate Logical Consistency
        if direction == "LONG":
            if final_sl >= current_price:
                self.logger.warning("Invalid SL for LONG (%s >= %s), using dynamic", final_sl, current_price)
                final_sl = dynamic_sl
            if final_tp <= current_price:
                self.logger.warning("Invalid TP for LONG (%s <= %s), using dynamic", final_tp, current_price)
                final_tp = dynamic_tp
        else:  # SHORT
            if final_sl <= current_price:
                self.logger.warning("Invalid SL for SHORT (%s <= %s), using dynamic", final_sl, current_price)
                final_sl = dynamic_sl
            if final_tp >= current_price:
                self.logger.warning("Invalid TP for SHORT (%s >= %s), using dynamic", final_tp, current_price)
                final_tp = dynamic_tp

        # 5. Position Sizing
        # AI-Driven ROI-Optimized Sizing: 20% to 50% based on confidence
        size_map = {"HIGH": 0.50, "MEDIUM": 0.35, "LOW": 0.20}
        final_size_pct = size_map.get(confidence.upper(), 0.20)
        self.logger.info("AI-Driven Sizing: %s confidence => %.0f%% allocation", confidence, final_size_pct * 100)

        # 5.1 Dynamic Leverage
        leverage = self.calculate_dynamic_leverage(confidence, atr_pct)
        self.logger.info("Calculated Dynamic Leverage: %sx", leverage)

        # 5.5 Apply Manual Allocation Constraints
        min_alloc = overrides.get("min_allocation_pct", 0) / 100
        max_alloc = overrides.get("max_allocation_pct", 0) / 100

        if max_alloc > 0 and final_size_pct > max_alloc:
            self.logger.info("Clamping size to MANUAL MAX allocation: %.1f%%", max_alloc * 100)
            final_size_pct = max_alloc
        if min_alloc > 0 and final_size_pct < min_alloc:
            self.logger.info("Boosting size to MANUAL MIN allocation: %.1f%%", min_alloc * 100)
            final_size_pct = min_alloc

        # 6. Calculate Financials & Fee-Awareness
        allocation = capital * final_size_pct
        quantity = (allocation * leverage) / current_price # Calculation considers leverage for quantity
        
        # Bybit-specific fee estimation (Taker: 0.055%, Maker: 0.02%)
        # Using Taker fee for conservative net ROI estimation
        taker_fee_pct = 0.00055
        est_entry_fee = (allocation * leverage) * taker_fee_pct
        est_exit_fee = (allocation * leverage) * taker_fee_pct # Assuming taker exit for safety
        total_est_fees = est_entry_fee + est_exit_fee
        
        # Predictive Funding Rate estimate (default 0.01% per 8h, assuming 1 period)
        est_funding_fee = (allocation * leverage) * 0.0001
        
        # 7. Metrics & ROI Prediction
        sl_distance_pct = abs(current_price - final_sl) / current_price
        tp_distance_pct = abs(final_tp - current_price) / current_price
        
        # Gross vs Net ROI
        gross_profit_quote = (allocation * leverage) * tp_distance_pct
        net_profit_quote = gross_profit_quote - total_est_fees - est_funding_fee
        net_roi_pct = (net_profit_quote / allocation) * 100
        
        # CRITICAL GUARDRAIL: Fee-Awareness - Check if net profit is at least positive
        if net_profit_quote <= 0:
            self.logger.warning("FEE-AWARENESS GUARDRAIL: Projected fees ($%.2f) exceed gross profit ($%.2f). Signal cancelled.", total_est_fees + est_funding_fee, gross_profit_quote)
            # We return a 'dummy' assessment with 0 quantity to safely signal cancellation to strategy
            quantity = 0.0

        rr_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

        return RiskAssessment(
            direction=direction,
            entry_price=current_price,
            stop_loss=final_sl,
            take_profit=final_tp,
            quantity=quantity,
            size_pct=final_size_pct,
            quote_amount=allocation,
            entry_fee=est_entry_fee,
            sl_distance_pct=sl_distance_pct,
            tp_distance_pct=tp_distance_pct,
            rr_ratio=rr_ratio,
            volatility_level=volatility_level,
            leverage=leverage,
            net_roi=net_roi_pct
        )

    def _get_manual_overrides(self) -> Dict[str, Any]:
        """Fetch manual overrides from disk if they exist."""
        path = Path(self.config.DATA_DIR) / "manual_overrides.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error("RiskManager failed to load manual overrides: %s", e)
            return {}
