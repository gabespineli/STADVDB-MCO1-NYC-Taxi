"""Deterministic synthetic aggregates for UI development, never NYC findings.

Each report is an independent layout fixture, not a reconciled warehouse snapshot.
No time boundaries or population policies are established by these examples.
"""

import pandas as pd

BOROUGHS = ["Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island"]
DISTANCES = ["1. Short (< 2 mi)", "2. Medium (2 - 4.99 mi)", "3. Long (5 - 9.99 mi)", "4. Very Long (10+ mi)"]


def sample_result(report_id):
    rows = []
    for index, borough in enumerate(BOROUGHS):
        weight = 5 - index
        if report_id == "q1_demand":
            for zone in range(1, 3):
                weekday, weekend, late = weight * zone * 120, weight * zone * 190, weight * zone * 70
                rows.append(dict(borough=borough, zone=f"Sample {borough} zone {zone}",
                                 weekday_late_night_pickups=weekday, weekend_late_night_pickups=late,
                                 all_weekend_pickups=weekend, total_filtered_pickups=weekday + weekend))
        elif report_id == "q1_hourly":
            for hour in range(24):
                weekday = weight * (60 + (hour * 17 + 13) % 100)
                weekend = weight * (50 + (hour * 11 + 31) % 90)
                rows.append(dict(borough=borough, time_period="Sample period", hour=hour,
                                 weekday_pickups=weekday, weekend_pickups=weekend,
                                 avg_weekday_hourly_pickups=round(weekday / 20, 2),
                                 avg_weekend_hourly_pickups=round(weekend / 8, 2)))
        elif report_id == "q1_monthly":
            for month in range(1, 13):
                rows.append(dict(zone=f"Sample {borough} zone 1", yr="2025", qtr=str((month - 1) // 3 + 1),
                                 mo=str(month), late_night_pickups=weight * (200 + (month * 31) % 160)))
        elif report_id == "q2_payment":
            for period in ["Sample period A", "Sample period B"]:
                for payment, multiplier in [("Credit card", 8), ("Cash", 2), ("Other", 1)]:
                    rows.append(dict(borough=borough, time_period=period, payment_method=payment,
                                     trip_count=weight * multiplier * 110, avg_fare=19.5 + index,
                                     avg_tip=2.4 if payment == "Credit card" else 0.0, avg_total=25.8 + index))
        elif report_id == "q3_comparison":
            for distance, bucket in enumerate(DISTANCES, 1):
                rows.append(dict(borough=borough, distance_bucket=bucket,
                                 rush_hour_duration_min=round(5 + distance * 7 + index * 0.5, 2),
                                 off_peak_duration_min=round(4 + distance * 5 + index * 0.4, 2),
                                 rush_hour_speed_mph=round(9 + distance * 1.5 + index, 2),
                                 off_peak_speed_mph=round(13 + distance * 1.8 + index, 2)))
        elif report_id == "q3_location":
            for hour in [8, 12, 18, 22]:
                rows.append(dict(borough=borough, zone=f"Sample {borough} zone 1",
                                 time_period="Sample period", hour=hour, trip_count=weight * (hour + 10),
                                 avg_distance_miles=2.4 + index * 0.4,
                                 avg_duration_minutes=12 + index * 2 + hour / 4,
                                 avg_speed_mph=9 + index + hour / 10))
    if report_id == "q2_fare":
        for index, tier in enumerate(["1. Under $10", "2. $10 - $24.99", "3. $25 - $49.99", "4. $50 and Above"], 1):
            card, cash, other = 900 * index, 230 * index, 60 * index
            rows.append(dict(fare_range=tier, credit_card_trips=card, cash_trips=cash,
                             other_payment_trips=other, total_trips=card + cash + other, avg_tip_amount=1.2 * index))
    return pd.DataFrame(rows)
