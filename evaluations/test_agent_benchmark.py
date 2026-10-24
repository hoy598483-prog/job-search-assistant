import json
from pathlib import Path
import tempfile
import unittest

from evaluations.agent_benchmark import evaluate, load_dataset, load_predictions, run

DATASET = Path(__file__).parent / "synthetic_cases.json"


class BenchmarkTests(unittest.TestCase):
    def test_baseline_report_bounded(self):
        report = run(DATASET)
        self.assertEqual(report["cases_total"], 6)
        self.assertEqual(report["cases_with_predictions"], 6)
        self.assertEqual(report["predictor"], "deterministic_rule_baseline")
        self.assertTrue(0 <= report["exact_item_f1"] <= 1)
        self.assertEqual(report["cost_observations"], 0)

    def test_gold_predictions_perfect(self):
        dataset = load_dataset(DATASET)
        pred = {c["id"]: {"candidate": c["gold"]} for c in dataset["cases"]}
        report = evaluate(dataset, pred, "gold_oracle_for_tests_only")
        self.assertEqual(report["exact_item_f1"], 1.0)
        self.assertEqual(report["validation_acceptance_rate"], 1.0)

    def test_missing_and_fabricated_quote(self):
        dataset = load_dataset(DATASET)
        pred = {"S01-any-of": {"candidate": {"items": [{
            "summary": "fabricated", "quote": "NOT IN SOURCE",
            "kind": "required", "relation": "single"
        }]}}}
        report = evaluate(dataset, pred, "faulty_fixture")
        self.assertEqual(report["coverage"], 1 / 6)
        self.assertEqual(report["validation_acceptance_rate"], 0)
        self.assertEqual(report["error_counts"]["missing_prediction"], 5)
        self.assertEqual(report["error_counts"]["validation_failed"], 1)
        self.assertEqual(report["source_quote_support_rate"], 0)

    def test_duplicate_unknown_prediction_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pred.json"
            p.write_text(json.dumps({"cases": [{"id": "X"}, {"id": "X"}]}))
            with self.assertRaises(ValueError):
                load_predictions(p)
        with self.assertRaises(ValueError):
            evaluate(load_dataset(DATASET), {"unknown": {}}, "invalid")

    def test_wrong_relation_is_counted(self):
        dataset = load_dataset(DATASET)
        predictions = {c["id"]: {"candidate": c["gold"]} for c in dataset["cases"]}
        wrong = dict(predictions["S02-required-preferred"]["candidate"]["items"][0])
        wrong["relation"] = "all_of"
        predictions["S02-required-preferred"] = {"candidate": {"items": [
            wrong, *dataset["cases"][1]["gold"]["items"][1:]
        ]}}
        report = evaluate(dataset, predictions, "misclassified")
        self.assertEqual(report["error_counts"]["wrong_label_or_relation"], 1)
        self.assertLess(report["exact_item_f1"], 1)


if __name__ == "__main__":
    unittest.main()
