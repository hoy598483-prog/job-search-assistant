import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dify"))
import complete_task_state as state_logic  # noqa: E402


OPTIONS = [
    {"name": "AI 产品研究助手", "reason": "适合岗位分析", "deliverable": "竞品研究报告", "acceptance": "至少五个竞品有来源"},
    {"name": "企业知识库构建", "reason": "适合 RAG 场景", "deliverable": "知识库原型", "acceptance": "至少十个条目有来源"},
    {"name": "AI 产品用户调研", "reason": "适合用户验证", "deliverable": "问卷与分析", "acceptance": "有问题设计和反馈分析"},
]


PERSONAS = [
    ("chat-only", "只会使用 Chat，不会编程", "AI 产品经理", "60", 1),
    ("prompt-beginner", "会写提示词，能使用表格", "AI 产品运营", "90", 1),
    ("python-basic", "会 Python 基础语法和 pandas", "Agent 应用开发", "120", 2),
    ("js-basic", "会 JavaScript 基础，做过简单网页", "AI 应用产品经理", "120", 2),
    ("math-master", "数学硕士，会 Python，无正式项目", "量化研究员", "120", 1),
    ("researcher", "做过两年科研，会 Python 和数据分析", "算法研究员", "150", 1),
    ("designer", "会产品设计、原型和用户访谈，不会编程", "用户研究员", "90", 3),
    ("backend", "会 Python 后端和 API，缺少产品经验", "RAG/智能体工程师", "120", 2),
    ("career-switcher", "有市场工作经验，只会 Chat 和 Excel", "外贸业务员", "60", 1),
    ("quant-adjacent", "会 Python、统计和量化基础，转向 AI 产品", "量化开发工程师", "120", 2),
]


def run_persona(background, role, minutes, option_number):
    state = {}
    first_query = f"目标岗位：{role}。背景：{background}。每天项目训练时间：{minutes}分钟。"
    profile = {"role_group": role, "background": background, "daily_minutes": minutes, "city": "不限"}
    analysis = {"action": "analyze", "profile_updates": profile,
                "new_jobs": [], "project_options": OPTIONS, "reply": "请选择项目。"}
    result = state_logic.main(json.dumps(analysis, ensure_ascii=False), state, first_query)
    chosen = state_logic.main("{}", result["state"], str(option_number))
    today = state_logic.main(json.dumps({"action": "show_today"}, ensure_ascii=False), chosen["state"], "今天做什么？")
    return result, chosen, today


class TenPersonaJourneyTests(unittest.TestCase):
    def test_all_personas_reach_day_one(self):
        for persona_id, background, role, minutes, option_number in PERSONAS:
            with self.subTest(persona=persona_id):
                analyzed, chosen, today = run_persona(background, role, minutes, option_number)
                state = chosen["state"]
                self.assertEqual("choosing_project", analyzed["state"]["status"])
                self.assertEqual(OPTIONS[option_number - 1]["name"], state["selected_project"])
                self.assertEqual("active", state["status"])
                self.assertEqual(1, state["plan"]["current_day"])
                self.assertEqual(7, len(state["plan"]["days"]))
                self.assertIn("第 1 天", today["reply"])
                self.assertLessEqual(max(day["estimated_minutes"] for day in state["plan"]["days"]), int(minutes))

    def test_low_budget_is_not_silently_increased(self):
        _, chosen, _ = run_persona("只会使用 Chat", "AI 产品经理", "30", 1)
        self.assertEqual(30, chosen["state"]["plan"]["daily_budget_minutes"])
        self.assertTrue(all(day["estimated_minutes"] <= 30 for day in chosen["state"]["plan"]["days"]))


if __name__ == "__main__":
    unittest.main()
