-- =====================================================================
-- Optional: Batched Loader Stored Procedure for Large Data (48M+ rows)
-- Prevents lock table exhaustion and out-of-memory errors in MySQL
-- =====================================================================

USE source_db;

DELIMITER $$

DROP PROCEDURE IF EXISTS LoadFactTripsBatched$$

CREATE PROCEDURE LoadFactTripsBatched(IN batch_size INT)
BEGIN
    DECLARE total_rows BIGINT;
    DECLARE offset_val BIGINT DEFAULT 0;
    
    SET FOREIGN_KEY_CHECKS = 0;
    SET UNIQUE_CHECKS = 0;
    
    SELECT COUNT(*) INTO total_rows FROM yellow_taxi_trips;
    
    WHILE offset_val < total_rows DO
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
            CAST(DATE_FORMAT(tpep_pickup_datetime, '%Y%m%d') AS SIGNED),
            CAST(DATE_FORMAT(tpep_dropoff_datetime, '%Y%m%d') AS SIGNED),
            (HOUR(tpep_pickup_datetime) * 60 + MINUTE(tpep_pickup_datetime)),
            (HOUR(tpep_dropoff_datetime) * 60 + MINUTE(tpep_dropoff_datetime)),
            COALESCE(PULocationID, 0),
            COALESCE(DOLocationID, 0),
            COALESCE(payment_type, 0),
            COALESCE(CAST(RatecodeID AS SIGNED), 0),
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
            TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime),
            CASE 
                WHEN TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) > 0 
                THEN ROUND(COALESCE(trip_distance, 0) / (TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) / 3600.0), 2)
                ELSE 0.00 
            END
        FROM yellow_taxi_trips
        WHERE tpep_pickup_datetime IS NOT NULL 
          AND tpep_dropoff_datetime IS NOT NULL
        LIMIT batch_size OFFSET offset_val;

        COMMIT;
        SET offset_val = offset_val + batch_size;
    END WHILE;
    
    SET FOREIGN_KEY_CHECKS = 1;
    SET UNIQUE_CHECKS = 1;
END$$

DELIMITER ;

-- Usage example:
-- CALL LoadFactTripsBatched(100000);
