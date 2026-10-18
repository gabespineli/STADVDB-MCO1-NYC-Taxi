# Current baseline and optimized EXPLAIN plans

Plain EXPLAIN only. Both versions use the same current indexes and statistics; this does not recreate historical pre-index plans.

Captured: 2026-10-19T04:48:30.466535+08:00

## Q1A

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 100.0 | Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 100.0 | None |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | Using where |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 100.0 | Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 100.0 | None |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | Using where |

## Q1B

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 100.0 | Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 100.0 | None |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| <derived2> | ALL | None | None | None | None | 334360 | 100.0 | Using temporary; Using filesort |
| d | ALL | PRIMARY | None | None | None | 366 | 100.0 | Using temporary |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 100.0 | None |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

## Q1C

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| t | ALL | PRIMARY | None | None | None | 1440 | 10.0 | Using where; Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q1_cover | idx_olap_q1_cover | 4 | source_db.t.time_id | 589 | 100.0 | Using index |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| d | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_date_id | 1 | 100.0 | None |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| <derived2> | ALL | None | None | None | None | 84951 | 100.0 | Using temporary; Using filesort |
| l | eq_ref | PRIMARY | PRIMARY | 4 | g.pu_location_id | 1 | 100.0 | None |
| d | eq_ref | PRIMARY | PRIMARY | 4 | g.pu_date_id | 1 | 100.0 | None |
| t | ALL | PRIMARY | None | None | None | 1440 | 10.0 | Using where; Using temporary |
| f | ref | idx_olap_q3_distance_cover,idx_olap_q1_cover | idx_olap_q1_cover | 4 | source_db.t.time_id | 589 | 100.0 | Using index |

## Q2A

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| p | ALL | PRIMARY | None | None | None | 7 | 100.0 | Using temporary; Using filesort |
| f | ref | fk_fact_payment | fk_fact_payment | 4 | source_db.p.payment_id | 12713 | 33.33 | Using where |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| p | ALL | PRIMARY | None | None | None | 7 | 100.0 | Using temporary; Using filesort |
| <derived2> | ref | <auto_key0> | <auto_key0> | 4 | source_db.p.payment_id | 148729 | 100.0 | None |
| f | ALL | None | None | None | None | 44623375 | 33.33 | Using where; Using temporary |

## Q2B

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| p | ALL | PRIMARY | None | None | None | 7 | 100.0 | Using temporary; Using filesort |
| f | ref | fk_fact_payment,idx_fact_pu_location,idx_olap_q1_cover | fk_fact_payment | 4 | source_db.p.payment_id | 12713 | 33.33 | Using where |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| p | ALL | PRIMARY | None | None | None | 7 | 100.0 | Using temporary; Using filesort |
| <derived2> | ref | <auto_key2> | <auto_key2> | 4 | source_db.p.payment_id | 4247 | 100.0 | None |
| l | eq_ref | PRIMARY | PRIMARY | 4 | g.pu_location_id | 1 | 100.0 | None |
| t | ALL | PRIMARY | None | None | None | 1440 | 100.0 | Using temporary |
| f | ref | idx_olap_q1_cover | idx_olap_q1_cover | 4 | source_db.t.time_id | 589 | 33.33 | Using where |

## Q3A

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 10.0 | Using where; Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q3_distance_cover,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 16.66 | Using where |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| l | ALL | PRIMARY | None | None | None | 266 | 100.0 | Using temporary; Using filesort |
| <derived2> | ref | <auto_key0> | <auto_key0> | 4 | source_db.l.location_id | 20 | 100.0 | None |
| d | ALL | PRIMARY | None | None | None | 366 | 10.0 | Using where; Using temporary |
| f | ref | idx_fact_pu_date,idx_olap_q3_distance_cover,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 16.66 | Using where |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

## Q3B

### baseline

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 10.0 | Using where; Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q3_distance_cover,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 16.66 | Using where |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |

### optimized

| table | type | possible_keys | key | key_len | ref | rows (estimated) | filtered (%) | Extra |
|---|---|---|---|---|---|---|---|---|
| d | ALL | PRIMARY | None | None | None | 366 | 10.0 | Using where; Using temporary; Using filesort |
| f | ref | idx_fact_pu_date,idx_fact_pu_location,idx_olap_q3_distance_cover,idx_olap_q1_cover | idx_fact_pu_date | 4 | source_db.d.date_id | 913 | 16.66 | Using where |
| l | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_location_id | 1 | 100.0 | None |
| t | eq_ref | PRIMARY | PRIMARY | 4 | source_db.f.pu_time_id | 1 | 100.0 | None |
