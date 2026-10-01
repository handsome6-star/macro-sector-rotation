-- Data quality checks, run after every ingestion: python -m src.check_data
-- Each query starts with a "name" marker comment, which check_data.py splits on.

-- name: Price coverage per ticker
SELECT a.ticker,
       a.name,
       COUNT(p.date)  AS trading_days,
       MIN(p.date)    AS first_date,
       MAX(p.date)    AS last_date
FROM assets a
LEFT JOIN prices p ON p.ticker = a.ticker
GROUP BY a.ticker, a.name
ORDER BY first_date;

-- name: Macro series coverage
SELECT m.series_id,
       s.frequency,
       COUNT(*)      AS observations,
       MIN(m.date)   AS first_date,
       MAX(m.date)   AS last_date
FROM macro m
JOIN series_meta s ON s.series_id = m.series_id
GROUP BY m.series_id, s.frequency
ORDER BY m.series_id;

-- name: Suspicious daily moves (|return| > 15%) - real crashes or bad data?
WITH daily AS (
    SELECT ticker,
           date,
           adj_close,
           adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS ret
    FROM prices
)
SELECT ticker, date, ROUND(ret * 100, 2) AS return_pct
FROM daily
WHERE ABS(ret) > 0.15
ORDER BY ABS(ret) DESC
LIMIT 15;

-- name: Latest macro readings
SELECT m.series_id, s.name, m.date, m.value
FROM macro m
JOIN series_meta s ON s.series_id = m.series_id
WHERE m.date = (SELECT MAX(date) FROM macro WHERE series_id = m.series_id)
ORDER BY m.series_id;

-- name: Failed ingestion steps in the latest run
SELECT source, item, message
FROM ingest_log
WHERE status = 'error'
  AND run_at >= (SELECT MAX(run_at) FROM ingest_log WHERE source = 'yfinance' AND item = 'XLK');
