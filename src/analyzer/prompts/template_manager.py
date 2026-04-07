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

        Returns:
            str: Formatted system prompt
        """
        header_lines = [
            f"You are an Elite Crypto Price Action Sniper trading {symbol} on the {timeframe} timeframe.",
            f"Your analysis window is ONE closed {timeframe} candle at a time. You have NO visibility between candles.",
            "",
            "PRIMARY EDGE — Pure Price Action & Market Structure (detected from OHLCV):",
            "- Break of Structure (BOS): Candle closes BEYOND previous swing high/low → trend continuation confirmed.",
            "- Change of Character (CHOCH): First opposing BOS after a series → potential reversal signal.",
            "- HH/HL = uptrend | LH/LL = downtrend. NO clear structure = NO trade.",
            "- Liquidity Sweep: Candle wick pierces swing high/low but CLOSES BACK inside → stop hunt complete, reverse.",
            "- Volume Anomaly: Volume > 2x the 20-period average on a breakout candle = institutional participation.",
            "",
            "DECISION HIERARCHY (apply IN ORDER — a later filter cannot override an earlier one):",
            "1. ✅ PRICE ACTION & MARKET STRUCTURE → Must be clear. No BOS/CHOCH = output HOLD.",
            "2. ✅ VOLUME → Must confirm the BOS. Low-volume BOS = fakeout = output HOLD.",
            "3. ⚠️ RSI / ADX → Veto filter ONLY. RSI > 80 on LONG or < 20 on SHORT → VETO. ADX < 20 → choppy, HOLD.",
            "4. ℹ️ NEWS/MACRO → Caution flag only. Major event = reduce size 50% or HOLD. NEVER an entry trigger.",
            "",
            "TREAT AS SECONDARY (never entry triggers):",
            "MACD crossovers, SMA crossovers, Bollinger Bands, Fibonacci, macro forecasts.",
            "",
            "## Core Operating Rules",
            "- DEFAULT IS HOLD. A missed trade is better than a wrong trade.",
            f"- {timeframe} BLINDSPOT: Price can fully reverse between your checks. Always SL at thesis invalidation point.",
            "- POSITION FIRST: If a position is open, managing it takes priority over finding new entries.",
            "- FEE MATH: Round-trip ~0.12%. Min viable trade = 0.3% gross. Never CLOSE for < 0.15% unless SL imminent.",
            "- ANTI-DUMP RULE: Never LONG into aggressive high-volume selling (vol > 1.5x avg on 3+ red candles).",
            "- ANTI-HESITATION: If BOS + Volume confirm, and RSI/ADX do NOT veto → FIRE the trade. Do not overthink.",
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

        # Add previous response context if available
        if previous_response:
            # previous_response will now be an aggregated string of up to 3 responses
            text_reasoning = previous_response.strip()
            if text_reasoning:
                window_minutes = 45  # Default to 3 candles of 15m
                if self.timeframe_validator:
                    try:
                        window_minutes = self.timeframe_validator.to_minutes(timeframe) * 3
                    except Exception:
                        pass

                header_lines.extend([
                    "",
                    "## 🆕 UPGRADE: MICRO-MEMORY (MAX 3 CANDLES)",
                ])
                if indicator_delta_alert:
                    header_lines.append(indicator_delta_alert)
                header_lines.extend([
                    "Your most recent analysis reasoning history:",
                    text_reasoning,
                    "",
                    "### CURRENT TIME CHECK",
                    f"- **Current Time**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
                    f"- **Relevance Window**: Track continuum of context over the last {window_minutes} minutes.",
                    "- Use this memory to track the sequence: BOS -> BOS = Trend confirmed. BOS -> CHOCH = Reversal.",
                ])

        # [🆕 UPGRADE: SESSION CONTEXT]
        current_hour_utc = datetime.now(timezone.utc).hour
        if 0 <= current_hour_utc < 8:
            session_name = "ASIA (Low volatility, high fakeouts - Require strict confirmation)"
        elif 8 <= current_hour_utc < 13:
            session_name = "LONDON (High volatility, primary window - Allow breakout execution)"
        elif 13 <= current_hour_utc < 21:
            session_name = "NEW YORK (Volatile - Watch for continuation traps and reversals)"
        else:
            session_name = "ASIA (Low volatility, high fakeouts - Require strict confirmation)"
            
        header_lines.extend([
            "",
            "## 🆕 UPGRADE: CURRENT SESSION CONTEXT",
            f"CURRENT SESSION: {session_name}",
            "Apply session-based confirmation logic to your trades.",
        ])

        return "\n".join(header_lines)

    def build_response_template(self, _has_chart_analysis: bool = False,
                                dynamic_thresholds: Optional[Dict[str, Any]] = None) -> str:
        """Build the response template for trading decision output."""
        thresholds = dynamic_thresholds or {}
        trade_count = thresholds.get("trade_count", 0)

        response_template = f'''Write your analysis in this exact order BEFORE the JSON (Chain-of-Thought reasoning):

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
   Fee check: Expected gross ≥ 0.3%? [YES/NO]
   Position size calculation (show your work):
     Base = confidence / 100
     Tier multiplier: confidence 55-69 → ×0.6 | 70-84 → ×1.0 | 85-100 → ×1.2
     ADX 20-25 developing: apply ×0.7 on final
     MACRO CAUTION flag: apply ×0.5 on final
     Final = max(0.10, min(0.50, base × tier × adjustments))

6. FINAL DECISION: [SIGNAL] — Confidence [X]/100
   One sentence: why this signal + exact invalidation condition.

⚠️ CRITICAL JSON RULES:
- HOLD/CLOSE: set entry_price, stop_loss, and take_profit to 0.0
- UPDATE: provide new stop_loss and/or take_profit only (entry_price = 0.0)
- position_size: 0.0 for HOLD/CLOSE, calculated tier value for entry

```json
{{
  "analysis": {{
    "signal": "BUY|SELL|HOLD|CLOSE|UPDATE",
    "confidence": 0,
    "entry_price": 0.0,
    "stop_loss": 0.0,
    "take_profit": 0.0,
    "position_size": 0.0,
    "risk_reward_ratio": 0.0,
    "reasoning": "1-2 short sentences: Structure + Volume + Why this signal",
    "key_levels": {{
      "support": [0.0, 0.0],
      "resistance": [0.0, 0.0]
    }},
    "confluence_factors": {{
      "structure_clarity": 0,
      "volume_confirmation": 0,
      "trend_alignment": 0,
      "veto_clear": 0,
      "liquidity_pool_quality": 0
    }},
    "trend": {{
      "direction": "BULLISH|BEARISH|SIDEWAYS",
      "structure": "BOS_UP|BOS_DOWN|CHOCH_UP|CHOCH_DOWN|NONE",
      "adx_strength": 0.0,
      "timeframe_alignment": "ALIGNED|MIXED|DIVERGENT"
    }}
  }}
}}
```

CONFLUENCE SCORING GUIDE (0-100):
- structure_clarity:  100=crystal clear BOS/CHOCH | 50=ambiguous | 0=no structure
- volume_confirmation: 100=>2x avg | 75=1.5-2x (minimum) | 0=<1.5x (fakeout)
- trend_alignment:    100=1H+4H both aligned | 60=1H only | 30=neutral | 0=opposing
- veto_clear:         100=RSI 30-70 + ADX>25 | 50=near extreme | 0=VETOED
- liquidity_pool_quality: 100=clean untouched swing | 50=partially tested | 0=arbitrary TP

SIGNAL RULES:
- BUY/SELL: ONLY if BOS confirmed + volume >1.5x avg + veto PASS + R/R ≥ 1.5:1
- HOLD: Default. No clear BOS | low volume | veto triggered | R/R < 1.5:1 | choppy
- CLOSE: Opposite BOS occurred against open position → EXIT IMMEDIATELY, no hope trading
- UPDATE: Position profitable >0.5% → trail SL to last structural swing, never move backward

UPDATE TRAILING RULE:
When signaling UPDATE:
- PRIMARY DUTY (SL Trail): Move SL to the most recent structural HL (for LONG) or LH (for SHORT).
  Trail SL progressively tighter on each candle as price moves further in favor.
  Never move SL away from profit direction.
- SECONDARY DUTY (TP Extension) — ⚡ PROACTIVE, NOT REACTIVE:
  → Do NOT wait for price to be near TP to think about extending it.
  → On EVERY candle while in profit, evaluate: Is there a MORE AMBITIOUS structural target beyond current TP?
  → If YES and structure still supports the trade → EXTEND TP to that target NOW.
  → Rule: New TP must be at a real untouched liquidity pool, not arbitrary. Min 2x ATR from current price.
  → Purpose: Capture the full move, not just the first target.
- Continue UPDATE signals until TP is hit or opposite BOS/CHOCH occurs.

TRADING SIGNALS (Gate-Based System):
- BUY/SELL: All 3 gates must pass → BOS confirmed + Volume >1.5x avg + Veto CLEAR
  R/R ≥ 1.5:1 required. Confidence tier determines position SIZE, not whether to enter.
- ANTI-HESITATION: BOS confirmed + Volume confirmed + Veto cleared → EXECUTE at confidence 55+.
  The BOS IS the signal. Do not wait for further confirmation candles.
- HOLD: Any gate failed | R/R < 1.5:1 | No clear structure | Fee check fails (<0.3% gross)
- CLOSE: Opposite BOS closed against open position → EXIT immediately. No averaging down.
- UPDATE: Profit >0.5% → (1) Trail SL to last swing structure. (2) Proactively EXTEND TP if next liquidity pool is visible and structure holds. Signal UPDATE every candle while profitable — evaluate BOTH SL trail AND TP extension each time.

RISK MANAGEMENT (Structural SL/TP Placement):
LONG: SL just below BOS origin candle's low or last HL (max 1.5% from entry)
      TP at next unswept swing HIGH / liquidity pool (target 1%-3%)
SHORT: SL just above BOS origin candle's high or last LH (max 1.5% from entry)
       TP at next unswept swing LOW / liquidity pool (target 1%-3%)
⛔ If structural SL requires >1.5% from entry → output HOLD. Setup risk is too wide.

DYNAMIC TRAILING (UPDATE Signal):
Trigger: Open position profit >0.5%%
Action: Move SL to most recent structural swing (HL for LONG, LH for SHORT)
Trail tighter each candle check. Never move SL away from profit direction.
Continue UPDATE signals until TP is hit or opposite BOS occurs.

HIGH-IMPACT EVENT PROTOCOL (replaces 365D Macro Conflict):
Sudden candle >2%% in ONE bar WITHOUT a preceding BOS setup → DO NOT chase.
This is likely news-driven, not structural. Wait for new BOS to form before entering.
If a high-volume news candle fires hard AGAINST an open position → treat as CLOSE signal immediately.
News can invalidate structural analysis instantly. Capital defense > being right.'''

        if trade_count > 0:
            response_template += (
                f"\n\nBRAIN NOTE: {trade_count} closed trades on record. "
                "Review recent trade outcomes to refine BOS confirmation requirements and SL tightness."
            )

        return response_template

    def build_analysis_steps(self, symbol: str, has_advanced_support_resistance: bool = False, has_chart_analysis: bool = False, available_periods: Optional[Dict] = None, timeframe: str = "15m") -> str:
        """Build analysis steps for the AI."""
        period_names = list(available_periods.keys()) if isinstance(available_periods, dict) else ["12h", "24h", "3d", "7d"]
        timeframe_desc = f"Analyze the provided Multi-Timeframe Price Summary periods: {', '.join(period_names)}"

        analysis_steps = f"""## Analysis Steps (use findings to determine trading signal):

**Step-to-Output Mapping:**
Step 1 → MARKET STRUCTURE (Primary decision driver)
Step 2 → VOLUME VALIDATION (Required confirmation & Anti-Dump check)
Step 3 → VETO CHECK (RSI/ADX extreme filter)
Step 4 → POSITION STATE (Manage existing or enter new?)
Step 5 → MACRO/NEWS ALERT (Black swan context only)
Synthesis → RISK/REWARD + STRICT SL/TP + FINAL DECISION

2. MARKET STRUCTURE MAPPING (PRIMARY):
   {timeframe_desc}
   [🆕 UPGRADE: H1/H4 DIRECTIONAL BIAS]
   → First, consult the Macro Bias data. Is the macro trend BULL, BEAR or SIDEWAYS?
   → Then identify swing highs/lows on the {timeframe} chart.
   → Is there a Break of Structure (BOS) or Change of Character (CHOCH)?
   → Check MICRO-MEMORY: Did you identify a BOS recently? Does this candle confirm it?
   🧠 CRITICAL GATE: Only take trades aligned with Macro Bias (BULL -> LONG only, BEAR -> SHORT only, SIDEWAYS -> HOLD or reduce confidence). If counter-trend or choppy structure → STOP HERE → Output HOLD.

2. VOLUME VALIDATION (REQUIRED):
   [🆕 UPGRADE: FLEXIBLE VOLUME]
   → Strong Confirmation: > 1.5x average (Valid)
   → Moderate Confirmation: 1.2x - 1.5x average (Valid ONLY if structure is very clear)
   → Weak Confirmation: < 1.2x average (Low-conviction breakout / fakeout → STOP HERE → Output HOLD)
   🛡️ ANTI-DUMP RADAR: Compare recent red vs. green volume. If recent sell volume aggressively
   dwarfs buy volume (massive red bars), DO NOT look for LONG setups on minor dips. It is a trap.

3. VETO CHECK (RSI/ADX):
   Use this ONLY to prevent terrible entries, NOT to find entries.
   → If bias is LONG: Is RSI > 80 (Overbought)?
   → If bias is SHORT: Is RSI < 20 (Oversold)?
   [🆕 UPGRADE: ADX RISING MOMENTUM]
   → Is ADX < 20? The trend is dead. VETO → HOLD.
     EXCEPTION: If ADX < 20 but is rising by ≥ 3 points → momentum building → DO NOT VETO.

4. POSITION STATE & DEFENSE:
   → Are we currently in an open position?
   → If YES (Losing): Did the {timeframe} candle close break market structure against us?
     If yes, Output CLOSE instantly.
   → If YES (Profitable, profit > 0.5%): MANDATORY — run the TP Extension Gate below:
     [TP EXTENSION GATE — run on EVERY candle while in profit]
     a. Is the current TP still 1 candle or less away? (i.e., distance from current price to TP < 1x ATR?)
     b. If YES: Is the market structure still strongly aligned with the trade direction?
        - SHORT in profit: Are LH/LL still forming? No CHOCH? Volume still sell-side dominant?
        - LONG in profit: Are HH/HL still forming? No CHOCH? Volume still buy-side dominant?
     c. If structure is still INTACT: Output UPDATE — set TP to the NEXT structural liquidity pool
        (next unswept swing low for SHORT, next unswept swing high for LONG), minimum 2x ATR away.
     d. If structure shows reversal signs (CHOCH forming, volume flipping): Output UPDATE — trail SL tight, keep current TP.
     e. If no clear structure or CHOCH confirmed against position: Output CLOSE.
   → If YES (Neutral / < 0.15% profit): HOLD.
   → If NO open position: Proceed to Synthesis ONLY if Steps 1–3 all passed.

5. NEWS ALERT (CONTEXT ONLY):
   → Is there a massive, sudden structural break >3%? Check the news context.

6. SYNTHESIS (EXECUTION):
   Combine findings to determine Entry, SL, and TP.
   → If R/R < 1.5:1 → output HOLD.
"""
        if has_chart_analysis:
            cfg_limit = int(self.config.AI_CHART_CANDLE_LIMIT)
            analysis_steps += f"""
## CHART IMAGE ANALYSIS (~{cfg_limit} candles):
1. **P1-PRICE:** SMA50/SMA200 status.
2. **P2-RSI:** Zone verification.
3. **P3-VOLUME:** Spike alignment.
4. **P4-CMF/OBV:** Accumulation status.
"""
        analysis_steps += "\nNOTE: Indicators calculated from CLOSED CANDLES ONLY."
        return analysis_steps
