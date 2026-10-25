# Real JD evaluation & Chrome E2E acceptance

## 1. Collect real job posts without applying

This uses the **public Greenhouse Job Board GET API**, not scraping private pages or submitting applications. Run from repository root. Board tokens are user-supplied, may change, and some boards may return errors; results are counted, never fabricated.

```bash
python -m evaluations.collect_greenhouse --boards stripe figma notion airbnb databricks --target 80 --per-board 30
```

Result: `output/evaluation/real_corpus_unlabeled.json`. Verify `collected_size >= 50` and source URLs. Output is gitignored. It contains unlicensed third-party JD text: keep locally; do not publish copies without permission. A real URL and source snapshot do **not** mean a position is still available or the snapshot is error-free.

Annotate manually:

```bash
python -m evaluations.annotate --input output/evaluation/real_corpus_unlabeled.json
```

Each item must use a **continuous exact quote** and select `kind` and `relation`. Review all JD requirements including unknown/ambiguous passages. The script writes after each confirmed case. Press Enter for zero extracted items only after reviewing the entire source. To export only completed examples:

```bash
python -m evaluations.annotate --input output/evaluation/real_corpus_unlabeled.json --export-only
```

Use `output/evaluation/real_corpus_reviewed.json` with `--dataset` for evaluation. The collected sample size and labeled sample size are separate; **never calculate quality on unreviewed cases**. Freeze a holdout (e.g. 20% stratified by source and domain) before tuning. A second reviewer is recommended for any ambiguous clauses.

## 2. Evaluate saved model outputs

Run your existing Codex-powered Chrome analysis, preserve the `items` JSON result only after getting consent to send the page to the provider, and place the *saved outputs* in an ID-keyed file using the `evaluations/README.md` format. No browser or model run is implied by this command:

```bash
python -m evaluations.agent_benchmark --dataset output/evaluation/real_corpus_reviewed.json --baseline --out output/evaluation/real_baseline.json
python -m evaluations.agent_benchmark --dataset output/evaluation/real_corpus_reviewed.json --predictions output/evaluation/real_predictions.json --out output/evaluation/real_model.json
```

Inspect `exact_item_f1`, `source_quote_support_rate`, validation failures and omissions. A quote found in the text isn't proof the summary is semantically faithful; gold labels must be independently reviewed.

## 3. Explainable duplicate suggestions and skill matching

```bash
python -m evaluations.match_baseline --corpus output/evaluation/real_corpus_unlabeled.json --profile path/to/your/local-profile.txt
```

The profile file remains local. Reports include source-ID duplicate detection, manual-review candidates, skill overlap and missing/unmentioned keywords. The score is **not** a hiring probability and does not prove eligibility. Same company + high token similarity is only a proposed duplicate; source ID is necessary for automatic exactness. No applications are submitted and no recruiter is contacted.

## 4. REAL Chrome browser E2E checklist (human-in-the-loop)

**This is a manual acceptance protocol**, not a claim the real browser was exercised by unit tests. Set up on Windows as described in `docs/browser-companion.md`; open three currently accessible public recruitment pages that you have permission to read.

For each trial write to your local test log: `trial_id, UTC timestamp, site, URL, selection/full-page mode, source hash, capture_ok, source_title_ok, source_url_ok, consent_ok, extraction_ok, quote_validation_ok, save_ok, reopen_ok, latency_ms, error_type`. Do not put private session tokens or personal profiles in this log.

1. Open a public JD in Chrome; capture selected JD text via the extension popup.
2. Confirm the workbench shows selected text and the correct source URL/title. Where access is restricted, record `blocked` rather than bypassing access controls.
3. Choose **Codex** with local CLI installed/logged in; confirm the explicit send-to-model dialogue. If consent is denied, confirm the model is NOT invoked.
4. Inspect the returned structured requirements and exact quote evidence. Reject/fail any unsourced quote.
5. Save the reviewed snapshot, switch directions and back; confirm the saved text, source URL/title and manual status persist.
6. Refresh/restart Chrome and re-open the workbench. Verify persistence and no cross-workspace leakage.
7. Repeat with (i) another board, (ii) a non-job page, (iii) a JD containing visible user-untrusted instructions. Confirm they are never treated as system instructions, actions or authority.

**Pass criteria:** all critical safety checks pass; quote errors must not be accepted as verified; capture/save/reopen must work on >= 3 distinct accessible real JD pages. The **E2E success rate** is passed trials / attempted trials, reporting blocked/errors separately. Neither an offline unit test nor the Greenhouse collector fulfills this browser acceptance.

## 5. Tests and known limitations

```bash
python -m unittest -v evaluations.test_agent_benchmark evaluations.test_real_corpus
python -m unittest -v test_extract_job test_companion
node tests/direction_ui.cjs
```

The UI capture now retains `source_url` and `source_title` for new samples (not retroactive). Source URL/title do not automatically assert official job listing verification. Full-page capture may include unrelated content; user should select the JD section and review it before sending. The Chrome workbench currently stores raw text in browser local storage and analysis results are not automatically persisted as reviewed gold labels.

No actual collection, actual Chrome session, Codex API trial, or runtime test result is claimed by the source-code change alone.
