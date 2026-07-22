# ============================================================
# CLAUDE AI ANALYST — Chart analysis & trade signal engine
# ============================================================

import json
import anthropic
from loguru import logger
from config import CLAUDE_API_KEY, CLAUDE_MODEL, CONFIDENCE_THRESHOLD


client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """
You are a professional XAUUSD (Gold) M5 scalping analyst with 20 years of experience.
Your job is to analyze real-time market data and make precise, disciplined trade decisions.

RULES YOU MUST FOLLOW:
- Only signal BUY or SELL when confidence is 75% or higher
- HOLD if conditions are unclear, spread is high, or market is choppy
- Never fight the trend — align with EMA direction
- RSI above 70 = avoid BUY, RSI below 30 = avoid SELL
- Check Bollinger Band position for confirmation
- Consider session context (Asian = low volatility, London/NY = high momentum)
- Prioritize capital preservation over profit

YOU MUST RESPOND ONLY WITH VALID JSON — no extra text, no markdown, no explanation outside JSON.

Response format:
{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": <integer 0-100>,
  "sl_pips": <integer, stop loss in pips>,
  "tp_pips": <integer, take profit in pips>,
  "reason": "<one clear sentence explaining the signal>",
  "risk_note": "<any warning or caution>"
}
"""


def build_prompt(indicators: dict, candles_summary: list,
                 account: dict, session: str, recent_trades: list) -> str:
    return f"""
Analyze current XAUUSD M5 market conditions and provide a trade signal.

=== ACCOUNT STATUS ===
Balance      : ${account.get('balance', 0):.2f}
Equity       : ${account.get('equity', 0):.2f}
Open P&L     : ${account.get('profit', 0):.2f}

=== SESSION ===
Current Session: {session}

=== LATEST INDICATORS ===
Price        : {indicators.get('price')}
EMA Fast(9)  : {indicators.get('ema_fast')}
EMA Slow(21) : {indicators.get('ema_slow')}
EMA Cross    : {indicators.get('ema_cross')} (1=bullish, -1=bearish, 0=none)
Trend        : {indicators.get('trend')}
RSI(14)      : {indicators.get('rsi')} [{indicators.get('rsi_zone')}]
ATR(14)      : {indicators.get('atr')}
BB Upper     : {indicators.get('bb_upper')}
BB Mid       : {indicators.get('bb_mid')}
BB Lower     : {indicators.get('bb_lower')}
BB Signal    : {indicators.get('bb_signal')}

=== LAST 10 CANDLES (newest last) ===
{json.dumps(candles_summary[-10:], indent=2)}

=== RECENT TRADES (last 5) ===
{json.dumps(recent_trades[-5:], indent=2)}

Based on all the above, provide your trading signal in JSON format.
"""


def get_signal(indicators: dict, candles_summary: list,
               account: dict, session: str, recent_trades: list) -> dict:
    """Call Claude API and return parsed trade signal."""

    prompt = build_prompt(indicators, candles_summary, account, session, recent_trades)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        logger.debug(f"Claude raw response: {raw}")

        # Strip markdown if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)

        # Validate required fields
        required = ["signal", "confidence", "sl_pips", "tp_pips", "reason"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing field: {field}")

        signal = result["signal"].upper()
        if signal not in ["BUY", "SELL", "HOLD"]:
            result["signal"] = "HOLD"

        logger.info(
            f"🧠 Claude Signal: {result['signal']} | "
            f"Confidence: {result['confidence']}% | "
            f"Reason: {result['reason']}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Claude JSON parse error: {e}")
        return {"signal": "HOLD", "confidence": 0, "sl_pips": 0,
                "tp_pips": 0, "reason": "Parse error", "risk_note": str(e)}
    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return {"signal": "HOLD", "confidence": 0, "sl_pips": 0,
                "tp_pips": 0, "reason": "API error", "risk_note": str(e)}
    except Exception as e:
        logger.error(f"Unexpected Claude error: {e}")
        return {"signal": "HOLD", "confidence": 0, "sl_pips": 0,
                "tp_pips": 0, "reason": "Unknown error", "risk_note": str(e)}


def get_daily_review(trades: list, account: dict) -> str:
    """Ask Claude to review today's performance and suggest improvements."""
    prompt = f"""
You are reviewing a gold trading bot's daily performance.

Account: {json.dumps(account, indent=2)}
Today's trades: {json.dumps(trades, indent=2)}

Analyze:
1. Win rate and profitability
2. Entry/exit quality
3. Risk management effectiveness
4. Specific improvements for tomorrow

Respond in plain text, 5-8 sentences, professional and concise.
"""
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        return f"Daily review unavailable: {e}"
