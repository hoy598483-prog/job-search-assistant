"""Local-only, human-in-the-loop JD annotation review workbench.

Run from repository root:
  python -m evaluations.review_workbench \
    --dataset output/evaluation/real_corpus_unlabeled.json --limit 20

Gold labels are created ONLY after explicit human confirmation. Suggestions are
never treated as gold labels. No model is called without explicit consent.
Python standard library only; binds to 127.0.0.1.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
from urllib.parse import parse_qs, urlsplit

from evaluations.agent_benchmark import simple_baseline
from extract_job import ITEM_PROPERTIES, validate

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "output/evaluation/real_corpus_unlabeled.json"
DEFAULT_STATE = ROOT / "output/evaluation/annotation_review_state.json"
DEFAULT_EXPORT = ROOT / "output/evaluation/real_corpus_reviewed.json"
MAX_BODY = 160000
MAX_ITEMS = 150


def fingerprint(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def atomic_json(path, payload):
    """Replace a complete JSON document atomically after flushing to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".annotation-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def normalized_items(items):
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("Expected an array of at most 150 annotation items")
    output = []
    for item in items:
        if not isinstance(item, dict) or set(item) != set(ITEM_PROPERTIES):
            raise ValueError("Annotation item has invalid fields")
        for k in ITEM_PROPERTIES:
            if not isinstance(item[k], str) or len(item[k]) > 60000:
                raise ValueError("Annotation strings must be bounded")
        output.append({k: item[k] for k in ITEM_PROPERTIES})
    return output


class ReviewStore:
    """Single-process local store; immutable collected sources, separate review state."""

    def __init__(self, dataset, state=DEFAULT_STATE, export=DEFAULT_EXPORT, limit=20):
        self.dataset_path = Path(dataset).resolve()
        self.state_path = Path(state).resolve()
        self.export_path = Path(export).resolve()
        if self.dataset_path in (self.state_path, self.export_path) or self.state_path == self.export_path:
            raise ValueError("Dataset, state and export paths must be distinct")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be 1..1000")
        dataset_doc = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        original_cases = dataset_doc.get("cases")
        if not isinstance(original_cases, list) or not original_cases:
            raise ValueError("Dataset requires a nonempty cases list")
        ids = set()
        cases = []
        for case in original_cases:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                raise ValueError("Invalid case ID")
            source = case.get("source")
            if (not isinstance(source, str) or not source.strip()
                    or len(source) > 60000 or case["id"] in ids):
                raise ValueError("Invalid or duplicate case source")
            ids.add(case["id"])
            sha = fingerprint(source)
            if case.get("source_sha256") and sha != case["source_sha256"]:
                raise ValueError("Source fingerprint mismatch: " + case["id"])
            # No guessing gold labels from upstream source material.
            cases.append(case)
        self.cases = cases[:limit]
        self.by_id = {case["id"]: case for case in self.cases}
        self.origin = dataset_doc.get("origin", "unspecified_source")
        self.dataset_id = hashlib.sha256(json.dumps(
            [(c["id"], fingerprint(c["source"])) for c in self.cases],
            ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.state = {"dataset_id": self.dataset_id, "entries": {}}
        if self.state_path.exists():
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if loaded.get("dataset_id") != self.dataset_id or not isinstance(loaded.get("entries"), dict):
                raise ValueError("Existing review state belongs to a different dataset/limit")
            if set(loaded["entries"]) - set(self.by_id):
                raise ValueError("Unknown ID in saved annotations")
            self.state = loaded
        else:
            # Do not import any upstream gold as confirmed human review automatically.
            self.state = {"dataset_id": self.dataset_id, "entries": {}}

    def overview(self):
        complete = sum(self.state["entries"].get(c["id"], {}).get("status") == "reviewed"
                       for c in self.cases)
        return {"total": len(self.cases), "reviewed": complete,
                "unreviewed": len(self.cases)-complete,
                "dataset_origin": self.origin,
                "cases": [{
                    "id": c["id"],
                    "company": c.get("company") or "",
                    "title": c.get("title") or "Untitled JD",
                    "status": self.state["entries"].get(c["id"], {}).get("status", "unlabeled")
                } for c in self.cases]}

    def case(self, case_id):
        if case_id not in self.by_id:
            raise ValueError("Unknown case ID")
        c = self.by_id[case_id]
        entry = self.state["entries"].get(case_id, {})
        return {"id": case_id, "source": c["source"],
                "source_sha256": fingerprint(c["source"]),
                "company": c.get("company") or "",
                "title": c.get("title") or "", "url": c.get("url") or "",
                "annotation_status": entry.get("status", "unlabeled"),
                "items": entry.get("items", []),
                "note": entry.get("note", ""), "reviewed_at": entry.get("reviewed_at")}

    def save(self, case_id, items, reviewed=False, confirmed_complete=False, note=""):
        if case_id not in self.by_id:
            raise ValueError("Unknown case ID")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Note must be at most 2000 characters")
        cleaned = normalized_items(items)
        source = self.by_id[case_id]["source"]
        if reviewed:
            if confirmed_complete is not True:
                raise ValueError("Explicit completeness confirmation is required")
            validate(source, {"items": cleaned})
        entry = {"status": "reviewed" if reviewed else "draft",
                 "items": cleaned, "note": note,
                 "source_sha256": fingerprint(source),
                 "reviewed_at": datetime.now(timezone.utc).isoformat() if reviewed else None}
        self.state["entries"][case_id] = entry
        atomic_json(self.state_path, self.state)
        return {"id": case_id, "status": entry["status"]}

    def suggest(self, case_id, provider="baseline", consent=False):
        if case_id not in self.by_id:
            raise ValueError("Unknown case ID")
        source = self.by_id[case_id]["source"]
        if provider == "baseline":
            candidate = simple_baseline(source)
        elif provider == "codex":
            if consent is not True:
                raise ValueError("Codex requires explicit consent to send JD text")
            # Reuse existing no-tools, read-only, no-web CLI adapter.
            from companion.providers import analyze
            try:
                response = analyze(source, provider="codex")
                candidate = {"items": [{k: item[k] for k in ITEM_PROPERTIES}
                                       for item in response["items"]]}
            except Exception as exc:
                # Never leak secrets, stderr or JD text through an error response.
                raise ValueError("Codex suggestion failed (" + type(exc).__name__ + ")") from None
        else:
            raise ValueError("Unsupported suggestion provider")
        # A suggestion is only a proposal. Never store it as a gold annotation.
        return {"provider": provider, "suggested_items": candidate["items"],
                "status": "unreviewed_suggestion",
                "notice": "Verify each quote, kind, relation AND omissions before human confirmation."}

    def export_reviewed(self):
        cases = []
        for case in self.cases:
            entry = self.state["entries"].get(case["id"], {})
            if entry.get("status") != "reviewed":
                continue
            if entry.get("source_sha256") != fingerprint(case["source"]):
                raise ValueError("Source changed since human review")
            validated = {"items": normalized_items(entry["items"])}
            validate(case["source"], validated)
            record = {k: v for k, v in case.items() if k not in ("gold", "annotation_status")}
            record["gold"] = validated
            record["annotation_status"] = "reviewed"
            record["reviewed_at"] = entry["reviewed_at"]
            cases.append(record)
        if not cases:
            raise ValueError("No human-reviewed cases to export")
        payload = {"origin": self.origin + "_human_reviewed",
                   "annotation_method": "explicit_manual_confirmation",
                   "cases": cases,
                   "collected_size": len(self.cases),
                   "annotated_size": len(cases)}
        atomic_json(self.export_path, payload)
        return {"path": str(self.export_path), "reviewed": len(cases),
                "total": len(self.cases),
                "notice": "Only manually confirmed labels are exported."}


def make_handler(store):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def allowed_host(self):
            return self.headers.get("Host") == "127.0.0.1:" + str(self.server.server_port)

        def get_asset(self, name, mime):
            data = (ASSETS / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {"error": "Invalid local Host"})
            url = urlsplit(self.path)
            if url.path == "/":
                return self.get_asset("review_workbench.html", "text/html; charset=utf-8")
            if url.path == "/review_workbench.js":
                return self.get_asset("review_workbench.js", "text/javascript; charset=utf-8")
            if url.path == "/review_workbench.css":
                return self.get_asset("review_workbench.css", "text/css; charset=utf-8")
            if url.path == "/api/overview":
                data = store.overview()
                data["csrf_token"] = token
                return self.reply(200, data)
            if url.path == "/api/case":
                try:
                    case_id = parse_qs(url.query).get("id", [None])[0]
                    return self.reply(200, store.case(case_id))
                except ValueError:
                    return self.reply(404, {"error": "Unknown case ID"})
            return self.reply(404, {"error": "Not found"})

        def do_POST(self):
            if not self.allowed_host():
                return self.reply(403, {"error": "Invalid local Host"})
            origin = self.headers.get("Origin")
            expected = "http://127.0.0.1:" + str(self.server.server_port)
            if (origin != expected or self.headers.get("X-Review-CSRF") != token
                    or self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                return self.reply(403, {"error": "Unauthorized cross-origin request"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("Request body too large")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Invalid request")
                if self.path == "/api/save":
                    # Never mark reviewed on ordinary draft saves.
                    result = store.save(payload.get("id"), payload.get("items"),
                                        reviewed=False, note=payload.get("note", ""))
                elif self.path == "/api/review":
                    result = store.save(payload.get("id"), payload.get("items"),
                                        reviewed=True,
                                        confirmed_complete=payload.get("confirmed_complete"),
                                        note=payload.get("note", ""))
                elif self.path == "/api/suggest":
                    result = store.suggest(payload.get("id"), payload.get("provider", "baseline"),
                                           consent=payload.get("consent") is True)
                elif self.path == "/api/export":
                    result = store.export_reviewed()
                else:
                    return self.reply(404, {"error": "Not found"})
                return self.reply(200, result)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                # The known validator reports field errors only; do not echo raw content.
                return self.reply(400, {"error": str(exc)})
            except Exception:
                return self.reply(500, {"error": "Local operation failed; no success confirmed"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--out", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--limit", type=int, default=20, help="First N JDs for a pilot; default 20")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    store = ReviewStore(args.dataset, args.state, args.out, limit=args.limit)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(store))
    print("Annotation Review: http://127.0.0.1:" + str(server.server_port), flush=True)
    print("Data stays local. Codex requires explicit per-case consent.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
