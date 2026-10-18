-- =====================================================================
-- STADVDB - MCO1: NYC Yellow Taxi ETL Load Script (Non-locking & Batched)
-- Loads raw data from yellow_taxi_trips into Star Schema tables:
--   1. dim_payment
--   2. dim_rate_code
--   3. dim_time
--   4. dim_location
--   5. dim_date
--   6. fact_trip_records
-- =====================================================================

USE source_db;

-- ---------------------------------------------------------------------
-- Session Settings:
-- READ COMMITTED prevents shared read locks on yellow_taxi_trips,
-- which completely eliminates Error 1206 (Lock table size exceeded).
-- ---------------------------------------------------------------------
SET FOREIGN_KEY_CHECKS = 0;
SET UNIQUE_CHECKS = 0;
SET SESSION cte_max_recursion_depth = 2000;
SET SQL_MODE = 'NO_ENGINE_SUBSTITUTION';
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- =====================================================================
-- STEP 1: Populate Dimension Tables (Zero table scans on raw trips)
-- =====================================================================

-- 1.1 dim_payment (Official TLC payment codes)
INSERT INTO dim_payment (payment_id, payment_method) VALUES
(0, 'Unknown'),
(1, 'Credit card'),
(2, 'Cash'),
(3, 'No charge'),
(4, 'Dispute'),
(5, 'Unknown'),
(6, 'Voided trip')
ON DUPLICATE KEY UPDATE payment_method = VALUES(payment_method);

-- 1.2 dim_rate_code (Official TLC rate codes)
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

-- 1.3 dim_time (Recursive generator for all 1,440 minutes of a day)
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

-- 1.4 dim_location (Official NYC TLC Taxi Zone Lookup: all 265 zones)
INSERT INTO dim_location (location_id, zone, borough) VALUES
(0, 'Unknown Zone', 'Unknown Borough')
ON DUPLICATE KEY UPDATE zone = VALUES(zone);

INSERT INTO dim_location (location_id, zone, borough) VALUES
(1, 'Newark Airport', 'EWR'),
(2, 'Jamaica Bay', 'Queens'),
(3, 'Allerton/Pelham Gardens', 'Bronx'),
(4, 'Alphabet City', 'Manhattan'),
(5, 'Arden Heights', 'Staten Island'),
(6, 'Arrochar/Fort Wadsworth', 'Staten Island'),
(7, 'Astoria', 'Queens'),
(8, 'Astoria Park', 'Queens'),
(9, 'Auburndale', 'Queens'),
(10, 'Baisley Park', 'Queens'),
(11, 'Bath Beach', 'Brooklyn'),
(12, 'Battery Park', 'Manhattan'),
(13, 'Battery Park City', 'Manhattan'),
(14, 'Bay Ridge', 'Brooklyn'),
(15, 'Bay Terrace/Fort Totten', 'Queens'),
(16, 'Bayside', 'Queens'),
(17, 'Bedford', 'Brooklyn'),
(18, 'Bedford Park', 'Bronx'),
(19, 'Bellerose', 'Queens'),
(20, 'Belmont', 'Bronx'),
(21, 'Bensonhurst East', 'Brooklyn'),
(22, 'Bensonhurst West', 'Brooklyn'),
(23, 'Bloomfield/Emerson Hill', 'Staten Island'),
(24, 'Bloomingdale', 'Manhattan'),
(25, 'Boerum Hill', 'Brooklyn'),
(26, 'Borough Park', 'Brooklyn'),
(27, 'Breezy Point/Fort Tilden/Riis Beach', 'Queens'),
(28, 'Briarwood/Jamaica Hills', 'Queens'),
(29, 'Brighton Beach', 'Brooklyn'),
(30, 'Broad Channel', 'Queens'),
(31, 'Bronx Park', 'Bronx'),
(32, 'Bronxdale', 'Bronx'),
(33, 'Brooklyn Heights', 'Brooklyn'),
(34, 'Brooklyn Navy Yard', 'Brooklyn'),
(35, 'Brownsville', 'Brooklyn'),
(36, 'Bushwick North', 'Brooklyn'),
(37, 'Bushwick South', 'Brooklyn'),
(38, 'Cambria Heights', 'Queens'),
(39, 'Canarsie', 'Brooklyn'),
(40, 'Carroll Gardens', 'Brooklyn'),
(41, 'Central Harlem', 'Manhattan'),
(42, 'Central Harlem North', 'Manhattan'),
(43, 'Central Park', 'Manhattan'),
(44, 'Charleston/Tottenville', 'Staten Island'),
(45, 'Chinatown', 'Manhattan'),
(46, 'City Island', 'Bronx'),
(47, 'Claremont/Bathgate', 'Bronx'),
(48, 'Clinton East', 'Manhattan'),
(49, 'Clinton Hill', 'Brooklyn'),
(50, 'Clinton West', 'Manhattan'),
(51, 'Co-Op City', 'Bronx'),
(52, 'Cobble Hill', 'Brooklyn'),
(53, 'College Point', 'Queens'),
(54, 'Columbia Street', 'Brooklyn'),
(55, 'Coney Island', 'Brooklyn'),
(56, 'Corona', 'Queens'),
(57, 'Corona', 'Queens'),
(58, 'Country Club', 'Bronx'),
(59, 'Crotona Park', 'Bronx'),
(60, 'Crotona Park East', 'Bronx'),
(61, 'Crown Heights North', 'Brooklyn'),
(62, 'Crown Heights South', 'Brooklyn'),
(63, 'Cypress Hills', 'Brooklyn'),
(64, 'Douglaston', 'Queens'),
(65, 'Downtown Brooklyn/MetroTech', 'Brooklyn'),
(66, 'DUMBO/Vinegar Hill', 'Brooklyn'),
(67, 'Dyker Heights', 'Brooklyn'),
(68, 'East Chelsea', 'Manhattan'),
(69, 'East Concourse/Concourse Village', 'Bronx'),
(70, 'East Elmhurst', 'Queens'),
(71, 'East Flatbush/Farragut', 'Brooklyn'),
(72, 'East Flatbush/Remsen Village', 'Brooklyn'),
(73, 'East Flushing', 'Queens'),
(74, 'East Harlem North', 'Manhattan'),
(75, 'East Harlem South', 'Manhattan'),
(76, 'East New York', 'Brooklyn'),
(77, 'East New York/Pennsylvania Avenue', 'Brooklyn'),
(78, 'East Tremont', 'Bronx'),
(79, 'East Village', 'Manhattan'),
(80, 'East Williamsburg', 'Brooklyn'),
(81, 'Eastchester', 'Bronx'),
(82, 'Elmhurst', 'Queens'),
(83, 'Elmhurst/Maspeth', 'Queens'),
(84, 'Eltingville/Annadale/Prince\'s Bay', 'Staten Island'),
(85, 'Erasmus', 'Brooklyn'),
(86, 'Far Rockaway', 'Queens'),
(87, 'Financial District North', 'Manhattan'),
(88, 'Financial District South', 'Manhattan'),
(89, 'Flatbush/Ditmas Park', 'Brooklyn'),
(90, 'Flatiron', 'Manhattan'),
(91, 'Flatlands', 'Brooklyn'),
(92, 'Flushing', 'Queens'),
(93, 'Flushing Meadows-Corona Park', 'Queens'),
(94, 'Fordham South', 'Bronx'),
(95, 'Forest Hills', 'Queens'),
(96, 'Forest Park/Highland Park', 'Queens'),
(97, 'Fort Greene', 'Brooklyn'),
(98, 'Fresh Meadows', 'Queens'),
(99, 'Freshkills Park', 'Staten Island'),
(100, 'Garment District', 'Manhattan'),
(101, 'Glen Oaks', 'Queens'),
(102, 'Glendale', 'Queens'),
(103, 'Governor\'s Island/Ellis Island/Liberty Island', 'Manhattan'),
(104, 'Governor\'s Island/Ellis Island/Liberty Island', 'Manhattan'),
(105, 'Governor\'s Island/Ellis Island/Liberty Island', 'Manhattan'),
(106, 'Gowanus', 'Brooklyn'),
(107, 'Gramercy', 'Manhattan'),
(108, 'Gravesend', 'Brooklyn'),
(109, 'Great Kills', 'Staten Island'),
(110, 'Great Kills Park', 'Staten Island'),
(111, 'Green-Wood Cemetery', 'Brooklyn'),
(112, 'Greenpoint', 'Brooklyn'),
(113, 'Greenwich Village North', 'Manhattan'),
(114, 'Greenwich Village South', 'Manhattan'),
(115, 'Grymes Hill/Clifton', 'Staten Island'),
(116, 'Hamilton Heights', 'Manhattan'),
(117, 'Hammels/Arverne', 'Queens'),
(118, 'Heartland Village/Todt Hill', 'Staten Island'),
(119, 'Highbridge', 'Bronx'),
(120, 'Highbridge Park', 'Manhattan'),
(121, 'Hillcrest/Pomonok', 'Queens'),
(122, 'Hollis', 'Queens'),
(123, 'Homecrest', 'Brooklyn'),
(124, 'Howard Beach', 'Queens'),
(125, 'Hudson Sq', 'Manhattan'),
(126, 'Hunts Point', 'Bronx'),
(127, 'Inwood', 'Manhattan'),
(128, 'Inwood Hill Park', 'Manhattan'),
(129, 'Jackson Heights', 'Queens'),
(130, 'Jamaica', 'Queens'),
(131, 'Jamaica Estates', 'Queens'),
(132, 'JFK Airport', 'Queens'),
(133, 'Kensington', 'Brooklyn'),
(134, 'Kew Gardens', 'Queens'),
(135, 'Kew Gardens Hills', 'Queens'),
(136, 'Kingsbridge Heights', 'Bronx'),
(137, 'Kips Bay', 'Manhattan'),
(138, 'LaGuardia Airport', 'Queens'),
(139, 'Laurelton', 'Queens'),
(140, 'Lenox Hill East', 'Manhattan'),
(141, 'Lenox Hill West', 'Manhattan'),
(142, 'Lincoln Square East', 'Manhattan'),
(143, 'Lincoln Square West', 'Manhattan'),
(144, 'Little Italy/NoLiTa', 'Manhattan'),
(145, 'Long Island City/Hunters Point', 'Queens'),
(146, 'Long Island City/Queens Plaza', 'Queens'),
(147, 'Longwood', 'Bronx'),
(148, 'Lower East Side', 'Manhattan'),
(149, 'Madison', 'Brooklyn'),
(150, 'Manhattan Beach', 'Brooklyn'),
(151, 'Manhattan Valley', 'Manhattan'),
(152, 'Manhattanville', 'Manhattan'),
(153, 'Marble Hill', 'Manhattan'),
(154, 'Marine Park/Floyd Bennett Field', 'Brooklyn'),
(155, 'Marine Park/Mill Basin', 'Brooklyn'),
(156, 'Mariners Harbor', 'Staten Island'),
(157, 'Maspeth', 'Queens'),
(158, 'Meatpacking/West Village West', 'Manhattan'),
(159, 'Melrose South', 'Bronx'),
(160, 'Middle Village', 'Queens'),
(161, 'Midtown Center', 'Manhattan'),
(162, 'Midtown East', 'Manhattan'),
(163, 'Midtown North', 'Manhattan'),
(164, 'Midtown South', 'Manhattan'),
(165, 'Midwood', 'Brooklyn'),
(166, 'Morningside Heights', 'Manhattan'),
(167, 'Morrisania/Melrose', 'Bronx'),
(168, 'Mott Haven/Port Morris', 'Bronx'),
(169, 'Mount Hope', 'Bronx'),
(170, 'Murray Hill', 'Manhattan'),
(171, 'Murray Hill-Queens', 'Queens'),
(172, 'New Dorp/Midland Beach', 'Staten Island'),
(173, 'North Corona', 'Queens'),
(174, 'Norwood', 'Bronx'),
(175, 'Oakland Gardens', 'Queens'),
(176, 'Oakwood', 'Staten Island'),
(177, 'Ocean Hill', 'Brooklyn'),
(178, 'Ocean Parkway South', 'Brooklyn'),
(179, 'Old Astoria', 'Queens'),
(180, 'Ozone Park', 'Queens'),
(181, 'Park Slope', 'Brooklyn'),
(182, 'Parkchester', 'Bronx'),
(183, 'Pelham Bay', 'Bronx'),
(184, 'Pelham Bay Park', 'Bronx'),
(185, 'Pelham Parkway', 'Bronx'),
(186, 'Penn Station/Madison Sq West', 'Manhattan'),
(187, 'Port Richmond', 'Staten Island'),
(188, 'Prospect-Lefferts Gardens', 'Brooklyn'),
(189, 'Prospect Heights', 'Brooklyn'),
(190, 'Prospect Park', 'Brooklyn'),
(191, 'Queens Village', 'Queens'),
(192, 'Queensboro Hill', 'Queens'),
(193, 'Queensbridge/Ravenswood', 'Queens'),
(194, 'Randalls Island', 'Manhattan'),
(195, 'Red Hook', 'Brooklyn'),
(196, 'Rego Park', 'Queens'),
(197, 'Richmond Hill', 'Queens'),
(198, 'Ridgewood', 'Queens'),
(199, 'Rikers Island', 'Bronx'),
(200, 'Riverdale/North Riverdale/Fieldston', 'Bronx'),
(201, 'Rockaway Park', 'Queens'),
(202, 'Roosevelt Island', 'Manhattan'),
(203, 'Rosedale', 'Queens'),
(204, 'Rossville/Woodrow', 'Staten Island'),
(205, 'Saint Albans', 'Queens'),
(206, 'Saint George/New Brighton', 'Staten Island'),
(207, 'Saint Michaels Cemetery/Woodside', 'Queens'),
(208, 'Schuylerville/Edgewater Park', 'Bronx'),
(209, 'Seaport', 'Manhattan'),
(210, 'Sheepshead Bay', 'Brooklyn'),
(211, 'SoHo', 'Manhattan'),
(212, 'Soundview/Bruckner', 'Bronx'),
(213, 'Soundview/Castle Hill', 'Bronx'),
(214, 'South Beach/Dongan Hills', 'Staten Island'),
(215, 'South Jamaica', 'Queens'),
(216, 'South Ozone Park', 'Queens'),
(217, 'South Williamsburg', 'Brooklyn'),
(218, 'Springfield Gardens North', 'Queens'),
(219, 'Springfield Gardens South', 'Queens'),
(220, 'Spuyten Duyvil/Kingsbridge', 'Bronx'),
(221, 'Stapleton', 'Staten Island'),
(222, 'Starrett City', 'Brooklyn'),
(223, 'Steinway', 'Queens'),
(224, 'Stuy Town/Peter Cooper Village', 'Manhattan'),
(225, 'Stuyvesant Heights', 'Brooklyn'),
(226, 'Sunnyside', 'Queens'),
(227, 'Sunset Park East', 'Brooklyn'),
(228, 'Sunset Park West', 'Brooklyn'),
(229, 'Sutton Place/Turtle Bay North', 'Manhattan'),
(230, 'Times Sq/Theatre District', 'Manhattan'),
(231, 'TriBeCa/Civic Center', 'Manhattan'),
(232, 'Two Bridges/Seward Park', 'Manhattan'),
(233, 'UN/Turtle Bay South', 'Manhattan'),
(234, 'Union Sq', 'Manhattan'),
(235, 'University Heights/Morris Heights', 'Bronx'),
(236, 'Upper East Side North', 'Manhattan'),
(237, 'Upper East Side South', 'Manhattan'),
(238, 'Upper West Side North', 'Manhattan'),
(239, 'Upper West Side South', 'Manhattan'),
(240, 'Van Cortlandt Park', 'Bronx'),
(241, 'Van Cortlandt Village', 'Bronx'),
(242, 'Van Nest/Morris Park', 'Bronx'),
(243, 'Washington Heights North', 'Manhattan'),
(244, 'Washington Heights South', 'Manhattan'),
(245, 'West Brighton', 'Staten Island'),
(246, 'West Chelsea/Hudson Yards', 'Manhattan'),
(247, 'West Concourse', 'Bronx'),
(248, 'West Farms/Bronx River', 'Bronx'),
(249, 'West Village', 'Manhattan'),
(250, 'Westchester Village/Unionport', 'Bronx'),
(251, 'Westerleigh', 'Staten Island'),
(252, 'Whitestone', 'Queens'),
(253, 'Willets Point', 'Queens'),
(254, 'Williamsbridge/Olinville', 'Bronx'),
(255, 'Williamsburg (North Side)', 'Brooklyn'),
(256, 'Williamsburg (South Side)', 'Brooklyn'),
(257, 'Windsor Terrace', 'Brooklyn'),
(258, 'Woodhaven', 'Queens'),
(259, 'Woodlawn/Wakefield', 'Bronx'),
(260, 'Woodside', 'Queens'),
(261, 'World Trade Center', 'Manhattan'),
(262, 'Yorkville East', 'Manhattan'),
(263, 'Yorkville West', 'Manhattan'),
(264, 'nan', 'Unknown'),
(265, 'Outside of NYC', 'nan')
ON DUPLICATE KEY UPDATE zone = VALUES(zone), borough = VALUES(borough);

-- 1.5 dim_date (Recursive generator for all dates: 2024 to 2026)
INSERT IGNORE INTO dim_date (date_id, `date`, is_weekend, day_of_week, `month`, `quarter`, `year`)
WITH RECURSIVE calendar AS (
    SELECT CAST('2024-01-01' AS DATE) AS dt
    UNION ALL
    SELECT DATE_ADD(dt, INTERVAL 1 DAY)
    FROM calendar
    WHERE dt < '2026-12-31'
)
SELECT 
    CAST(DATE_FORMAT(dt, '%Y%m%d') AS SIGNED) AS date_id,
    dt AS `date`,
    IF(DAYOFWEEK(dt) IN (1, 7), 1, 0) AS is_weekend,
    DAYNAME(dt) AS day_of_week,
    MONTH(dt) AS `month`,
    QUARTER(dt) AS `quarter`,
    YEAR(dt) AS `year`
FROM calendar;

-- =====================================================================
-- STEP 2: Populate fact_trip_records in Safe Batches
-- =====================================================================

DROP PROCEDURE IF EXISTS LoadFactTripsBatched;

DELIMITER $$

CREATE PROCEDURE LoadFactTripsBatched(IN batch_size INT)
BEGIN
    DECLARE total_rows BIGINT DEFAULT 0;
    DECLARE offset_val BIGINT DEFAULT 0;
    
    SET FOREIGN_KEY_CHECKS = 0;
    SET UNIQUE_CHECKS = 0;
    SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
    
    SELECT COUNT(*) INTO total_rows 
    FROM yellow_taxi_trips
    WHERE tpep_pickup_datetime IS NOT NULL 
      AND tpep_dropoff_datetime IS NOT NULL;
    
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
            -- Date IDs (format: YYYYMMDD)
            CAST(DATE_FORMAT(tpep_pickup_datetime, '%Y%m%d') AS SIGNED) AS pu_date_id,
            CAST(DATE_FORMAT(tpep_dropoff_datetime, '%Y%m%d') AS SIGNED) AS do_date_id,
            
            -- Time IDs (format: minute of day, 0 to 1439)
            (HOUR(tpep_pickup_datetime) * 60 + MINUTE(tpep_pickup_datetime)) AS pu_time_id,
            (HOUR(tpep_dropoff_datetime) * 60 + MINUTE(tpep_dropoff_datetime)) AS do_time_id,
            
            -- Locations (0 fallback for unknown)
            COALESCE(PULocationID, 0) AS pu_location_id,
            COALESCE(DOLocationID, 0) AS do_location_id,
            
            -- Payment & Rate Code (0 fallback for unknown)
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
          AND tpep_dropoff_datetime IS NOT NULL
        LIMIT batch_size OFFSET offset_val;

        COMMIT;
        SET offset_val = offset_val + batch_size;
    END WHILE;
    
    SET FOREIGN_KEY_CHECKS = 1;
    SET UNIQUE_CHECKS = 1;
END$$

DELIMITER ;

-- Execute in safe batches of 25,000 rows (fits comfortably in default InnoDB lock table)
CALL LoadFactTripsBatched(25000);

-- Clean up temporary procedure
DROP PROCEDURE IF EXISTS LoadFactTripsBatched;
