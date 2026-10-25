"""Collect reproducible 50–100 *real* published job snapshots via Greenhouse public GET API.

No application endpoints, no resume, no credentials. Network required.
Snapshots and source text stay under output/ (gitignored) for annotation and review.
This command does not claim that collected cases have gold labels.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

DEFAULT_OUT = Path("output/evaluation/real_corpus_unlabeled.json")


class VisibleHTML(HTMLParser):
    OMIT = {"script", "style", "form", "button", "select", "textarea", "noscript", "svg"}
    BREAK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "ul", "ol", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.OMIT:
            self.skip += 1
        elif not self.skip and tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.OMIT:
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def strip_description(raw):
    if not isinstance(raw, str):
        return ""
    parser = VisibleHTML()
    parser.feed(unescape(raw))
    text = unescape("".join(parser.parts))
    return "\n".join(
        line for line in (re.sub(r"\s+", " ", v).strip() for v in text.splitlines()) if line
    )[:60000]


def collect(boards, target=80, per_board=35, pause=1.0, fetch=None):
    """Deterministic board order; bounded requests; no invented samples."""
    if not 50 <= target <= 100:
        raise ValueError("Target must be between 50 and 100")
    if not 1 <= per_board <= 100:
        raise ValueError("per-board limit must be 1..100")
    if not boards or len(boards) > 12:
        raise ValueError("Provide 1..12 explicit board tokens")
    unique_boards = list(dict.fromkeys(boards))
    for board in unique_boards:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{2,80}", board):
            raise ValueError("Invalid Greenhouse board token")
    def http_get(url):
        req = Request(url, headers={"User-Agent": "job-assistant-research/0.1 (read-only; local evaluation)", "Accept": "application/json"})
        with urlopen(req, timeout=20) as response:
            if response.status != 200:
                raise ValueError("HTTP " + str(response.status))
            return json.load(response)
    get = fetch or http_get
    cases = []
    errors = []
    known_ids = set()
    for board in unique_boards:
        url = "https://boards-api.greenhouse.io/v1/boards/" + board + "/jobs?content=true"
        try:
            data = get(url)
            jobs = data.get("jobs")
            if not isinstance(jobs, list):
                raise ValueError("Greenhouse response has no jobs list")
            accepted = 0
            for job in sorted(jobs, key=lambda job: str(job.get("id", ""))):
                if len(cases) >= target or accepted >= per_board:
                    break
                job_id = job.get("id")
                title = job.get("title")
                source_url = job.get("absolute_url")
                if not isinstance(job_id, int) or not isinstance(title, str):
                    continue
                if not isinstance(source_url, str) or not source_url.startswith("https://"):
                    continue
                if job.get("internal_job_id") is None:
                    continue  # Exclude general prospect pools.
                text = strip_description(job.get("content", ""))
                if not 120 <= len(text) <= 60000:
                    continue
                key = board + ":" + str(job_id)
                if key in known_ids:
                    continue
                known_ids.add(key)
                cases.append({
                    "id": key, "source": text, "gold": None,
                    "annotation_status": "unlabeled",
                    "origin": "greenhouse_public_board_api",
                    "company": board,
                    "title": title,
                    "location": (job.get("location") or {}).get("name", ""),
                    "url": source_url,
                    "api_url": url,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                })
                accepted += 1
        except Exception as exc:
            errors.append({"board": board, "error_type": type(exc).__name__})
        if len(cases) >= target:
            break
        if fetch is None and pause:
            time.sleep(pause)
    return {"origin": "real_public_job_posts_unlabeled",
            "intended_size": target,
            "collected_size": len(cases), "annotated_size": 0,
            "label_guidance": "Manually annotate gold before using accuracy metrics. Do not publish third-party source text without permission.",
            "data_source": "Greenhouse public Job Board GET API",
            "cases": cases, "collection_errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boards", nargs="+", required=True, help="Explicit public Greenhouse board tokens, not URLs")
    parser.add_argument("--target", type=int, default=80)
    parser.add_argument("--per-board", type=int, default=35)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = collect(args.boards, args.target, args.per_board)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"collected": report["collected_size"], "target": args.target,
                      "annotated": 0, "errors": report["collection_errors"],
                      "path": str(args.out)}, ensure_ascii=False))
    if report["collected_size"] < 50:
        raise SystemExit("Fewer than 50 real JDs collected; check board names and availability. Results saved but not a 50-case corpus.")


if __name__ == "__main__":
    main()
