import unittest
from role_scope import build_skill_map


def brief(identifier, priority, items):
    return {"id": identifier, "role_group": "AI产品", "priority": priority, "status": "reviewed", "items": items}


def item(key, summary, quote, kind="required", relation="single"):
    return {"capability_key": key, "summary": summary, "quote": quote, "kind": kind, "relation": relation}


class RoleScopeTests(unittest.TestCase):
    def test_recurring_requirement_becomes_core(self):
        result = build_skill_map([
            brief("a", 5, [item("user_research", "用户洞察", "具备用户洞察能力")]),
            brief("b", 3, [item("user_research", "用户洞察", "能分析用户反馈")]),
        ])
        self.assertEqual(result["items"][0]["placement"], "core")
        self.assertEqual(result["items"][0]["required_brief_count"], 2)

    def test_high_priority_single_requirement_is_targeted(self):
        result = build_skill_map([brief("a", 5, [item("rag", "RAG", "拥有RAG项目经验")])])
        self.assertEqual(result["items"][0]["placement"], "targeted")

    def test_preferred_item_is_not_core(self):
        result = build_skill_map([
            brief("a", 5, [item("overseas", "海外经验", "有海外经验者优先", "preferred")]),
            brief("b", 5, [item("overseas", "海外经验", "有全球化经验优先", "preferred")]),
        ])
        self.assertEqual(result["items"][0]["placement"], "optional")

    def test_unreviewed_or_mixed_groups_rejected(self):
        with self.assertRaises(ValueError):
            build_skill_map([{**brief("a", 5, []), "status": "unreviewed"}])
        with self.assertRaises(ValueError):
            build_skill_map([brief("a", 5, []), {**brief("b", 5, []), "role_group": "量化研究"}])


if __name__ == "__main__":
    unittest.main()
