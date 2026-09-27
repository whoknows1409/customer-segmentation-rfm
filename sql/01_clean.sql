-- 01_clean.sql
-- Build an analysis-ready table from the raw UCI Online Retail transactions.
--
-- Raw data: one row per invoice line, Dec 2010 - Dec 2011, UK-based online gift retailer.
-- Cleaning rules (each is explained in the README):
--   1. Drop rows with no CustomerID (cannot be attributed to a customer).
--   2. Drop cancellations (InvoiceNo starting with 'C') and non-positive quantities.
--   3. Drop non-positive prices (free samples, data errors, bad-debt adjustments).
--   4. Drop non-product stock codes (postage, manual adjustments, bank charges, fees).
--   5. Remove exact duplicate lines.

CREATE OR REPLACE TABLE raw AS
SELECT * FROM read_csv_auto('data/online_retail.csv.gz', header = true,
                            types = {'InvoiceNo': 'VARCHAR', 'StockCode': 'VARCHAR'});

CREATE OR REPLACE TABLE sales AS
SELECT DISTINCT
    InvoiceNo                               AS invoice_no,
    StockCode                               AS stock_code,
    Description                             AS description,
    Quantity                                AS quantity,
    CAST(InvoiceDate AS TIMESTAMP)          AS invoice_ts,
    UnitPrice                               AS unit_price,
    CAST(CustomerID AS INTEGER)             AS customer_id,
    Country                                 AS country,
    Quantity * UnitPrice                    AS revenue
FROM raw
WHERE CustomerID IS NOT NULL
  AND InvoiceNo NOT LIKE 'C%'
  AND Quantity > 0
  AND UnitPrice > 0
  AND StockCode NOT IN ('POST', 'D', 'M', 'DOT', 'BANK CHARGES', 'AMAZONFEE',
                        'CRUK', 'C2', 'PADS', 'S', 'B');

-- Cancellations kept separately to measure revenue lost to returns.
CREATE OR REPLACE TABLE cancellations AS
SELECT InvoiceNo AS invoice_no, CAST(CustomerID AS INTEGER) AS customer_id,
       Quantity * UnitPrice AS revenue
FROM raw
WHERE InvoiceNo LIKE 'C%' AND CustomerID IS NOT NULL
  AND StockCode NOT IN ('POST', 'D', 'M', 'DOT', 'BANK CHARGES', 'AMAZONFEE',
                        'CRUK', 'C2', 'PADS', 'S', 'B');
