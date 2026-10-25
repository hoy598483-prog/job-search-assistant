"""Explainable, non-LLM job deduplication and profile matching baselines.

Conservative rule: same source job ID is exact duplicate. Text similarity alone
is only a suggested match for human review, never automatic merging.
"""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

STOPWORDS = {"the", "and", "for", "with", "your", "you", "are", "our",
             "job", "work", "team", "role", "experience", "skills", "ability",
             "职位", "岗位", "工作", "经验", "能力", "要求", "负责"}
SKILLS = ["python", "sql", "pytorch", "tensorflow", "java", "javascript",
          "typescript", "react", "docker", "kubernetes", "aws",
          "machine learning", "deep learning", "llm", "rag", "pandas",
          "numpy", "statistics", "optimization", "excel", "tableau",
          "spark", "airflow", "git", "xgboost"]


def tokens(text):
    text = text.lower()
    parts = re.findall(r"[a-z0-9+#.]+|[\u4e00-\u9fff]{2,}", text)
    return set(x for x in parts if len(x) > 1 and x not in STOPWORDS)


def similarity(a, b):
    a, b = tokens(a), tokens(b)
    return len(a & b) / len(a | b) if a or b else 0.0


def stable_job_key(job):
    identifier = str(job.get("id", ""))
    if ":" in identifier and identifier.split(":", 1)[1].isdigit():
        return identifier.lower()
    url = job.get("url", "")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        parsed = urlsplit(url)
        if parsed.hostname and parsed.path:
            return parsed.hostname.lower() + parsed.path.rstrip("/").lower()
    return None


def duplicate_decision(a, b):
    """Return suggested decision plus reasons; never auto-merge."""
    akey, bkey = stable_job_key(a), stable_job_key(b)
    if akey and bkey and akey == bkey:
        return {"label": "exact_duplicate", "score": 1.0, "reason": "same stable source ID/URL"}
    ta = (a.get("title") or "").strip()
    tb = (b.get("title") or "").strip()
    ca = (a.get("company") or "").strip().lower()
    cb = (b.get("company") or "").strip().lower()
    if ca and cb and ca != cb:
        return {"label": "different", "score": 0.0, "reason": "different company"}
    title_score = similarity(ta, tb)
    text_score = similarity(a.get("source", ""), b.get("source", ""))
    score = 0.4 * title_score + 0.6 * text_score
    if ca and cb and ca == cb and title_score >= 0.8 and text_score >= 0.7:
        return {"label": "review_possible_duplicate", "score": round(score, 4),
                "reason": "same company; similar title and requirements"}
    return {"label": "different", "score": round(score, 4), "reason": "insufficient similarity"}


def find_duplicates(jobs):
    proposals = []
    for i, a in enumerate(jobs):
        for b in jobs[i + 1:]:
            result = duplicate_decision(a, b)
            if result["label"] != "different":
                proposals.append({"first": a["id"], "second": b["id"], **result})
    return proposals


def skill_matches(text, term):
    # Boundary matching prevents counting java inside javascript.
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text.lower()))


def match_job(job, profile, skills=SKILLS):
    """Explicit skill overlap, not eligibility or hiring probability."""
    wanted = {s for s in skills if skill_matches(job.get("source", ""), s)}
    possessed = {s for s in skills if skill_matches(profile, s)}
    found = sorted(wanted & possessed)
    missing = sorted(wanted - possessed)
    return {"id": job["id"], "score": round(len(found)/len(wanted), 4) if wanted else None,
            "matched": found, "missing_or_unmentioned": missing,
            "known_skills": sorted(wanted),
            "caveat": "Keyword-only; unmentioned is not proof of lacking skill. Review manually."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True, help="Text profile, local only")
    parser.add_argument("--out", type=Path, default=Path("output/evaluation/matching.json"))
    args = parser.parse_args()
    dataset = json.loads(args.corpus.read_text(encoding="utf-8"))
    jobs = dataset["cases"]
    profile = args.profile.read_text(encoding="utf-8")
    result = {"origin": dataset.get("origin"),
              "dedup_proposals": find_duplicates(jobs),
              "matching": sorted((match_job(j, profile) for j in jobs),
                                 key=lambda x: (x["score"] is None, -(x["score"] or 0), x["id"])),
              "notice": "No auto merging, auto applying or inferred hiring probability."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reviewed candidates: {len(jobs)}; duplicate suggestions: {len(result['dedup_proposals'])}; saved {args.out}")


if __name__ == "__main__":
    main()
