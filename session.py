"""聊天会话持久化：由聊天助手调用，用户无需编辑文件。

自然语言理解仍由当前聊天完成。这里保存消息、计划版本、提交与审阅记录。
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from coach import ROOT, build_report, read_json, render_markdown


class Session:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / "data/session.json"
        self.state = read_json(self.path) if self.path.exists() else {
            "version": 1, "messages": [], "plans": [], "active_plan_id": None,
            "submissions": [], "reviews": [], "profile_updates": []}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def message(self, role, text):
        if role not in ("user", "assistant") or not text.strip():
            raise ValueError("消息角色或内容无效")
        item = {"id": uuid4().hex, "role": role, "text": text,
                "at": datetime.now(timezone.utc).isoformat()}
        self.state["messages"].append(item)
        self.save()
        return item["id"]

    def update_profile(self, changes, source_message_id):
        self._user_message(source_message_id)
        allowed = {"project_learning_hours_per_day", "weekly_prep_hours", "target_directions"}
        if not changes or not set(changes) <= allowed:
            raise ValueError("不支持的资料字段")
        for key, value in changes.items():
            if key == "target_directions":
                if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
                    raise ValueError("方向需为非空文本列表")
            elif value is None and key == "weekly_prep_hours":
                continue
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= (24 if key == "project_learning_hours_per_day" else 168):
                raise ValueError("时间预算无效")
        self.state["profile_updates"].append({"changes": copy.deepcopy(changes), "source_message_id": source_message_id})
        self.save()

    def profile(self):
        result = read_json(ROOT / "data/profile.json")
        for update in self.state["profile_updates"]:
            result.update(update["changes"])
        return result

    def propose(self, minutes, jobs=None, reason="首次计划"):
        report = build_report(self.profile(), read_json(ROOT / "data/jobs.json")["samples"],
                              read_json(ROOT / "data/assessment_rules.json")["rules"],
                              jobs or ["job_01", "job_02"], minutes)
        item = {"id": uuid4().hex, "status": "proposed", "reason": reason,
                "previous_plan_id": self.state["active_plan_id"], "report": report}
        self.state["plans"].append(item)
        self.save()
        return item["id"]

    def _user_message(self, message_id):
        if not any(m["id"] == message_id and m["role"] == "user" for m in self.state["messages"]):
            raise ValueError("需要关联用户聊天消息")

    def plan(self, plan_id):
        return next(p for p in self.state["plans"] if p["id"] == plan_id)

    def activate(self, plan_id, source_message_id):
        # 聊天助手负责判断消息是否明确授权，不能仅凭消息存在推断同意。
        self._user_message(source_message_id)
        plan = self.plan(plan_id)
        if plan["status"] != "proposed":
            raise ValueError("只能采用待确认计划")
        old_id = self.state["active_plan_id"]
        if old_id:
            self.plan(old_id)["status"] = "superseded"
        plan.update(status="active", confirmation_message_id=source_message_id)
        self.state["active_plan_id"] = plan_id
        self.save()

    def submit(self, task_index, text, artifact_refs=None):
        plan_id = self.state["active_plan_id"]
        if not plan_id:
            raise ValueError("尚无当前计划")
        tasks = self.plan(plan_id)["report"]["tasks"]
        if isinstance(task_index, bool) or not isinstance(task_index, int) or not 0 <= task_index < len(tasks) or not text.strip():
            raise ValueError("任务编号或成果内容无效")
        item = {"id": uuid4().hex, "plan_id": plan_id, "task_index": task_index,
                "text": text, "artifact_refs": artifact_refs or [], "status": "awaiting_review"}
        self.state["submissions"].append(item)
        self.save()
        return item["id"]

    def review(self, submission_id, outcome, rationale, evidence_notes):
        # 非自动评分：聊天助手检查实际产出后提交判断及依据。
        if outcome not in ("needs_evidence", "needs_revision", "accepted") or not rationale.strip():
            raise ValueError("审阅结果或理由无效")
        item = next(s for s in self.state["submissions"] if s["id"] == submission_id)
        if outcome == "accepted" and not evidence_notes.strip():
            raise ValueError("验收通过必须记录实际审阅证据")
        self.state["reviews"].append({"submission_id": submission_id, "outcome": outcome,
                                      "rationale": rationale, "evidence_notes": evidence_notes})
        item["status"] = outcome
        self.save()

    def export(self, path):
        plan_id = self.state["active_plan_id"]
        if not plan_id:
            raise ValueError("尚无当前计划")
        text = render_markdown(self.plan(plan_id)["report"])
        text += "\n## 成果进展\n\n"
        for item in self.state["submissions"]:
            if item["plan_id"] == plan_id:
                text += f"- 任务 {item['task_index'] + 1}：{item['status']}。{item['text']}\n"
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
