"""AEGIS QUANT AI - Financial NLP / sentiment layer (directive Sections 18-19).

Policy (Section 19):
  - If no legal/free news source is configured, the module stays DISABLED
    (default) and never produces signals.
  - No website scraping in violation of terms of service.
  - Sentiment NEVER generates a trade on its own; it can only annotate the
    decision record and (optionally, if enabled) contribute a bounded
    risk-event flag consumed by the risk engine.
"""
from quant_ai.nlp.sentiment import FinBertSentiment, SentimentEngine  # noqa: F401

__all__ = ["FinBertSentiment", "SentimentEngine"]
