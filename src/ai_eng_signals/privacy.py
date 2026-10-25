"""Guardrails that keep private data out of commits.

Two checks, both run by the pre-commit hook and by ``signals check-privacy``:

- every file about to be committed is scanned for local user paths, raw
  session logs, and the terms listed in the untracked ``.private-terms`` file;
- every published session row may only use the fields in ``ROW_FIELDS``.

The private terms live outside git on purpose: writing them in a tracked file
would publish exactly what the check is meant to protect.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import ROOT
from .sessions import ROW_FIELDS

# Local home-directory paths and Claude Code's folder names derived from them.
PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+\w", re.I),
    re.compile(r"/Users/\w[\w.-]*/"),
    re.compile(r"/home/\w[\w.-]*/"),
    re.compile(r"[A-Z]--Users-\w"),
]
TERMS_FILE = ".private-terms"


def private_terms(root: Path = ROOT) -> list[str]:
    path = root / TERMS_FILE
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [t.strip().lower() for t in lines if t.strip() and not t.startswith("#")]


def tracked_files(root: Path = ROOT, staged: bool = False) -> list[str]:
    cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def scan_text(name: str, text: str, terms: list[str]) -> list[str]:
    problems = []
    for pattern in PATH_PATTERNS:
        if (m := pattern.search(text)) is not None:
            problems.append(f"{name}: local user path ({m.group(0)!r}...)")
    lowered = text.lower()
    for i, term in enumerate(terms, 1):
        if term in lowered:
            problems.append(f"{name}: private term #{i} from {TERMS_FILE}")
    return problems


def check_report(rows: list[dict], name: str = "reports/sessions.json") -> list[str]:
    allowed = set(ROW_FIELDS)
    return [f"{name}: row {i} has unexpected fields {sorted(set(r) - allowed)}" for i, r in enumerate(rows) if set(r) - allowed]


def check(root: Path = ROOT, staged: bool = False) -> list[str]:
    terms = private_terms(root)
    problems = [] if terms else [f"{TERMS_FILE} is missing or empty: add your real name, email and username, one per line (it is git-ignored)"]
    for name in tracked_files(root, staged):
        path = root / name
        if name.endswith(".jsonl") and not name.startswith("tests/fixtures/"):
            problems.append(f"{name}: raw session logs must never be committed")
        if name == TERMS_FILE:
            problems.append(f"{name}: this file must stay untracked")
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        problems += scan_text(name, text, terms)
        if name == "reports/sessions.json":
            problems += check_report(json.loads(text).get("sessions", []), name)
    return problems
