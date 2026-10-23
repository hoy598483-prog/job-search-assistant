import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dify"))


def get_transition():
    app = json.loads((ROOT / "dify" / "job-prep-full-v0.7.yml").read_text(encoding="utf-8"))
    code = next(n["data"]["code"] for n in app["workflow"]["graph"]["nodes"] if n["id"] == "state_update")
    namespace = {}
    exec(compile(code, "<Dify code node>", "exec"), namespace)
    return namespace["main"]


def sample_plan():
    return {
        "project": "求职准备 Agent",
        "daily_budget_minutes": 120,
        "current_day": 1,
        "days": [
            {
                "day": n,
                "goal": f"完成第{n}天目标",
                "tasks": f"整理并实现第{n}天内容",
                "estimated_minutes": 100,
                "deliverable": f"第{n}天文档",
                "acceptance": f"文档包含第{n}天的证据",
                "status": "not_started",
                "review": "",
            }
            for n in range(1, 8)
        ],
    }


class DifyDslTests(unittest.TestCase):
    def setUp(self):
        self.app = json.loads((ROOT / "dify" / "job-prep-full-v0.7.yml").read_text(encoding="utf-8"))
        self.transition = get_transition()

    def test_graph_and_references(self):
        self.assertEqual("0.7.0", self.app["version"])
        graph = self.app["workflow"]["graph"]
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(5, len(nodes))
        self.assertEqual(4, len(graph["edges"]))
        for edge in graph["edges"]:
            self.assertIn(edge["source"], nodes)
            self.assertIn(edge["target"], nodes)
            self.assertEqual(nodes[edge["source"]]["data"]["type"], edge["data"]["sourceType"])
            self.assertEqual(nodes[edge["target"]]["data"]["type"], edge["data"]["targetType"])

    def test_create_revise_and_advance(self):
        plan = sample_plan()
        creation = {
            "action": "create_plan",
            "profile_updates": {"daily_minutes": "120"},
            "selected_project": "求职准备 Agent",
            "plan": plan,
        }
        created = self.transition(json.dumps(creation), {}, "我选求职准备 Agent，每天 120 分钟")
        self.assertEqual(1, created["state"]["plan"]["current_day"])
        self.assertIn("第 1 天", created["reply"])

        vague = {"action": "review", "review": {"status": "passed", "feedback": "已完成", "evidence": "做完了。"}}
        revised = self.transition(json.dumps(vague), created["state"], "做完了。")
        self.assertEqual(1, revised["state"]["plan"]["current_day"])
        self.assertEqual("revise", revised["state"]["plan"]["days"][0]["status"])

        query = "我提交了第1天文档，包含三份JD摘录和能力差距标注。"
        passed = {
            "action": "review",
            "review": {
                "status": "passed",
                "feedback": "已满足验收标准。",
                "evidence": "包含三份JD摘录和能力差距标注",
            },
        }
        advanced = self.transition(json.dumps(passed), revised["state"], query)
        self.assertEqual(2, advanced["state"]["plan"]["current_day"])
        self.assertIn("第 2 天", advanced["reply"])

    def test_invalid_plan_does_not_replace_saved_plan(self):
        old = {"profile": {"daily_minutes": "120"}, "plan": sample_plan()}
        result = self.transition(json.dumps({"action": "create_plan", "plan": {"days": []}}), old, "重做计划")
        self.assertEqual(7, len(result["state"]["plan"]["days"]))
        self.assertIn("格式", result["reply"])


if __name__ == "__main__":
    unittest.main()
