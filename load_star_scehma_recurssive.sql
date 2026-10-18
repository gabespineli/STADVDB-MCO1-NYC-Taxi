-- Retired alternative entry point; do not run the older Downloads copy either.
-- Recursive dimension generation and the single-pass fact transformation now
-- live in load_star_schema.sql. This guard prevents conflicting seed policies.
-- Use: schema.sql -> load_star_schema.sql -> seed_dimensions.sql -> load_fact.sql.
SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Retired alternate loader. Use load_star_schema.sql, seed_dimensions.sql, and load_fact.sql.';
