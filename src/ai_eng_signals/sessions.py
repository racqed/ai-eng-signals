"""Turn local Claude Code and Codex session logs into per-session numbers.

Privacy is the design constraint: only allowlisted folders are opened, and a
SessionStats row holds counts, token totals, model names, tool names and a
project alias. No prompt, response, file path or command text is kept.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from . import ROOT

# Every field a published row may contain. privacy.check_report enforces it.
ROW_FIELDS = (
    "session", "agent", "kind", "project", "date", "minutes", "human_prompts",
    "api_calls", "tool_calls", "tool_errors", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_write_tokens", "compactions", "models", "tools",
)


@dataclass
class SessionStats:
    session: str  # short hash of the session id, so rows can't be linked back
    agent: str  # "claude-code" or "codex"
    kind: str  # "main" or "subagent"
    project: str
    date: str  # YYYY-MM-DD of the first event
    minutes: float  # first to last event, including idle time
    human_prompts: int
    api_calls: int
    tool_calls: int
    tool_errors: int | None  # None where the log doesn't record failures (Codex)
    input_tokens: int  # uncached input only, for both agents
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    compactions: int
    models: list[str] = field(default_factory=list)
    tools: dict[str, int] = field(default_factory=dict)

    def row(self) -> dict:
        return asdict(self)


def load_sources(path: Path | None = None) -> dict:
    with open(path or ROOT / "config" / "sources.toml", "rb") as fh:
        return tomllib.load(fh)


def _hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()[:10]


def _project(cwd: str | None, aliases: dict[str, str]) -> str:
    name = (cwd or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or "unknown"
    return aliases.get(name, name)


def _ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _span(stamps: list[datetime]) -> tuple[str, float]:
    if not stamps:
        return "", 0.0
    return min(stamps).date().isoformat(), round((max(stamps) - min(stamps)).total_seconds() / 60, 1)


def _records(path: Path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# Prompts that start with these are commands or harness output, not something typed.
_NOT_TYPED = ("<local-command", "<command-", "<system-reminder>", "<task-notification>")


def _typed_prompt(record: dict) -> bool:
    if record.get("isMeta") or record.get("toolUseResult") is not None:
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return isinstance(content, str) and bool(content.strip()) and not content.lstrip().startswith(_NOT_TYPED)


def parse_claude(path: Path, aliases: dict[str, str] | None = None) -> SessionStats | None:
    """One Claude Code transcript (main session or sub-agent) to numbers."""
    aliases = aliases or {}
    usage: dict[str, dict[str, int]] = {}  # per API message id; streamed blocks repeat it
    models: set[str] = set()
    tools: Counter[str] = Counter()
    seen_tool_ids: set[str] = set()
    stamps: list[datetime] = []
    session_id = cwd = None
    prompts = errors = compactions = 0

    for r in _records(path):
        session_id = session_id or r.get("sessionId")
        cwd = cwd or r.get("cwd")
        if (t := _ts(r.get("timestamp"))) is not None:
            stamps.append(t)
        kind = r.get("type")
        msg = r.get("message") if isinstance(r.get("message"), dict) else {}
        if kind == "assistant":
            mid = msg.get("id") or r.get("requestId") or r.get("uuid")
            if msg.get("model") and msg["model"] != "<synthetic>":
                models.add(msg["model"])
            u = msg.get("usage") or {}
            if u and mid:
                prev = usage.setdefault(mid, {})
                for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
                    prev[key] = max(prev.get(key, 0), int(u.get(key) or 0))
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in seen_tool_ids:
                    seen_tool_ids.add(block.get("id"))
                    tools[block.get("name", "unknown")] += 1
        elif kind == "user":
            content = msg.get("content")
            if isinstance(content, list):
                errors += sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"))
            prompts += _typed_prompt(r)
        elif kind == "system" and r.get("subtype") == "compact_boundary":
            compactions += 1

    if not session_id or not usage:
        return None
    date, minutes = _span(stamps)
    total = lambda key: sum(u.get(key, 0) for u in usage.values())  # noqa: E731
    return SessionStats(
        session=_hash(f"{session_id}:{path.stem}"),
        agent="claude-code",
        kind="subagent" if path.parent.name == "subagents" else "main",
        project=_project(cwd, aliases),
        date=date,
        minutes=minutes,
        human_prompts=prompts,
        api_calls=len(usage),
        tool_calls=sum(tools.values()),
        tool_errors=errors,
        input_tokens=total("input_tokens"),
        output_tokens=total("output_tokens"),
        cache_read_tokens=total("cache_read_input_tokens"),
        cache_write_tokens=total("cache_creation_input_tokens"),
        compactions=compactions,
        models=sorted(models),
        tools=dict(tools.most_common()),
    )


def parse_codex(path: Path, aliases: dict[str, str] | None = None) -> SessionStats | None:
    """One Codex rollout to numbers. Codex counts cached tokens inside input_tokens."""
    aliases = aliases or {}
    meta: dict = {}
    models: set[str] = set()
    tools: Counter[str] = Counter()
    stamps: list[datetime] = []
    totals: dict = {}
    prompts = api_calls = compactions = 0

    for r in _records(path):
        p = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        if (t := _ts(r.get("timestamp"))) is not None:
            stamps.append(t)
        kind, sub = r.get("type"), p.get("type")
        if kind == "session_meta":
            meta = p
        elif kind == "turn_context" and p.get("model"):
            models.add(p["model"])
        elif kind == "event_msg" and sub == "task_started":
            prompts += 1
        elif kind == "event_msg" and sub in ("context_compacted", "compacted"):
            compactions += 1
        elif kind == "compacted":
            compactions += 1
        elif kind == "response_item" and sub in ("function_call", "custom_tool_call"):
            tools[p.get("name", "unknown")] += 1
        elif kind == "token_usage_record":
            api_calls += 1
            totals = p.get("thread_token_usage") or totals  # cumulative for the thread

    if not meta.get("id") or not totals:
        return None
    date, minutes = _span(stamps)
    cached = int(totals.get("cached_input_tokens") or 0)
    return SessionStats(
        session=_hash(meta["id"]),
        agent="codex",
        kind="main",
        project=_project(meta.get("cwd"), aliases),
        date=date,
        minutes=minutes,
        human_prompts=prompts,
        api_calls=api_calls,
        tool_calls=sum(tools.values()),
        tool_errors=None,
        input_tokens=max(0, int(totals.get("input_tokens") or 0) - cached),
        output_tokens=int(totals.get("output_tokens") or 0),
        cache_read_tokens=cached,
        cache_write_tokens=int(totals.get("cache_write_input_tokens") or 0),
        compactions=compactions,
        models=sorted(models),
        tools=dict(tools.most_common()),
    )


def _codex_cwd(path: Path) -> str:
    for r in _records(path):
        if r.get("type") == "session_meta":
            return str((r.get("payload") or {}).get("cwd", "")).replace("\\", "/")
    return ""


def collect(home: Path | None = None, sources: dict | None = None) -> list[SessionStats]:
    """Read every allowlisted session under ``home`` (default: the user's home)."""
    home = home or Path.home()
    sources = sources or load_sources()
    aliases = sources.get("aliases", {})
    rows: list[SessionStats] = []

    claude_root = home / ".claude" / "projects"
    for folder in sorted(claude_root.glob("*")) if claude_root.exists() else []:
        if not folder.is_dir() or not any(fnmatch.fnmatch(folder.name, g) for g in sources["claude"]["folders"]):
            continue
        for path in sorted(folder.glob("*.jsonl")) + sorted(folder.glob("*/subagents/*.jsonl")):
            if (stats := parse_claude(path, aliases)) is not None:
                rows.append(stats)

    codex_root = home / ".codex" / "sessions"
    for path in sorted(codex_root.rglob("*.jsonl")) if codex_root.exists() else []:
        cwd = _codex_cwd(path)
        if any(part in cwd for part in sources["codex"]["cwd_contains"]):
            if (stats := parse_codex(path, aliases)) is not None:
                rows.append(stats)
    return rows
