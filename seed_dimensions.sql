-- =====================================================================
-- STADVDB - MCO1: Populate All 5 Dimensions for NYC Taxi Star Schema
-- =====================================================================

USE source_db;

SET FOREIGN_KEY_CHECKS = 0;
SET UNIQUE_CHECKS = 0;
SET SESSION cte_max_recursion_depth = 2000;

-- 1. Populate dim_payment
INSERT INTO dim_payment (payment_id, payment_method) VALUES
(0, 'Unknown'),
(1, 'Credit card'),
(2, 'Cash'),
(3, 'No charge'),
(4, 'Dispute'),
(5, 'Unknown'),
(6, 'Voided trip')
ON DUPLICATE KEY UPDATE payment_method = VALUES(payment_method);

INSERT IGNORE INTO dim_payment (payment_id, payment_method)
SELECT DISTINCT payment_type, 'Unknown/Other'
FROM yellow_taxi_trips
WHERE payment_type IS NOT NULL AND payment_type NOT IN (0, 1, 2, 3, 4, 5, 6);

-- 2. Populate dim_rate_code
INSERT INTO dim_rate_code (rate_code_id, rate_description) VALUES
(0, 'Unknown'),
(1, 'Standard rate'),
(2, 'JFK'),
(3, 'Newark'),
(4, 'Nassau or Westchester'),
(5, 'Negotiated fare'),
(6, 'Group ride'),
(99, 'Special rate')
ON DUPLICATE KEY UPDATE rate_description = VALUES(rate_description);

INSERT IGNORE INTO dim_rate_code (rate_code_id, rate_description)
SELECT DISTINCT CAST(RatecodeID AS SIGNED), 'Unknown/Other'
FROM yellow_taxi_trips
WHERE RatecodeID IS NOT NULL AND CAST(RatecodeID AS SIGNED) NOT IN (0, 1, 2, 3, 4, 5, 6, 99);

-- 3. Populate dim_time (All 1,440 minutes of a 24-hour day: 0 to 1439)
INSERT INTO dim_time (time_id, minute, hour, time_period)
WITH RECURSIVE minutes AS (
    SELECT 0 AS m
    UNION ALL
    SELECT m + 1 FROM minutes WHERE m < 1439
)
SELECT 
    m AS time_id,
    (m % 60) AS minute,
    FLOOR(m / 60) AS hour,
    CASE 
        WHEN FLOOR(m / 60) BETWEEN 5 AND 11 THEN 'Morning'
        WHEN FLOOR(m / 60) BETWEEN 12 AND 16 THEN 'Afternoon'
        WHEN FLOOR(m / 60) BETWEEN 17 AND 20 THEN 'Evening'
        ELSE 'Night'
    END AS time_period
FROM minutes
ON DUPLICATE KEY UPDATE time_period = VALUES(time_period);

-- 4. Populate dim_location (Unique locations from pickup & dropoff)
INSERT IGNORE INTO dim_location (location_id, zone, borough) VALUES
(0, 'Unknown Zone', 'Unknown Borough');

INSERT IGNORE INTO dim_location (location_id, zone, borough)
SELECT DISTINCT PULocationID, CONCAT('Zone ', PULocationID), 'Unknown'
FROM yellow_taxi_trips
WHERE PULocationID IS NOT NULL
UNION
SELECT DISTINCT DOLocationID, CONCAT('Zone ', DOLocationID), 'Unknown'
FROM yellow_taxi_trips
WHERE DOLocationID IS NOT NULL;

-- 5. Populate dim_date (Unique dates from pickup & dropoff)
INSERT IGNORE INTO dim_date (date_id, `date`, is_weekend, day_of_week, `month`, `quarter`, `year`)
SELECT 
    CAST(DATE_FORMAT(dt, '%Y%m%d') AS SIGNED) AS date_id,
    dt AS `date`,
    IF(DAYOFWEEK(dt) IN (1, 7), 1, 0) AS is_weekend,
    DAYNAME(dt) AS day_of_week,
    MONTH(dt) AS `month`,
    QUARTER(dt) AS `quarter`,
    YEAR(dt) AS `year`
FROM (
    SELECT DISTINCT DATE(tpep_pickup_datetime) AS dt 
    FROM yellow_taxi_trips 
    WHERE tpep_pickup_datetime IS NOT NULL
    UNION
    SELECT DISTINCT DATE(tpep_dropoff_datetime) AS dt 
    FROM yellow_taxi_trips 
    WHERE tpep_dropoff_datetime IS NOT NULL
) AS unique_dates;

SET FOREIGN_KEY_CHECKS = 1;
SET UNIQUE_CHECKS = 1;
