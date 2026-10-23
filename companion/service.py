import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from companion.providers import analyze
from session import Session
from workspace_manager import WorkspaceStore, WORKSPACE_ID


def safe_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError("来源 URL 无效")
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("只接受不含登录凭据的 HTTP(S) 来源")
    # No URL is fetched server-side. Strip fragments; preserve job-identifying query strings.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


class Companion:
    def __init__(self, root):
        self.root = Path(root)
        self.store = WorkspaceStore(self.root / "data/workspaces")
        self.directory = self.root / "output/companion"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "jobs.db"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (workspace TEXT, id TEXT, payload TEXT, status TEXT, PRIMARY KEY(workspace,id))")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def route(self, workspace, direction=None):
        if not isinstance(workspace, str) or not WORKSPACE_ID.fullmatch(workspace):
            raise ValueError("工作分区无效")
        try:
            self.store.load(workspace)
        except ValueError:
            if not isinstance(direction, dict):
                raise
            title, objective = direction.get("name"), direction.get("target")
            if not isinstance(title, str) or not title.strip() or len(title) > 80:
                raise ValueError("方向名称无效")
            if not isinstance(objective, str) or len(objective) > 4000:
                raise ValueError("岗位目标无效")
            self.store.create(workspace, title, objective.strip() or title)
        return workspace

    def audit(self, action, workspace, outcome):
        # Do not log page text, tokens, personal profile or model stderr.
        record = dict(at=datetime.now(timezone.utc).isoformat(), action=action, workspace=workspace, outcome=outcome)
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError("请求需为对象")
        workspace = self.route(request.get("workspace"), request.get("direction"))
        action = request.get("action")
        if action not in {"resume_analyze", "resume_extract", "chat", "provider_status", "provider_login", "analyze", "save", "list", "status", "training", "propose", "adopt", "submit", "progress"}:
            raise ValueError("不支持此动作；禁止投递、填写申请和联系招聘方")
        if action in {"resume_analyze", "chat", "save", "status", "propose", "adopt", "submit"} and request.get("approved") is not True:
            raise ValueError("写入操作需要明确确认")
        if action == "resume_analyze":
            from companion.resume_text import analyze_pdf
            return analyze_pdf(request.get("file"))
        if action == "resume_extract":
            from companion.resume_text import extract_resume
            return extract_resume(request.get("name"), request.get("file"))
        if action == "chat":
            from companion.providers import chat
            result = chat(request.get("messages"), request.get("samples", []))
            self.audit(action, workspace, "ok")
            return result
        if action in {"provider_status", "provider_login"}:
            import shutil
            import subprocess
            from companion.cli_paths import find_codex
            executable = find_codex()
            if not executable:
                return {"installed": False, "authenticated": False, "notice": "未找到 Codex CLI，请先安装"}
            if action == "provider_login":
                if request.get("approved") is not True:
                    raise ValueError("启动官方登录需要确认")
                subprocess.Popen([executable, "login"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {"notice": "已启动官方 CLI 登录，请在浏览器完成后点击重新检查登录"}
            try:
                status = subprocess.run([executable, "login", "status"], capture_output=True, timeout=15)
                return {"installed": True, "authenticated": status.returncode == 0,
                        "notice": "Codex 已登录；模型调用尚未验证" if status.returncode == 0 else "Codex 未登录，请启动官方登录"}
            except subprocess.TimeoutExpired:
                raise ValueError("Codex 登录检查超时") from None
        if action == "analyze":
            pages = request.get("pages")
            if not isinstance(pages, list) or not 1 <= len(pages) <= 6:
                raise ValueError("每次选择 1–6 个页面")
            provider = request.get("provider", "mock")
            if provider != "mock" and request.get("approved") is not True:
                raise ValueError("发送页面至模型前需要确认")
            results, seen = [], set()
            for page in pages:
                if not isinstance(page, dict):
                    raise ValueError("页面数据无效")
                source = page.get("text")
                if not isinstance(source, str) or not source.strip() or len(source) > 60000:
                    raise ValueError("页面文本需为 1–60000 字符")
                key = hashlib.sha256(source.encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                result = analyze(source, provider)
                result.update(id=key, url="", title="文本样本",
                              captured_at=str(page.get("captured_at", ""))[:80],
                              official_status="UNVERIFIED", official_url=None)
                results.append(result)
            self.audit(action, workspace, "ok")
            return {"results": results, "comparison": "按来源逐列呈现；未判断录用概率或跨来源语义重复。"}
        if action == "save":
            page = request.get("page", {})
            source = page.get("text")
            if not isinstance(source, str) or not source.strip() or len(source) > 60000:
                raise ValueError("文本样本需为 1–60000 字符")
            result = {"items": []}
            key = hashlib.sha256(source.encode()).hexdigest()
            result.update(id=key, url="", title="文本样本",
                          captured_at=str(page.get("captured_at", ""))[:80],
                          saved_at=datetime.now(timezone.utc).isoformat(),
                          official_status="UNVERIFIED", official_url=None)
            with self.connect() as db:
                db.execute("INSERT INTO jobs VALUES(?,?,?,?) ON CONFLICT(workspace,id) DO UPDATE SET payload=excluded.payload",
                           (workspace, key, json.dumps(result, ensure_ascii=False), "saved"))
            response = {"saved": key, "notice": "保存原文快照；未将模型结论导入能力或计划。"}
        elif action == "list":
            with self.connect() as db:
                rows = db.execute("SELECT payload,status FROM jobs WHERE workspace=?", (workspace,)).fetchall()
            return {"jobs": [dict(json.loads(payload), status=status) for payload, status in rows]}
        elif action == "status":
            status = request.get("status")
            if status not in {"saved", "considering", "applied_manually", "interview", "offer", "rejected", "archived"}:
                raise ValueError("状态无效")
            with self.connect() as db:
                count = db.execute("UPDATE jobs SET status=? WHERE workspace=? AND id=?", (status, workspace, request.get("id"))).rowcount
                if not count:
                    raise ValueError("岗位不在当前工作分区")
            response = {"status": status}
        else:
            # Separate per-workspace state; reuse existing submissions/reviews/history.
            session = Session(self.directory / (workspace + "-session.json"))
            if action == "training":
                from companion.training import candidate_options
                response = candidate_options()
            elif action == "propose":
                minutes = request.get("minutes")
                if type(minutes) is not int or not 15 <= minutes <= 120:
                    raise ValueError("每天预算为 15–120 分钟")
                from companion.training import propose_training
                response = propose_training(session, minutes, request.get("project_id"))
            elif action == "adopt":
                from companion.training import adopt_training
                response = adopt_training(session, request.get("plan_id"))
            elif action == "submit":
                day = request.get("day", 1)
                if type(day) is not int or not 1 <= day <= 7:
                    raise ValueError("成果天数需为 1–7 的整数")
                text = request.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > 10000:
                    raise ValueError("请提供成果说明（最多10000字符）")
                response = {"submission_id": session.submit(day - 1, text), "status": "awaiting_review"}
            else:
                response = session.state
        self.audit(action, workspace, "ok")
        return response
