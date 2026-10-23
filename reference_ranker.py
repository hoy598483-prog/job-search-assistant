"""参考资料排序与用途限制。

发布时间决定时效度；站内浏览量决定阅读优先级；来源和原文决定能否支撑结论。
不跨平台比较原始浏览量。
"""
from datetime import date


KINDS = {"official_job", "official_technical", "community_experience", "user_artifact"}
USES = {"market_requirement", "implementation_constraint", "project_pattern", "user_problem_hypothesis", "completion_evidence"}


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("published_at 必须为 YYYY-MM-DD") from None


def freshness_level(published_at, today=None):
    days = ((today or date.today()) - parse_date(published_at)).days
    if days < 0:
        return "invalid_future_date"
    if days <= 30:
        return "current"
    if days <= 180:
        return "recent"
    if days <= 365:
        return "aging"
    return "historical"


def engagement_level(reference):
    """浏览量只在同一平台、同一内容类型的分位档可比较。"""
    engagement = reference.get("engagement")
    if not engagement:
        return "unavailable"
    percentile = engagement.get("platform_percentile")
    if not isinstance(percentile, (int, float)) or isinstance(percentile, bool) or not 0 <= percentile <= 100:
        return "unavailable"
    if percentile >= 90:
        return "high"
    if percentile >= 50:
        return "medium"
    return "low"


def assess(reference, today=None):
    required = {"id", "source_kind", "platform", "url_or_user_provided", "published_at", "collected_at", "quote", "use", "review_status"}
    if not required <= set(reference) or reference["source_kind"] not in KINDS or reference["use"] not in USES:
        raise ValueError("参考资料字段或类别无效")
    if not isinstance(reference["quote"], str) or not reference["quote"].strip():
        raise ValueError("影响计划的参考必须有原文引用")
    fresh = freshness_level(reference["published_at"], today)
    if fresh == "invalid_future_date":
        raise ValueError("发布时间不能晚于评估日期")
    engagement = engagement_level(reference)
    permitted = {
        "official_job": {"market_requirement"},
        "official_technical": {"implementation_constraint"},
        "community_experience": {"project_pattern", "user_problem_hypothesis"},
        "user_artifact": {"completion_evidence"},
    }[reference["source_kind"]]
    can_drive_plan = reference["review_status"] == "reviewed" and reference["use"] in permitted
    return {
        "freshness": fresh,
        "engagement_priority": engagement,
        "permitted_use": sorted(permitted),
        "can_drive_plan": can_drive_plan,
        "explanation": (
            "发布时间用于判断时效度；浏览量分位用于决定阅读优先级；来源类型、原文引用和人工审阅决定能否影响计划。"
        ),
    }
