import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dify"))
import complete_task_state as logic

PERSONAS = [
    ("只会使用 Chat", "AI 产品经理", "60", 1),
    ("会写提示词，能使用表格", "AI 产品运营", "90", 1),
    ("会 Python 基础语法和 pandas", "Agent 应用开发", "120", 2),
    ("会 JavaScript 基础，做过简单网页", "AI 应用产品经理", "120", 2),
    ("数学硕士，会 Python，无正式项目", "量化研究员", "120", 1),
    ("做过两年科研，会 Python 和数据分析", "算法研究员", "150", 1),
    ("会产品设计、原型和用户访谈，不会编程", "用户研究员", "90", 3),
    ("会 Python 后端和 API，缺少产品经验", "RAG/智能体工程师", "120", 2),
    ("有市场工作经验，只会 Chat 和 Excel", "外贸业务员", "60", 1),
    ("会 Python、统计和量化基础，转向 AI 产品", "量化开发工程师", "120", 2),
]

OPTIONS = [
    {"name": "岗位能力与竞品研究", "reason": "分析岗位和行业要求", "deliverable": "研究报告", "acceptance": "至少五个岗位或竞品有来源"},
    {"name": "可运行的岗位作品原型", "reason": "用项目证明实践能力", "deliverable": "可运行原型", "acceptance": "有演示、代码或操作记录"},
    {"name": "用户/业务验证项目", "reason": "把能力转成业务证据", "deliverable": "验证报告", "acceptance": "有假设、样本、结果和局限"},
]

lines = ["# 十类用户对话测试记录", "", "说明：这是离线状态流转测试，使用固定的分析结果模拟模型，不代表真实模型回答质量。", ""]
for number, (background, role, minutes, selected) in enumerate(PERSONAS, 1):
    query1 = f"目标岗位：{role}。背景：{background}。每天项目训练时间：{minutes}分钟。"
    proposal = {"action": "analyze", "profile_updates": {"role_group": role, "background": background, "daily_minutes": minutes, "city": "不限"}, "project_options": OPTIONS, "reply": "请选择项目。"}
    first = logic.main(json.dumps(proposal, ensure_ascii=False), {}, query1)
    generated_days = [{"day": day, "goal": f"围绕{OPTIONS[selected - 1]['name']}完成第{day}天目标",
                       "tasks": "按当天步骤完成并记录证据",
                       "estimated_minutes": min(int(minutes), 120),
                       "deliverable": f"第{day}天成果",
                       "acceptance": "成果可检查并包含来源或过程证据"}
                      for day in range(1, 8)]
    generated = {"action": "create_plan", "selected_project": OPTIONS[selected - 1]["name"],
                 "plan": {"days": generated_days}}
    second = logic.main(json.dumps(generated, ensure_ascii=False), first["state"], str(selected))
    third = logic.main(json.dumps({"action": "show_today"}, ensure_ascii=False), second["state"], "今天做什么？")
    lines += [f"## 用户 {number}：{background}", "", "**用户：** " + query1, "", "**Agent：** " + first["reply"], ""]
    lines += ["可选项目：", "", *[f"{i}. {x['name']}：{x['reason']}；交付物：{x['deliverable']}；验收：{x['acceptance']}" for i, x in enumerate(OPTIONS, 1)], "", f"**用户：** 选择第 {selected} 个项目", "", "**Agent：** " + second["reply"], "", "**用户：** 今天做什么？", "", "**Agent：** " + third["reply"], "", f"状态：{second['state']['status']}；当前天数：{second['state']['plan']['current_day']}；每日预算：{second['state']['plan']['daily_budget_minutes']} 分钟", ""]
(ROOT / "output").mkdir(exist_ok=True)
(ROOT / "output" / "ten-persona-conversations.md").write_text("\n".join(lines), encoding="utf-8")
print(ROOT / "output" / "ten-persona-conversations.md")
