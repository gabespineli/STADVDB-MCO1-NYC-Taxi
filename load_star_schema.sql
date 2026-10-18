-- STADVDB MCO1: install the authoritative 2025 ETL implementation.
-- INSTALLATION ONLY: creates a view and two procedures; loads no trip rows.
-- Use a fresh connection, without an open transaction, with autocommit and FK/unique checks ON.
-- Order: schema.sql -> this file -> seed_dimensions.sql -> inspect -> load_fact.sql.
USE source_db;

-- Stored procedures retain creation-time SQL mode. Keep other modes and restore
-- the installer's mode below. Do not disable binary logging or redo logging.
SET @nyc_etl_previous_sql_mode = @@SESSION.sql_mode;
SET SESSION sql_mode = IF(
    FIND_IN_SET('STRICT_TRANS_TABLES', @@SESSION.sql_mode)
    OR FIND_IN_SET('STRICT_ALL_TABLES', @@SESSION.sql_mode),
    @@SESSION.sql_mode,
    CONCAT_WS(',', NULLIF(@@SESSION.sql_mode, ''), 'STRICT_TRANS_TABLES')
);

-- ETL input, not a dashboard reporting table. One row per accepted source row.
-- Local NYC wall-clock timestamps remain as supplied; no timezone conversion.
-- Pickups in 2025; later drop-off within 24 hours; duration 1..86,400 whole seconds.
-- Original NULL amounts remain NULL. Negative amounts (refunds) remain signed.
-- CAST follows the diagram's two-decimal precision. The loader rolls back on
-- errors OR conversion diagnostics, rather than accepting clipped source values.
CREATE OR REPLACE SQL SECURITY INVOKER VIEW etl_trip_source_2025 AS
SELECT
    YEAR(src.tpep_pickup_datetime) * 10000 + MONTH(src.tpep_pickup_datetime) * 100
        + DAY(src.tpep_pickup_datetime) AS pu_date_id,
    YEAR(src.tpep_dropoff_datetime) * 10000 + MONTH(src.tpep_dropoff_datetime) * 100
        + DAY(src.tpep_dropoff_datetime) AS do_date_id,
    HOUR(src.tpep_pickup_datetime) * 60 + MINUTE(src.tpep_pickup_datetime) AS pu_time_id,
    HOUR(src.tpep_dropoff_datetime) * 60 + MINUTE(src.tpep_dropoff_datetime) AS do_time_id,
    CASE WHEN src.PULocationID BETWEEN 1 AND 265 THEN src.PULocationID ELSE 0 END AS pu_location_id,
    CASE WHEN src.DOLocationID BETWEEN 1 AND 265 THEN src.DOLocationID ELSE 0 END AS do_location_id,
    CASE WHEN src.payment_type IN (0, 1, 2, 3, 4, 5, 6) THEN src.payment_type ELSE 5 END AS payment_id,
    CASE WHEN src.RatecodeID IN (1, 2, 3, 4, 5, 6, 99) THEN src.RatecodeID ELSE 99 END AS rate_code_id,
    CAST(CASE WHEN src.trip_distance >= 0 THEN src.trip_distance END AS DECIMAL(8,2)) AS trip_distance,
    CAST(src.fare_amount AS DECIMAL(10,2)) AS fare_amount,
    CAST(src.extra AS DECIMAL(10,2)) AS extra,
    CAST(src.mta_tax AS DECIMAL(10,2)) AS mta_tax,
    CAST(src.tip_amount AS DECIMAL(10,2)) AS tip_amount,
    CAST(src.tolls_amount AS DECIMAL(10,2)) AS tolls_amount,
    CAST(src.improvement_surcharge AS DECIMAL(10,2)) AS improvement_surcharge,
    CAST(src.total_amount AS DECIMAL(10,2)) AS total_amount,
    CAST(src.Airport_fee AS DECIMAL(10,2)) AS airport_fee,
    CAST(src.cbd_congestion_fee AS DECIMAL(10,2)) AS cbd_congestion_fee,
    src.duration_sec AS trip_duration_seconds,
    -- Missing/negative distance or a speed that cannot fit DECIMAL(6,2) -> NULL.
    -- Representable speeds above 100 mph are retained but flagged by the checker.
    CAST(CASE
        WHEN src.trip_distance >= 0
         AND ROUND(src.trip_distance * 3600.0 / NULLIF(src.duration_sec, 0), 2) <= 9999.99
        THEN ROUND(src.trip_distance * 3600.0 / NULLIF(src.duration_sec, 0), 2)
    END AS DECIMAL(6,2)) AS estimated_speed_mph
FROM (
    SELECT tpep_pickup_datetime, tpep_dropoff_datetime, PULocationID, DOLocationID,
        payment_type, RatecodeID, trip_distance, fare_amount, extra, mta_tax,
        tip_amount, tolls_amount, improvement_surcharge, total_amount,
        Airport_fee, cbd_congestion_fee,
        TIMESTAMPDIFF(SECOND, tpep_pickup_datetime, tpep_dropoff_datetime) AS duration_sec
    FROM yellow_taxi_trips
    WHERE tpep_pickup_datetime IS NOT NULL
      AND tpep_dropoff_datetime IS NOT NULL
      AND tpep_pickup_datetime >= '2025-01-01'
      AND tpep_pickup_datetime < '2026-01-01'
      AND tpep_dropoff_datetime > tpep_pickup_datetime
      AND tpep_dropoff_datetime <= DATE_ADD(tpep_pickup_datetime, INTERVAL 24 HOUR)
) AS src
WHERE src.duration_sec BETWEEN 1 AND 86400;

DROP PROCEDURE IF EXISTS SeedTaxiDimensions2025;
DROP PROCEDURE IF EXISTS LoadTaxiFacts2025;
DELIMITER $$

CREATE PROCEDURE SeedTaxiDimensions2025()
SQL SECURITY INVOKER
BEGIN
    DECLARE v_lock INT DEFAULT 0;
    DECLARE v_started BOOLEAN DEFAULT FALSE;
    DECLARE v_old_depth BIGINT DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        IF v_started THEN ROLLBACK; END IF;
        IF v_old_depth IS NOT NULL THEN SET SESSION cte_max_recursion_depth = v_old_depth; END IF;
        IF v_lock = 1 THEN DO RELEASE_LOCK('source_db.nyc_yellow_2025_etl'); END IF;
        RESIGNAL;
    END;

    IF @@SESSION.autocommit <> 1 OR @@SESSION.foreign_key_checks <> 1 OR @@SESSION.unique_checks <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Use a fresh connection with autocommit, foreign_key_checks and unique_checks ON.';
    END IF;
    SELECT GET_LOCK('source_db.nyc_yellow_2025_etl', 0) INTO v_lock;
    IF COALESCE(v_lock, 0) <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Another warehouse seed/load is running.';
    END IF;
    IF EXISTS (SELECT 1 FROM fact_trip_records LIMIT 1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Refusing to reseed dimensions while facts exist. Review the existing warehouse first.';
    END IF;

    SET v_old_depth = @@SESSION.cte_max_recursion_depth;
    SET SESSION cte_max_recursion_depth = GREATEST(v_old_depth, 2000);
    SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
    START TRANSACTION;
    SET v_started = TRUE;

    INSERT INTO dim_payment (payment_id, payment_method) VALUES
    (0, 'Flex Fare'), (1, 'Credit Card'), (2, 'Cash'), (3, 'No Charge'),
    (4, 'Dispute'), (5, 'Unknown'), (6, 'Voided Trip')
    AS incoming ON DUPLICATE KEY UPDATE payment_method = incoming.payment_method;

    INSERT INTO dim_rate_code (rate_code_id, rate_description) VALUES
    (1, 'Standard rate'), (2, 'JFK'), (3, 'Newark'), (4, 'Nassau or Westchester'),
    (5, 'Negotiated fare'), (6, 'Group ride'), (99, 'Null/unknown')
    AS incoming ON DUPLICATE KEY UPDATE rate_description = incoming.rate_description;

    -- Time-only categories. Weekday/weekend is supplied by dim_date.
    -- These are analysis windows, not holiday-aware fare-surcharge rules.
    -- Update from the primary key; MySQL 8 cannot resolve the SELECT alias here.
    INSERT INTO dim_time (time_id, `minute`, `hour`, time_period)
    WITH RECURSIVE minutes AS (
        SELECT 0 AS m UNION ALL SELECT m + 1 FROM minutes WHERE m < 1439
    )
    SELECT m, MOD(m, 60), FLOOR(m / 60),
        CASE
            WHEN m < 360 OR m >= 1200 THEN 'Late Night'
            WHEN m < 600 THEN 'Morning Rush'
            WHEN m < 960 THEN 'Midday'
            ELSE 'Evening Rush'
        END AS seeded_period
    FROM minutes
    ON DUPLICATE KEY UPDATE time_period = CASE
            WHEN time_id < 360 OR time_id >= 1200 THEN 'Late Night'
            WHEN time_id < 600 THEN 'Morning Rush'
            WHEN time_id < 960 THEN 'Midday'
            ELSE 'Evening Rush'
        END,
        `minute` = MOD(time_id, 60), `hour` = FLOOR(time_id / 60);

    -- Pinned official lookup: reference_data/taxi_zone_lookup.csv
    -- https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
    INSERT INTO dim_location (location_id, zone, borough) VALUES
(0, 'Unknown Zone', 'Unknown Borough'),
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
(84, 'Eltingville/Annadale/Prince''s Bay', 'Staten Island'),
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
(103, 'Governor''s Island/Ellis Island/Liberty Island', 'Manhattan'),
(104, 'Governor''s Island/Ellis Island/Liberty Island', 'Manhattan'),
(105, 'Governor''s Island/Ellis Island/Liberty Island', 'Manhattan'),
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
(264, 'N/A', 'Unknown'),
(265, 'Outside of NYC', 'N/A')
    AS incoming ON DUPLICATE KEY UPDATE zone = incoming.zone, borough = incoming.borough;

    INSERT INTO dim_date (date_id, `date`, is_weekend, day_of_week, `month`, `quarter`, `year`)
    WITH RECURSIVE calendar AS (
        SELECT CAST('2025-01-01' AS DATE) AS dt
        UNION ALL SELECT DATE_ADD(dt, INTERVAL 1 DAY) FROM calendar WHERE dt < '2026-01-01'
    )
    SELECT YEAR(dt) * 10000 + MONTH(dt) * 100 + DAY(dt), dt AS seeded_date,
        DAYOFWEEK(dt) IN (1, 7), DAYNAME(dt), MONTH(dt), QUARTER(dt), YEAR(dt)
    FROM calendar
    ON DUPLICATE KEY UPDATE `date` = STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d'),
        is_weekend = DAYOFWEEK(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')) IN (1, 7),
        day_of_week = DAYNAME(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')),
        `month` = MONTH(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')),
        `quarter` = QUARTER(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d')),
        `year` = YEAR(STR_TO_DATE(CAST(date_id AS CHAR), '%Y%m%d'));

    COMMIT;
    SET v_started = FALSE;
    SET SESSION cte_max_recursion_depth = v_old_depth;
    DO RELEASE_LOCK('source_db.nyc_yellow_2025_etl');
    SET v_lock = 0;
    SELECT (SELECT COUNT(*) FROM dim_time) AS time_rows,
        (SELECT COUNT(*) FROM dim_date) AS date_rows,
        (SELECT COUNT(*) FROM dim_location) AS location_rows,
        (SELECT COUNT(*) FROM dim_payment) AS payment_rows,
        (SELECT COUNT(*) FROM dim_rate_code) AS rate_code_rows;
END$$

CREATE PROCEDURE LoadTaxiFacts2025()
SQL SECURITY INVOKER
BEGIN
    DECLARE v_lock INT DEFAULT 0;
    DECLARE v_started BOOLEAN DEFAULT FALSE;
    DECLARE v_rows BIGINT DEFAULT 0;
    DECLARE v_conditions INT DEFAULT 0;
    DECLARE v_warning VARCHAR(512);
    DECLARE v_error VARCHAR(128);
    DECLARE v_begin DATETIME(6);
    DECLARE v_seconds DECIMAL(20,6);
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        IF v_started THEN ROLLBACK; END IF;
        IF v_lock = 1 THEN DO RELEASE_LOCK('source_db.nyc_yellow_2025_etl'); END IF;
        RESIGNAL;
    END;

    IF @@SESSION.autocommit <> 1 OR @@SESSION.foreign_key_checks <> 1 OR @@SESSION.unique_checks <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Use a fresh connection with autocommit, foreign_key_checks and unique_checks ON.';
    END IF;
    SELECT GET_LOCK('source_db.nyc_yellow_2025_etl', 0) INTO v_lock;
    IF COALESCE(v_lock, 0) <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Another warehouse seed/load is running.';
    END IF;
    IF EXISTS (SELECT 1 FROM fact_trip_records LIMIT 1) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Fact table is not empty. Refusing to append or duplicate a previous load.';
    END IF;

    -- Cheap dimension checks; FK checks stay ON for every inserted fact.
    IF (SELECT COUNT(*) FROM dim_time WHERE time_id BETWEEN 0 AND 1439
        AND time_id = `hour` * 60 + `minute`
        AND time_period = CASE WHEN time_id < 360 OR time_id >= 1200 THEN 'Late Night'
            WHEN time_id < 600 THEN 'Morning Rush' WHEN time_id < 960 THEN 'Midday'
            ELSE 'Evening Rush' END) <> 1440
       OR (SELECT COUNT(*) FROM dim_date WHERE `date` BETWEEN '2025-01-01' AND '2026-01-01'
            AND date_id = YEAR(`date`) * 10000 + MONTH(`date`) * 100 + DAY(`date`)
            AND is_weekend = (DAYOFWEEK(`date`) IN (1, 7))
            AND `month` = MONTH(`date`) AND `quarter` = QUARTER(`date`) AND `year` = YEAR(`date`)) <> 366
       OR (SELECT COUNT(*) FROM dim_location WHERE location_id BETWEEN 0 AND 265
            AND zone IS NOT NULL AND borough IS NOT NULL AND zone NOT LIKE 'Zone %'
            AND zone <> 'nan' AND borough <> 'nan') <> 266
       OR (SELECT COUNT(*) FROM dim_payment WHERE
            (payment_id = 0 AND payment_method = 'Flex Fare')
            OR (payment_id = 1 AND payment_method = 'Credit Card')
            OR (payment_id = 2 AND payment_method = 'Cash')
            OR (payment_id = 3 AND payment_method = 'No Charge')
            OR (payment_id = 4 AND payment_method = 'Dispute')
            OR (payment_id = 5 AND payment_method = 'Unknown')
            OR (payment_id = 6 AND payment_method = 'Voided Trip')) <> 7
       OR (SELECT COUNT(*) FROM dim_rate_code WHERE
            (rate_code_id = 1 AND rate_description = 'Standard rate')
            OR (rate_code_id = 2 AND rate_description = 'JFK')
            OR (rate_code_id = 3 AND rate_description = 'Newark')
            OR (rate_code_id = 4 AND rate_description = 'Nassau or Westchester')
            OR (rate_code_id = 5 AND rate_description = 'Negotiated fare')
            OR (rate_code_id = 6 AND rate_description = 'Group ride')
            OR (rate_code_id = 99 AND rate_description = 'Null/unknown')) <> 7 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dimensions are incomplete or inconsistent. Run seed_dimensions.sql and validate first.';
    END IF;

    SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
    START TRANSACTION;
    SET v_started = TRUE;
    SET v_begin = SYSDATE(6);
    INSERT INTO fact_trip_records (
        pu_date_id, do_date_id, pu_time_id, do_time_id, pu_location_id, do_location_id,
        payment_id, rate_code_id, trip_distance, fare_amount, extra, mta_tax, tip_amount,
        tolls_amount, improvement_surcharge, total_amount, airport_fee, cbd_congestion_fee,
        trip_duration_seconds, estimated_speed_mph
    )
    SELECT
        pu_date_id, do_date_id, pu_time_id, do_time_id, pu_location_id, do_location_id,
        payment_id, rate_code_id, trip_distance, fare_amount, extra, mta_tax, tip_amount,
        tolls_amount, improvement_surcharge, total_amount, airport_fee, cbd_congestion_fee,
        trip_duration_seconds, estimated_speed_mph
    FROM etl_trip_source_2025;
    GET DIAGNOSTICS v_rows = ROW_COUNT, v_conditions = NUMBER;
    IF v_conditions > 0 THEN
        GET DIAGNOSTICS CONDITION 1 v_warning = MESSAGE_TEXT;
        SET v_error = LEFT(CONCAT('ETL conversion warning; rolled back: ', v_warning), 128);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_error;
    END IF;
    IF v_rows = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No eligible 2025 trips were found. Nothing was loaded.';
    END IF;
    COMMIT;
    SET v_started = FALSE;
    SET v_seconds = TIMESTAMPDIFF(MICROSECOND, v_begin, SYSDATE(6)) / 1000000.0;
    DO RELEASE_LOCK('source_db.nyc_yellow_2025_etl');
    SET v_lock = 0;
    SELECT v_rows AS imported_rows, v_seconds AS elapsed_seconds,
        ROUND(v_rows / NULLIF(v_seconds, 0), 1) AS rows_per_second;
END$$
DELIMITER ;

SET SESSION sql_mode = @nyc_etl_previous_sql_mode;
SET @nyc_etl_previous_sql_mode = NULL;
-- No procedure is called automatically. Next: seed_dimensions.sql.
