# Indeed 20-job pilot: AI draft first, human gold last

The repository contains `evaluations/indeed_20_sources.json`, a **list of 20 Indeed links**, not 20 complete job descriptions. Some Indeed pages may require manual opening. **No complete source text, model-extracted labels or human gold annotations have been verified for all 20.** Do not claim otherwise.

## Start local review

Run these commands from the repository root, using Python 3.10+:

```powershell
git checkout feat/agent-evaluation-mvp
python -m evaluations.review_workbench --dataset evaluations/indeed_20_sources.json --limit 20
```

Open `http://127.0.0.1:8766` in Chrome.

For each Indeed source, click its listing, open the source link in your browser, and copy the complete position description that you are permitted to process. Paste into **JD 正文**, click **保存当前 JD 原文**. Then choose **Codex 预标注** and explicitly approve sending that JD text to your logged-in Codex CLI. You can also try the local deterministic baseline without a model call. The AI output is only a suggestion; click **复制建议到编辑区**, check every requirement and missing clause, correct the entries, and finally **逐项检查后确认完整**.

Only completed reviews go into the exported file:

```
output/evaluation/real_corpus_reviewed.json
```

This file can be read by the existing benchmark command:

```powershell
python -m evaluations.agent_benchmark --dataset output/evaluation/real_corpus_reviewed.json --baseline
```

The UI is served locally at 127.0.0.1, not exposed to the public internet. Local state is stored in `output/evaluation/annotation_review_state.json`, which is gitignored. The original link manifest is unchanged. Updating JD text resets existing draft and review status to prevent stale citations. Suggestions are **not** saved as gold, and only an explicit human completeness confirmation marks the JD reviewed.

**Evaluation integrity:** If Codex supplied the initial labels, the result is an **AI-assisted human-verified benchmark**, not a fully independently authored test set. Audit omissions carefully; for final holdout claims, use an independent second reviewer. Avoid evaluating the same Codex outputs that you adopted wholesale as gold.

**Limits:** The system does not bypass Indeed access restrictions, automatically scrape protected pages, or upload local JD bodies to GitHub. There is no verified real-website E2E run yet. Any Codex model use here happens only on your own computer after the per-JD consent dialogue.

Regression tests:

```powershell
python -m unittest -v evaluations.test_review_workbench
```
