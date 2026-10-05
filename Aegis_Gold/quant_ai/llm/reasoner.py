"""AEGIS QUANT AI - OPTIONAL free local LLM reasoning layer (Task 6).

Uses Ollama (http://localhost:11434) with free local models only
(qwen2.5, llama3.1, mistral, gemma2, phi3 - whatever is pulled locally).
No DeepSeek. No paid APIs. No internet requirement: if Ollama is
unreachable the layer returns ``available=False`` and the trading
pipeline continues unchanged.

HARD CONSTRAINTS (enforced by design, not just convention):
  - the LLM NEVER places orders and has NO access to MT5/order_send
  - its output is advisory reasoning attached to an ALREADY-computed
    quant signal; it cannot change direction, lot size, SL or TP
  - malformed/timeout/unavailable responses degrade to ``None`` reason
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("quant_ai.llm")

DEFAULT_URL = "http://localhost:11434"
_TIMEOUT_S = 20


@dataclass
class LLMReasoning:
    model: str
    reasoning: str
    risk_notes: str
    raw_text: str


class OllamaReasoner:
    """Advisory-only market reasoning via a free local Ollama model."""

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = DEFAULT_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._available: Optional[bool] = None

    # -- availability ------------------------------------------------------
    def health_check(self, force: bool = False) -> bool:
        """True only if the Ollama daemon answers AND the model is pulled."""
        if self._available is not None and not force:
            return self._available
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.base_url}/api/tags",
                                        timeout=3) as resp:
                tags = json.loads(resp.read().decode("utf-8"))
            names = [t.get("name", "") for t in tags.get("models", [])]
            self._available = any(n.startswith(self.model.split(":")[0])
                                  for n in names)
        except Exception:
            self._available = False
        return self._available

    # -- generation --------------------------------------------------------
    def reason(self, *, symbol: str, timeframe: str, regime: str,
               volatility: dict, signal_direction: str,
               ensemble_summary: dict, risk_summary: str = "") -> Optional[LLMReasoning]:
        """Produce advisory reasoning for an already-computed quant signal.

        Returns None on ANY failure (offline, timeout, malformed output) -
        callers must treat None as 'no LLM commentary available'.
        """
        if not self.health_check():
            logger.info("ollama unavailable - reasoning layer skipped")
            return None
        prompt = (
            "You are a cautious trading ANALYST. You do NOT execute trades. "
            "Given this measured data, explain in <=120 words the risks and "
            "context of the proposed signal. Do not invent numbers.\n"
            f"Symbol: {symbol} ({timeframe})\n"
            f"Quant signal: {signal_direction}\n"
            f"Regime: {regime}\n"
            f"Volatility: {json.dumps(volatility, default=str)}\n"
            f"Ensemble: {json.dumps(ensemble_summary, default=str)}\n"
            f"Risk checks: {risk_summary}\n"
            "Answer as JSON: {\"reasoning\": \"...\", \"risk_notes\": \"...\"}"
        )
        payload = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256},
        }).encode("utf-8")
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/generate", data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("ollama generate failed (fail-safe skip): %s", exc)
            self._available = None
            return None
        text = str(data.get("response", "")).strip()
        if not text:
            return None
        parsed = self._parse_json_block(text)
        if parsed is None:
            # valid generation but non-JSON -> keep raw text as reasoning only
            return LLMReasoning(model=self.model, reasoning=text[:1200],
                                risk_notes="", raw_text=text)
        return LLMReasoning(model=self.model,
                            reasoning=str(parsed.get("reasoning", ""))[:1200],
                            risk_notes=str(parsed.get("risk_notes", ""))[:600],
                            raw_text=text)

    @staticmethod
    def _parse_json_block(text: str) -> Optional[dict]:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
