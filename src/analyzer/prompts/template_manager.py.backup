"""
Template management for prompt building system.
Handles system prompts, response templates, and analysis steps for TRADING DECISIONS.
"""

import re
from datetime import datetime, timezone
from typing import Optional, Any, Dict

from src.logger.logger import Logger


class TemplateManager:
    """Manages prompt templates, system prompts, and analysis steps for trading decisions."""

    def __init__(self, config: Any, logger: Optional[Logger] = None, timeframe_validator: Any = None):
        """Initialize the template manager.

        Args:
            config: Configuration module providing prompt defaults
            logger: Optional logger instance for debugging
            timeframe_validator: TimeframeValidator instance (injected)
        """
        self.logger = logger
        self.config = config
        self.timeframe_validator = timeframe_validator

    def build_system_prompt(self, symbol: str, timeframe: str = "1h", previous_response: Optional[str] = None,
                            performance_context: Optional[str] = None, brain_context: Optional[str] = None,
                            last_analysis_time: Optional[str] = None,
                            indicator_delta_alert: str = "") -> str:
        # pylint: disable=too-many-arguments
        """Build the system prompt for trading decision AI.

        Args:
            symbol: Trading symbol (e.g., "BTC/USDT")
            timeframe: Timeframe for analysis (e.g., "1h", "4h", "1d")
            previous_response: Previous AI response for context continuity (JSON stripped)
            performance_context: Recent trading history and performance metrics
            brain_context: Distilled trading insights from closed trades
            last_analysis_time: Formatted timestamp of last analysis (e.g., "2025-12-26 14:30:00")
            indicator_delta_alert: Alert string when many indicators changed significantly

        Returns:
            str: Formatted system prompt
        """
        header_lines = [
            f"You are an Elite Crypto Price Action Sniper trading {symbol} on {timeframe} timeframe.",
            "Your analysis window is ONE closed candle at a time. You have NO visibility between candles.",
            "",
            "PRIMARY EDGE — Pure Price Action & Market Structure (detected from OHLCV):",
            "- Break of Structure (BOS): Candle closes BEYOND previous swing high/low → trend continuation confirmed.",
            "- Change of Character (CHOCH): First opposing BOS after a series → potential reversal signal.",
            "- HH/HL = uptrend | LH/LL = downtrend. NO clear structure = NO trade.",
            "- Liquidity Sweep: Candle wick pierces swing high/low but CLOSES BACK inside → stop hunt complete, reverse.",
            "- Volume Anomaly: Volume > 2x the 20-period average on a breakout candle = institutional participation.",
            "",
            "DECISION HIERARCHY (apply IN ORDER — a later filter cannot override an earlier one):",
            "1. ✅ MULTI-TIMEFRAME ALIGNMENT → Check [MULTI-TIMEFRAME ALIGNMENT]. Scalp (15m) should align with Macro (1h). Daily should align with Weekly Macro (200W SMA). High conflict = HOLD.",
            "2. ✅ PRICE ACTION & MARKET STRUCTURE → Must be clear. No BOS/CHOCH = output HOLD.",
            "3. ✅ VOLUME → Must confirm the BOS. Low-volume BOS = fakeout = output HOLD.",
            "4. ⚠️ RSI / ADX → Veto filter ONLY. RSI > 80 on LONG or < 20 on SHORT → VETO. ADX < 20 → choppy, HOLD.",
            "5. ℹ️ NEWS/MACRO → Caution flag only. Major event = reduce size 50% or HOLD. NEVER an entry trigger.",
            "",
            "TREAT AS SECONDARY (never entry triggers):",
            "MACD crossovers, SMA crossovers, Bollinger Bands, Fibonacci, macro forecasts.",
            "",
            "## Core Operating Rules",
            "- DEFAULT IS HOLD. A missed trade is better than a wrong trade.",
            "- 15m BLINDSPOT: Price can fully reverse between your checks. Always SL at thesis invalidation point.",
            "- POSITION FIRST: If a position is open, managing it takes priority over finding new entries.",
            "- FEE MATH: Round-trip ~0.12%. Min viable trade = 0.3% gross. Never CLOSE for < 0.15% unless SL imminent.",
            "- ANTI-DUMP RULE: Never LONG into aggressive high-volume selling (vol > 1.5x avg on 3+ red candles).",
            "- ANTI-HESITATION: If BOS + Volume confirm, and RSI/ADX do NOT veto → FIRE the trade. Do not overthink.",
            "- MTF SYNERGY: Treat the [MULTI-TIMEFRAME ALIGNMENT] block as your 'compass'. If 1h is strongly Bearish, any 15m Long signal must have extraordinary confluence or be treated as a quick scalp ONLY.",
            "",
        ]

        if last_analysis_time:
            header_lines.extend([
                "## Temporal Context",
                f"Last analysis: {last_analysis_time} UTC",
                "",
            ])

        # Add performance context if available
        if performance_context:
            header_lines.extend([
                "",
                performance_context.strip(),
                "",
                "## Performance Adaptation",
                "- LEARN from closed trades: Was the BOS real or a fakeout? Was volume sufficient?",
                "- AVOID repeated mistakes: If recent BOS entries failed, demand higher volume confirmation.",
                "- UPDATE positions actively: Trail SL to last structural swing immediately after entry.",
            ])

        if brain_context:
            header_lines.extend([
                "",
                brain_context.strip(),
            ])

        # Add previous response context if available (strip JSON to save tokens)
        if previous_response:
            text_reasoning = re.split(r'```json', previous_response, flags=re.IGNORECASE)[0].strip()
            if text_reasoning:
                window_minutes = 30  # Default for 15m timeframe
                if self.timeframe_validator:
                    try:
                        window_minutes = self.timeframe_validator.to_minutes(timeframe) * 2
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        if self.logger:
                            self.logger.warning("Failed to calculate relevance window for %s: %s", timeframe, e)

                header_lines.extend([
                    "",
                    "## PREVIOUS ANALYSIS CONTEXT",
                ])
                if indicator_delta_alert:
                    header_lines.append(indicator_delta_alert)
                header_lines.extend([
                    "Your last analysis reasoning (for continuity):",
                    text_reasoning,
                    "",
                    "### CURRENT TIME CHECK",
                    f"- **Current Time**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    f"- **Relevance Window**: Only consider a setup 'valid' if BOS occurred within the last 2 candles ({window_minutes} minutes).",
                    "- PREVIOUS reasoning MUST be verified against CURRENT market structure. Stale BOS signals are invalid.",
                ])

        return "\n".join(header_lines)

    def build_response_template(self, _has_chart_analysis: bool = False,
                                dynamic_thresholds: Optional[Dict[str, Any]] = None) -> str:
        """Build the response template for trading decision output.

        Args:
            has_chart_analysis: Whether chart image analysis is available
            dynamic_thresholds: Brain-learned thresholds for dynamic values

        Returns:
            str: Formatted response template
        """
        thresholds = dynamic_thresholds or {}
        trade_count = thresholds.get("trade_count", 0)

        response_template = '''## Response Format

Write your analysis in this exact order BEFORE the JSON (Chain-of-Thought reasoning):

1. MARKET STRUCTURE:
   State: [HH/HL | LH/LL | Sideways] — [BOS UP/DOWN/NONE] — [CHOCH YES/NO]
   Identify unswept liquidity pools above/below.

2. VOLUME ANALYSIS:
   BOS/Trigger candle volume vs 20-period average: [X]x average.
   Anti-Dump Status: [Buy dominant | Sell dominant | Neutral]

3. VETO CHECK:
   RSI: [value] → [Clear | VETOED - reason]
   ADX: [value] → [Clear >20 | VETOED <20]
   Result: [PASS | VETOED]

4. POSITION STATE:
   Open position: [YES/NO]
   Action: [Proceed to entry | HOLD | UPDATE trailing stop | CLOSE immediately]

5. RISK/REWARD (required for BUY/SELL/UPDATE):
   Entry: [price] — [exact trigger condition]
   SL: [price] — at [exact structural level where thesis is invalidated]
   TP: [price] — at [structural liquidity pool target]
   R/R calc: risk=|entry-SL|, reward=|TP-entry|. For UPDATE: risk=|current_price-SL|
   R/R ratio: [X]:1 (minimum 1.5:1 required, else output HOLD)
   Fee check: Expected gross >= 0.3%? [YES/NO]
   Position size (show your work):
     Base = confidence / 100
     Tier: confidence 55-69 → x0.6 | 70-84 → x1.0 | 85-100 → x1.2
     ADX 20-25: apply x0.7 | MACRO CAUTION: apply x0.5
     Final = max(0.10, min(0.50, base x tier x adjustments))

6. FINAL DECISION: [SIGNAL] — Confidence [X]/100
   One sentence: why this signal + exact invalidation condition.

⚠️ CRITICAL JSON RULES:
- HOLD/CLOSE: set entry_price, stop_loss, and take_profit to 0.0
- UPDATE: provide the new stop_loss and/or take_profit values
- position_size: 0.0 for HOLD/CLOSE, calculated tier value for active signals
- PROVIDE EXACTLY ONE signal. Never combine signals.

Then output the JSON block:

```json
{
    "analysis": {
        "signal": "BUY|SELL|HOLD|CLOSE|UPDATE",
        "confidence": 0,
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "position_size": 0.0,
        "risk_reward_ratio": 0.0,
        "reasoning": "1-2 sentences: BOS direction + volume status + why this signal",
        "key_levels": {"support": [0.0, 0.0], "resistance": [0.0, 0.0]},
        "confluence_factors": {
            "structure_clarity": 0,
            "volume_confirmation": 0,
            "trend_alignment": 0,
            "veto_clear": 0,
            "liquidity_pool_quality": 0
        },
        "trend": {
            "direction": "BULLISH|BEARISH|SIDEWAYS",
            "structure": "BOS_UP|BOS_DOWN|CHOCH_UP|CHOCH_DOWN|NONE",
            "adx_strength": 0.0,
            "timeframe_alignment": "ALIGNED|MIXED|DIVERGENT"
        }
    }
}
```


CONFLUENCE SCORING GUIDE (0-100, rate how strongly each factor supports signal):
- structure_clarity:      100=crystal clear BOS/CHOCH | 50=ambiguous | 0=no structure
- volume_confirmation:    100=>2x avg | 75=1.5-2x (minimum valid) | 0=<1.5x (fakeout risk)
- trend_alignment:        100=1H+4H both aligned | 60=1H only | 30=neutral | 0=opposing
- veto_clear:             100=RSI 30-70 + ADX>25 | 50=near extreme | 0=VETOED → output HOLD
- liquidity_pool_quality: 100=clean untouched swing | 50=partially tested | 0=arbitrary TP

[BAGIAN 4 — SIGNAL EXECUTION RULES]

TRADING SIGNALS (Gate-Based System):
- BUY/SELL: All 3 gates must pass → BOS confirmed + Volume >1.5x avg + Veto CLEAR
  R/R ≥ 1.5:1 required. Confidence tier determines position SIZE, not whether to enter.
- ANTI-HESITATION: BOS confirmed + Volume confirmed + Veto cleared → EXECUTE at confidence 55+.
  The BOS IS the signal. Do not wait for further confirmation candles.
- HOLD: Any gate failed | R/R < 1.5:1 | No clear structure | Fee check fails (<0.3% gross)
- CLOSE: Opposite BOS closed against open position → EXIT immediately. No averaging down.
- UPDATE: Profit >0.5% → trail SL to last swing structure. Signal UPDATE every candle while profitable.

RISK MANAGEMENT (Structural SL/TP Placement):
LONG: SL just below BOS origin candle's low or last HL (max 1.5% from entry)
      TP at next unswept swing HIGH / liquidity pool (target 1%-3%)
SHORT: SL just above BOS origin candle's high or last LH (max 1.5% from entry)
       TP at next unswept swing LOW / liquidity pool (target 1%-3%)
⛔ If structural SL requires >1.5% from entry → output HOLD. Setup risk is too wide.

DYNAMIC TRAILING (UPDATE Signal):
Trigger: Open position profit >0.5%
Action: Move SL to most recent structural swing (HL for LONG, LH for SHORT)
Trail tighter each candle check. Never move SL away from profit direction.
Continue UPDATE signals until TP is hit or opposite BOS occurs.

HIGH-IMPACT EVENT PROTOCOL (replaces 365D Macro Conflict):
Sudden candle >2% in ONE bar WITHOUT a preceding BOS setup → DO NOT chase.
This is likely news-driven, not structural. Wait for new BOS to form before entering.
If a high-volume news candle fires hard AGAINST an open position → treat as CLOSE signal immediately.
News can invalidate structural analysis instantly. Capital defense > being right.'''

        # Append brain learning note if trade history exists
        if trade_count > 0:
            response_template += (
                f"\n\nBRAIN NOTE: {trade_count} closed trades on record. "
                "Review recent trade outcomes to refine BOS confirmation requirements and SL tightness."
            )

        return response_template

    def build_analysis_steps(self, symbol: str, has_advanced_support_resistance: bool = False, has_chart_analysis: bool = False, available_periods: dict = None) -> str:
        """Build analysis steps instructions for the AI model.

        Args:
            symbol: Trading symbol being analyzed
            has_advanced_support_resistance: Whether advanced S/R indicators are detected
            has_chart_analysis: Whether chart image analysis is available (Google AI only)
            available_periods: Dict of period names to candle counts (e.g., {"12h": 2, "24h": 4, "3d": 12, "7d": 28})

        Returns:
            str: Formatted analysis steps
        """
        # Get the base asset for market comparisons
        analyzed_base = symbol.split('/')[0] if '/' in symbol else symbol

        # Build dynamic timeframe description based on available periods
        if available_periods:
            period_names = list(available_periods.keys())
            timeframe_desc = f"Analyze the provided Multi-Timeframe Price Summary periods: {', '.join(period_names)}"
        else:
            timeframe_desc = (
                "Analyze the provided Multi-Timeframe Price Summary periods "
                "(dynamically calculated based on your analysis timeframe)"
            )

        analysis_steps = f"""
## Analysis Steps (use findings to determine trading signal):

**Step-to-Output Mapping:**
Steps 1-4 → Section 1 (MARKET STRUCTURE) + Section 2 (INDICATOR ASSESSMENT)
Step 5 → Section 3 (CONTEXT & CATALYST)
Step 5.5 → Section 3.5 (SCENARIO ANALYSIS)
Step 6 → Sections 3 + 5 (NEWS & historical evidence in CONTEXT and DECISION)
Step 7 → Section 2.5 (QUANTITATIVE & VISUAL VALIDATION)
Step 8 (if chart) → Section 2.5 (chart sub-section)
Synthesis → Sections 4 + 5 (RISK/REWARD + DECISION)

1. MULTI-TIMEFRAME ASSESSMENT:
   {timeframe_desc} | Compare short vs multi-day vs long-term (30d+, 365d) | Weekly macro (200-week SMA)
   🧠 Are timeframes aligned or divergent? Which dominates?

2. TECHNICAL INDICATORS:
   Analyze all provided Momentum, Trend, Volatility, and Volume indicators (RSI, MACD, ADX, ATR, ROC, MFI, etc.)
   🧠 Do indicators confirm each other or show divergence?

3. PATTERN RECOGNITION (Conservative Approach):
   **Swing Structure:** HH/HL = uptrend, LH/LL = downtrend | **Classic:** H&S, double tops/bottoms, wedges, flags | **Candlesticks:** doji, hammer, engulfing at key S/R | **Divergences:** Price vs RSI/MACD/OBV | **IMPORTANT:** If unclear, state "No clear pattern" - do NOT force conclusions
   🧠 Is pattern complete or forming? Could this be a fakeout?

4. SUPPORT/RESISTANCE:
   Key levels across timeframes | Historical reaction zones (3+ touches) | Confluences (S/R + Fib + SMA) | Volume nodes | Risk/reward for SL/TP
   🧠 How did price react last time at this level?

5. MARKET CONTEXT:
   Market Overview (global cap, dominance)"""

        if "BTC" not in analyzed_base:
            analysis_steps += "\n   - Compare performance relative to BTC (correlation/divergence)"

        if "ETH" not in analyzed_base:
            analysis_steps += "\n   - Compare performance relative to ETH if relevant"

        analysis_steps += """
 | Fear & Greed Index (extremes) | Asset alignment with market | Relevant events

5.5. BULL vs BEAR CASE (Forced Dialectical Analysis):
   🐂 BULL CASE: What confluence supports LONG? What would need to happen for price to rise?
   🐻 BEAR CASE: What confluence supports SHORT? What would need to happen for price to fall?
   🧠 WHICH PERSPECTIVE WINS? Justify with data. If brain has relevant semantic rules for either direction, weight those appropriately.

6. NEWS & SENTIMENT:
   Asset news | Market events | Sentiment | Institutional activity | Regulatory impacts | News that could override technicals

7. STATISTICAL ANALYSIS:
   Z-Score (extremes revert) | Kurtosis (tail risk) | Hurst (>0.5 trending, <0.5 reverting) | Volatility cycles"""

        # Add chart analysis steps only if chart images are available
        step_number = 8
        if has_chart_analysis:
            cfg_limit = int(self.config.AI_CHART_CANDLE_LIMIT)

            analysis_steps += f"""

{step_number}. CHART IMAGE ANALYSIS (~{cfg_limit} candles, 4 panels):
   **P1-PRICE:** SMA50 (orange), SMA200 (purple) - Golden/Death Cross? | Read MIN/MAX labels | Apply patterns from Step 3 to visual data
   **P2-RSI:** Read value from annotation | Zone (>70 overbought, <30 oversold) | Check divergence vs price
   **P3-VOLUME:** Trend direction | Spikes align with price moves? | Green/red bar ratio
   **P4-CMF/OBV:** CMF (cyan, left axis): >0 buying, <0 selling | OBV (magenta, right): rising=accumulation
   **VALIDATE:** Cross-check visuals with numerical indicators - flag discrepancies"""
            step_number += 1

        analysis_steps += f"""

{step_number}. SYNTHESIS:
   Trend direction/strength | Indicator confluence | SL/TP levels | R/R ratio | Confidence | Invalidation triggers

NOTE: Indicators calculated from CLOSED CANDLES ONLY. No pattern = state "No clear pattern detected"."""

        if has_advanced_support_resistance:
            analysis_steps += """
ADVANCED S/R: Volume-weighted pivots with 3+ touches, above-average volume. Only strong levels provided."""

        return analysis_steps
