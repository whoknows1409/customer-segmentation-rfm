-- 03_cohort_retention.sql
-- Monthly acquisition cohorts: of the customers whose first order was in month M,
-- what % ordered again in month M+1, M+2, ...?
-- December 2011 is excluded because the data stops on 9 Dec 2011 (a partial month
-- would understate retention).

-- name: cohort_retention
WITH orders AS (
    SELECT DISTINCT customer_id, DATE_TRUNC('month', invoice_ts) AS order_month
    FROM sales
    WHERE invoice_ts < TIMESTAMP '2011-12-01'
), first_month AS (
    SELECT customer_id, MIN(order_month) AS cohort_month
    FROM orders GROUP BY customer_id
), activity AS (
    SELECT f.cohort_month,
           DATE_DIFF('month', f.cohort_month, o.order_month) AS month_index,
           COUNT(DISTINCT o.customer_id)                      AS active_customers
    FROM orders o JOIN first_month f USING (customer_id)
    GROUP BY 1, 2
)
SELECT a.cohort_month,
       a.month_index,
       a.active_customers,
       c.active_customers                                         AS cohort_size,
       ROUND(100.0 * a.active_customers / c.active_customers, 1) AS retention_pct
FROM activity a
JOIN activity c ON c.cohort_month = a.cohort_month AND c.month_index = 0
ORDER BY 1, 2;
