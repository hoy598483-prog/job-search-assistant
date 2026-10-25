import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluations.review_workbench import ReviewStore


class ReviewWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.source_path = base / "manifest.json"
        self.state_path = base / "state.json"
        self.export_path = base / "gold.json"
        self.source_path.write_text(json.dumps({"origin":"indeed_pilot",
            "cases":[{"id":"indeed:test1","title":"AI Engineer","company":"Example",
                      "url":"https://ca.indeed.com/viewjob?jk=demo",
                      "annotation_status":"unlabeled"}]}), encoding="utf-8")
        self.store = ReviewStore(self.source_path, self.state_path, self.export_path)

    def test_manifest_without_source_and_capture(self):
        self.assertEqual(self.store.overview()["reviewed"], 0)
        self.assertEqual(self.store.case("indeed:test1")["source"], "")
        with self.assertRaisesRegex(ValueError, "Capture JD source"):
            self.store.suggest("indeed:test1")
        result = self.store.set_source("indeed:test1", "任职要求：熟悉Python。")
        self.assertEqual(result["length"], len("任职要求：熟悉Python。"))
        self.assertIn("熟悉Python", self.store.case("indeed:test1")["source"])

    def test_drafts_do_not_become_gold(self):
        self.store.set_source("indeed:test1", "任职要求：熟悉Python。")
        item = {"summary":"Python","quote":"熟悉Python。",
                "kind":"required","relation":"single"}
        self.store.save("indeed:test1", [item], reviewed=False)
        self.assertEqual(self.store.overview()["reviewed"], 0)
        with self.assertRaisesRegex(ValueError, "No human-reviewed"):
            self.store.export_reviewed()
        with self.assertRaisesRegex(ValueError, "completeness"):
            self.store.save("indeed:test1", [item], reviewed=True)
        self.store.save("indeed:test1", [item], reviewed=True, confirmed_complete=True)
        self.assertEqual(self.store.overview()["reviewed"], 1)
        result = self.store.export_reviewed()
        self.assertEqual(result["reviewed"], 1)
        gold = json.loads(self.export_path.read_text())
        self.assertEqual(gold["cases"][0]["gold"]["items"][0]["quote"], "熟悉Python。")
        self.assertEqual(gold["cases"][0]["source"], "任职要求：熟悉Python。")

    def test_source_change_invalidates_review(self):
        self.store.set_source("indeed:test1", "任职要求：熟悉Python。")
        self.store.save("indeed:test1", [], reviewed=True, confirmed_complete=True)
        self.store.set_source("indeed:test1", "任职要求：熟悉SQL。")
        self.assertEqual(self.store.overview()["reviewed"], 0)
        self.assertEqual(self.store.case("indeed:test1")["items"], [])

    def test_suggestion_is_never_stored(self):
        self.store.set_source("indeed:test1", "任职要求：熟悉Python。")
        with patch("companion.providers.analyze", return_value={
            "provider":"codex","items":[{"summary":"Python", "quote":"熟悉Python。",
                "kind":"required","relation":"single"}]}) as provider:
            with self.assertRaisesRegex(ValueError, "consent"):
                self.store.suggest("indeed:test1", "codex")
            self.assertEqual(provider.call_count, 0)
            proposal = self.store.suggest("indeed:test1", "codex", consent=True)
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(proposal["status"], "unreviewed_suggestion")
        self.assertEqual(self.store.overview()["reviewed"], 0)
        self.assertEqual(self.store.case("indeed:test1")["items"], [])

    def test_reopen_keeps_source_and_draft(self):
        self.store.set_source("indeed:test1", "任职要求：熟悉Python。")
        self.store.save("indeed:test1", [], reviewed=False, note="read later")
        reopened = ReviewStore(self.source_path, self.state_path, self.export_path)
        self.assertEqual(reopened.case("indeed:test1")["source"], "任职要求：熟悉Python。")
        self.assertEqual(reopened.case("indeed:test1")["note"], "read later")


if __name__ == "__main__":
    unittest.main()
