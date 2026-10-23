import unittest
from datetime import date
from reference_ranker import assess, freshness_level


def reference(**changes):
    base = {
        "id": "r1", "source_kind": "community_experience", "platform": "reddit",
        "url_or_user_provided": "https://example.test/post", "published_at": "2026-10-01",
        "collected_at": "2026-10-16", "quote": "我用小项目准备面试。",
        "use": "project_pattern", "review_status": "reviewed",
        "engagement": {"view_count": 100000, "platform_percentile": 95},
    }
    base.update(changes)
    return base


class ReferenceRankerTests(unittest.TestCase):
    def test_date_levels(self):
        today = date(2026, 10, 16)
        self.assertEqual(freshness_level("2026-10-01", today), "current")
        self.assertEqual(freshness_level("2026-07-01", today), "recent")
        self.assertEqual(freshness_level("2025-01-01", today), "historical")

    def test_popular_post_is_not_market_requirement(self):
        result = assess(reference(), date(2026, 10, 16))
        self.assertEqual(result["engagement_priority"], "high")
        self.assertNotIn("market_requirement", result["permitted_use"])

    def test_official_job_can_support_requirement(self):
        result = assess(reference(source_kind="official_job", platform="company_site", use="market_requirement"), date(2026, 10, 16))
        self.assertTrue(result["can_drive_plan"])

    def test_raw_views_without_percentile_are_unavailable(self):
        result = assess(reference(engagement={"view_count": 999999}), date(2026, 10, 16))
        self.assertEqual(result["engagement_priority"], "unavailable")

    def test_wrong_source_use_cannot_drive_plan(self):
        result = assess(reference(use="market_requirement"), date(2026, 10, 16))
        self.assertFalse(result["can_drive_plan"])


if __name__ == "__main__":
    unittest.main()
