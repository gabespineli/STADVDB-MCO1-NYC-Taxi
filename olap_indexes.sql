-- Optional physical optimization for Q1a and Q3b in olap_queries_optimized.sql
-- Select your warehouse database before running this file.
-- MANUAL SETUP ONLY - each index is built once, not before each report.
-- Inspect SHOW INDEX FROM fact_trip_records first. Skip an equivalent index.
-- Building these indexes on ~48 million rows can take time and substantial disk.
-- These statements add indexes only. They do not delete rows or alter columns.

CREATE INDEX idx_olap_q1_cover
    ON fact_trip_records (pu_time_id, pu_date_id, pu_location_id);

CREATE INDEX idx_olap_q3_distance_cover
    ON fact_trip_records (
        trip_distance, pu_date_id, pu_location_id, pu_time_id,
        trip_duration_seconds, estimated_speed_mph
    );
