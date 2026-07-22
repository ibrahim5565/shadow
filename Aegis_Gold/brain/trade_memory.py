"""
═══════════════════════════════════════════════════════════════════════════════
🧠 AEGIS TRADE MEMORY DATABASE - Institutional AI Learning Foundation
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
Record EVERY trade forever with complete context, market state, and outcomes.
This database is the foundation for ALL learning, optimization, and ML training.

PHILOSOPHY:
-----------
"Those who cannot remember the past are condemned to repeat it."

Every trade contains lessons. Every win teaches what works. Every loss teaches
what to avoid. The AI must never forget.

STORAGE ARCHITECTURE:
---------------------
- SQLite database: data/trade_memory.db
- Persistent, indexed, queryable
- Supports time-series analysis
- Enables pattern recognition across thousands of trades

RECORDED DATA:
--------------
ENTRY:
  - Timestamp, Symbol, Direction, Entry Price, Lot Size
  - Confidence Score, Signal Source (SMC/SCALP/ML)
  - Market Regime, Structure, Momentum, Volatility
  - All indicator values at entry
  - News events nearby
  - Spread, Session, Time of day
  
EXIT:
  - Exit Timestamp, Exit Price, Duration
  - Profit/Loss (absolute and percentage)
  - Exit Reason (TP hit, SL hit, Early exit, Time-based, etc.)
  - Market state at exit
  
CONTEXT:
  - Multi-timeframe analysis snapshot (M1, M5, M15, H1, H4)
  - SMC signals (Order Blocks, BOS/CHoCH, Liquidity, FVG)
  - Statistical metrics (Bayesian probability, Hurst, entropy)
  - Correlation with other instruments
  - Recent win/loss streak
  - Account state (balance, equity, margin, drawdown)
  
OUTCOME ANALYSIS:
  - Was the entry accurate?
  - Was the exit optimal?
  - Could profit have been larger?
  - Was risk managed correctly?
  - Slippage analysis
  - Execution quality

═══════════════════════════════════════════════════════════════════════════════
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger("TradeMemory")


@dataclass
class TradeMemory:
    """
    Complete trade record with full context and outcome.
    """
    # IDENTITY
    trade_id: int  # MT5 ticket number
    symbol: str
    direction: str  # "BUY" or "SELL"
    
    # ENTRY
    entry_time: str  # ISO timestamp
    entry_price: float
    lot_size: float
    confidence: int  # 0-100
    signal_source: str  # "SMC", "SCALP", "ML"
    
    # EXIT
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    profit_usd: Optional[float] = None
    profit_pct: Optional[float] = None
    duration_seconds: Optional[int] = None
    exit_reason: Optional[str] = None
    
    # RISK MANAGEMENT
    sl_points: int = 0
    tp_points: int = 0
    rr_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_profit_reached: float = 0.0
    
    # MARKET STATE AT ENTRY
    regime: str = "UNKNOWN"
    regime_score: int = 0
    structure: str = "UNKNOWN"
    structure_score: int = 0
    entry_score: int = 0
    momentum_score: int = 0
    volatility_state: str = "NORMAL"
    trend_state: str = "UNKNOWN"
    
    # INDICATORS AT ENTRY
    rsi: float = 0.0
    adx: float = 0.0
    atr: float = 0.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    bbands_position: str = "MIDDLE"  # "UPPER", "MIDDLE", "LOWER"
    
    # SMC SIGNALS
    smc_ob_present: bool = False
    smc_bos_present: bool = False
    smc_choch_present: bool = False
    smc_liquidity_sweep: bool = False
    smc_fvg_present: bool = False
    smc_po3_phase: str = "NONE"  # "ACCUMULATION", "MANIPULATION", "DISTRIBUTION"
    smc_score: int = 0
    
    # MULTI-TIMEFRAME CONTEXT
    mtf_m1_trend: str = "UNKNOWN"
    mtf_m5_trend: str = "UNKNOWN"
    mtf_m15_trend: str = "UNKNOWN"
    mtf_h1_trend: str = "UNKNOWN"
    mtf_h4_trend: str = "UNKNOWN"
    mtf_alignment: int = 0  # 0-5 (how many timeframes align)
    
    # STATISTICAL METRICS
    bayesian_probability: float = 0.0
    hurst_exponent: float = 0.5
    entropy: float = 0.0
    
    # ENVIRONMENTAL FACTORS
    spread: float = 0.0
    session: str = "UNKNOWN"  # "LONDON", "NY", "ASIA", "OVERLAP"
    hour_of_day: int = 0
    day_of_week: int = 0  # 0=Monday, 6=Sunday
    news_nearby: bool = False
    news_impact: str = "NONE"  # "LOW", "MEDIUM", "HIGH"
    
    # ACCOUNT STATE
    balance_before: float = 0.0
    equity_before: float = 0.0
    balance_after: Optional[float] = None
    equity_after: Optional[float] = None
    
    # RECENT PERFORMANCE
    recent_wins: int = 0
    recent_losses: int = 0
    win_streak: int = 0
    loss_streak: int = 0
    
    # TRADE QUALITY ASSESSMENT
    slippage_points: float = 0.0
    execution_quality: str = "GOOD"  # "EXCELLENT", "GOOD", "FAIR", "POOR"
    was_patient: bool = True
    followed_rules: bool = True
    
    # OUTCOME ANALYSIS (filled after exit)
    was_entry_optimal: Optional[bool] = None
    was_exit_optimal: Optional[bool] = None
    could_have_captured_more: Optional[float] = None  # Additional pips available
    tp_was_hit: Optional[bool] = None
    sl_was_hit: Optional[bool] = None
    
    # LEARNING TAGS
    tags: str = ""  # JSON array of tags: ["revenge_trade", "news_related", "perfect_setup"]
    notes: str = ""  # AI-generated insights about this trade


class TradeMemoryDatabase:
    """
    Persistent trade memory storage and retrieval system.
    """
    
    def __init__(self, db_path: str = "d:\\Trading\\Aegis_Gold\\data\\trade_memory.db"):
        self.db_path = db_path
        self._ensure_database_exists()
        logger.info(f"TradeMemoryDatabase initialized: {db_path}")
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                
                entry_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                lot_size REAL NOT NULL,
                confidence INTEGER NOT NULL,
                signal_source TEXT NOT NULL,
                
                exit_time TEXT,
                exit_price REAL,
                profit_usd REAL,
                profit_pct REAL,
                duration_seconds INTEGER,
                exit_reason TEXT,
                
                sl_points INTEGER,
                tp_points INTEGER,
                rr_ratio REAL,
                max_drawdown_pct REAL,
                max_profit_reached REAL,
                
                regime TEXT,
                regime_score INTEGER,
                structure TEXT,
                structure_score INTEGER,
                entry_score INTEGER,
                momentum_score INTEGER,
                volatility_state TEXT,
                trend_state TEXT,
                
                rsi REAL,
                adx REAL,
                atr REAL,
                ema_fast REAL,
                ema_slow REAL,
                bbands_position TEXT,
                
                smc_ob_present INTEGER,
                smc_bos_present INTEGER,
                smc_choch_present INTEGER,
                smc_liquidity_sweep INTEGER,
                smc_fvg_present INTEGER,
                smc_po3_phase TEXT,
                smc_score INTEGER,
                
                mtf_m1_trend TEXT,
                mtf_m5_trend TEXT,
                mtf_m15_trend TEXT,
                mtf_h1_trend TEXT,
                mtf_h4_trend TEXT,
                mtf_alignment INTEGER,
                
                bayesian_probability REAL,
                hurst_exponent REAL,
                entropy REAL,
                
                spread REAL,
                session TEXT,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                news_nearby INTEGER,
                news_impact TEXT,
                
                balance_before REAL,
                equity_before REAL,
                balance_after REAL,
                equity_after REAL,
                
                recent_wins INTEGER,
                recent_losses INTEGER,
                win_streak INTEGER,
                loss_streak INTEGER,
                
                slippage_points REAL,
                execution_quality TEXT,
                was_patient INTEGER,
                followed_rules INTEGER,
                
                was_entry_optimal INTEGER,
                was_exit_optimal INTEGER,
                could_have_captured_more REAL,
                tp_was_hit INTEGER,
                sl_was_hit INTEGER,
                
                tags TEXT,
                notes TEXT
            )
        """)
        
        # Indices for fast querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON trades(entry_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_source ON trades(signal_source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profit_usd ON trades(profit_usd)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON trades(confidence)")
        
        # Performance metrics table (aggregated statistics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate REAL,
                
                avg_profit_winning REAL,
                avg_loss_losing REAL,
                profit_factor REAL,
                expectancy REAL,
                
                total_profit_usd REAL,
                max_drawdown_usd REAL,
                max_drawdown_pct REAL,
                
                avg_confidence_winning REAL,
                avg_confidence_losing REAL,
                
                best_signal_source TEXT,
                best_session TEXT,
                best_hour INTEGER,
                best_regime TEXT,
                
                notes TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Trade memory database schema created/verified")
    
    def record_entry(self, trade: TradeMemory) -> bool:
        """
        Record a new trade entry.
        Returns True if successful, False otherwise.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert dataclass to dict
            data = asdict(trade)
            
            # Convert booleans to integers for SQLite
            for key, value in data.items():
                if isinstance(value, bool):
                    data[key] = 1 if value else 0
            
            # Insert
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            query = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
            
            cursor.execute(query, list(data.values()))
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Trade entry recorded: {trade.trade_id} {trade.symbol} {trade.direction} @ {trade.entry_price}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to record trade entry: {e}")
            return False
    
    def update_exit(self, trade_id: int, exit_data: Dict[str, Any]) -> bool:
        """
        Update trade with exit information and outcome analysis.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert booleans to integers
            for key, value in exit_data.items():
                if isinstance(value, bool):
                    exit_data[key] = 1 if value else 0
            
            # Build UPDATE query
            set_clause = ", ".join(f"{k} = ?" for k in exit_data.keys())
            query = f"UPDATE trades SET {set_clause} WHERE trade_id = ?"
            
            values = list(exit_data.values()) + [trade_id]
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Trade exit updated: {trade_id} | P&L: {exit_data.get('profit_usd', 'N/A')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update trade exit: {e}")
            return False
    
    def get_trade(self, trade_id: int) -> Optional[Dict]:
        """Retrieve a single trade by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve trade {trade_id}: {e}")
            return None
    
    def get_recent_trades(self, limit: int = 100, symbol: Optional[str] = None) -> List[Dict]:
        """Get most recent trades, optionally filtered by symbol."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if symbol:
                query = "SELECT * FROM trades WHERE symbol = ? ORDER BY entry_time DESC LIMIT ?"
                cursor.execute(query, (symbol, limit))
            else:
                query = "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?"
                cursor.execute(query, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve recent trades: {e}")
            return []
    
    def get_winning_trades(self, limit: int = 100, min_confidence: int = 0) -> List[Dict]:
        """Get winning trades for pattern analysis."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM trades 
                WHERE profit_usd > 0 AND confidence >= ?
                ORDER BY profit_usd DESC 
                LIMIT ?
            """
            cursor.execute(query, (min_confidence, limit))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve winning trades: {e}")
            return []
    
    def get_losing_trades(self, limit: int = 100) -> List[Dict]:
        """Get losing trades for error analysis."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM trades 
                WHERE profit_usd < 0
                ORDER BY profit_usd ASC 
                LIMIT ?
            """
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve losing trades: {e}")
            return []
    
    def analyze_performance(self, symbol: Optional[str] = None, days: int = 30) -> Dict:
        """
        Analyze trading performance over specified period.
        Returns comprehensive statistics.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Base query
            where_clause = ""
            params = []
            
            if symbol:
                where_clause = "WHERE symbol = ?"
                params.append(symbol)
            
            # Total trades
            cursor.execute(f"SELECT COUNT(*) FROM trades {where_clause}", params)
            total_trades = cursor.fetchone()[0]
            
            if total_trades == 0:
                return {"error": "No trades found"}
            
            # Wins and losses
            cursor.execute(f"SELECT COUNT(*) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd > 0", params)
            wins = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd < 0", params)
            losses = cursor.fetchone()[0]
            
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            # Profit metrics
            cursor.execute(f"SELECT AVG(profit_usd) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd > 0", params)
            avg_win = cursor.fetchone()[0] or 0
            
            cursor.execute(f"SELECT AVG(profit_usd) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd < 0", params)
            avg_loss = cursor.fetchone()[0] or 0
            
            cursor.execute(f"SELECT SUM(profit_usd) FROM trades {where_clause}", params)
            total_profit = cursor.fetchone()[0] or 0
            
            # Profit factor
            cursor.execute(f"SELECT SUM(profit_usd) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd > 0", params)
            gross_profit = cursor.fetchone()[0] or 0
            
            cursor.execute(f"SELECT SUM(profit_usd) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd < 0", params)
            gross_loss = abs(cursor.fetchone()[0] or 1)
            
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Expectancy
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * abs(avg_loss))
            
            # Best signal source
            cursor.execute(f"""
                SELECT signal_source, COUNT(*) as cnt, AVG(profit_usd) as avg_profit
                FROM trades {where_clause}
                GROUP BY signal_source
                ORDER BY avg_profit DESC
                LIMIT 1
            """, params)
            best_source_row = cursor.fetchone()
            best_signal_source = best_source_row[0] if best_source_row else "UNKNOWN"
            
            # Best session
            cursor.execute(f"""
                SELECT session, AVG(profit_usd) as avg_profit
                FROM trades {where_clause}
                GROUP BY session
                ORDER BY avg_profit DESC
                LIMIT 1
            """, params)
            best_session_row = cursor.fetchone()
            best_session = best_session_row[0] if best_session_row else "UNKNOWN"
            
            # Avg confidence for wins vs losses
            cursor.execute(f"SELECT AVG(confidence) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd > 0", params)
            avg_conf_win = cursor.fetchone()[0] or 0
            
            cursor.execute(f"SELECT AVG(confidence) FROM trades {where_clause} {'AND' if where_clause else 'WHERE'} profit_usd < 0", params)
            avg_conf_loss = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "avg_win_usd": round(avg_win, 2),
                "avg_loss_usd": round(avg_loss, 2),
                "total_profit_usd": round(total_profit, 2),
                "profit_factor": round(profit_factor, 2),
                "expectancy": round(expectancy, 2),
                "best_signal_source": best_signal_source,
                "best_session": best_session,
                "avg_confidence_winning": round(avg_conf_win, 1),
                "avg_confidence_losing": round(avg_conf_loss, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ Performance analysis failed: {e}")
            return {"error": str(e)}
    
    def find_similar_trades(self, current_conditions: Dict, limit: int = 20) -> List[Dict]:
        """
        Find historical trades with similar market conditions.
        Used for probabilistic forecasting.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build similarity query based on key conditions
            query = """
                SELECT *, 
                    ABS(confidence - ?) as conf_diff,
                    ABS(rsi - ?) as rsi_diff,
                    ABS(adx - ?) as adx_diff
                FROM trades
                WHERE symbol = ?
                    AND regime = ?
                    AND structure = ?
                    AND signal_source = ?
                    AND profit_usd IS NOT NULL
                ORDER BY (conf_diff + rsi_diff + adx_diff) ASC
                LIMIT ?
            """
            
            cursor.execute(query, (
                current_conditions.get("confidence", 50),
                current_conditions.get("rsi", 50),
                current_conditions.get("adx", 25),
                current_conditions.get("symbol", "XAUUSD"),
                current_conditions.get("regime", "UNKNOWN"),
                current_conditions.get("structure", "UNKNOWN"),
                current_conditions.get("signal_source", "SCALP"),
                limit
            ))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"❌ Failed to find similar trades: {e}")
            return []
    
    def get_trade_count(self) -> int:
        """Get total number of trades in memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except:
            return 0


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def create_trade_memory_from_decision(
    ticket: int,
    symbol: str,
    direction: str,
    entry_price: float,
    lot_size: float,
    decision_data: Dict,
    account_data: Dict,
    indicators: Dict,
    smc_data: Dict = None,
    mtf_data: Dict = None,
    stats_data: Dict = None
) -> TradeMemory:
    """
    Helper function to create TradeMemory object from trading decision.
    """
    return TradeMemory(
        trade_id=ticket,
        symbol=symbol,
        direction=direction,
        entry_time=datetime.utcnow().isoformat(),
        entry_price=entry_price,
        lot_size=lot_size,
        confidence=decision_data.get("confidence", 0),
        signal_source=decision_data.get("signal_source", "SCALP"),
        sl_points=decision_data.get("sl_points", 0),
        tp_points=decision_data.get("tp_points", 0),
        rr_ratio=decision_data.get("rr_ratio", 0.0),
        regime=decision_data.get("regime", "UNKNOWN"),
        regime_score=decision_data.get("regime_score", 0),
        structure=decision_data.get("structure", "UNKNOWN"),
        structure_score=decision_data.get("structure_score", 0),
        entry_score=decision_data.get("entry_score", 0),
        momentum_score=decision_data.get("momentum_score", 0),
        volatility_state=decision_data.get("volatility_state", "NORMAL"),
        trend_state=decision_data.get("trend_state", "UNKNOWN"),
        rsi=indicators.get("rsi", 0.0),
        adx=indicators.get("adx", 0.0),
        atr=indicators.get("atr", 0.0),
        ema_fast=indicators.get("ema_fast", 0.0),
        ema_slow=indicators.get("ema_slow", 0.0),
        bbands_position=indicators.get("bbands_position", "MIDDLE"),
        smc_ob_present=smc_data.get("ob_present", False) if smc_data else False,
        smc_bos_present=smc_data.get("bos_present", False) if smc_data else False,
        smc_choch_present=smc_data.get("choch_present", False) if smc_data else False,
        smc_liquidity_sweep=smc_data.get("liquidity_sweep", False) if smc_data else False,
        smc_fvg_present=smc_data.get("fvg_present", False) if smc_data else False,
        smc_po3_phase=smc_data.get("po3_phase", "NONE") if smc_data else "NONE",
        smc_score=smc_data.get("total_score", 0) if smc_data else 0,
        mtf_m1_trend=mtf_data.get("m1_trend", "UNKNOWN") if mtf_data else "UNKNOWN",
        mtf_m5_trend=mtf_data.get("m5_trend", "UNKNOWN") if mtf_data else "UNKNOWN",
        mtf_m15_trend=mtf_data.get("m15_trend", "UNKNOWN") if mtf_data else "UNKNOWN",
        mtf_h1_trend=mtf_data.get("h1_trend", "UNKNOWN") if mtf_data else "UNKNOWN",
        mtf_h4_trend=mtf_data.get("h4_trend", "UNKNOWN") if mtf_data else "UNKNOWN",
        mtf_alignment=mtf_data.get("alignment", 0) if mtf_data else 0,
        bayesian_probability=stats_data.get("bayesian_probability", 0.0) if stats_data else 0.0,
        hurst_exponent=stats_data.get("hurst_exponent", 0.5) if stats_data else 0.5,
        entropy=stats_data.get("entropy", 0.0) if stats_data else 0.0,
        spread=account_data.get("spread", 0.0),
        session=account_data.get("session", "UNKNOWN"),
        hour_of_day=datetime.now().hour,
        day_of_week=datetime.now().weekday(),
        news_nearby=decision_data.get("news_nearby", False),
        news_impact=decision_data.get("news_impact", "NONE"),
        balance_before=account_data.get("balance", 0.0),
        equity_before=account_data.get("equity", 0.0),
        recent_wins=account_data.get("recent_wins", 0),
        recent_losses=account_data.get("recent_losses", 0),
        win_streak=account_data.get("win_streak", 0),
        loss_streak=account_data.get("loss_streak", 0),
        was_patient=True,
        followed_rules=True
    )


# ═══════════════════════════════════════════════════════════════════════════
# INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

# Global instance
_trade_memory_db = None

def get_trade_memory_db() -> TradeMemoryDatabase:
    """Get or create singleton trade memory database instance."""
    global _trade_memory_db
    if _trade_memory_db is None:
        _trade_memory_db = TradeMemoryDatabase()
    return _trade_memory_db
