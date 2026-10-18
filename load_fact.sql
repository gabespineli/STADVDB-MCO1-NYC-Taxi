-- Run after schema.sql, load_star_schema.sql, and seed_dimensions.sql.
-- One atomic full-population load. Refuses a nonempty fact table.
-- Check destination state before retrying an interrupted/uncertain commit.
USE source_db;
CALL LoadTaxiFacts2025();
