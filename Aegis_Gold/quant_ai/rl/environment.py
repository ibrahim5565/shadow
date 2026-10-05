"""AEGIS QUANT AI - RL trading environment (directive Sections 9-12).

RESEARCH ONLY by default. Gymnasium-compatible (falls back to a minimal
internal base when gymnasium is absent so tests run dependency-free).

Design constraints honored:
  Section 11 - state uses OBSERVABLE information only (no future data).
  Section 12 - actions HOLD/BUY/SELL/CLOSE; every action passes through the
               independent RiskManager: an agent can NEVER bypass risk,
               drawdown, spread, session or margin checks, and lot size is
               computed by the risk engine - never from raw agent confidence.
  Section 10 - rl_mode_gate() promotes nothing beyond RL_RESEARCH until
               walk-forward validation evidence is supplied.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from quant_ai.config import DEFAULT_CONFIG, QAIConfig, RL_DEMO, RL_DISABLED
from quant_ai.config import RL_PAPER, RL_RESEARCH
from quant_ai.quant.factors import adx as _adx, ema as _ema, rsi as _rsi
from quant_ai.quant.volatility import VolatilityEngine
from quant_ai.risk.risk_engine import RiskManager

logger = logging.getLogger("quant_ai.rl.environment")

# -- action space (Section 12) ---------------------------------------------
ACTIONS = ("HOLD", "BUY", "SELL", "CLOSE")          # discrete indices 0..3
ACTION_HOLD, ACTION_BUY, ACTION_SELL, ACTION_CLOSE = 0, 1, 2, 3

STATE_FIELDS = ("ret_1", "ret_5", "rsi_14", "ema_gap", "macd_gap", "adx_14",
                "atr_pct", "vol_pctile", "bb_pos", "session_idx",
                "position_dir", "unrealized_r")
OBS_DIM = len(STATE_FIELDS)                          # 12

SESSION_NAMES = ("ASIAN", "LONDON", "NY", "LATE_NY")


# -- gymnasium-compatible base (optional dependency) ------------------------
try:
    import gymnasium as gym
    _Base = gym.Env
except Exception:                                    # pragma: no cover
    class _Base:                                     # minimal stand-in
        metadata = {"render_modes": []}
        observation_space = None
        action_space = None


@dataclass
class EnvPosition:
    direction: int                       # 0 flat, 1 long, -1 short
    lot: float
    entry: float
    sl: float
    tp: float
    entry_index: int


def _hour_session(hour: float) -> int:
    h = int(hour) % 24
    if 7 <= h < 12:
        return 1        # LONDON
    if 12 <= h < 17:
        return 2        # NY / overlap
    if 0 <= h < 7:
        return 0        # ASIAN
    return 3            # late NY / rollover


class TradingEnv(_Base):
    """Walk a closed OHLCV history bar-by-bar with observable-only features.

    Every trade is sized/validated by RiskManager; SL/TP are ATR-derived and
    clamped by the risk engine's bounds. Episode ends on data exhaustion or
    drawdown breach; an open position is force-closed at the terminal bar.
    """

    def __init__(self, df: pd.DataFrame, config: Optional[QAIConfig] = None,
                 symbol: str = "EURUSD", timeframe: str = "M5",
                 equity: float = 10_000.0, spread_pts: float = 2.0,
                 point: float = 0.00001, point_value_per_lot: float = 1.0,
                 warmup: int = 60, max_drawdown: Optional[float] = None):
        self.df = df.reset_index(drop=True)
        self.cfg = config or DEFAULT_CONFIG
        self.symbol = symbol
        self.timeframe = timeframe
        self.start_equity = float(equity)
        self.spread_pts = float(spread_pts)
        self.point = float(point)
        self.point_value_per_lot = float(point_value_per_lot)
        self.warmup = max(int(warmup), 60)
        self.max_dd = max_drawdown if max_drawdown is not None else self.cfg.max_drawdown

        self.vol_engine = VolatilityEngine()
        self.risk = RiskManager(self.cfg)
        self._precompute()
        self._session_col = self._session_series()

        self.t = self.warmup
        self.position: Optional[EnvPosition] = None
        self.closed_pnl: list = []
        self.history_equity = self.start_equity
        self.done = False
        self.last_gate: str = ""

        # SB3-compatible spaces (only when gymnasium is available)
        try:
            from gymnasium import spaces
            self.observation_space = spaces.Box(
                -10.0, 10.0, shape=(OBS_DIM,), dtype=np.float32)
            self.action_space = spaces.Discrete(len(ACTIONS))
        except Exception:                                # pragma: no cover
            self.observation_space = None
            self.action_space = None

    # -- observable-only feature computation (Section 11) -------------------
    def _precompute(self) -> None:
        c = self.df["close"].astype(float)
        h = self.df["high"].astype(float)
        l = self.df["low"].astype(float)
        self.f_ret1 = c.pct_change(1).fillna(0.0)
        self.f_ret5 = c.pct_change(5).fillna(0.0)
        self.f_rsi = (_rsi(c, 14).fillna(50.0) / 100.0)
        e21, e50 = _ema(c, 21), _ema(c, 50)
        self.f_ema_gap = ((e21 - e50) / (e50 + 1e-12)).fillna(0.0)
        macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
        self.f_macd_gap = (macd / (c + 1e-12)).fillna(0.0)
        self.f_adx = (_adx(h, l, c, 14).fillna(0.0) / 100.0)
        atr = self.vol_engine.atr(self.df).fillna(0.0)
        self.f_atr_pct = ((atr / (c + 1e-12)).clip(0, 0.01) * 100.0)
        rv = c.pct_change().rolling(20).std().fillna(0.0)
        self.f_vol_pctile = rv.rolling(300, min_periods=30).apply(
            lambda w: (w[:-1] <= w[-1]).mean() if len(w) > 30 else 0.5,
            raw=True).fillna(0.5)
        mid, sd = c.rolling(20).mean(), c.rolling(20).std()
        self.f_bb_pos = (((c - mid) / (2 * sd + 1e-12)).fillna(0.0).clip(-2, 2) / 2.0)

    def _session_series(self) -> pd.Series:
        if "time" in self.df.columns:
            hrs = (self.df["time"].astype(float) % 86400.0) // 3600.0
            return hrs.map(lambda x: float(_hour_session(x)))
        if isinstance(self.df.index, pd.DatetimeIndex):
            return pd.Series(self.df.index.hour.map(_hour_session).astype(float),
                             index=self.df.index)
        return pd.Series(1.0, index=self.df.index)      # LONDON default

    # -- state (Section 11) --------------------------------------------------
    def _obs(self) -> np.ndarray:
        i = self.t
        pos_dir = float(self.position.direction) if self.position else 0.0
        unreal_r = self._unrealized_r()
        return np.array([
            float(np.clip(self.f_ret1.iloc[i], -0.05, 0.05)) * 20.0,
            float(np.clip(self.f_ret5.iloc[i], -0.10, 0.10)) * 10.0,
            float(self.f_rsi.iloc[i]) * 2.0 - 1.0,
            float(np.clip(self.f_ema_gap.iloc[i] * 100.0, -1, 1)),
            float(np.clip(self.f_macd_gap.iloc[i] * 100.0, -1, 1)),
            float(self.f_adx.iloc[i]) * 2.0 - 1.0,
            float(self.f_atr_pct.iloc[i]),
            float(self.f_vol_pctile.iloc[i]) * 2.0 - 1.0,
            float(self.f_bb_pos.iloc[i]),
            float(self._session_col.iloc[i]) / 3.0,
            pos_dir,
            float(np.clip(unreal_r, -3.0, 3.0)),
        ], dtype=np.float32)

    def _unrealized_r(self) -> float:
        if self.position is None:
            return 0.0
        price = float(self.df["close"].iloc[self.t])
        p = self.position
        move_pts = (price - p.entry) / self.point * p.direction
        sl_pts = abs(p.entry - p.sl) / self.point
        return move_pts * p.lot / max(sl_pts * p.lot, 1e-9)

    def state_dict(self) -> Dict[str, float]:
        """Named observable state, exported for research/audit."""
        return {k: round(float(v), 6)
                for k, v in zip(STATE_FIELDS, self._obs())}

    # -- gymnasium API --------------------------------------------------------
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        if hasattr(super(), "reset"):
            super().reset(seed=seed)
        self.t = self.warmup
        self.position = None
        self.risk = RiskManager(self.cfg)
        self.closed_pnl = []
        self.history_equity = self.start_equity
        self.done = False
        return self._obs(), {"symbol": self.symbol, "timeframe": self.timeframe}

    def step(self, action: int):
        if self.done:
            return self._obs(), 0.0, True, False, {"reason": "episode finished"}
        prev_equity = self._mark_equity()
        self._apply(int(action))
        self.t += 1
        self._check_stops()
        equity = self._mark_equity()
        peak = max(self.history_equity, equity)
        dd = (peak - equity) / max(peak, 1.0)
        self.history_equity = peak
        self.done = (self.t >= len(self.df) - 1) or dd >= self.max_dd
        if self.done and self.position is not None:
            self._apply(ACTION_CLOSE, force=True)
            equity = self._mark_equity()
        reward = (equity - prev_equity) / max(self.start_equity, 1.0)
        info = {"equity": round(equity, 2),
                "position": self.position.direction if self.position else 0,
                "gate": self.last_gate,
                "drawdown_pct": round(dd, 4),
                "t": self.t}
        return self._obs(), float(reward), bool(self.done), False, info

    # -- action application THROUGH the risk engine (Section 12) -------------
    def _apply(self, action: int, force: bool = False) -> None:
        self.last_gate = ""
        price = float(self.df["close"].iloc[self.t])
        if action == ACTION_HOLD:
            return
        if action in (ACTION_BUY, ACTION_SELL):
            if self.position is not None:
                self.last_gate = "position_open"
                return
            self._open(action, price)
            return
        if action == ACTION_CLOSE:
            self._close_position(price, force=force)

    def _open(self, action: int, price: float) -> None:
        direction = 1 if action == ACTION_BUY else -1
        atr = float(self.vol_engine.atr(self.df).iloc[self.t])
        atr_pts = atr / self.point if self.point > 0 and atr > 0 else 20.0
        sl_points = int(min(max(2.0 * atr_pts, 10.0), 400.0))
        tp_points = int(sl_points * 1.5)
        session = SESSION_NAMES[int(self._session_col.iloc[self.t])]
        decision = self.risk.evaluate(
            symbol=self.symbol, direction="BUY" if direction == 1 else "SELL",
            equity=self.start_equity + sum(self.closed_pnl),
            spread_pts=self.spread_pts, point=self.point,
            point_value_per_lot=self.point_value_per_lot,
            atr_points=atr_pts, vol_ratio=1.0,
            vol_percentile=float(self.f_vol_pctile.iloc[self.t]),
            session=session, sl_points=sl_points, tp_points=tp_points)
        if not decision.allowed:
            self.last_gate = f"risk_blocked:{decision.reason}"
            return
        lot = decision.lot_size
        sl = price - sl_points * self.point * direction
        tp = price + tp_points * self.point * direction
        self.position = EnvPosition(direction=direction, lot=lot, entry=price,
                                    sl=sl, tp=tp, entry_index=self.t)
        self.last_gate = f"opened:{lot}@sl{sl_points}/tp{tp_points}"

    def _close_position(self, price: float, force: bool = False) -> None:
        if self.position is None:
            self.last_gate = "no_position"
            return
        tag = "forced_close" if force else "closed"
        self._close_at(price, tag)

    def _close_at(self, price: float, tag: str) -> None:
        p = self.position
        move_pts = (price - p.entry) / self.point * p.direction
        pnl = move_pts * p.lot * self.point_value_per_lot
        self.closed_pnl.append(pnl)
        self.risk.on_trade_result(pnl)
        self.last_gate = f"{tag}:{round(pnl, 2)}"
        self.position = None

    def _check_stops(self) -> None:
        """Intra-bar SL/TP enforcement (Section 12: agent cannot bypass SL/TP).

        Conservative assumption: if a bar touches both SL and TP, the STOP is
        counted first (pessimistic fill). point_value_per_lot semantics:
        account currency per lot per 1 point move (1.0 for a 100k FX contract
        quoted with point=0.00001, and 1.0 for XAUUSD point=0.01/100oz).
        """
        if self.position is None:
            return
        bar = self.df.iloc[self.t]
        p = self.position
        if p.direction == 1:
            if float(bar["low"]) <= p.sl:
                self._close_at(p.sl, "sl_hit")
            elif float(bar["high"]) >= p.tp:
                self._close_at(p.tp, "tp_hit")
        else:
            if float(bar["high"]) >= p.sl:
                self._close_at(p.sl, "sl_hit")
            elif float(bar["low"]) <= p.tp:
                self._close_at(p.tp, "tp_hit")

    # -- mark-to-market -------------------------------------------------------
    def _mark_equity(self) -> float:
        equity = self.start_equity + sum(self.closed_pnl)
        if self.position is None:
            return equity
        price = float(self.df["close"].iloc[min(self.t, len(self.df) - 1)])
        p = self.position
        move_pts = (price - p.entry) / self.point * p.direction
        return equity + move_pts * p.lot * self.point_value_per_lot


def make_env(df: pd.DataFrame, **kwargs) -> TradingEnv:
    """Factory used by research scripts and the tournament runner."""
    return TradingEnv(df, **kwargs)


def rl_mode_gate(mode: str, validated: bool = False) -> Tuple[bool, str]:
    """Section 10/48 promotion gate. RL_DEMO requires validation evidence."""
    if mode == RL_DISABLED:
        return False, "RL disabled by configuration"
    if mode == RL_RESEARCH:
        return True, "research training allowed"
    if mode == RL_PAPER:
        return True, "paper simulation allowed"
    if mode == RL_DEMO:
        if validated:
            return True, "demo promotion allowed (walk-forward validated)"
        return False, "RL_DEMO BLOCKED - no walk-forward validation evidence"
    return False, f"unknown RL mode {mode!r}"


