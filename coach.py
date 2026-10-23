"""本地、无模型API的证据报告与计划内核。聊天由当前Codex会话承接。

仅分析已审阅映射；不会把关键词匹配伪装成能力判断。
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


TASKS = {
    "prototype": {
        "title": "验证招聘分析到当天任务的完整原型",
        "artifact": "一份有原文依据的差距报告和当天计划",
        "acceptance": "只使用所选岗位要求；未知能力不判定为不会；总时长不超预算",
        "ai_action": "生成报告、实现代码并运行检查",
        "user_action": "实际查看结果；有不符合真实情况的地方直接在聊天指出",
    },
    "validation": {
        "title": "验证聊天录入和两种失败情况",
        "artifact": "正常预算、20分钟预算、缺少能力证据的测试记录",
        "acceptance": "缩短预算时缩小产出范围；不凭一句懂了宣布能力达标",
        "ai_action": "执行案例并记录问题与修改",
        "user_action": "试用；无需回答教学式问题",
    },
    "concepts": {
        "title": "理解当前原型的工作方式",
        "artifact": "输入、证据、判断、计划四步说明及当前限制",
        "acceptance": "明确当前为已审阅样本的规则内核，未接通独立模型或网页采集",
        "ai_action": "结合实际代码解释流程，不安排术语测验",
        "user_action": "阅读说明，按需提问",
    },
    "domain": {
        "title": "查看具体岗位的业务场景",
        "artifact": "该岗位的业务问题与待确认领域经验记录",
        "acceptance": "不把企业协作场景或内容兴趣当成全部AI产品岗位通用条件",
        "ai_action": "根据原文归纳业务场景，标明未知信息",
        "user_action": "有相关经历时在聊天补充，无需编造案例",
    },
}


def build_report(profile, jobs, rules, selected_ids, minutes):
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
        raise ValueError("项目学习预算需为正整数分钟")
    if not selected_ids:
        raise ValueError("至少选择一个岗位样本")
    by_id = {job["id"]: job for job in jobs}
    if any(job_id not in by_id for job_id in selected_ids):
        raise ValueError("所选岗位样本不存在")
    selected_ids = list(dict.fromkeys(selected_ids))
    evidence = {item["id"]: item for item in profile.get("experience_evidence", [])}
    mappings = {(r["job_id"], r["requirement_index"]): r for r in rules}
    rows, task_sources = [], {}
    for job_id in selected_ids:
        job = by_id[job_id]
        for index, requirement in enumerate(job["requirements"]):
            rule = mappings.get((job_id, index))
            item = evidence.get(rule.get("evidence_id")) if rule else None
            status = "有初步证据，尚未证明熟练" if item else "待确认，不等于不会"
            explanation = item["description"] if item else "当前没有足够证据作出能力结论。"
            # 学历只匹配本样本明确的层级条件，不推断专业或其他学历措辞。
            if job_id == "job_01" and index == 0 and profile.get("education", {}).get("degree") == "硕士":
                status, explanation = "自述符合学历层级", "用户自述数学硕士；未核验学历文件。"
            rows.append({"job_id": job_id, "requirement": requirement["summary"],
                         "quote": requirement["source_quote"], "status": status,
                         "evidence": explanation, "mapping_reviewed": bool(rule)})
            if rule:
                task_sources.setdefault(rule["task_key"], []).append({"job_id": job_id, "quote": requirement["source_quote"]})
    ordered = [key for key in ("prototype", "validation", "concepts", "domain") if key in task_sources]
    tasks = []
    if ordered:
        if minutes < 30:
            tasks = [{"title": "只检查一项岗位要求与用户证据的对应关系", "minutes": minutes,
                      "artifact": "一条带原文与能力状态的分析记录",
                      "acceptance": "不扩展为完整项目；没有证据时明确待确认",
                      "ai_action": "生成单条分析并解释依据", "user_action": "查看，必要时纠正事实",
                      "sources": task_sources[ordered[0]][:1]}]
        else:
            chosen = ordered[:min(3, minutes // 30)]
            each, remainder = divmod(minutes, len(chosen))
            tasks = [{**TASKS[key], "minutes": each + (1 if i < remainder else 0),
                      "sources": task_sources[key]} for i, key in enumerate(chosen)]
    return {
        "mode": "本地已审阅样本原型，无独立模型调用",
        "budget_minutes": minutes, "budget_scope": "项目学习开发，不包含另行安排的投递与面试",
        "selected_jobs": [by_id[j] for j in selected_ids], "assessments": rows, "tasks": tasks,
        "unallocated_minutes": minutes - sum(t["minutes"] for t in tasks),
        "alternatives": [],
        "limitations": ["截图缺少公司、职位名称、链接与发布日期，在招状态未核实。",
                        "未映射要求保持待确认，不自动推导训练任务。",
                        "相近岗位尚无充分验证，不凑满三个；未实现网页采集。",
                        "当前任务是首轮项目安排，尚不支持自动评价提交成果或证明用户掌握能力。"],
    }


def render_markdown(report):
    lines = ["# 求职准备报告", "", report["mode"], "", f"预算：{report['budget_minutes']} 分钟；{report['budget_scope']}。", ""]
    for job in report["selected_jobs"]:
        lines += [f"## {job['id']} · {job['category']}", "", f"来源：用户截图 `{job['filename']}`；{job['source_status']}。类别为推断。", ""]
        for row in (r for r in report["assessments"] if r["job_id"] == job["id"]):
            lines += [f"- **{row['requirement']}**：{row['status']}。{row['evidence']}", f"  - 原文：{row['quote']}"]
        lines += ["", "加分项（不升级为必需）："] + [f"- {p}" for p in job.get("preferred", [])]
        if not job.get("preferred"):
            lines += ["- 当前摘录没有单独标出的加分项。"]
        lines += [""]
    lines += ["## 当天行动", ""]
    for task in report["tasks"]:
        lines += [f"### {task['title']} · {task['minutes']} 分钟", "", f"产出：{task['artifact']}", "", f"验收：{task['acceptance']}", "", f"AI负责：{task['ai_action']}。用户：{task['user_action']}。", "", "依据："]
        lines += [f"- {s['job_id']}：{s['quote']}" for s in task["sources"]]
        lines += [""]
    if not report["tasks"]:
        lines += ["所选样本没有已审阅任务映射，暂不生成计划；需先在聊天中分析。", ""]
    lines += ["## 当前限制", ""] + [f"- {s}" for s in report["limitations"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=None)
    parser.add_argument("--jobs", nargs="+", default=["job_01", "job_02"])
    args = parser.parse_args()
    profile = read_json(ROOT / "data/profile.json")
    minutes = args.minutes if args.minutes is not None else int(profile["project_learning_hours_per_day"] * 60)
    report = build_report(profile, read_json(ROOT / "data/jobs.json")["samples"],
                          read_json(ROOT / "data/assessment_rules.json")["rules"], args.jobs, minutes)
    destination = ROOT / "output"
    destination.mkdir(exist_ok=True)
    name = f"report-{'-'.join(args.jobs)}-{minutes}min"
    (destination / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    path = destination / f"{name}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
