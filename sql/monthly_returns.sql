-- Monthly total returns for every ETF, computed from month-end adjusted closes.
-- Grain: one row per (ticker, month). The first month of each ticker has a NULL return.

WITH month_end AS (
    -- last trading day actually present in the data for each ticker and month
    SELECT ticker,
           strftime('%Y-%m', date) AS month,
           MAX(date)               AS last_day
    FROM prices
    GROUP BY ticker, month
),

month_price AS (
    -- join on (date, ticker), the primary key of prices, so each row matches exactly once
    SELECT m.ticker, m.month, p.adj_close
    FROM month_end m
    JOIN prices p
      ON p.date   = m.last_day
     AND p.ticker = m.ticker
)

SELECT ticker,
       month,
       adj_close,
       adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY month) - 1 AS ret
FROM month_price
ORDER BY ticker, month;
