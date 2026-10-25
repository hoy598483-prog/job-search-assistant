import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluations.run_codex_eval import run_evaluation, _predict


class CodexRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.dataset = self.folder / "dataset.json"
        self.out = self.folder / "predictions.json"
        self.report = self.folder / "report.json"
        self.cases = [
            {"id": "c1", "source": "任职要求：熟悉Python。",
             "gold": {"items": [{"summary": "Python", "quote": "熟悉Python。",
                                 "kind": "required", "relation": "single"}]},
             "annotation_status": "reviewed"},
            {"id": "c2", "source": "任职要求：熟悉SQL。",
             "gold": {"items": [{"summary": "SQL", "quote": "熟悉SQL。",
                                 "kind": "required", "relation": "single"}]},
             "annotation_status": "reviewed"},
        ]
        self.write_dataset()

    def write_dataset(self):
        self.dataset.write_text(json.dumps({"origin": "synthetic_test_only",
                                            "cases": self.cases}, ensure_ascii=False),
                                encoding="utf-8")

    @staticmethod
    def fake_analyze(source, provider):
        import hashlib
        assert provider == "codex"
        quote = source.split("：", 1)[1]
        return {"provider": "codex",
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "items": [{"summary": "fixture", "quote": quote,
                           "kind": "required", "relation": "single"}]}

    def call(self, **kw):
        return run_evaluation(self.dataset, self.out, self.report, **kw)

    def test_preview_no_calls_and_no_files(self):
        with patch("evaluations.run_codex_eval.providers.analyze") as model:
            result = self.call(max_new=1)
        model.assert_not_called()
        self.assertEqual(result["will_run"], 1)
        self.assertFalse(self.out.exists())

    def test_no_send_without_explicit_consent(self):
        with patch("evaluations.run_codex_eval.providers.analyze") as model:
            with self.assertRaises(ValueError):
                self.call(execute=True)
            model.assert_not_called()

    def test_resume_preserves_previous_success(self):
        with patch("evaluations.run_codex_eval.providers.analyze",
                   side_effect=self.fake_analyze) as model:
            first = self.call(execute=True, consent=True, max_new=1)
            second = self.call(execute=True, consent=True)
        self.assertEqual(first["new_attempts"], 1)
        self.assertEqual(second["new_attempts"], 1)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(second["exact_item_f1"], 1)
        entries = json.loads(self.out.read_text())["cases"]
        self.assertEqual([e["id"] for e in entries], ["c1", "c2"])
        self.assertTrue(all(e["candidate"] is not None for e in entries))

    def test_failure_checkpoint_and_retry(self):
        with patch("evaluations.run_codex_eval.providers.analyze",
                   side_effect=ValueError("Secret source text")):
            result = self.call(execute=True, consent=True, max_new=1)
        self.assertEqual(result["new_failed"], 1)
        saved = self.out.read_text()
        self.assertNotIn("Secret source text", saved)
        with patch("evaluations.run_codex_eval.providers.analyze",
                   side_effect=self.fake_analyze) as model:
            result = self.call(execute=True, consent=True)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(result["provider_failures"], 1)
            result = self.call(execute=True, consent=True, retry_failed=True)
            self.assertEqual(result["provider_failures"], 0)
            self.assertEqual(result["provider_successes"], 2)

    def test_changed_dataset_fails_without_overwriting(self):
        with patch("evaluations.run_codex_eval.providers.analyze",
                   side_effect=self.fake_analyze):
            self.call(execute=True, consent=True, max_new=1)
        before = self.out.read_bytes()
        self.cases[1]["source"] += " 额外描述"
        self.write_dataset()
        with self.assertRaisesRegex(ValueError, "different dataset"):
            self.call(execute=True, consent=True)
        self.assertEqual(self.out.read_bytes(), before)

    def test_unreviewed_rejected(self):
        self.cases[1]["annotation_status"] = "unlabeled"
        self.write_dataset()
        with self.assertRaisesRegex(ValueError, "Unreviewed JD"):
            self.call()

    def test_provider_never_receives_gold_labels(self):
        observed = []
        def model(source, provider):
            observed.append(source)
            return self.fake_analyze(source, provider)
        with patch("evaluations.run_codex_eval.providers.analyze", side_effect=model):
            self.call(execute=True, consent=True, max_new=1)
        self.assertEqual(observed, [self.cases[0]["source"]])
        self.assertNotIn("gold", observed[0])


if __name__ == "__main__":
    unittest.main()
