"""Run stateful end-to-end checks against a published Dify Chatflow.

Set DIFY_API_KEY. DIFY_BASE_URL defaults to Dify Cloud's v1 API endpoint.
Each case uses an independent user ID and preserves conversation_id between turns.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1").rstrip("/")
API_KEY = os.getenv("DIFY_API_KEY")
CASES_PATH = Path(__file__).with_name("dify_chatflow_cases.json")


def send_message(query: str, user: str, conversation_id: str | None) -> dict:
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "user": user,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    request = urllib.request.Request(
        f"{BASE_URL}/chat-messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    if not API_KEY:
        print("Missing DIFY_API_KEY. Create an app API key in Dify and set it as an environment variable.")
        return 2

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    for case in cases:
        conversation_id = None
        user = f"e2e-{case['id']}"
        print(f"\nCASE {case['id']}")
        for index, turn in enumerate(case["turns"], start=1):
            try:
                result = send_message(turn["query"], user, conversation_id)
            except urllib.error.HTTPError as error:
                failures.append(f"{case['id']} turn {index}: HTTP {error.code}: {error.read().decode('utf-8', 'replace')}")
                break
            except Exception as error:  # network/model errors should fail the case
                failures.append(f"{case['id']} turn {index}: {error}")
                break

            answer = (result.get("answer") or "").strip()
            conversation_id = result.get("conversation_id") or conversation_id
            expected = turn.get("expect_any", [])
            passed = bool(answer) and (not expected or any(token in answer for token in expected))
            print(f"  turn {index}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                failures.append(
                    f"{case['id']} turn {index}: expected one of {expected}; got {answer[:500]!r}"
                )

    if failures:
        print("\nFAILURES")
        print("\n".join(failures))
        return 1

    print("\nAll Dify end-to-end checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
