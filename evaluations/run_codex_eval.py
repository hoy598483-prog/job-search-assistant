"""Run the *existing* sandboxed Codex JD extractor against a reviewed corpus.

Example, run from repository root:
  python -m evaluations.run_codex_eval --dataset output/evaluation/real_corpus_reviewed.json
  python -m evaluations.run_codex_eval --dataset output/evaluation/real_corpus_reviewed.json --execute --consent-to-send-jds

Preview is the default: no provider invocation or file writes. The explicit
execute + consent gates are required to share JD text with the official Codex
CLI. Gold annotations are never passed to the provider.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

from companion import providers
from extract_job import INSTRUCTIONS, ITEM_PROPERTIES, SCHEMA, validate
from evaluations.agent_benchmark import evaluate, load_dataset, load_predictions

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output/evaluation/codex_predictions.json"
DEFAULT_REPORT = ROOT / "output/evaluation/codex_report.json"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _fingerprint(data):
    return _sha(json.dumps(data, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8"))


def _model_config_hash():
    # Refuse to resume results from changed prompt, schema or provider adapter.
    return _fingerprint({
        "runner_schema_version": SCHEMA_VERSION,
        "prompt": INSTRUCTIONS,
        "schema": SCHEMA,
        "provider_adapter_sha256": _sha(Path(providers.__file__).read_bytes()),
    })


def _atomic_json_write(path, data):
    """Checkpoint one completed attempt at a time, without truncated JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".codex-eval-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _validate_input(dataset):
    # Do not allow pending/unknown annotation records into a real benchmark.
    for case in dataset["cases"]:
        status = case.get("annotation_status")
        if status is not None and status != "reviewed":
            raise ValueError("Unreviewed JD in dataset: " + case["id"])


def _metadata(dataset):
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_sha256": _fingerprint(dataset),
        "extractor_config_sha256": _model_config_hash(),
        "provider": "codex_cli_existing_sandbox",
        "dataset_origin": dataset.get("origin", "unknown"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cost_note": "Codex CLI does not expose reliable per-request USD cost here.",
    }


def _load_existing(path, metadata, ids):
    if not Path(path).exists():
        return {"metadata": metadata, "cases": []}
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    existing = result.get("metadata")
    if not isinstance(existing, dict) or any(
        existing.get(key) != metadata[key]
        for key in ("schema_version", "dataset_sha256",
                    "extractor_config_sha256", "provider")
    ):
        raise ValueError("Existing predictions use a different dataset or "
                         "extractor. Choose a new --out file; do not mix runs.")
    parsed = load_predictions(path)
    if set(parsed) - ids:
        raise ValueError("Existing predictions contain unknown IDs")
    for item in parsed.values():
        if item.get("status") not in ("ok", "failed"):
            raise ValueError("Existing prediction has invalid status")
    return result


def _predict(source):
    """Only JD source is passed to Codex; no gold answers, profiles or links."""
    result = providers.analyze(source, provider="codex")
    if result.get("provider") != "codex":
        raise ValueError("Unexpected extraction provider")
    expected = _sha(source.encode("utf-8"))
    if result.get("source_sha256") != expected:
        raise ValueError("Provider source fingerprint mismatch")
    candidate = {"items": [
        {key: item[key] for key in ITEM_PROPERTIES}
        for item in result["items"]
    ]}
    # Defence in depth: reject invalid citations/labels prior to persistence.
    validate(source, candidate)
    return candidate


def _run_one(case):
    start = perf_counter()
    try:
        candidate = _predict(case["source"])
        entry = {"id": case["id"], "status": "ok", "candidate": candidate}
    except Exception as exc:
        # Deliberately omit exception text: errors may include private JD text,
        # CLI output, paths or credentials. Never record stderr or raw prompts.
        entry = {"id": case["id"], "status": "failed", "candidate": None,
                 "error_type": type(exc).__name__}
    entry["source_sha256"] = _sha(case["source"].encode("utf-8"))
    entry["latency_ms"] = round((perf_counter() - start) * 1000, 3)
    # No cost_usd: no trustworthy USD price is exposed through this adapter.
    entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    return entry


def run_evaluation(dataset_path, output_path=DEFAULT_OUTPUT,
                   report_path=DEFAULT_REPORT, execute=False, consent=False,
                   max_new=None, retry_failed=False):
    """Returns a status summary. Dry-run does not call provider or write files.

    Successful cases are never rerun; failed cases rerun only if requested.
    Any existing run must match exact dataset and prompt/adapter fingerprints.
    """
    if execute and not consent:
        raise ValueError("Live Codex requires --consent-to-send-jds")
    if consent and not execute:
        raise ValueError("--consent-to-send-jds requires --execute")
    if retry_failed and not execute:
        raise ValueError("--retry-failed requires --execute")
    if max_new is not None and (type(max_new) is not int or max_new < 1):
        raise ValueError("--max-new must be a positive integer")
    dataset = load_dataset(dataset_path)
    _validate_input(dataset)
    metadata = _metadata(dataset)
    ids = {c["id"] for c in dataset["cases"]}
    document = _load_existing(output_path, metadata, ids)
    previous = {entry["id"]: entry for entry in document["cases"]}
    pending = [case for case in dataset["cases"]
               if case["id"] not in previous or
               (retry_failed and previous[case["id"]]["status"] == "failed")]
    initial_pending = len(pending)
    if not execute:
        return {"mode": "preview_no_model_calls", "total": len(ids),
                "existing": len(previous), "pending": initial_pending,
                "will_run": min(initial_pending, max_new or initial_pending),
                "dataset_origin": metadata["dataset_origin"]}
    if max_new is not None:
        pending = pending[:max_new]
    new_ok = 0
    new_failed = 0
    for case in pending:
        entry = _run_one(case)
        previous[case["id"]] = entry
        document["cases"] = [previous[c["id"]] for c in dataset["cases"]
                             if c["id"] in previous]
        _atomic_json_write(output_path, document)
        if entry["status"] == "ok":
            new_ok += 1
        else:
            new_failed += 1
    # The benchmark explicitly counts failed provider calls as failed attempts.
    # Report always includes the full reviewed corpus denominator.
    report = evaluate(dataset, previous, "codex_cli_actual_run")
    report["run_metadata"] = metadata
    report["provider_successes"] = sum(
        entry["status"] == "ok" for entry in previous.values())
    report["provider_failures"] = sum(
        entry["status"] == "failed" for entry in previous.values())
    report["not_yet_attempted"] = len(ids) - len(previous)
    _atomic_json_write(report_path, report)
    return {"mode": "live_codex", "total": len(ids), "new_attempts": len(pending),
            "new_ok": new_ok, "new_failed": new_failed,
            "provider_successes": report["provider_successes"],
            "provider_failures": report["provider_failures"],
            "not_yet_attempted": report["not_yet_attempted"],
            "exact_item_f1": report["exact_item_f1"],
            "predictions": str(output_path), "report": str(report_path),
            "cost_usd": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Reviewed corpus; contains gold annotations")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--execute", action="store_true",
                        help="Actually call the installed official Codex CLI")
    parser.add_argument("--consent-to-send-jds", action="store_true",
                        help="I have permission to send these JD texts to Codex")
    parser.add_argument("--max-new", type=int, help="Maximum new provider calls")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Explicitly retry previous failures")
    args = parser.parse_args()
    result = run_evaluation(args.dataset, args.out, args.report,
                            execute=args.execute,
                            consent=args.consent_to_send_jds,
                            max_new=args.max_new,
                            retry_failed=args.retry_failed)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from None
