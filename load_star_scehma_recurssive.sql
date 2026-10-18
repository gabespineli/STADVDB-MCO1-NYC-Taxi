-- =====================================================================
-- STADVDB - MCO1: NYC Yellow Taxi ETL Load Script
-- Loads raw data from yellow_taxi_trips into Star Schema tables:
--   1. dim_payment
--   2. dim_rate_code
--   3. dim_time
--   4. dim_location
--   5. dim_date
--   6. fact_trip_records
-- =====================================================================

USE source_db;

-- Speed up bulk inserts by disabling checks temporarily
SET FOREIGN_KEY_CHECKS = 0;
SET UNIQUE_CHECKS = 0;
SET SESSION cte_max_recursion_depth = 2000;
SET SQL_MODE = 'NO_ENGINE_SUBSTITUTION';

-- =====================================================================
-- STEP 1: Populate Dimension Tables
-- =====================================================================

-- 1.1 dim_payment
INSERT INTO dim_payment (payment_id, payment_method) VALUES
(0, 'Unknown'),
(1, 'Credit card'),
(2, 'Cash'),
(3, 'No charge'),
(4, 'Dispute'),
(5, 'Unknown'),
(6, 'Voided trip')
ON DUPLICATE KEY UPDATE payment_method = VALUES(payment_method);

-- Catch any unknown payment_type values from yellow_taxi_trips
INSERT IGNORE INTO dim_payment (payment_id, payment_method)
SELECT DISTINCT payment_type, 'Unknown/Other'
FROM yellow_taxi_trips
WHERE payment_type IS NOT NULL AND payment_type NOT IN (0, 1, 2, 3, 4, 5, 6);

-- 1.2 dim_rate_code
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

-- Catch any unlisted RatecodeID values from yellow_taxi_trips
INSERT IGNORE INTO dim_rate_code (rate_code_id, rate_description)
SELECT DISTINCT CAST(RatecodeID AS SIGNED), 'Unknown/Other'
FROM yellow_taxi_trips
WHERE RatecodeID IS NOT NULL AND CAST(RatecodeID AS SIGNED) NOT IN (0, 1, 2, 3, 4, 5, 6, 99);

-- 1.3 dim_time (All 1,440 minutes of a day, 0 to 1439)
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

-- 1.4 dim_location (Populate distinct pickup & dropoff location IDs)
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

-- 1.5 dim_date (Populate unique pickup & dropoff dates)
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

-- =====================================================================
-- STEP 2: Populate fact_trip_records
-- =====================================================================

INSERT INTO fact_trip_records (
    pu_date_id,
    do_date_id,
    pu_time_id,
    do_time_id,
    pu_location_id,
    do_location_id,
    payment_id,
    rate_code_id,
    trip_distance,
    fare_amount,
    extra,
    mta_tax,
    tip_amount,
    tolls_amount,
    improvement_surcharge,
    total_amount,
    airport_fee,
    cbd_congestion_fee,
    trip_duration_seconds,
    estimated_speed_mph
)
SELECT 
    -- Date IDs (format: YYYYMMDD)
    CAST(DATE_FORMAT(tpep_pickup_datetime, '%Y%m%d') AS SIGNED) AS pu_date_id,
    CAST(DATE_FORMAT(tpep_dropoff_datetime, '%Y%m%d') AS SIGNED) AS do_date_id,
    
    -- Time IDs (format: minute of day, 0 to 1439)
    (HOUR(tpep_pickup_datetime) * 60 + MINUTE(tpep_pickup_datetime)) AS pu_time_id,
    (HOUR(tpep_dropoff_datetime) * 60 + MINUTE(tpep_dropoff_datetime)) AS do_time_id,
    
    -- Locations
    COALESCE(PULocationID, 0) AS pu_location_id,
    COALESCE(DOLocationID, 0) AS do_location_id,
    
    -- Payment & Rate Code
    COALESCE(payment_type, 0) AS payment_id,
    COALESCE(CAST(RatecodeID AS SIGNED), 0) AS rate_code_id,
    
    -- Metrics
    COALESCE(trip_distance, 0.00),
    COALESCE(fare_amount, 0.00),
    COALESCE(extra, 0.00),
    COALESCE(mta_tax, 0.00),
    COALESCE(tip_amount, 0.00),
    COALESCE(tolls_amount, 0.00),
    COALESCE(improvement_surcharge, 0.00),
    COALESCE(total_amount, 0.00),
    COALESCE(Airport_fee, 0.00),
    COALESCE(cbd_congestion_fee, 0.00),
    
    -- Derived: / trip_duration_seconds
    TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) AS trip_duration_seconds,
    
    -- Derived: / estimated_speed_mph
    CASE 
        WHEN TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) > 0 
        THEN ROUND(COALESCE(trip_distance, 0) / (TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) / 3600.0), 2)
        ELSE 0.00 
    END AS estimated_speed_mph
FROM yellow_taxi_trips
WHERE tpep_pickup_datetime IS NOT NULL 
  AND tpep_dropoff_datetime IS NOT NULL;

-- Re-enable constraints
SET FOREIGN_KEY_CHECKS = 1;
SET UNIQUE_CHECKS = 1;
