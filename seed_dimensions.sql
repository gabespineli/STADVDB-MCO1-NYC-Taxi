-- Run after schema.sql and load_star_schema.sql (routine installation).
-- Populates dimensions only; safe to repeat while fact_trip_records is empty.
-- Inspect the returned dimension counts before running load_fact.sql.
USE source_db;
CALL SeedTaxiDimensions2025();
