import os
import re
import json
import logging
import requests
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger("aegis.llm_analyst")

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

class LLMTradingAnalyst:
    """
    QuantHive V3 — LLM Trading Analyst
    Checks whether independent evidence sources agree, explains disagreements in plain terms, 
    and recommends whether a candidate trade is coherent enough to proceed.
    """
    
    # Class-level cache: once a provider returns a billing/quota error, skip it
    # for the entire process lifetime so we don't hammer it on every trade.
    _disabled_providers: set = set()
    
    def __init__(self, local_url: str = "http://localhost:8080"):
        self.local_url = local_url
        
    def format_prompt(self, quant_signals: dict, performance_context: dict,
                      market_microstructure: dict, structure_context: dict,
                      risk_state: dict) -> str:
        """Formats the input data into the exact schema structured for the analyst."""
        prompt = (
            "You are a trading analyst, not a trading engine. Your job is to check whether independent "
            "evidence sources agree, explain any disagreement in plain terms, and recommend whether a candidate "
            "trade is coherent enough to proceed — you do not decide size, stop-loss, or take-profit, "
            "and you do not invent a probability. Those come from deterministic code downstream.\n\n"
            "You will receive: quant_signals (model outputs), performance_context (historical edge stats), "
            "market_microstructure (regime/liquidity/spread), structure_context (multi-timeframe price structure), "
            "and risk_state.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "STEP 1 — MODEL RECONCILIATION\n"
            "═══════════════════════════════════════════════════════════\n"
            "List what each of lstm, transformer, rl_agent, and statistical_model actually say. Count how many "
            "agree on direction. If they disagree, state the most likely reason (e.g. \"LSTM is reacting to recent "
            "momentum while the RL agent is pricing in expected reversion given current volatility regime\") — "
            "do not just report the disagreement, explain it in terms of what each model type is built to see.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "STEP 2 — QUANTITATIVE EDGE CHECK\n"
            "═══════════════════════════════════════════════════════════\n"
            "State plainly, using the numbers given: does this setup's reason_code have a positive historical "
            "edge (win rate, profit factor, ev_per_trade)? Is recent_sharpe and current_drawdown_pct in a range "
            "where taking more risk is reasonable, or should conviction be discounted because performance has been "
            "poor recently regardless of how good this setup looks? A strong-looking setup during a bad drawdown "
            "period is a reason for caution, not an exception to it.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "STEP 3 — MICROSTRUCTURE CHECK\n"
            "═══════════════════════════════════════════════════════════\n"
            "Given current liquidity_score, order_flow_imbalance, spread, and estimated_slippage: is this a clean "
            "environment to enter, or would execution costs likely erode the edge identified above? A good signal "
            "in a bad liquidity environment should be downgraded.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "STEP 4 — STRUCTURAL CONTEXT\n"
            "═══════════════════════════════════════════════════════════\n"
            "Does structure_context (HTF bias, MTF zone, LTF trigger, SMC context) support or contradict the "
            "direction the models agree on? This is confirming evidence, not the primary decision driver.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "STEP 5 — SELF-CRITIQUE\n"
            "═══════════════════════════════════════════════════════════\n"
            "State the single strongest reason this trade could fail, using the actual data given, not a generic "
            "risk disclaimer.\n\n"
            "═══════════════════════════════════════════════════════════\n"
            "OUTPUT — respond in exactly this structure\n"
            "═══════════════════════════════════════════════════════════\n"
            "<thought>\n"
            "Steps 1-5 above, each 1-2 sentences, citing actual values you were given.\n"
            "</thought>\n"
            "<verdict>\n"
            "{\n"
            "  \"model_agreement_count\": \"n/4\",\n"
            "  \"historical_edge\": \"positive\" | \"negative\" | \"neutral\",\n"
            "  \"microstructure_quality\": \"clean\" | \"degraded\",\n"
            "  \"structure_alignment\": \"confirming\" | \"contradicting\" | \"neutral\",\n"
            "  \"strongest_risk\": \"one sentence\",\n"
            "  \"recommendation\": \"approve\" | \"approve_reduced\" | \"reject\",\n"
            "  \"reason_code\": \"string\"\n"
            "}\n"
            "</verdict>\n\n"
            "--- INPUT DATA ---\n"
            f"quant_signals: {json.dumps(quant_signals, indent=2)}\n\n"
            f"performance_context: {json.dumps(performance_context, indent=2)}\n\n"
            f"market_microstructure: {json.dumps(market_microstructure, indent=2)}\n\n"
            f"structure_context: {json.dumps(structure_context, indent=2)}\n\n"
            f"risk_state: {json.dumps(risk_state, indent=2)}"
        )
        return prompt

    def analyze_trade(self, quant_signals: dict, performance_context: dict,
                      market_microstructure: dict, structure_context: dict,
                      risk_state: dict) -> tuple[str, dict]:
        """Runs the main evaluation. Tries local server, falls back to cloud APIs, then deterministic rules."""
        prompt = self.format_prompt(quant_signals, performance_context, market_microstructure, structure_context, risk_state)
        
        # 1. Try Local llama.cpp/vLLM server first (skip if already known offline)
        if "local" not in LLMTradingAnalyst._disabled_providers:
            try:
                headers = {"Content-Type": "application/json"}
                payload = {
                    "model": "qwen-1.5b-trading-analyst",
                    "messages": [
                        {"role": "system", "content": "You are a trading analyst. Respond strictly in the <thought>/<verdict> format."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024
                }
                response = requests.post(
                    f"{self.local_url}/v1/chat/completions",
                    headers=headers, json=payload, timeout=0.5,
                )
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]
                    thought, verdict = self._parse_output(content)
                    if thought and verdict:
                        logger.info("[LLM ANALYST] Successfully received decision from Local llama-server.")
                        return thought, verdict
            except requests.exceptions.ConnectionError:
                logger.debug("[LLM ANALYST] Local llama-server not reachable ? disabling for this session.")
                LLMTradingAnalyst._disabled_providers.add("local")
            except Exception as e:
                logger.debug(f"[LLM ANALYST] Local llama-server failed: {e}")

        # 2. Fallback to Claude (Anthropic API) if key is present and not disabled
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key and "anthropic" not in LLMTradingAnalyst._disabled_providers:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    temperature=0.1,
                    system="You are a trading analyst. Respond strictly in the <thought>/<verdict> format.",
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
                thought, verdict = self._parse_output(content)
                if thought and verdict:
                    logger.info("[LLM ANALYST] Successfully received decision from Anthropic API (Claude).")
                    return thought, verdict
            except Exception as e:
                err_str = str(e)
                if "credit balance" in err_str or "quota" in err_str.lower() or "402" in err_str or "400" in err_str:
                    logger.warning("[LLM ANALYST] Claude credits exhausted ? disabling for this session.")
                    LLMTradingAnalyst._disabled_providers.add("anthropic")
                else:
                    logger.warning(f"[LLM ANALYST] Claude API request failed: {e}")

        # 3. Fallback to Gemini (Google GenAI API) if key is present and not disabled
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_key and "gemini" not in LLMTradingAnalyst._disabled_providers:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.1, "max_output_tokens": 1024}
                )
                content = response.text
                thought, verdict = self._parse_output(content)
                if thought and verdict:
                    logger.info("[LLM ANALYST] Successfully received decision from Gemini API.")
                    return thought, verdict
            except Exception as e:
                err_str = str(e)
                if "quota" in err_str.lower() or "billing" in err_str.lower():
                    logger.warning("[LLM ANALYST] Gemini quota exhausted ? disabling for this session.")
                    LLMTradingAnalyst._disabled_providers.add("gemini")
                else:
                    logger.warning(f"[LLM ANALYST] Gemini API request failed: {e}")

        # 4. Fallback to OpenAI API if key is present and not disabled
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and "openai" not in LLMTradingAnalyst._disabled_providers:
            try:
                import openai
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a trading analyst. Respond strictly in the <thought>/<verdict> format."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024,
                    temperature=0.1
                )
                content = response.choices[0].message.content
                thought, verdict = self._parse_output(content)
                if thought and verdict:
                    logger.info("[LLM ANALYST] Successfully received decision from OpenAI API.")
                    return thought, verdict
            except Exception as e:
                err_str = str(e)
                if "quota" in err_str.lower() or "billing" in err_str.lower() or "insufficient_quota" in err_str:
                    logger.warning("[LLM ANALYST] OpenAI quota exhausted ? disabling for this session.")
                    LLMTradingAnalyst._disabled_providers.add("openai")
                else:
                    logger.warning(f"[LLM ANALYST] OpenAI API request failed: {e}")

        # 5. Deterministic Local Rule Consensus Fallback (100% resilient offline baseline)
        logger.warning("[LLM ANALYST] Serving Offline Deterministic Rule Consensus Fallback.")
        return self._consensus_fallback(quant_signals, performance_context, market_microstructure, structure_context, risk_state)

    def _consensus_fallback(self, quant_signals: dict, performance_context: dict,
                            market_microstructure: dict, structure_context: dict,
                            risk_state: dict) -> tuple[str, dict]:
        """Gives a deterministic, rule-based fallback thought/verdict for trade execution safety."""
        # Calculate agreement
        lstm_dir = quant_signals.get("lstm", {}).get("direction", 0)
        trans_dir = quant_signals.get("transformer", {}).get("direction", 0)
        rl_action = quant_signals.get("rl_agent", {}).get("action", "wait")
        stat_dir = quant_signals.get("statistical_model", {}).get("direction", 0)
        
        # v6.1 FIX: RL agent returns "BUY"/"SELL" (uppercase) — the old
        # case-sensitive check `rl_action == "buy"` silently discarded every
        # RL vote as neutral, forcing 1v1 ties -> "conflicting_signals" rejections.
        rl_norm = str(rl_action).strip().lower()
        rl_dir = 1 if rl_norm == "buy" else (-1 if rl_norm == "sell" else 0)
        
        # Count agreement direction
        directions = [lstm_dir, trans_dir, rl_dir, stat_dir]
        buys = sum(1 for d in directions if d == 1)
        sells = sum(1 for d in directions if d == -1)
        waits = sum(1 for d in directions if d == 0)
        
        max_agreement = max(buys, sells)
        agg_dir = "BUY" if buys > sells else ("SELL" if sells > buys else "NA")
        
        # Edge checks
        wr = performance_context.get("reason_code_historical_win_rate", 50.0)
        pf = performance_context.get("profit_factor", 1.0)
        dd = performance_context.get("current_drawdown_pct", 0.0)
        
        edge_quality = "neutral"
        if wr >= 53.0 and pf >= 1.4:
            edge_quality = "positive"
        elif wr < 47.0 or pf < 1.0:
            edge_quality = "negative"
            
        # Microstructure checks — use symbol-aware max spread
        spread = market_microstructure.get("current_spread", 20.0)
        symbol_hint = market_microstructure.get("symbol", "")
        if "XAU" in str(symbol_hint).upper() or "GOLD" in str(symbol_hint).upper():
            max_spread = 55.0  # Gold normal spread is 30-50pts — allow through
        elif "XAG" in str(symbol_hint).upper():
            max_spread = 100.0
        else:
            max_spread = 25.0  # Forex — tight spread expected
        micro_quality = "clean" if spread <= max_spread else "degraded"
        
        # Structure alignment
        htf = structure_context.get("htf_bias", "").lower()
        trigger = structure_context.get("ltf_trigger", "").lower()
        
        align = "neutral"
        if htf in ("bullish", "bearish") and trigger in ("bos", "choch", "sweep", "rsi_bounce"):
            align = "confirming"
            
        # Coherence recommendation logic
        rec = "approve"
        reason = "acceptable_consensus_and_clean_microstructure"
        risk_str = "Standard market noise."
        
        if max_agreement >= 3:
            if micro_quality == "clean":
                rec = "approve" if edge_quality != "negative" else "approve_reduced"
                reason = "high_consensus"
                risk_str = "Minor model variance."
            else:
                rec = "approve_reduced"
                reason = "high_consensus_degraded_microstructure"
                risk_str = "Spread elevated."
        elif max_agreement >= 1:
            if edge_quality == "negative" and micro_quality != "clean":
                rec = "reject"
                reason = "low_consensus_and_negative_edge"
                risk_str = "Model disagreement with poor historical edge."
            elif buys > 0 and sells > 0 and min(buys, sells) >= 2:
                # v6.1 FIX: a 1-vs-1 tie with 2 neutral models is weak evidence,
                # not a conflict — it was hard-rejecting 100% of signals
                # ("conflicting_signals"). Only a 2-vs-2 split is a true conflict.
                rec = "reject"
                reason = "conflicting_signals"
                risk_str = "Equal opposing signals across models."
            else:
                rec = "approve_reduced" if edge_quality == "negative" else "approve"
                reason = "moderate_consensus"
                risk_str = "Partial model consensus with acceptable parameters."
        else:
            rec = "reject"
            reason = "no_directional_consensus"
            risk_str = "No models generated directional bias."
                
        if dd >= 4.0:
            rec = "reject"
            reason = "drawdown_veto"
            risk_str = f"Account drawdown at {dd}% is too high."
            
        if micro_quality == "degraded":
            rec = "reject"
            reason = "spread_veto"
            risk_str = f"Spread {spread} exceeds standard thresholds."

        # Template natural language thought
        thought = (
            f"Step 1: Quant signals show directional agreement count at {max_agreement}/4 on {agg_dir}. "
            f"Step 2: Quantitative edge check shows win rate is {wr}% and profit factor is {pf}, yielding a {edge_quality} edge. "
            f"Step 3: Microstructure check shows spread is {spread} pts, indicating a {micro_quality} environment. "
            f"Step 4: Structural context HTF bias is {htf} which yields a {align} alignment. "
            f"Step 5: Self-critique identifies risk as: {risk_str}"
        )
        
        verdict = {
            "model_agreement_count": f"{max_agreement}/4",
            "historical_edge": edge_quality,
            "microstructure_quality": micro_quality,
            "structure_alignment": align,
            "strongest_risk": risk_str,
            "recommendation": rec,
            "reason_code": reason
        }
        
        return thought, verdict

    def _parse_output(self, model_output: str) -> tuple[str, dict]:
        """Tries parsing thought and verdict from output string."""
        try:
            from brain.train_analyst_grpo import parse_output as grpo_parse
            return grpo_parse(model_output)
        except Exception:
            # Re-implement fallback parser in case import fails
            thought = ""
            verdict = {}
            thought_match = re.search(r"<thought>(.*?)</thought>", model_output, re.DOTALL | re.IGNORECASE)
            if thought_match:
                thought = thought_match.group(1).strip()
            verdict_match = re.search(r"<verdict>(.*?)</verdict>", model_output, re.DOTALL | re.IGNORECASE)
            if verdict_match:
                verdict_str = verdict_match.group(1).strip()
                try:
                    verdict_str = re.sub(r"```json\s*", "", verdict_str)
                    verdict_str = re.sub(r"\s*```", "", verdict_str)
                    verdict = json.loads(verdict_str)
                except Exception:
                    pass
            return thought, verdict
