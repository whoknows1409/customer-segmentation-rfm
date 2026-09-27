-- 04_rfm.sql
-- RFM (Recency, Frequency, Monetary) per customer, scored 1-5 by quintile.
--   Recency   = days since last order, measured from the day after the last invoice in the data
--   Frequency = number of distinct orders
--   Monetary  = total revenue (GBP)
-- Quintile scores give a transparent, rule-based segmentation that the K-Means model
-- (src/segment_customers.py) is compared against.

-- name: rfm
WITH snapshot AS (
    SELECT CAST(MAX(invoice_ts) AS DATE) + INTERVAL 1 DAY AS snapshot_date FROM sales
), base AS (
    SELECT s.customer_id,
           DATE_DIFF('day', MAX(s.invoice_ts), ANY_VALUE(snap.snapshot_date)) AS recency_days,
           COUNT(DISTINCT s.invoice_no)                                       AS frequency,
           ROUND(SUM(s.revenue), 2)                                           AS monetary
    FROM sales s CROSS JOIN snapshot snap
    GROUP BY s.customer_id
), scored AS (
    SELECT *,
           6 - NTILE(5) OVER (ORDER BY recency_days, customer_id) AS r_score,  -- recent = 5; customer_id breaks ties so runs are identical
           NTILE(5) OVER (ORDER BY frequency, customer_id)    AS f_score,
           NTILE(5) OVER (ORDER BY monetary, customer_id)     AS m_score
    FROM base
)
SELECT *,
       CASE
           WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
           WHEN r_score >= 3 AND f_score >= 3                  THEN 'Loyal'
           WHEN r_score >= 4 AND f_score <= 2                  THEN 'New / Promising'
           WHEN r_score <= 2 AND f_score >= 3                  THEN 'At Risk'
           WHEN r_score = 3  AND f_score <= 2                  THEN 'Needs Attention'
           ELSE                                                     'Hibernating'
       END AS rfm_segment
FROM scored
ORDER BY monetary DESC;
