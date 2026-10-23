import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dify"))
import complete_task_state  # noqa: E402


OPTIONS = [
    {"name": "AI 产品研究助手", "reason": "岗位相关", "deliverable": "研究报告", "acceptance": "五个竞品"},
    {"name": "企业知识库构建", "reason": "岗位相关", "deliverable": "原型", "acceptance": "十个条目"},
    {"name": "AI 产品用户调研", "reason": "岗位相关", "deliverable": "问卷", "acceptance": "有分析"},
]


class SelectionTests(unittest.TestCase):
    def test_numbered_choice_survives_bad_model_json(self):
        state = {"profile": {"daily_minutes": "2小时"}, "project_options": OPTIONS}
        result = complete_task_state.main("{truncated", state, "1")
        self.assertEqual("AI 产品研究助手", result["state"]["selected_project"])
        self.assertEqual(120, result["state"]["plan"]["daily_budget_minutes"])
        self.assertEqual(7, len(result["state"]["plan"]["days"]))
        self.assertIn("第 1 天", result["reply"])

    def test_missing_budget_is_specific(self):
        result = complete_task_state.main("{truncated", {"project_options": OPTIONS}, "1")
        self.assertIn("每天", result["reply"])
        self.assertNotIn("格式", result["reply"])

    def test_chinese_choice_uses_model_generated_plan(self):
        state = {"profile": {"daily_minutes": "120"}, "project_options": OPTIONS}
        days = [{"day": n, "goal": f"个性化目标{n}", "tasks": "按岗位要求训练",
                 "estimated_minutes": 100, "deliverable": "成果文档", "acceptance": "含具体证据"}
                for n in range(1, 8)]
        raw = json.dumps({"action": "create_plan", "plan": {"days": days}}, ensure_ascii=False)
        result = complete_task_state.main(raw, state, "第一个计划")
        self.assertEqual("AI 产品研究助手", result["state"]["selected_project"])
        self.assertEqual("个性化目标1", result["state"]["plan"]["days"][0]["goal"])
        self.assertIn("按你的背景生成", result["reply"])

    def test_no_saved_options_does_not_invent_choice(self):
        result = complete_task_state.main("{truncated", {}, "1")
        self.assertFalse(result["state"].get("plan"))

    def test_invalid_generated_plan_uses_selected_template(self):
        state = {"profile": {"daily_minutes": "120分钟"}, "project_options": OPTIONS}
        proposal = {"action": "create_plan", "selected_project": OPTIONS[1]["name"], "plan": {"days": []}}
        result = complete_task_state.main(json.dumps(proposal), state, "选企业知识库构建")
        self.assertEqual(7, len(result["state"]["plan"]["days"]))
        self.assertEqual(OPTIONS[1]["name"], result["state"]["selected_project"])


if __name__ == "__main__":
    unittest.main()
