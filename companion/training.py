from uuid import uuid4

PROJECT_OPTIONS = [
    {"id": "browser-companion", "title": "浏览器求职助理", "reason": "适合练习页面上下文、来源追溯、权限和 Agent 工作流。", "deliverable": "Chrome MVP、来源证据和七天演示", "difficulty": "中"},
    {"id": "knowledge-rag", "title": "企业知识库 RAG 助手", "reason": "适合练习检索、引用、拒答和评测。", "deliverable": "带引用的问答原型和评测记录", "difficulty": "中"},
    {"id": "product-research", "title": "AI 产品需求研究助手", "reason": "适合练习用户问题、需求假设和验证闭环。", "deliverable": "问题地图、功能假设和验证记录", "difficulty": "低"},
]

MILESTONES = [
    ("定义浏览器求职流程", "记录一次真实浏览岗位时的困难", "一张用户流程卡", "写明输入、输出、未知信息和禁止动作"),
    ("采集与来源", "采集同类岗位样本并检查原文", "两至五份页面快照", "样本属于同一岗位类别；来源和采集时间可追溯"),
    ("结构化提取", "审阅一条要求的引用及条件关系", "一条已审阅提取记录", "优先不变成必须；择一不变成全部"),
    ("多页面比较", "比较两个已采集岗位的要求", "一张比较表", "每项差异有各自来源；未知不补全"),
    ("类别能力地图", "从已审阅样本归纳共同与定向能力", "一张类别能力地图", "共同要求、定向要求和不确定项分开；每项保留样本引用"),
    ("反馈与失败修复", "提交一个成果并记录一项实际失败", "成果和修复记录", "待审阅不自动通过；保留失败输入和复测结果"),
    ("演示与复盘", "演示采集、分析、比较、收藏和训练", "三分钟演示与限制说明", "区分真实模型结果、离线结果与尚未实现能力"),
]


def candidate_options():
    return {"options": PROJECT_OPTIONS, "notice": "请先选择一个主项目；浏览器伴侣只是推荐项，不会自动成为计划。"}


def propose_training(session, minutes, project_id):
    selected = next((item for item in PROJECT_OPTIONS if item["id"] == project_id), None)
    if selected is None:
        raise ValueError("请从项目候选中选择一个有效项目")
    tasks = []
    for day, (title, action, artifact, acceptance) in enumerate(MILESTONES, 1):
        tasks.append(dict(day=day, title=title, action=action,
                          scope="只处理一个例子；未完成部分保留到后续" if minutes < 60 else "完成最小功能并复测一个边界例子",
                          minutes=minutes, artifact=artifact, acceptance=acceptance))
    plan = dict(id=uuid4().hex, status="proposed", reason=f"用户选择项目：{selected['title']}",
                previous_plan_id=session.state["active_plan_id"], selected_project=selected,
                report={"tasks": tasks, "type": "user_selected_project_template"})
    session.state["plans"].append(plan)
    session.save()
    return {"plan": plan, "notice": "这是待确认草案；用户确认后才会成为当前计划。"}


def adopt_training(session, plan_id):
    plan = session.plan(plan_id)
    if plan["status"] != "proposed":
        raise ValueError("只能采用待确认的计划草案")
    message = session.message("user", f"确认采用项目：{plan['selected_project']['title']}")
    session.activate(plan_id, message)
    return {"plan": session.plan(plan_id), "notice": "已采用用户选择的计划。"}
