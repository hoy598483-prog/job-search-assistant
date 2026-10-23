import copy
import json
import re


def _clean_json(raw):
    if isinstance(raw, dict):
        return raw
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip()).strip()
    return json.loads(text)


def _day_text(plan, number):
    day = next((d for d in plan.get("days", []) if d.get("day") == number), None)
    if not day:
        return "当前计划中找不到对应日期，请重新生成计划。"
    return (f"第 {number} 天：{day['goal']}\n任务：{day['tasks']}\n"
            f"预计：{day['estimated_minutes']} 分钟\n交付物：{day['deliverable']}\n"
            f"验收方法：{day['acceptance']}")


def _valid_plan(plan, budget):
    if not isinstance(plan, dict) or not isinstance(plan.get("days"), list):
        return False
    days = plan["days"]
    if len(days) != 7 or [d.get("day") for d in days if isinstance(d, dict)] != list(range(1, 8)):
        return False
    for day in days:
        if any(not isinstance(day.get(k), str) or not day[k].strip()
               for k in ("goal", "tasks", "deliverable", "acceptance")):
            return False
        try:
            minutes = int(day.get("estimated_minutes", 0))
        except (TypeError, ValueError):
            return False
        if not 1 <= minutes <= budget:
            return False
    return True


def _budget_minutes(value):
    text = str(value or "").strip().lower()
    try:
        return int(text)
    except ValueError:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(小时|h|hour)", text)
        if match:
            return int(float(match.group(1)) * 60)
        match = re.search(r"(\d+)\s*(分钟|min)", text)
        return int(match.group(1)) if match else 0


def _selected_option(state, query):
    options = state.get("project_options") or []
    text = query.strip()
    match = re.fullmatch(r"(?:我选|选择|选)?\s*([1-3])\s*(?:号|个|项|计划|项目|\.?)?", text)
    if not match:
        match = re.fullmatch(r"(?:我选|选择|选)?\s*(第?[一二三])\s*(?:个|项)?\s*(?:计划|项目)?", text)
    if match:
        number = match.group(1)
        index = (int(number) if number.isdigit() else {"一": 1, "二": 2, "三": 3,
                 "第一": 1, "第二": 2, "第三": 3}[number]) - 1
        return options[index] if index < len(options) else None
    return next((item for item in options if item.get("name") == text), None)


def _fallback_plan(project, budget):
    name = project["name"]
    if "调研" in name and "用户" in name:
        steps = [
            ("界定调研问题", "写目标用户、待验证假设和样本获取方式", "一页调研方案", "含用户定义、3个假设和招募渠道"),
            ("设计问卷", "写筛选题与8至12个中性问题", "问卷初稿", "每题标注对应假设，无诱导性问法"),
            ("试测问卷", "找2至3人试填或模拟认知访谈，记录歧义", "试测记录与修订版", "列出至少3处问题及修改理由"),
            ("执行招募", "发布问卷并记录渠道与响应情况", "招募台账", "记录发送数、有效回复数与偏差；不足时如实标注"),
            ("清洗反馈", "剔除无效回答并按问题编码", "匿名反馈表", "保留原始回答、清洗规则和有效样本数"),
            ("形成发现", "汇总主要模式、反例与样本限制", "初步分析报告", "每条发现有数据依据且写明不能外推的范围"),
            ("完成展示", "整理调研过程、结论和下一步验证", "作品集案例", "可说明方法、证据、局限与下一步"),
        ]
    elif "知识库" in name or "RAG" in name:
        steps = [
            ("界定场景", "选一个真实使用场景并列出10个用户问题", "场景与问题清单", "含目标用户、边界和10个可回答问题"),
            ("整理资料", "收集公开或自有资料并保留出处", "资料目录", "至少10个条目各有来源与更新时间"),
            ("设计结构", "定义条目字段、分类和检索入口", "知识库结构图", "每个条目可定位来源、主题和适用范围"),
            ("搭建原型", "录入条目并完成基本搜索或检索", "可操作原型", "输入问题可返回相关条目"),
            ("设计引用", "为回答加入来源引用和未命中提示", "引用与未命中样例", "至少3个回答有出处，未知问题明确说未命中"),
            ("测试改进", "运行10个测试问题并记录错误", "测试记录", "有命中、误答、未命中统计及修改项"),
            ("整理展示", "写使用说明、效果和局限", "演示与作品集页", "能现场演示3个问题并解释来源"),
        ]
    else:
        steps = [
            ("明确研究范围", "定义用户、竞品范围和对比维度", "研究框架", "包含目标问题、5个候选竞品和比较维度"),
            ("收集一手材料", "查看竞品官网和公开文档并记出处", "竞品来源表", "至少5个竞品各有可访问来源与发布日期或访问日期"),
            ("制作竞品矩阵", "比较功能、目标用户和差异点", "竞品矩阵", "5个竞品均有功能证据与原文短引"),
            ("补充用户问题", "收集公开反馈并区分事实与观点", "需求证据表", "每条观察保留出处，无法核实者标注未核实"),
            ("提出机会假设", "从矩阵和反馈中提出2至3个机会", "机会假设卡", "每个假设写目标用户、依据和反证条件"),
            ("设计验证", "选一个机会做低成本原型或访谈提纲", "验证方案", "含可观察指标、样本和通过标准"),
            ("完成报告", "整理方法、发现、建议与限制", "市场研究报告", "覆盖至少5个竞品，有引用、结论和局限"),
        ]
    days = []
    for number, (goal, tasks, deliverable, acceptance) in enumerate(steps, 1):
        days.append({"day": number, "goal": goal, "tasks": tasks,
                     "estimated_minutes": min(budget, 120), "deliverable": deliverable,
                     "acceptance": acceptance, "status": "not_started", "review": ""})
    return {"project": name, "daily_budget_minutes": budget, "current_day": 1, "days": days}


def _create_from_selection(state, option):
    budget = _budget_minutes(state["profile"].get("daily_minutes"))
    if budget < 1:
        return {"state": state, "reply": "已选“" + option["name"] + "”。请告诉我每天用于项目训练的时间，例如“每天 120 分钟”或“每天 2 小时”。"}
    if state.get("plan", {}).get("days"):
        return {"state": state, "reply": "已保存的计划仍保留。如需重做，请说明要调整的内容。"}
    plan = _fallback_plan(option, budget)
    state["selected_project"] = option["name"]
    state["plan"] = plan
    state["status"] = "active"
    return {"state": state, "reply": "已选择“" + option["name"] + "”。个性化计划未通过校验，先保存七天基础计划供你开始；你可以随时要求按背景调整。\n\n" +
            _day_text(plan, 1) + "\n\n完成后请提交可检查的成果。"}


def _add_inputs(state, proposal, query):
    updates = proposal.get("profile_updates") or {}
    if isinstance(updates, dict):
        for key in ("role_group", "background", "daily_minutes", "city"):
            value = updates.get(key)
            if isinstance(value, str) and value.strip():
                state["profile"][key] = value.strip()
        legacy_jd = updates.get("job_briefs")
        if isinstance(legacy_jd, str) and legacy_jd.strip() and legacy_jd.strip() in query:
            proposal.setdefault("new_jobs", []).append({"title": "用户提供的岗位", "raw_text": legacy_jd.strip(), "source_url": ""})

    jobs = proposal.get("new_jobs") or []
    if isinstance(jobs, list):
        for item in jobs[:10]:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("raw_text") or "").strip()
            if len(raw) < 10 or raw not in query or any(j["raw_text"] == raw for j in state["jobs"]):
                continue
            state["jobs"].append({"id": "JD-" + str(len(state["jobs"]) + 1),
                                  "title": str(item.get("title") or "未命名岗位")[:100],
                                  "raw_text": raw[:12000],
                                  "source_url": str(item.get("source_url") or "")[:1000]})

    refs = proposal.get("new_references") or []
    if isinstance(refs, list):
        for item in refs[:10]:
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote") or "").strip()
            if len(quote) < 8 or quote not in query:
                continue
            url = str(item.get("url") or "")[:1000]
            if any(r["quote"] == quote and r["url"] == url for r in state["references"]):
                continue
            source_type = str(item.get("source_type") or "user_supplied")
            if source_type not in ("official", "community", "user_supplied"):
                source_type = "user_supplied"
            # A pasted quote and URL are user-supplied until an external retrieval verifies them.
            state["references"].append({"source_type": source_type,
                "platform": str(item.get("platform") or "")[:100], "url": url,
                "published_at": str(item.get("published_at") or "")[:40],
                "collected_at": str(item.get("collected_at") or "")[:40],
                "views": str(item.get("views") or "")[:40], "quote": quote[:1500],
                "use": str(item.get("use") or "")[:300], "verification": "user_supplied_unverified"})


def main(raw: str, prior_state: dict, user_query: str) -> dict:
    state = copy.deepcopy(prior_state) if isinstance(prior_state, dict) else {}
    state.setdefault("workspace_id", "ai-product-job-agent")
    state.setdefault("profile", {})
    state.setdefault("jobs", [])
    state.setdefault("references", [])
    state.setdefault("project_options", [])
    state.setdefault("selected_project", "")
    state.setdefault("plan", {})
    state.setdefault("status", "collecting")
    state.setdefault("submissions", [])
    if state["workspace_id"] != "ai-product-job-agent":
        return {"state": state, "reply": "当前对话的工作分区不匹配，请在对应工作区继续。"}

    option = _selected_option(state, user_query)

    try:
        proposal = _clean_json(raw)
        if not isinstance(proposal, dict):
            raise ValueError("Output is not an object")
    except (json.JSONDecodeError, ValueError, TypeError):
        if option is not None:
            return _create_from_selection(state, option)
        return {"state": state, "reply": "我没有正确处理这条信息，请再发一次。已有资料和计划仍保留。"}

    _add_inputs(state, proposal, user_query)
    if option is not None:
        budget = _budget_minutes(state["profile"].get("daily_minutes"))
        generated = proposal.get("plan")
        if budget > 0 and _valid_plan(generated, budget) and not state.get("plan", {}).get("days"):
            state["selected_project"] = option["name"]
            plan = copy.deepcopy(generated)
            plan["project"] = option["name"]
            plan["daily_budget_minutes"] = budget
            plan["current_day"] = 1
            for day in plan["days"]:
                day["status"] = "not_started"
                day["review"] = ""
            state["plan"] = plan
            state["status"] = "active"
            return {"state": state, "reply": "已按你的背景生成并保存七天计划。\n\n" +
                    _day_text(plan, 1) + "\n\n完成后请提交可检查的成果。"}
        return _create_from_selection(state, option)
    action = proposal.get("action", "other")
    reply = proposal.get("reply") if isinstance(proposal.get("reply"), str) else ""

    if action == "collect":
        if not state.get("plan"):
            state["status"] = "collecting"
        return {"state": state, "reply": reply or "请补充岗位类别、招聘要求、个人背景和每天训练时间。"}

    if action == "analyze":
        options = proposal.get("project_options")
        if isinstance(options, list) and 2 <= len(options) <= 3:
            valid = [o for o in options if isinstance(o, dict) and
                     all(str(o.get(k) or "").strip() for k in ("name", "reason", "deliverable", "acceptance"))]
            if len(valid) == len(options):
                state["project_options"] = valid
        if not state.get("plan"):
            state["status"] = "choosing_project"
        return {"state": state, "reply": reply or "已记录资料。请选择一个项目。"}

    if action == "create_plan":
        budget = _budget_minutes(state["profile"].get("daily_minutes"))
        plan = proposal.get("plan")
        choice = proposal.get("selected_project") or state.get("selected_project", "")
        if budget < 1:
            return {"state": state, "reply": "还缺少每天用于项目训练的时间，例如“每天 120 分钟”。原计划仍保留。"}
        if not isinstance(choice, str) or not choice.strip():
            return {"state": state, "reply": "还没有确定项目。请回复项目编号或名称。"}
        if not _valid_plan(plan, budget):
            option = next((o for o in state["project_options"] if o.get("name") == choice.strip()), None)
            if option and not state.get("plan", {}).get("days"):
                return _create_from_selection(state, option)
            return {"state": state, "reply": "生成的七天计划未通过格式校验；原计划仍保留。请明确选择已列出的项目编号。"}
        if state.get("plan", {}).get("days") and not any(x in user_query for x in ("重做计划", "重新生成计划", "调整计划", "修改计划")):
            return {"state": state, "reply": "已有计划仍保留。若想重做，请明确说‘调整计划’并说明变化。"}
        state["selected_project"] = choice.strip()
        plan = copy.deepcopy(plan)
        plan["project"] = choice.strip()
        plan["daily_budget_minutes"] = budget
        plan["current_day"] = 1
        for day in plan["days"]:
            day["status"] = "not_started"
            day["review"] = ""
        state["plan"] = plan
        state["status"] = "active"
        return {"state": state, "reply": "已保存七天计划。\n\n" + _day_text(plan, 1) + "\n\n完成后请提交可检查的成果。"}

    if action == "show_today":
        plan = state.get("plan") or {}
        if not plan.get("days"):
            return {"state": state, "reply": "还没有保存训练计划。请先选择一个项目。"}
        if state.get("status") == "completed":
            return {"state": state, "reply": "七天计划已完成。你可以提交最终作品供复盘。"}
        return {"state": state, "reply": _day_text(plan, int(plan.get("current_day", 1)))}

    if action == "review":
        plan = state.get("plan") or {}
        if not plan.get("days"):
            return {"state": state, "reply": "还没有保存训练计划。请先选择一个项目。"}
        number = int(plan.get("current_day", 1))
        if not 1 <= number <= 7:
            return {"state": state, "reply": "计划日期无效，请检查当前计划。"}
        review = proposal.get("review") or {}
        if not isinstance(review, dict):
            review = {}
        feedback = str(review.get("feedback") or "请补充可检查的成果。")
        evidence = str(review.get("evidence") or "").strip()
        passed = review.get("status") == "passed" and len(evidence) >= 8 and evidence in user_query and len(user_query.strip()) > 12
        today = plan["days"][number - 1]
        today["review"] = feedback
        state["submissions"].append({"day": number, "evidence": evidence[:500] if evidence in user_query else "",
                                      "result": "passed" if passed else "revise", "feedback": feedback[:500]})
        if passed:
            today["status"] = "passed"
            if number == 7:
                state["status"] = "completed"
                return {"state": state, "reply": "第 7 天已通过。" + feedback + "\n七天计划完成，请整理最终作品用于投递。"}
            plan["current_day"] = number + 1
            return {"state": state, "reply": "第 " + str(number) + " 天通过。" + feedback + "\n\n" + _day_text(plan, number + 1)}
        today["status"] = "revise"
        revision = str(review.get("revision_task") or "请提交能按验收标准检查的交付物。")
        return {"state": state, "reply": "第 " + str(number) + " 天仍需修改。" + feedback + "\n修改动作：" + revision}

    return {"state": state, "reply": reply or "请告诉我想分析的岗位、所选项目，或提交今天的成果。"}
