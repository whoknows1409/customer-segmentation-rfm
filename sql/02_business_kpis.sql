-- 02_business_kpis.sql
-- Headline business metrics. Each query result is saved to outputs/ by run_analysis.py.

-- name: overall_kpis
SELECT
    COUNT(*)                                        AS line_items,
    COUNT(DISTINCT invoice_no)                      AS orders,
    COUNT(DISTINCT customer_id)                     AS customers,
    COUNT(DISTINCT stock_code)                      AS products,
    COUNT(DISTINCT country)                         AS countries,
    ROUND(SUM(revenue), 0)                          AS total_revenue_gbp,
    ROUND(SUM(revenue) / COUNT(DISTINCT invoice_no), 2) AS avg_order_value_gbp,
    MIN(invoice_ts)                                 AS first_order,
    MAX(invoice_ts)                                 AS last_order
FROM sales;

-- name: repeat_customers
-- Share of customers who ordered more than once, and their share of revenue.
WITH per_customer AS (
    SELECT customer_id, COUNT(DISTINCT invoice_no) AS orders, SUM(revenue) AS revenue
    FROM sales GROUP BY customer_id
)
SELECT
    ROUND(100.0 * AVG(CASE WHEN orders > 1 THEN 1 ELSE 0 END), 1)              AS repeat_customer_pct,
    ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN revenue ELSE 0 END) / SUM(revenue), 1) AS repeat_revenue_pct
FROM per_customer;

-- name: revenue_concentration
-- Pareto check: what share of revenue comes from the top 20% of customers?
WITH per_customer AS (
    SELECT customer_id, SUM(revenue) AS revenue
    FROM sales GROUP BY customer_id
), ranked AS (
    SELECT customer_id, revenue, NTILE(5) OVER (ORDER BY revenue DESC, customer_id) AS quintile
    FROM per_customer
)
SELECT quintile,
       COUNT(*)                                          AS customers,
       ROUND(SUM(revenue), 0)                            AS revenue_gbp,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1) AS revenue_share_pct
FROM ranked GROUP BY quintile ORDER BY quintile;

-- name: monthly_revenue
SELECT DATE_TRUNC('month', invoice_ts)          AS month,
       COUNT(DISTINCT invoice_no)               AS orders,
       COUNT(DISTINCT customer_id)              AS active_customers,
       ROUND(SUM(revenue), 0)                   AS revenue_gbp
FROM sales GROUP BY 1 ORDER BY 1;

-- name: country_revenue
SELECT country,
       COUNT(DISTINCT customer_id)                                   AS customers,
       ROUND(SUM(revenue), 0)                                        AS revenue_gbp,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 1)    AS revenue_share_pct
FROM sales GROUP BY country ORDER BY revenue_gbp DESC LIMIT 10;

-- name: cancellation_impact
SELECT
    COUNT(DISTINCT c.invoice_no)                                         AS cancelled_orders,
    ROUND(-SUM(c.revenue), 0)                                            AS cancelled_value_gbp,
    ROUND(100.0 * -SUM(c.revenue) / (SELECT SUM(revenue) FROM sales), 1) AS pct_of_net_sales
FROM cancellations c;
