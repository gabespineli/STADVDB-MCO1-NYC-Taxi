-- Retired: unordered LIMIT/OFFSET batches cannot guarantee source coverage
-- or safe recovery. This filename guards against older runbooks.
-- Use: schema.sql -> load_star_schema.sql -> seed_dimensions.sql -> load_fact.sql.
SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Retired batched loader. Install load_star_schema.sql, seed dimensions, then run load_fact.sql.';
