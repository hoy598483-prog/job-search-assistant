"""Reproducible JD-extraction evaluation: offline baseline or saved predictions.

This deliberately does NOT call a model, a browser, or an external service.
Metrics on synthetic fixtures are regression checks, not production accuracy.
Run: python -m evaluations.agent_benchmark --baseline
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from extract_job import validate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = Path(__file__).with_name("synthetic_cases.json")
LABELS = {
    "岗位职责": "duty", "职责": "duty",
    "任职要求": "required", "职位要求": "required",
    "加分项": "preferred", "优先条件": "preferred",
}
ANY_OF = ("至少一项", "任一", "其中之一", "之一")
ALL_OF = ("和", "以及", "并且", "并能", "同时", "、")


def simple_baseline(source):
    """Intentionally weak, transparent line-prefix baseline; no gold-label access."""
    items = []
    for line in source.splitlines():
        heading, separator, quote = line.strip().partition("：")
        kind = LABELS.get(heading.strip())
        if not separator or not kind or not quote.strip():
            continue
        quote = quote.strip()
        if "优先" in quote or "加分" in quote:
            kind = "preferred"
        relation = "any_of" if any(x in quote for x in ANY_OF) else (
            "all_of" if any(x in quote for x in ALL_OF) else "single"
        )
        items.append({"summary": quote, "quote": quote,
                      "kind": kind, "relation": relation})
    return {"items": items}


def load_dataset(path):
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must contain a nonempty cases list")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValueError("Invalid case ID")
        if case["id"] in seen:
            raise ValueError("Duplicate case ID: " + case["id"])
        seen.add(case["id"])
        validate(case.get("source"), case.get("gold"))
    return dataset


def load_predictions(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = document.get("cases")
    if not isinstance(entries, list):
        raise ValueError("Predictions must contain a cases list")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Invalid prediction ID")
        if entry["id"] in result:
            raise ValueError("Duplicate prediction ID: " + entry["id"])
        result[entry["id"]] = entry
    return result


def item_key(item):
    return (item["quote"], item["kind"], item["relation"])


def safe_number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value < float("inf"):
        return None
    return float(value)


def evaluate(dataset, predictions, predictor_name):
    ids = {c["id"] for c in dataset["cases"]}
    extras = sorted(set(predictions) - ids)
    if extras:
        raise ValueError("Unknown prediction IDs: " + ", ".join(extras))
    total = len(ids)
    errors = []
    errors_by_type = Counter()
    matched = predicted_count = gold_count = 0
    covered = accepted = 0
    quote_total = quote_supported = 0
    elapsed = []
    costs = []
    for case in dataset["cases"]:
        case_id, source = case["id"], case["source"]
        gold_items = case["gold"]["items"]
        gold_count += len(gold_items)
        entry = predictions.get(case_id)
        if entry is None:
            errors_by_type["missing_prediction"] += 1
            errors.append({"id": case_id, "type": "missing_prediction"})
            continue
        covered += 1
        latency = safe_number(entry.get("latency_ms"))
        cost = safe_number(entry.get("cost_usd"))
        if latency is not None:
            elapsed.append(latency)
        if cost is not None:
            costs.append(cost)
        candidate = entry.get("candidate")
        raw_items = candidate.get("items") if isinstance(candidate, dict) else None
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict) and isinstance(item.get("quote"), str) and item["quote"]:
                    quote_total += 1
                    if item["quote"] in source:
                        quote_supported += 1
        try:
            verified = validate(source, candidate)
        except (ValueError, TypeError) as exc:
            errors_by_type["validation_failed"] += 1
            errors.append({"id": case_id, "type": "validation_failed", "reason": str(exc)})
            continue
        accepted += 1
        predicted = verified["items"]
        predicted_count += len(predicted)
        pred_keys = Counter(item_key(x) for x in predicted)
        gold_keys = Counter(item_key(x) for x in gold_items)
        matched += sum((pred_keys & gold_keys).values())
        gold_quotes = {x["quote"]: x for x in gold_items}
        pred_quotes = {x["quote"]: x for x in predicted}
        for quote in sorted(gold_quotes.keys() - pred_quotes.keys()):
            errors_by_type["omission"] += 1
            errors.append({"id": case_id, "type": "omission", "quote": quote})
        for quote in sorted(pred_quotes.keys() - gold_quotes.keys()):
            errors_by_type["extra_item"] += 1
            errors.append({"id": case_id, "type": "extra_item", "quote": quote})
        for quote in sorted(pred_quotes.keys() & gold_quotes.keys()):
            if item_key(pred_quotes[quote]) != item_key(gold_quotes[quote]):
                errors_by_type["wrong_label_or_relation"] += 1
                errors.append({"id": case_id, "type": "wrong_label_or_relation", "quote": quote,
                               "expected": item_key(gold_quotes[quote])[1:],
                               "predicted": item_key(pred_quotes[quote])[1:]})
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / gold_count if gold_count else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "dataset_origin": dataset.get("origin", "unknown"),
        "predictor": predictor_name,
        "disclaimer": "Offline extraction benchmark, not browser E2E or live-model validation.",
        "cases_total": total,
        "cases_with_predictions": covered,
        "coverage": covered / total,
        "cases_passing_validation": accepted,
        "validation_acceptance_rate": accepted / total,
        "gold_items": gold_count,
        "accepted_predicted_items": predicted_count,
        "exact_item_true_positives": matched,
        "exact_item_precision": round(precision, 4),
        "exact_item_recall": round(recall, 4),
        "exact_item_f1": round(f1, 4),
        "source_quote_support_rate": round(quote_supported / quote_total, 4) if quote_total else None,
        "quotes_checked": quote_total,
        "latency_ms_average_reported": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
        "latency_observations": len(elapsed),
        "cost_usd_total_reported": round(sum(costs), 6) if costs else None,
        "cost_observations": len(costs),
        "error_counts": dict(sorted(errors_by_type.items())),
        "errors": errors,
    }


def run(dataset_path=DEFAULT_DATASET, predictions_path=None):
    dataset = load_dataset(dataset_path)
    if predictions_path:
        predictions = load_predictions(predictions_path)
        name = "saved_predictions_not_live_call"
    else:
        predictions = {}
        for case in dataset["cases"]:
            start = time.perf_counter()
            candidate = simple_baseline(case["source"])
            elapsed_ms = (time.perf_counter() - start) * 1000
            predictions[case["id"]] = {"id": case["id"], "candidate": candidate,
                                       "latency_ms": elapsed_ms}
        name = "deterministic_rule_baseline"
    return evaluate(dataset, predictions, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--baseline", action="store_true")
    mode.add_argument("--predictions", type=Path, help="Saved model outputs; no live API call")
    parser.add_argument("--out", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = run(args.dataset, args.predictions)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
