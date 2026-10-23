import unittest
from quant_research import chronological_split, make_return_observations, validate_prices


PRICES = [
    {"date": "2026-01-01", "asset": "AAA", "close": 100},
    {"date": "2026-01-02", "asset": "AAA", "close": 110},
    {"date": "2026-01-03", "asset": "AAA", "close": 121},
    {"date": "2026-01-04", "asset": "AAA", "close": 108.9},
    {"date": "2026-01-05", "asset": "AAA", "close": 119.79},
    {"date": "2026-01-06", "asset": "AAA", "close": 131.769},
]


class QuantResearchTests(unittest.TestCase):
    def test_feature_only_uses_present_or_past(self):
        rows = make_return_observations(PRICES, lookback=1, horizon=1)
        first = rows[0]
        self.assertEqual(first["feature_date"].isoformat(), "2026-01-02")
        self.assertEqual(first["target_date"].isoformat(), "2026-01-03")
        self.assertAlmostEqual(first["past_return"], 0.1)
        self.assertAlmostEqual(first["forward_return"], 0.1)

    def test_split_keeps_training_label_before_cutoff(self):
        rows = make_return_observations(PRICES)
        split = chronological_split(rows, "2026-01-04")
        self.assertTrue(all(item["target_date"] < split["cutoff"] for item in split["train"]))
        self.assertTrue(all(item["feature_date"] >= split["cutoff"] for item in split["validation"]))

    def test_duplicate_and_invalid_prices_rejected(self):
        with self.assertRaises(ValueError): validate_prices(PRICES + [PRICES[0]])
        with self.assertRaises(ValueError): validate_prices([{"date": "bad", "asset": "AAA", "close": 1}])
        with self.assertRaises(ValueError): make_return_observations(PRICES, 0, 1)

    def test_empty_split_rejected(self):
        rows = make_return_observations(PRICES)
        with self.assertRaises(ValueError): chronological_split(rows, "2026-12-01")


if __name__ == "__main__":
    unittest.main()
