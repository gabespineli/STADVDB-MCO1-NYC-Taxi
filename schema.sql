-- =====================================================================
-- STADVDB - MCO1: NYC Yellow Taxi Star Schema
-- DDL Script to create Dimension and Fact tables
-- =====================================================================

-- Create and select database as specified in load_parquet_to_mysql.py / .env
CREATE DATABASE IF NOT EXISTS source_db;
USE source_db;

-- Drop Fact table first due to foreign key constraints
DROP TABLE IF EXISTS fact_trip_records;

-- Drop Dimension tables
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_time;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS dim_payment;
DROP TABLE IF EXISTS dim_rate_code;

-- =====================================================================
-- 1. Dimension: Date (dim_date)
-- =====================================================================
CREATE TABLE dim_date (
    date_id INT NOT NULL,                          -- e.g., YYYYMMDD (e.g., 20250101) or auto-increment surrogate key
    `date` DATE NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,              -- e.g., 'Monday', 'Tuesday'
    `month` SMALLINT NOT NULL,                     -- 1 - 12
    `quarter` SMALLINT NOT NULL,                   -- 1 - 4
    `year` SMALLINT NOT NULL,                      -- e.g., 2025
    PRIMARY KEY (date_id),
    UNIQUE KEY uq_date (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- 2. Dimension: Time (dim_time)
-- =====================================================================
CREATE TABLE dim_time (
    time_id INT NOT NULL,                          -- e.g., HHMM (0 to 2359) or surrogate key (0 to 1439)
    `minute` SMALLINT NOT NULL,                    -- 0 - 59
    `hour` SMALLINT NOT NULL,                      -- 0 - 23
    time_period VARCHAR(20) NOT NULL,              -- e.g., 'Morning', 'Afternoon', 'Evening', 'Night'
    PRIMARY KEY (time_id),
    KEY idx_time_hour_min (`hour`, `minute`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- 3. Dimension: Location (dim_location)
-- =====================================================================
CREATE TABLE dim_location (
    location_id INT NOT NULL,                      -- Matches TLC Taxi Zone ID (1 - 265)
    zone VARCHAR(100) DEFAULT NULL,
    borough VARCHAR(50) DEFAULT NULL,
    PRIMARY KEY (location_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- 4. Dimension: Payment (dim_payment)
-- =====================================================================
CREATE TABLE dim_payment (
    payment_id INT NOT NULL,                       -- TLC payment_type code (1: Credit card, 2: Cash, etc.)
    payment_method VARCHAR(30) NOT NULL,
    PRIMARY KEY (payment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- 5. Dimension: Rate Code (dim_rate_code)
-- =====================================================================
CREATE TABLE dim_rate_code (
    rate_code_id INT NOT NULL,                     -- TLC RatecodeID (1: Standard rate, 2: JFK, etc.)
    rate_description VARCHAR(50) NOT NULL,
    PRIMARY KEY (rate_code_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- 6. Fact: Trip Records (fact_trip_records)
-- Note: '/ trip_duration_seconds' and '/ estimated_speed_mph' are
-- derived measures in the schema model calculated during ETL.
-- =====================================================================
CREATE TABLE fact_trip_records (
    trip_id BIGINT NOT NULL AUTO_INCREMENT,
    pu_date_id INT NOT NULL,
    do_date_id INT NOT NULL,
    pu_time_id INT NOT NULL,
    do_time_id INT NOT NULL,
    pu_location_id INT NOT NULL,
    do_location_id INT NOT NULL,
    payment_id INT NOT NULL,
    rate_code_id INT NOT NULL,
    trip_distance DECIMAL(8, 2) DEFAULT 0.00,
    fare_amount DECIMAL(10, 2) DEFAULT 0.00,
    extra DECIMAL(10, 2) DEFAULT 0.00,
    mta_tax DECIMAL(10, 2) DEFAULT 0.00,
    tip_amount DECIMAL(10, 2) DEFAULT 0.00,
    tolls_amount DECIMAL(10, 2) DEFAULT 0.00,
    improvement_surcharge DECIMAL(10, 2) DEFAULT 0.00,
    total_amount DECIMAL(10, 2) DEFAULT 0.00,
    airport_fee DECIMAL(10, 2) DEFAULT 0.00,
    cbd_congestion_fee DECIMAL(10, 2) DEFAULT 0.00,
    trip_duration_seconds INT DEFAULT NULL,        -- Derived: TIMESTAMPDIFF(SECOND, pickup, dropoff)
    estimated_speed_mph DECIMAL(6, 2) DEFAULT NULL,-- Derived: trip_distance / (trip_duration_seconds / 3600)
    PRIMARY KEY (trip_id),

    -- Foreign Key Constraints
    CONSTRAINT fk_fact_pu_date FOREIGN KEY (pu_date_id) REFERENCES dim_date (date_id),
    CONSTRAINT fk_fact_do_date FOREIGN KEY (do_date_id) REFERENCES dim_date (date_id),
    CONSTRAINT fk_fact_pu_time FOREIGN KEY (pu_time_id) REFERENCES dim_time (time_id),
    CONSTRAINT fk_fact_do_time FOREIGN KEY (do_time_id) REFERENCES dim_time (time_id),
    CONSTRAINT fk_fact_pu_location FOREIGN KEY (pu_location_id) REFERENCES dim_location (location_id),
    CONSTRAINT fk_fact_do_location FOREIGN KEY (do_location_id) REFERENCES dim_location (location_id),
    CONSTRAINT fk_fact_payment FOREIGN KEY (payment_id) REFERENCES dim_payment (payment_id),
    CONSTRAINT fk_fact_rate_code FOREIGN KEY (rate_code_id) REFERENCES dim_rate_code (rate_code_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================================
-- Helpful Performance Indexes for OLAP queries
-- =====================================================================
CREATE INDEX idx_fact_pu_date ON fact_trip_records (pu_date_id);
CREATE INDEX idx_fact_do_date ON fact_trip_records (do_date_id);
CREATE INDEX idx_fact_pu_location ON fact_trip_records (pu_location_id);
CREATE INDEX idx_fact_do_location ON fact_trip_records (do_location_id);
