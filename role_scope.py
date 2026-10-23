"""按岗位类别聚合已审阅招聘简介。

语义归并（capability_key）必须在提取与人工/模型审阅后给出；本模块不靠关键词猜测技能相同。
"""
from collections import defaultdict


def build_skill_map(briefs):
    """返回一个类别岗位的能力地图。

    brief: {id, role_group, priority: 1..5, status: reviewed,
            items: [{capability_key, summary, quote, kind, relation}]}
    """
    if not briefs:
        raise ValueError("至少需要一条已审阅招聘简介")
    group = briefs[0].get("role_group")
    if not isinstance(group, str) or not group.strip() or any(b.get("role_group") != group for b in briefs):
        raise ValueError("所有简介必须属于同一个非空岗位类别")
    buckets = defaultdict(list)
    for brief in briefs:
        if brief.get("status") != "reviewed":
            raise ValueError("只有已审阅简介可进入类别计划")
        priority = brief.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 5:
            raise ValueError("岗位优先级必须为1至5")
        for item in brief.get("items", []):
            if item.get("kind") not in {"required", "preferred", "duty", "unclear"}:
                raise ValueError("简介条目类别无效")
            key = item.get("capability_key")
            if not isinstance(key, str) or not key.strip() or not isinstance(item.get("quote"), str) or not item["quote"].strip():
                raise ValueError("能力归类与原文引用不能为空")
            buckets[key].append({"brief_id": brief["id"], "priority": priority, **item})

    map_items = []
    for key, evidence in buckets.items():
        required = [item for item in evidence if item["kind"] == "required"]
        target_briefs = {item["brief_id"] for item in required}
        highest_priority = max(item["priority"] for item in evidence)
        if len(target_briefs) >= 2:
            placement = "core"
        elif required and highest_priority >= 4:
            placement = "targeted"
        elif required:
            placement = "watch"
        else:
            placement = "optional"
        map_items.append({
            "capability_key": key,
            "summary": evidence[0]["summary"],
            "placement": placement,
            "required_brief_count": len(target_briefs),
            "highest_priority": highest_priority,
            "evidence": [{"brief_id": item["brief_id"], "kind": item["kind"],
                          "relation": item.get("relation", "unclear"), "quote": item["quote"]} for item in evidence],
        })
    rank = {"core": 0, "targeted": 1, "watch": 2, "optional": 3}
    return {"role_group": group, "brief_count": len(briefs),
            "items": sorted(map_items, key=lambda item: (rank[item["placement"]], -item["highest_priority"], item["summary"]))}
