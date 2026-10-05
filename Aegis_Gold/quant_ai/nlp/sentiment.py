"""AEGIS QUANT AI - sentiment engine (Sections 18-19).

Verified model (see models/verified_models.json):
  FinBERT - ProsusAI/finbert, Apache-2.0, official repo
  https://github.com/ProsusAI/finBERT - 3-class softmax
  (positive / negative / neutral), weights on Hugging Face.

Restrictions honored:
  - FinGPT models are HF-gated (require auth) -> NOT auto-downloaded.
  - No scraping of news sites; only data sources explicitly configured by
    the operator (e.g. a licensed RSS/file feed) are consumed.
  - news_mode DISABLED (default): engine returns unavailable sentiment and
    never influences decisions.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("quant_ai.nlp")

FINBERT_REPO = "ProsusAI/finbert"          # verified: Apache-2.0
NEWS_MODES = ("DISABLED", "PASSIVE", "ACTIVE")   # ACTIVE still never trades alone


@dataclass
class SentimentResult:
    source: str
    label: str = "neutral"           # positive / negative / neutral
    p_positive: Optional[float] = None
    p_negative: Optional[float] = None
    p_neutral: Optional[float] = None
    score: Optional[float] = None    # p_pos - p_neg (FinBERT convention)
    available: bool = False
    reason: str = "module disabled"

    def to_dict(self) -> Dict:
        return {"source": self.source, "label": self.label,
                "p_positive": self.p_positive, "p_negative": self.p_negative,
                "p_neutral": self.p_neutral, "score": self.score,
                "available": self.available, "reason": self.reason}


class FinBertSentiment:
    """Lazy-loading FinBERT adapter.  Download-once, cache-locally (Sec 41)."""

    name = "finbert"
    min_history = 0                    # NLP model: no OHLCV history needed

    def __init__(self, repo: str = FINBERT_REPO, device: Optional[str] = None,
                 cache_dir: Optional[str] = None):
        self.repo = repo
        self.device = device
        self.cache_dir = cache_dir
        self._pipe = None

    def load(self) -> bool:
        if self._pipe is not None:
            return True
        try:
            from transformers import pipeline   # lazy: heavy import
            kwargs = {"model": self.repo}
            if self.device:
                kwargs["device"] = self.device
            if self.cache_dir:
                os.environ.setdefault("HF_HOME", self.cache_dir)
            self._pipe = pipeline("text-classification", **kwargs)
            return True
        except Exception as exc:
            logger.error("FinBERT load failed (weights/download/transformers): %s", exc)
            self._pipe = None
            return False

    def score_headlines(self, headlines: List[str]) -> SentimentResult:
        """Aggregate sentiment over headlines.  Never fabricates: if the
        model is unavailable the result is marked unavailable."""
        if not headlines:
            return SentimentResult(self.name, available=False, reason="no headlines")
        if self._pipe is None and not self.load():
            return SentimentResult(self.name, available=False,
                                   reason="model not loaded")
        try:
            outs = self._pipe(list(headlines)[:50], truncation=True)
            n = len(outs)
            agg = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
            for row in outs:
                agg[row["label"].lower()] += float(row["score"])
            p_pos, p_neg, p_neu = (agg["positive"] / n, agg["negative"] / n,
                                   agg["neutral"] / n)
            dom = max(agg, key=agg.get)
            return SentimentResult(self.name, label=dom, p_positive=round(p_pos, 4),
                                   p_negative=round(p_neg, 4), p_neutral=round(p_neu, 4),
                                   score=round(p_pos - p_neg, 4), available=True,
                                   reason=f"{n} headlines scored")
        except Exception as exc:
            logger.error("FinBERT inference failed: %s", exc)
            return SentimentResult(self.name, available=False,
                                   reason=f"inference error: {exc}")


class SentimentEngine:
    """Mode-gated facade.  news_mode DISABLED (default) => no-op."""

    def __init__(self, news_mode: str = "DISABLED",
                 backends: Optional[List[FinBertSentiment]] = None):
        self.news_mode = news_mode if news_mode in NEWS_MODES else "DISABLED"
        self.backends = backends or []

    @classmethod
    def from_config(cls, cfg) -> "SentimentEngine":
        return cls(news_mode=cfg.news_mode,
                   backends=[FinBertSentiment()])

    def evaluate(self, headlines: List[str]) -> SentimentResult:
        if self.news_mode == "DISABLED" or not headlines:
            return SentimentResult("sentiment_engine", available=False,
                                   reason=f"news_mode={self.news_mode}")
        for backend in self.backends:
            res = backend.score_headlines(headlines)
            if res.available:
                return res
        return SentimentResult("sentiment_engine", available=False,
                               reason="no backend available")

    def risk_event_flag(self, sentiment: SentimentResult,
                        abs_score_threshold: float = 0.6) -> bool:
        """Bounded consumption by risk layer: strong one-sided sentiment may
        flag a news-risk event; it can only BLOCK, never create a trade."""
        if not sentiment.available or self.news_mode != "ACTIVE":
            return False
        return (sentiment.score is not None
                and abs(sentiment.score) >= abs_score_threshold)
