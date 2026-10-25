"""Manual gold annotation for source-preserved real JD snapshots.

Run: python -m evaluations.annotate --input output/evaluation/real_corpus_unlabeled.json
All edits remain local under output/; the evaluator only sees manually reviewed gold.
"""
import argparse
import hashlib
import json
from pathlib import Path
from extract_job import validate


def verify_annotations(dataset):
    annotated = 0
    for case in dataset["cases"]:
        source = case["source"]
        if case.get("source_sha256") and hashlib.sha256(source.encode()).hexdigest() != case["source_sha256"]:
            raise ValueError("Source changed after capture: " + case["id"])
        if case.get("annotation_status") == "reviewed":
            validate(source, case["gold"])
            annotated += 1
    dataset["annotated_size"] = annotated
    return annotated


def export_reviewed(dataset, out_path):
    cases = [case for case in dataset["cases"] if case.get("annotation_status") == "reviewed"]
    if not cases:
        raise ValueError("No reviewed cases yet")
    subset = {"origin": dataset.get("origin", "real_public_job_posts") + "_reviewed",
              "cases": cases, "collected_size": len(dataset["cases"]), "annotated_size": len(cases)}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(subset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(cases)


def annotate_case(case):
    """Explicit interactive validation; 'no requirements' must be reviewed too."""
    print("\n", "=" * 70, "\n", case["id"], case.get("title", ""), "\n")
    source = case["source"]
    for i in range(0, len(source), 1500):
        print(source[i:i+1500])
    print("\nCopy exact continuous spans from the source; blank quote finishes this JD.")
    items = []
    while True:
        quote = input("Exact quote (blank = done, :skip = skip JD): ").strip()
        if quote == ":skip":
            return False
        if not quote:
            break
        if quote not in source:
            print("Quote NOT found in source; try again.")
            continue
        kind = input("kind [duty / required / preferred / unclear]: ").strip()
        relation = input("relation [single / any_of / all_of / unclear]: ").strip()
        summary = input("Brief faithful summary: ").strip()
        item = {"quote": quote, "kind": kind, "relation": relation, "summary": summary}
        try:
            validate(source, {"items": items + [item]})
        except ValueError as exc:
            print("Rejected:", exc)
            continue
        items.append(item)
    if input("Confirm COMPLETE gold annotation (y/N): ").lower() != "y":
        return False
    case["gold"] = {"items": items}
    case["annotation_status"] = "reviewed"
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("output/evaluation/real_corpus_reviewed.json"))
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(args.input.read_text(encoding="utf-8"))
    if not args.export_only:
        for case in dataset["cases"]:
            if case.get("annotation_status") == "reviewed":
                continue
            if not annotate_case(case):
                continue
            # Save immediately so interrupted annotation doesn't lose work.
            verify_annotations(dataset)
            args.input.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = verify_annotations(dataset)
    args.input.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if count:
        exported = export_reviewed(dataset, args.out)
        print(f"Reviewed {exported}/{len(dataset['cases'])}; exported to {args.out}")
    else:
        print("No gold cases reviewed yet; nothing exported.")


if __name__ == "__main__":
    main()
