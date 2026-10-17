-- =====================================================================
-- STADVDB - MCO1: Populate fact_trip_records directly from yellow_taxi_trips
-- Run this in your MySQL GUI (DBeaver, MySQL Workbench, phpMyAdmin, etc.)
-- =====================================================================

USE source_db;

-- Speed up bulk insert by temporarily disabling index/constraint checks
SET FOREIGN_KEY_CHECKS = 0;
SET UNIQUE_CHECKS = 0;
SET SQL_MODE = 'NO_ENGINE_SUBSTITUTION';

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
    
    -- Derived: trip_duration_seconds
    TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) AS trip_duration_seconds,
    
    -- Derived: estimated_speed_mph
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
