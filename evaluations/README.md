# JD Extraction Evaluation (P0)

Run at repository root (Python 3.10+, standard library only):

```bash
python -m unittest -v evaluations.test_agent_benchmark
python -m evaluations.agent_benchmark --baseline --out output/evaluation/baseline.json
python -m evaluations.agent_benchmark --predictions output/evaluation/predictions.json --out output/evaluation/model.json
```

The provided `synthetic_cases.json` is a **small, manually-authored synthetic smoke-test suite**, not a real job listing benchmark. It exists to catch regression errors and test the scoring code. **Never advertise its scores as real-world accuracy.**

## Saved prediction format

Use the same `extract_job.py` candidate schema, with case IDs exactly as in the dataset:

```json
{
  "cases": [
    {
      "id": "S01-any-of",
      "candidate": {
        "items": [
          {
            "summary": "Python or SQL",
            "quote": "掌握Python、SQL至少一项。",
            "kind": "required",
            "relation": "any_of"
          }
        ]
      },
      "latency_ms": 1234,
      "cost_usd": 0.001
    }
  ]
}
```

Missing case IDs count as missing predictions; unknown or duplicate IDs are rejected. No network or model invocation occurs. `latency_ms` and `cost_usd` are **only user-supplied measurements** and are left null if absent. Empty/no-output predictions should use an empty items array. Invalid candidates fail validation and earn zero item credit.

## Interpretation

- **Exact item match:** exact continuous source quote + classification (`kind`) + logical relation (`relation`). Summaries are intentionally not auto-graded.
- **Precision / Recall / F1:** micro-aggregated over all accepted predictions. Missing/invalid predictions contribute no true positives. A predicted quote may be supported by the source but semantically incorrect; quote support is **not** semantic correctness.
- **Validation acceptance:** share of all dataset cases with candidates passing `extract_job.validate`.
- **Coverage:** fraction of cases with supplied outputs.
- **Errors:** missing predictions, invalid candidates, omissions, extras, wrong labels/relations.
- **Latency / costs:** optional imported measurements only; never assume a local baseline's runtime is an LLM call cost.

## Research protocol before making resume claims

1. Collect 50–100 **permitted, anonymized** job-description snapshots, diverse by source, language, and job type. Do not commit personal information or access tokens.
2. Independently annotate quotes, category and relation; review disagreements; version the gold labels.
3. Freeze a holdout set **before** prompt tuning. Measure extraction quality on holdout, compare against deterministic baseline, report confidence intervals and error examples.
4. Add Chrome real-world E2E trials separately, measuring selection capture, explicit model consent, extraction, saving, and retrieval.
5. Add prompt-injection adversarial test cases. Browser text is untrusted; never execute embedded instructions. Keep model tools disabled and do not auto-apply or contact recruiters.

Current status: **offline evaluation harness only**. No live Codex calls or real Chrome E2E tests were run as part of these fixtures.
