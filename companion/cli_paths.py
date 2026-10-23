"""Resolve the official CLI even when Chrome inherits an older PATH."""
import os
import shutil
from pathlib import Path


def find_codex():
    configured = os.environ.get("JOB_COMPANION_CODEX_PATH")
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
    executable = shutil.which("codex")
    if executable:
        return executable
    roots = [Path.home() / "AppData" / "Local"]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]))
    candidates = []
    for root in roots:
        candidates.extend((root / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
    candidates = [path for path in candidates if path.is_file()]
    if candidates:
        return str(max(candidates, key=lambda path: path.stat().st_mtime))
    return None
