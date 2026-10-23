import tempfile
import unittest
from pathlib import Path
from session import Session


class SessionTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parent / "output"
        test_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "session.json"
        self.session = Session(self.path)
        self.message = self.session.message("user", "按目前每天两小时的模板开始")
        self.plan = self.session.propose(120)
        self.session.activate(self.plan, self.message)

    def test_draft_does_not_replace_active(self):
        new = self.session.propose(20, reason="今天只有20分钟")
        self.assertEqual(Session(self.path).state["active_plan_id"], self.plan)
        message = self.session.message("user", "采用20分钟计划")
        self.session.activate(new, message)
        restored = Session(self.path)
        self.assertEqual(restored.plan(self.plan)["status"], "superseded")
        self.assertEqual(restored.state["active_plan_id"], new)

    def test_claim_is_not_completion(self):
        submission = self.session.submit(0, "我都懂了")
        self.assertEqual(self.session.state["submissions"][0]["status"], "awaiting_review")
        with self.assertRaises(ValueError):
            self.session.review(submission, "accepted", "通过", "")
        self.session.review(submission, "needs_evidence", "尚无成果", "只收到自述")
        self.assertEqual(Session(self.path).state["submissions"][0]["status"], "needs_evidence")

    def test_profile_updates_are_persistent(self):
        self.session.update_profile({"weekly_prep_hours": 6}, self.message)
        self.assertEqual(Session(self.path).profile()["weekly_prep_hours"], 6)
        with self.assertRaises(ValueError):
            self.session.update_profile({"weekly_prep_hours": -1}, self.message)

    def test_bad_reference(self):
        with self.assertRaises(ValueError):
            self.session.update_profile({"weekly_prep_hours": 6}, "missing")
        with self.assertRaises(ValueError):
            self.session.submit(-1, "成果")


if __name__ == "__main__":
    unittest.main()
