"""Display arithmetic and interactions, independent of expensive warehouse queries."""

import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard import db
from dashboard.analytics import monthly_totals, payment_composition, rush_differences, safe_heatmap
from dashboard.config import ROOT
from dashboard.geography import load_geography, match_groups, validate_boundaries
from dashboard.presentation import metrics, insight
from dashboard.sample_data import sample_result


class DisplayCalculationTests(unittest.TestCase):
    def test_short_findings_follow_the_selected_population(self):
        data = pd.DataFrame({"borough": ["Queens", "Queens"], "zone": ["A", "B"], "total_filtered_pickups": [90, 10]})
        self.assertEqual(insight("q1_demand", data), "A accounts for 90.0% of selected pickups.")
        self.assertEqual(insight("q1_demand", data.iloc[[1]]), "B accounts for 100.0% of selected pickups.")
        data["total_filtered_pickups"] = 0
        self.assertEqual(insight("q1_demand", data), "")

    def test_payment_shares_are_group_specific_with_missing_and_zero_denominators(self):
        data = pd.DataFrame({"tier": ["a", "a", "b", "b", "c", "c"], "Trips": [90, 10, 0, 0, 20, None]})
        result = payment_composition(data, ["tier"])
        self.assertEqual(result.loc[:1, "Share (%)"].tolist(), [90, 10])
        self.assertTrue(result.loc[2:, "Share (%)"].isna().all())
        self.assertNotIn("Share (%)", data)

    def test_rush_differences_preserve_negative_changes_and_invalid_baselines(self):
        data = pd.DataFrame({"rush_hour_duration_min": [30, 8, 4, None], "off_peak_duration_min": [20, 10, 0, 10]})
        result = rush_differences(data)
        self.assertEqual(result["Extra minutes"].iloc[:3].tolist(), [10, -2, 4])
        self.assertEqual(result["Duration difference (%)"].iloc[:2].tolist(), [50, -20])
        self.assertTrue(result["Duration difference (%)"].iloc[2:].isna().all())

    def test_monthly_missing_months_are_gaps_and_rollups_are_not_added(self):
        data = pd.DataFrame({"zone": ["A", "A", "ALL ZONES"], "yr": ["2025"] * 3,
                             "qtr": ["1"] * 3, "mo": ["1", "3", "1"], "late_night_pickups": [10, 30, 999]})
        result = monthly_totals(data)
        self.assertEqual(len(result), 3)
        self.assertTrue(pd.isna(result.late_night_pickups.iloc[1]))
        self.assertEqual(result.late_night_pickups.sum(), 40)

    def test_heatmap_does_not_pool_averages_or_fill_missing_hours(self):
        data = pd.DataFrame({"zone": ["a", "a"], "hour": [8, 10], "mean": [10, 30]})
        matrix = safe_heatmap(data, "zone", "hour", "mean", [8, 9, 10])
        self.assertEqual(matrix.loc["a", 8], 10)
        self.assertTrue(pd.isna(matrix.loc["a", 9]))
        with self.assertRaisesRegex(ValueError, "Multiple result groups"):
            safe_heatmap(pd.concat([data, data.iloc[[0]]]), "zone", "hour", "mean")

    def test_cards_sum_counts_and_exclude_rollups_without_mean_of_means(self):
        data = sample_result("q2_fare")
        rollup = data.iloc[[0]].copy()
        rollup["fare_range"] = "ALL FARE TIERS"
        card = dict(metrics("q2_fare", pd.concat([data, rollup])))
        self.assertEqual(card["Selected positive-fare trips"], f"{data.total_trips.sum():,}")
        self.assertEqual(card["Credit-card share"], f"{100 * data.credit_card_trips.sum() / data.total_trips.sum():.1f}%")


class GeographyTests(unittest.TestCase):
    def test_official_polygons_validate_and_merge_split_ids(self):
        geojson, lookup = load_geography.__wrapped__()
        ids = [feature["id"] for feature in geojson["features"]]
        self.assertEqual(len(ids), 260)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("1", ids)
        bad = {"type": "FeatureCollection", "features": [{"properties": {"locationid": "99999"}, "geometry": {}}]}
        with self.assertRaises(ValueError):
            validate_boundaries(bad, lookup)

    def test_map_join_preserves_ambiguous_unknown_and_missing_boundary_groups(self):
        lookup = pd.DataFrame({"LocationID": ["1", "2", "3", "4"], "Borough": ["A"] * 4, "Zone": ["Unique", "Ambiguous", "Ambiguous", "No shape"]})
        data = pd.DataFrame({"borough": ["A"] * 4, "zone": ["Unique", "Ambiguous", "No shape", "Unknown"], "total_filtered_pickups": [100, 20, 5, 1]})
        joined = match_groups(data, lookup, {"features": [{"id": "1"}]})
        self.assertEqual(len(joined), len(data))
        self.assertEqual(joined.total_filtered_pickups.sum(), 126)
        self.assertEqual(joined["Map status"].tolist(), ["Mapped", "Ambiguous taxi-zone label", "No polygon for this ID", "No lookup match"])


class DashboardViewTests(unittest.TestCase):
    def setUp(self):
        from dashboard_fixtures import saved_fixtures
        self.fixture = saved_fixtures()
        self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)

    def test_overview_and_all_options_render_without_queries(self):
        from dashboard_fixtures import start_app, select_report
        with patch.object(db, "run_report") as query:
            app = start_app()
            self.assertEqual(len(app.get("plotly_chart")), 3)
            cases = [
                ("Q1", "q1_hourly", "Hourly comparison", ["Average per represented day", "Total pickups"]),
                ("Q2", "q2_fare", "Payment composition", ["Percentage", "Count"]),
                ("Q3", "q3_comparison", "Rush-hour comparison", ["Extra minutes", "Duration difference (%)", "Paired duration and speed"]),
                ("Q3", "q3_location", "Location view", ["Hourly profile", "Zone × hour heatmap", "Bubble exploration"]),
            ]
            for section, report, label, choices in cases:
                select_report(app, section, report)
                for choice in choices:
                    next(w for w in app.selectbox if w.label == label).set_value(choice).run()
                    self.assertEqual(len(app.exception), 0, (report, choice))
                    self.assertGreater(len(app.get("plotly_chart")), 0)
            select_report(app, "Q2", "q2_payment")
            for choice in ["Trip count", "Mean fare ($)", "Mean recorded tip ($)", "Mean total ($)"]:
                next(w for w in app.selectbox if w.label == "Payment measure").set_value(choice).run()
                self.assertEqual(len(app.exception), 0)
            select_report(app, "Q1", "q1_monthly")
            self.assertEqual(len(app.get("plotly_chart")), 3)
            query.assert_not_called()

    def test_chart_selections_remain_valid_after_filters(self):
        from dashboard_fixtures import start_app, select_report
        app = select_report(start_app(), "Q3", "q3_location")
        next(w for w in app.selectbox if w.label == "Borough").set_value("Queens").run()
        self.assertEqual(len(app.exception), 0)
        next(b for b in app.button if b.label == "Reset view").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertGreater(len(app.get("plotly_chart")), 0)


if __name__ == "__main__":
    unittest.main()
