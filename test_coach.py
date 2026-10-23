import unittest
from coach import ROOT, read_json, build_report


class CoachTests(unittest.TestCase):
    def setUp(self):
        self.profile = read_json(ROOT / "data/profile.json")
        self.jobs = read_json(ROOT / "data/jobs.json")["samples"]
        self.rules = read_json(ROOT / "data/assessment_rules.json")["rules"]

    def report(self, minutes=120, jobs=None, profile=None):
        return build_report(profile or self.profile, self.jobs, self.rules, jobs or ["job_01", "job_02"], minutes)

    def test_budget_and_short_scope(self):
        for minutes in (1, 20, 30, 59, 60, 120):
            result = self.report(minutes)
            self.assertLessEqual(sum(t["minutes"] for t in result["tasks"]), minutes)
        short = self.report(20)
        self.assertEqual(len(short["tasks"]), 1)
        self.assertIn("一条", short["tasks"][0]["artifact"])

    def test_no_technical_contamination(self):
        self.assertNotIn("C++", str(self.report()))

    def test_evidence_not_mastery(self):
        profile = {**self.profile, "experience_evidence": []}
        result = self.report(profile=profile)
        rows = [r for r in result["assessments"] if "学历" not in r["requirement"]]
        self.assertTrue(all(r["status"] == "待确认，不等于不会" for r in rows))

    def test_unmapped_keeps_alternatives_and_original_logic(self):
        result = self.report(jobs=["job_04"])
        self.assertEqual(result["tasks"], [])
        self.assertEqual(result["alternatives"], [])
        self.assertTrue(any("至少一项" in r["quote"] for r in result["assessments"]))

    def test_every_task_source_is_selected_requirement(self):
        result = self.report()
        quotes = {(r["job_id"], r["quote"]) for r in result["assessments"]}
        for task in result["tasks"]:
            for source in task["sources"]:
                self.assertIn((source["job_id"], source["quote"]), quotes)

    def test_bad_input(self):
        for minutes in (0, -1):
            with self.assertRaises(ValueError):
                self.report(minutes)
        with self.assertRaises(ValueError):
            self.report(jobs=["missing"])


if __name__ == "__main__":
    unittest.main()
