/**
 * AEGIS GOLD  -  SCALPING MODE  -  50% CONFIDENCE
 * Local AI Engine Dashboard v6.0 ULTRA
 * No external AI dependencies. Fully local intelligence.
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';
import {
  Activity, ShieldCheck, ShieldAlert, Zap, Target, TrendingUp, TrendingDown,
  History, Pause, Play, X, BarChart2, Cpu, Brain, DollarSign, RefreshCw,
  AlertTriangle, Wifi, WifiOff, Server, Bot, Radio, BookOpen,
  ChevronUp, ChevronDown, Circle,
} from 'lucide-react';
import './index.css';

const API = 'http://127.0.0.1:5001';

/* ═══════════════════════════════════════════════
   UTILITY HOOKS
═══════════════════════════════════════════════ */
function useApi(path, interval = 1500) {
  const [data, setData] = useState(null);
  const [err,  setErr]  = useState(false);
  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const r = await fetch(`${API}${path}`, { signal: AbortSignal.timeout(4000) });
        if (!r.ok) throw new Error();
        const d = await r.json();
        if (alive) { setData(d); setErr(false); }
      } catch { if (alive) setErr(true); }
    };
    run();
    const t = setInterval(run, interval);
    return () => { alive = false; clearInterval(t); };
  }, [path, interval]);
  return [data, err];
}

async function postCmd(cmd) {
  try {
    const r = await fetch(`${API}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd }),
      signal: AbortSignal.timeout(4000),
    });
    return r.ok;
  } catch { return false; }
}

/* ═══════════════════════════════════════════════
   REUSABLE UI PRIMITIVES
═══════════════════════════════════════════════ */
const cx = (...cls) => cls.filter(Boolean).join(' ');

function Badge({ variant = 'neutral', size = 'sm', children }) {
  return <span className={cx('badge', `badge-${variant}`, `badge-${size}`)}>{children}</span>;
}

function StatusBadge({ status, online }) {
  if (!online) return <Badge variant="red">⬤ OFFLINE</Badge>;
  const map = {
    ACTIVE:        <Badge variant="green">⬤ ACTIVE</Badge>,
    PAUSED:        <Badge variant="yellow">⏸ PAUSED</Badge>,
    STOPPED:       <Badge variant="red">■ STOPPED</Badge>,
    LOCKED:        <Badge variant="red">🔒 LOCKED</Badge>,
    'MARKET CLOSED':<Badge variant="neutral">⏳ CLOSED</Badge>,
    STARTING:      <Badge variant="blue"> -  -  -  STARTING</Badge>,
  };
  return map[status] ?? <Badge variant="blue">{status}</Badge>;
}

function Pill({ color = 'gold', children }) {
  return <span className={`pill pill-${color}`}>{children}</span>;
}

function Card({ title, icon: Icon, iconColor = 'gold', right, children, className = '' }) {
  return (
    <div className={cx('card', className)}>
      {(title || right) && (
        <div className="card-hdr">
          <div className="card-hdr-left">
            {Icon && <Icon size={13} className={`icon-${iconColor}`} />}
            {title && <span className="card-title">{title}</span>}
          </div>
          {right && <div className="card-hdr-right">{right}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, color = 'gold', flash = false }) {
  return (
    <div className={cx('stat-card', flash && 'stat-flash')}>
      <div className="stat-hdr">
        <span className="stat-lbl">{label}</span>
        {Icon && <Icon size={14} className={`icon-${color}`} />}
      </div>
      <div className={`stat-val text-${color}`}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function GaugeBar({ label, value = 0, color = '#f59e0b', showPct = true }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="gauge">
      <div className="gauge-hdr">
        <span>{label}</span>
        {showPct && <span style={{ color, fontFamily: 'monospace', fontWeight: 600 }}>{pct}%</span>}
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function PnL({ value }) {
  const pos = value >= 0;
  return (
    <span className={cx('pnl', pos ? 'pnl-pos' : 'pnl-neg')}>
      {pos ? '+' : ''}${Math.abs(value).toFixed(2)}
    </span>
  );
}

function Tooltip2({ label, value }) {
  return (
    <div className="tip2">
      <div className="tip2-lbl">{label}</div>
      <div className="tip2-val">{value}</div>
    </div>
  );
}

const CustomChartTooltip = ({ active, payload, label }) =>
  active && payload?.length ? (
    <div className="chart-tip">
      <div className="chart-tip-time">{label}</div>
      <div className="chart-tip-price">{Number(payload[0].value).toFixed(2)}</div>
    </div>
  ) : null;

/* ═══════════════════════════════════════════════
   SYSTEM STATUS PANEL
═══════════════════════════════════════════════ */
function SystemStatus({ st, online }) {
  const items = [
    { label: 'MT5 Gateway',     ok: online && st?.status !== 'DISCONNECTED', icon: Server  },
    { label: 'Trading Engine',  ok: online && st?.status === 'ACTIVE',       icon: Activity },
    { label: 'AI Engine',       ok: online,                                   icon: Brain   },
    { label: 'Telegram Bot',    ok: online,                                   icon: Radio   },
  ];
  return (
    <Card title="SYSTEM STATUS" icon={ShieldCheck} iconColor="green">
      <div className="sys-grid">
        {items.map(({ label, ok, icon: Icon }) => (
          <div key={label} className={cx('sys-item', ok ? 'sys-ok' : 'sys-err')}>
            <Icon size={12} />
            <span>{label}</span>
            <span className={cx('sys-dot', ok ? 'dot-green' : 'dot-red')}>{ok ? 'ON' : 'OFF'}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   ACCOUNT PANEL
═══════════════════════════════════════════════ */
function AccountPanel({ st }) {
  const equity   = st?.equity   ?? 0;
  const pnl      = st?.daily_pnl ?? 0;
  const pnlPct   = st?.start_equity > 0 ? ((pnl / st.start_equity) * 100).toFixed(2) : '0.00';
  return (
    <Card title="ACCOUNT" icon={DollarSign} iconColor="gold">
      <div className="acct-grid">
        <div className="acct-item">
          <span className="acct-lbl">Equity</span>
          <span className="acct-val text-gold">${equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div className="acct-item">
          <span className="acct-lbl">Daily P&L</span>
          <span className="acct-val"><PnL value={pnl} /></span>
        </div>
        <div className="acct-item">
          <span className="acct-lbl">Return %</span>
          <span className={cx('acct-val', pnl >= 0 ? 'text-green' : 'text-red')}>{pnl >= 0 ? '+' : ''}{pnlPct}%</span>
        </div>
        <div className="acct-item">
          <span className="acct-lbl">Mode</span>
          <span className="acct-val text-blue">{st?.mode ?? 'DEMO'}</span>
        </div>
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   TRADE PANEL
═══════════════════════════════════════════════ */
function TradePanel({ st, trades }) {
  const total  = (st?.wins ?? 0) + (st?.losses ?? 0);
  const wr     = total > 0 ? ((st.wins / total) * 100).toFixed(0) : 0;
  const earned = trades.filter(t => t.win).reduce((s, t) => s + (t.pnl ?? 0), 0);
  const done   = st?.daily_trades ?? 0;

  return (
    <Card title="TRADES" icon={History} iconColor="blue">
      <div className="trade-stats">
        <div className="ts-item">
          <span className="ts-lbl">Today</span>
          <span className="ts-val text-blue">{done}</span>
        </div>
        <div className="ts-item">
          <span className="ts-lbl">Win Rate</span>
          <span className={cx('ts-val', wr >= 60 ? 'text-green' : wr >= 45 ? 'text-gold' : 'text-red')}>{wr}%</span>
        </div>
        <div className="ts-item">
          <span className="ts-lbl">Wins / Loss</span>
          <span className="ts-val"><span className="text-green">{st?.wins ?? 0}</span><span className="text-sub"> / </span><span className="text-red">{st?.losses ?? 0}</span></span>
        </div>
        <div className="ts-item">
          <span className="ts-lbl">Earned</span>
          <span className="ts-val"><PnL value={earned} /></span>
        </div>
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   LIVE CONFIDENCE GAUGE  -  animated bar
═══════════════════════════════════════════════ */
function LiveGaugeBar({ label, value = 0, color = '#f59e0b' }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="gauge">
      <div className="gauge-hdr">
        <span>{label}</span>
        <span style={{ color, fontFamily: 'monospace', fontWeight: 700, fontSize: 13 }}>{pct}%</span>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}, ${color}cc)`,
          transition: 'width 0.6s ease',
          boxShadow: `0 0 8px ${color}66`
        }} />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   AI ENGINE PANEL - Separate EURUSD Analysis
═══════════════════════════════════════════════ */
function EURUSDPanel({ aiState }) {
  const symData = aiState?.EURUSD || {};
  const conf = symData.confidence || 0;
  const regime = symData.regime || 'SCANNING';
  const reason = symData.reason || 'Initializing...';
  const adx = symData.adx || 0;
  const rsi = symData.rsi || 0;
  const action = symData.action || 'WAIT';
  const direction = symData.direction || 'NA';

  const confColor = conf >= 60 ? '#10b981' : conf >= 40 ? '#f59e0b' : '#ef4444';
  const confBg    = conf >= 60 ? 'rgba(16,185,129,0.12)' : conf >= 40 ? 'rgba(245,158,11,0.10)' : 'rgba(239,68,68,0.10)';
  const confEmoji = conf >= 60 ? '🟢' : conf >= 40 ? '🟡' : '🔴';

  return (
    <Card title="EURUSD AI ENGINE" icon={Brain} iconColor="blue"
      right={<span style={{ color: confColor, fontWeight: 'bold', fontSize: 14 }}>{conf}%</span>}>

      {/* Big confidence display */}
      <div style={{ background: confBg, borderRadius: 8, padding: '10px 12px', marginBottom: 10, border: `1px solid ${confColor}33` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{confEmoji}</span>
          <div>
            <div style={{ color: confColor, fontWeight: 'bold', fontSize: 18, fontFamily: 'monospace' }}>
              {conf}% CONFIDENCE
            </div>
            <div style={{ color: '#94a3b8', fontSize: 10 }}>
              {action === 'TRADE' ? `✅ TRADE ${direction}` : `⏳ WAITING  -  need 60%+`}
            </div>
          </div>
          {/* Live pulse dot */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: confColor, animation: 'pulse 1.5s infinite', boxShadow: `0 0 6px ${confColor}` }} />
            <span style={{ color: '#64748b', fontSize: 9 }}>LIVE</span>
          </div>
        </div>
      </div>

      <LiveGaugeBar label="Confidence"      value={conf}                         color={confColor} />
      <LiveGaugeBar label="Regime Score"    value={symData.regime_score || 0}    color="#3b82f6" />
      <LiveGaugeBar label="Structure Score" value={symData.structure_score || 0} color="#f59e0b" />
      <LiveGaugeBar label="Entry Score"     value={symData.entry_score || 0}     color="#10b981" />

      <div style={{ marginTop: 8, fontSize: 10, color: '#64748b', lineHeight: 1.5 }}>
        <div><span style={{ color: '#94a3b8' }}>REGIME:</span> {regime}</div>
        <div><span style={{ color: '#94a3b8' }}>ADX:</span> {adx} &nbsp;|&nbsp; <span style={{ color: '#94a3b8' }}>RSI:</span> {rsi}</div>
        <div style={{ marginTop: 4, color: '#475569' }}>{reason.length > 60 ? reason.substring(0, 60) + '...' : reason}</div>
      </div>

      <div className="ai-badges" style={{ marginTop: 8 }}>
        <Pill color="blue">EURUSD</Pill>
        <Pill color={conf >= 60 ? 'green' : 'neutral'}>60%+ = TRADE</Pill>
        <Pill color="gold">$0.80 TARGET</Pill>
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   GOLD AI ENGINE PANEL - Separate XAUUSD Analysis
═══════════════════════════════════════════════ */
function XAUUSDPanel({ aiState }) {
  const symData = aiState?.XAUUSD || {};
  const conf = symData.confidence || 0;
  const regime = symData.regime || 'SCANNING';
  const reason = symData.reason || 'Initializing...';
  const adx = symData.adx || 0;
  const rsi = symData.rsi || 0;
  const action = symData.action || 'WAIT';
  const direction = symData.direction || 'NA';

  const confColor = conf >= 60 ? '#10b981' : conf >= 40 ? '#f59e0b' : '#ef4444';
  const confBg    = conf >= 60 ? 'rgba(16,185,129,0.12)' : conf >= 40 ? 'rgba(245,158,11,0.10)' : 'rgba(239,68,68,0.10)';
  const confEmoji = conf >= 60 ? '🟢' : conf >= 40 ? '🟡' : '🔴';

  return (
    <Card title="GOLD (XAUUSD) AI ENGINE" icon={Brain} iconColor="gold"
      right={<span style={{ color: confColor, fontWeight: 'bold', fontSize: 14 }}>{conf}%</span>}>

      {/* Big confidence display */}
      <div style={{ background: confBg, borderRadius: 8, padding: '10px 12px', marginBottom: 10, border: `1px solid ${confColor}33` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{confEmoji}</span>
          <div>
            <div style={{ color: confColor, fontWeight: 'bold', fontSize: 18, fontFamily: 'monospace' }}>
              {conf}% CONFIDENCE
            </div>
            <div style={{ color: '#94a3b8', fontSize: 10 }}>
              {action === 'TRADE' ? `✅ TRADE ${direction}` : `⏳ WAITING  -  need 60%+`}
            </div>
          </div>
          {/* Live pulse dot */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: confColor, animation: 'pulse 1.5s infinite', boxShadow: `0 0 6px ${confColor}` }} />
            <span style={{ color: '#64748b', fontSize: 9 }}>LIVE</span>
          </div>
        </div>
      </div>

      <LiveGaugeBar label="Confidence"      value={conf}                         color={confColor} />
      <LiveGaugeBar label="Regime Score"    value={symData.regime_score || 0}    color="#3b82f6" />
      <LiveGaugeBar label="Structure Score" value={symData.structure_score || 0} color="#f59e0b" />
      <LiveGaugeBar label="Entry Score"     value={symData.entry_score || 0}     color="#10b981" />

      <div style={{ marginTop: 8, fontSize: 10, color: '#64748b', lineHeight: 1.5 }}>
        <div><span style={{ color: '#94a3b8' }}>REGIME:</span> {regime}</div>
        <div><span style={{ color: '#94a3b8' }}>ADX:</span> {adx} &nbsp;|&nbsp; <span style={{ color: '#94a3b8' }}>RSI:</span> {rsi}</div>
        <div style={{ marginTop: 4, color: '#475569' }}>{reason.length > 60 ? reason.substring(0, 60) + '...' : reason}</div>
      </div>

      <div className="ai-badges" style={{ marginTop: 8 }}>
        <Pill color="gold">XAUUSD</Pill>
        <Pill color={conf >= 60 ? 'green' : 'neutral'}>60%+ = TRADE</Pill>
        <Pill color="purple">$0.50 TARGET</Pill>
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   LIVE PRICE CHART  -  Per Symbol
═══════════════════════════════════════════════ */
function SymbolChart({ symbol, color = '#f59e0b', aiState }) {
  const [priceData, priceErr] = useApi(`/price/${symbol}`, 500);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!priceData?.price) return;
    setHistory(prev => {
      const next = [...prev, { time: priceData.time, price: priceData.price }];
      return next.length > 90 ? next.slice(-90) : next;
    });
  }, [priceData]);

  const price  = priceData?.price  ?? 0;
  const spread = priceData?.spread ?? 0;
  const up = history.length > 1 && history[history.length - 1].price >= history[history.length - 2]?.price;
  const symData = aiState?.[symbol] || {};
  const conf = symData.confidence || 0;
  const confColor = conf >= 50 ? '#10b981' : conf >= 35 ? '#f59e0b' : '#ef4444';

  return (
    <Card
      title={`${symbol} LIVE FEED`}
      icon={Activity}
      iconColor={symbol === 'EURUSD' ? 'blue' : 'gold'}
      right={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: confColor, fontFamily: 'monospace', fontSize: 11, fontWeight: 'bold' }}>
            AI: {conf}%
          </span>
          <span className={up ? 'text-green' : 'text-red'} style={{ fontFamily: 'monospace', fontSize: 13, fontWeight: 'bold' }}>
            {price > 0 ? price.toFixed(symbol === 'EURUSD' ? 5 : 2) : '---'} {up ? '▲' : '▼'}
          </span>
        </div>
      }
    >
      <div className="chart-meta">
        <span className="text-sub">Spread: <span style={{ color }}>{spread} pts</span></span>
        <span className="text-sub">Session: <span className="text-blue">{priceData?.session ?? '---'}</span></span>
        <span className="text-sub">Status: <span style={{ color: confColor }}>{conf >= 50 ? '🟢 READY' : conf >= 35 ? '🟡 WATCH' : '🔴 WAIT'}</span></span>
      </div>
      <ResponsiveContainer width="100%" height={130}>
        <AreaChart data={history} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`g-${symbol}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.35} />
              <stop offset="95%" stopColor={color} stopOpacity={0}    />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" hide />
          <YAxis domain={['auto', 'auto']} hide />
          <Tooltip content={<CustomChartTooltip />} />
          <Area type="monotone" dataKey="price" stroke={color}
            fill={`url(#g-${symbol})`} strokeWidth={2} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   TRADE JOURNAL TABLE
═══════════════════════════════════════════════ */
function Journal({ trades }) {
  const earned = trades.filter(t => t.win).reduce((s, t) => s + (t.pnl ?? 0), 0);
  return (
    <Card title="TRADE JOURNAL  -  TODAY"
      icon={BookOpen} iconColor="blue"
      right={<span className="text-sub" style={{ fontSize: 10 }}>{trades.length} trades | <PnL value={earned} /></span>}
    >
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>TIME</th><th>DIR</th><th>ENTRY</th><th>EXIT</th>
              <th>PTS</th><th>P&L</th><th>SESSION</th><th>RESULT</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr><td colSpan={8} className="tbl-empty">No trades executed today</td></tr>
            )}
            {trades.slice().reverse().map((t, i) => (
              <tr key={i} className={t.win ? 'row-win' : 'row-loss'}>
                <td className="text-sub mono">{t.time}</td>
                <td className={t.dir === 'BUY' ? 'text-green fw-bold' : 'text-red fw-bold'}>{t.dir}</td>
                <td className="mono">{t.entry?.toFixed(2)}</td>
                <td className="mono">{t.exit?.toFixed(2) || ' - '}</td>
                <td className={cx('mono', t.pts > 0 ? 'text-green' : 'text-red')}>
                  {t.pts > 0 ? '+' : ''}{t.pts?.toFixed(1)}
                </td>
                <td className={cx('fw-bold mono', t.pnl >= 0 ? 'text-green' : 'text-red')}>
                  {t.pnl >= 0 ? '+' : ''}${Math.abs(t.pnl).toFixed(2)}
                </td>
                <td className="text-sub">{t.session}</td>
                <td>
                  <span className={cx('result-badge', t.win ? 'rb-win' : 'rb-loss')}>
                    {t.win ? 'WIN' : 'LOSS'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   CONTROL PANEL
═══════════════════════════════════════════════ */
function Controls({ st, online }) {
  const [msg, setMsg] = useState('');
  const send = useCallback(async (cmd) => {
    const ok = await postCmd(cmd);
    setMsg(ok ? `✓ ${cmd}` : ' -  -  Command failed');
    setTimeout(() => setMsg(''), 3000);
  }, []);

  const paused = st?.status === 'PAUSED' || st?.manual_pause;

  return (
    <Card title="CONTROL PANEL" icon={Zap} iconColor="gold">
      <div className="ctrl-grid">
        <button className="btn btn-buy"  onClick={() => send('/resume')} disabled={!online}>
          <Play size={13} /> RESUME
        </button>
        <button className="btn btn-sell" onClick={() => send('/pause')} disabled={!online}>
          <Pause size={13} /> PAUSE
        </button>
      </div>
      <div className="ctrl-grid ctrl-3">
        <button className="btn btn-ghost" onClick={() => send('/closeall')} disabled={!online}>
          <X size={12} /> CLOSE ALL
        </button>
        <button className="btn btn-ghost" onClick={() => send('/diagnose')} disabled={!online}>
          <Cpu size={12} /> DIAGNOSE
        </button>
        <button className="btn btn-ghost" onClick={() => send('/reconnect')} disabled={!online}>
          <RefreshCw size={12} /> RECONNECT
        </button>
      </div>
      {st?.consecutive_losses >= 3 && (
        <div className="warn-row">
          <AlertTriangle size={12} />
          {st.consecutive_losses} consecutive losses  -  caution mode
        </div>
      )}
      {msg && <div className="ctrl-msg">{msg}</div>}
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   LOG PANEL
═══════════════════════════════════════════════ */
function LogPanel({ trades, st }) {
  const events = useMemo(() => {
    const out = [];
    if (!st) return out;
    trades.slice(-5).reverse().forEach(t => {
      out.push({
        type: t.win ? 'win' : 'loss',
        msg: `${t.dir} ${t.session} ${t.win ? '+' : ''}${t.pts?.toFixed(1)}pts $${t.pnl >= 0 ? '+' : ''}${t.pnl?.toFixed(2)}`,
        time: t.time,
      });
    });
    if (st.status === 'ACTIVE') out.push({ type: 'info', msg: 'Engine running  -  scanning market', time: 'now' });
    if (st.status === 'PAUSED') out.push({ type: 'warn', msg: 'Trading paused by operator', time: 'now' });
    if (st.consecutive_losses >= 3) out.push({ type: 'warn', msg: `${st.consecutive_losses} consecutive losses`, time: 'now' });
    return out;
  }, [trades, st]);

  return (
    <Card title="EVENT LOG" icon={Activity} iconColor="sub">
      <div className="log-list">
        {events.length === 0 && <div className="log-empty">Waiting for events...</div>}
        {events.map((e, i) => (
          <div key={i} className={cx('log-item', `log-${e.type}`)}>
            <Circle size={6} style={{ flexShrink: 0, marginTop: 1 }} />
            <span className="log-msg">{e.msg}</span>
            <span className="log-time">{e.time}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ═══════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════ */
export default function App() {
  const [status, statusErr]  = useApi('/status', 1500);
  const [trades, tradesErr]  = useApi('/trades', 2000);
  const [aiState, aiStateErr] = useApi('/aistate', 500);  // 500ms = live updates

  const online = !statusErr;
  const st     = status ?? {};
  const tList  = Array.isArray(trades) ? trades : [];
  
  // Get symbol-specific confidence
  const eurusdConf = aiState?.EURUSD?.confidence ?? 0;
  const xauusdConf = aiState?.XAUUSD?.confidence ?? 0;

  const price  = 0;
  const spread = 0;

  return (
    <div className="app">

      {/* ─── HEADER ─────────────────────────────── */}
      <header className="hdr">
        <div className="hdr-l">
          <Activity className="icon-gold" size={20} />
          <span className="hdr-brand">AEGIS <span className="hdr-gold">GOLD</span></span>
          <span className="hdr-tag">v6.0 ULTRA</span>
        </div>
        <div className="hdr-c">
          <StatusBadge status={st.status} online={online} />
          <Pill color="gold">XAUUSD</Pill>
          <Pill color="blue">{st.session ?? '---'}</Pill>
          <Pill color="purple">LOCAL AI</Pill>
        </div>
        <div className="hdr-r">
          {online
            ? <><ShieldCheck size={13} className="icon-green" /><span className="conn text-green">SECURE</span></>
            : <><ShieldAlert size={13} className="icon-red pulse" /><span className="conn text-red">OFFLINE</span></>}
          <span className="utc">{new Date().toLocaleTimeString('en-GB', { timeZone: 'UTC' })} UTC</span>
        </div>
      </header>

      {/* ─── TOP STATS ───────────────────────────── */}
      <section className="stats-row">
        <StatCard
          label="Account Equity"
          value={`$${(st.equity ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          sub="Live Balance"
          icon={TrendingUp} color="gold"
        />
        <StatCard
          label="Today P&L"
          value={<PnL value={st.daily_pnl ?? 0} />}
          sub={`${st.wins ?? 0}W / ${st.losses ?? 0}L`}
          icon={DollarSign} color={st.daily_pnl >= 0 ? 'green' : 'red'}
        />
        <StatCard
          label="EURUSD Confidence"
          value={`${eurusdConf}%`}
          sub="50%+ = SCALP TRADE"
          icon={Brain} color={eurusdConf >= 50 ? 'green' : eurusdConf >= 35 ? 'gold' : 'red'}
        />
        <StatCard
          label="XAUUSD Confidence"
          value={`${xauusdConf}%`}
          sub="50%+ = SCALP TRADE"
          icon={Brain} color={xauusdConf >= 50 ? 'green' : xauusdConf >= 35 ? 'gold' : 'red'}
        />
        <StatCard
          label="Trades Today"
          value={st.daily_trades ?? 0}
          sub={`Win Rate: ${(st.wins ?? 0) + (st.losses ?? 0) > 0 ? (((st.wins ?? 0) / ((st.wins ?? 0) + (st.losses ?? 0))) * 100).toFixed(0) : 0}%`}
          icon={History} color="blue"
        />
        <StatCard
          label="Latency"
          value={`${(st.latency ?? 0).toFixed(0)}ms`}
          sub="MT5 Execution"
          icon={Cpu} color="sub"
        />
      </section>

      {/* ─── MAIN GRID ───────────────────────────── */}
      <div className="grid-main">

        {/* ── LEFT: Charts + Journal ── */}
        <div className="col-left">
          <SymbolChart symbol="EURUSD" color="#3b82f6" aiState={aiState} />
          <SymbolChart symbol="XAUUSD" color="#f59e0b" aiState={aiState} />
          <Journal trades={tList} />
        </div>

        {/* ── RIGHT: Panels ── */}
        <div className="col-right">
          <SystemStatus st={st} online={online} />
          <AccountPanel st={st} />
          <TradePanel st={st} trades={tList} />
          <EURUSDPanel aiState={aiState} />
          <XAUUSDPanel aiState={aiState} />
          <Controls st={st} online={online} />
          <LogPanel trades={tList} st={online ? st : null} />
        </div>

      </div>

      {/* ─── FOOTER ──────────────────────────────── */}
      <footer className="ftr">
        <span>AEGIS GOLD v6.0 ULTRA  -  SCALPING MODE  -  50% CONFIDENCE</span>
        <span>LOCAL AI | EURUSD + XAUUSD | SCALPING | LATENCY {(st.latency ?? 0).toFixed(0)}ms</span>
      </footer>

    </div>
  );
}
