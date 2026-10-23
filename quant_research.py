"""量化研究原型的最小数据与时间切分内核。

只生成研究用特征/标签，不执行交易、不提供投资建议。输入数据来源与复权方式须另行记录。
"""
from collections import defaultdict
from datetime import date


def _row(row):
    try:
        day = date.fromisoformat(row["date"])
        asset = str(row["asset"]).strip()
        close = float(row["close"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("每条记录必须包含有效的 date、asset、close") from None
    if not asset or close <= 0:
        raise ValueError("asset 不能为空，close 必须为正数")
    return {"date": day, "asset": asset, "close": close}


def validate_prices(records):
    """清洗后的最小字段检查；不假定数据已经复权或来自特定市场。"""
    grouped, seen = defaultdict(list), set()
    for source in records:
        row = _row(source)
        key = (row["date"], row["asset"])
        if key in seen:
            raise ValueError("同一资产同一日期存在重复价格")
        seen.add(key)
        grouped[row["asset"]].append(row)
    if not grouped:
        raise ValueError("至少需要一条价格记录")
    for asset in grouped:
        grouped[asset].sort(key=lambda item: item["date"])
    return grouped


def make_return_observations(records, lookback=1, horizon=1):
    """构造过去收益率特征和未来收益率标签。

    feature_date 当天的 past_return 只使用当天及之前价格；forward_return 仅是供后续评估使用的标签。
    """
    if isinstance(lookback, bool) or isinstance(horizon, bool) or not isinstance(lookback, int) or not isinstance(horizon, int) or lookback < 1 or horizon < 1:
        raise ValueError("lookback 与 horizon 必须为正整数")
    grouped = validate_prices(records)
    output = []
    for asset, rows in grouped.items():
        for index in range(lookback, len(rows) - horizon):
            now, past, future = rows[index], rows[index - lookback], rows[index + horizon]
            output.append({
                "asset": asset,
                "feature_date": now["date"],
                "target_date": future["date"],
                "past_return": now["close"] / past["close"] - 1,
                "forward_return": future["close"] / now["close"] - 1,
            })
    return sorted(output, key=lambda item: (item["feature_date"], item["asset"]))


def chronological_split(observations, cutoff):
    """按日期划分训练/验证，确保训练标签在 cutoff 前结束，避免标签跨界泄漏。"""
    try:
        cutoff_day = date.fromisoformat(cutoff) if isinstance(cutoff, str) else cutoff
    except ValueError:
        raise ValueError("cutoff 必须是 YYYY-MM-DD") from None
    if not isinstance(cutoff_day, date):
        raise ValueError("cutoff 必须是 YYYY-MM-DD")
    train = [item for item in observations if item["target_date"] < cutoff_day]
    validation = [item for item in observations if item["feature_date"] >= cutoff_day]
    if not train or not validation:
        raise ValueError("切分后训练集或验证集为空；请调整 cutoff 或增加数据")
    return {"train": train, "validation": validation, "cutoff": cutoff_day}
