PLACE YOUR REAL MT5 EXPORTS HERE (tab-separated, \\r\\n ok):
  XAUUSD_M5_*.csv, XAUUSD_M15_*.csv, XAUUSD_H1_*.csv
Header must be: <DATE>\\t<TIME>\\t<OPEN>\\t<HIGH>\\t<LOW>\\t<CLOSE>\\t<TICKVOL>\\t<VOL>\\t<SPREAD>
Date format YYYY.MM.DD, spread in points.
Gates per timeframe: M5 >= 60,000 bars, M15 >= 20,000 bars, H1 >= 5,000 bars;
span >= 12 months (below 12m warns and caps verdict at NEEDS_MORE_DATA).
Bars below minimum ABORTS the audit; missing files REFUSE to run.
Your 1-day 169-bar sample is loader-test ONLY, not audit-grade.
Previous funnel results (48,018 patterns / 4 trades): INVALID (synthetic).
