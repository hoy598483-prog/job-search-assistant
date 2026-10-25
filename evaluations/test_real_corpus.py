import unittest
from evaluations.collect_greenhouse import collect, strip_description
from evaluations.annotate import verify_annotations
from evaluations.match_baseline import duplicate_decision, find_duplicates, match_job, skill_matches


class RealCorpusTests(unittest.TestCase):
    def test_html_cleaning(self):
        text = strip_description("<p>Python &amp; SQL</p><script>secret()</script><p>Develop models</p>")
        self.assertIn("Python & SQL", text)
        self.assertNotIn("secret", text)

    def test_public_collector_is_bounded_and_unlabeled(self):
        description = "<p>" + "Python engineering role and data model development. " * 5 + "</p>"
        seen = []
        def fetch(url):
            seen.append(url)
            return {"jobs": [
                {"id": i, "internal_job_id": i, "title": f"Role {i}",
                 "absolute_url": f"https://boards.greenhouse.io/example/jobs/{i}",
                 "location": {"name": "Remote"}, "content": description}
                for i in range(60)
            ]}
        result = collect(["example"], target=50, per_board=50, fetch=fetch)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result["collected_size"], 50)
        self.assertEqual(result["annotated_size"], 0)
        self.assertTrue(all(x["gold"] is None for x in result["cases"]))
        self.assertTrue(all(x["url"].startswith("https://") for x in result["cases"]))

    def test_never_mark_unreviewed_as_gold(self):
        fixture = {"cases": [{"id": "a", "source": "任职要求：熟悉Python。",
                             "source_sha256": None, "gold": None,
                             "annotation_status": "unlabeled"}]}
        self.assertEqual(verify_annotations(fixture), 0)

    def test_dedup_requires_source_or_company(self):
        j = {"id": "board:123", "title": "Python Engineer", "company": "Acme",
             "source": "Python SQL engineer"}
        same = dict(j)
        self.assertEqual(duplicate_decision(j, same)["label"], "exact_duplicate")
        different = dict(j, id="board:124", company="Other")
        self.assertEqual(duplicate_decision(j, different)["label"], "different")
        self.assertEqual(len(find_duplicates([j, same])), 1)

    def test_matching_does_not_claim_eligibility(self):
        j = {"id": "j1", "source": "Python, SQL and JavaScript"}
        m = match_job(j, "Python SQL")
        self.assertEqual(m["score"], 2/3 if 2/3 == round(2/3,4) else round(2/3,4))
        self.assertIn("javascript", m["missing_or_unmentioned"])
        self.assertFalse(skill_matches("JavaScript", "java"))
        self.assertIn("unmentioned", m["caveat"])


if __name__ == "__main__":
    unittest.main()
