"""工作分区注册表。

每个分区拥有独立的目标、计划、参考资料、成果和消息记录。跨分区共享必须显式登记；
本模块不自动合并任何分区的资料或结论。
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKSPACE_ID = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class WorkspaceStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else ROOT / "data" / "workspaces"
        self.index_path = self.root / "index.json"

    def _index(self):
        if not self.index_path.exists():
            return {"version": 1, "active_workspace_id": None, "workspaces": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self, index):
        write_json(self.index_path, index)

    def _state_path(self, workspace_id):
        return self.root / f"{workspace_id}.json"

    def create(self, workspace_id, title, objective, status="ready"):
        if not WORKSPACE_ID.fullmatch(workspace_id):
            raise ValueError("工作分区 ID 必须为小写字母开头的连字符标识")
        if not isinstance(title, str) or not title.strip() or not isinstance(objective, str) or not objective.strip():
            raise ValueError("工作分区需要非空标题和目标")
        index = self._index()
        if any(item["id"] == workspace_id for item in index["workspaces"]):
            raise ValueError("工作分区已存在")
        state = {"version": 1, "id": workspace_id, "title": title, "objective": objective,
                 "status": status, "references": [], "plans": [], "artifacts": [], "messages": [],
                 "shared_from": [], "created_at": now(), "updated_at": now()}
        write_json(self._state_path(workspace_id), state)
        index["workspaces"].append({"id": workspace_id, "title": title, "status": status})
        if index["active_workspace_id"] is None:
            index["active_workspace_id"] = workspace_id
        self._save_index(index)
        return state

    def load(self, workspace_id):
        path = self._state_path(workspace_id)
        if not path.exists():
            raise ValueError("工作分区不存在")
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, state):
        state["updated_at"] = now()
        write_json(self._state_path(state["id"]), state)

    def activate(self, workspace_id):
        self.load(workspace_id)
        index = self._index()
        index["active_workspace_id"] = workspace_id
        self._save_index(index)

    def active(self):
        workspace_id = self._index()["active_workspace_id"]
        if not workspace_id:
            raise ValueError("尚无活动工作分区")
        return self.load(workspace_id)

    def append(self, workspace_id, collection, record):
        if collection not in {"references", "plans", "artifacts", "messages"}:
            raise ValueError("不支持的工作分区记录类型")
        if not isinstance(record, dict):
            raise ValueError("记录必须为对象")
        state = self.load(workspace_id)
        state[collection].append(record)
        self.save(state)

    def explicitly_share(self, recipient_id, source_id, description):
        """仅登记共享关系，不复制来源内容，防止无意的上下文混合。"""
        if recipient_id == source_id or not isinstance(description, str) or not description.strip():
            raise ValueError("共享来源和说明无效")
        self.load(source_id)
        recipient = self.load(recipient_id)
        item = {"workspace_id": source_id, "description": description, "shared_at": now()}
        if item["workspace_id"] not in {entry["workspace_id"] for entry in recipient["shared_from"]}:
            recipient["shared_from"].append(item)
            self.save(recipient)


def initialize(store):
    defaults = [
        ("ai-product-job-agent", "AI 产品求职 Agent", "构建可追溯的岗位类别分析、项目计划与成果反馈闭环。", "active"),
        ("quant-smallcap-strategy", "小市值量化策略", "独立开展小市值策略研究、数据验证与可复现回测；不与 AI 产品工作混合。", "ready"),
    ]
    existing = {item["id"] for item in store._index()["workspaces"]}
    for workspace_id, title, objective, status in defaults:
        if workspace_id not in existing:
            store.create(workspace_id, title, objective, status)
    store.activate("ai-product-job-agent")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "list", "active", "use"])
    parser.add_argument("workspace_id", nargs="?")
    args = parser.parse_args()
    store = WorkspaceStore()
    if args.command == "init":
        initialize(store)
    elif args.command == "use":
        if not args.workspace_id:
            raise SystemExit("use 需要 workspace_id")
        store.activate(args.workspace_id)
    if args.command in {"init", "list"}:
        print(json.dumps(store._index(), ensure_ascii=False, indent=2))
    elif args.command == "active":
        print(json.dumps(store.active(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
