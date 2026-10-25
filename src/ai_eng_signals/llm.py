"""Headless Claude Code (``claude -p``) as the LLM backend.

It runs on my existing subscription, so no API key is needed. Calls run in a
temporary directory with no tools and no saved session, so they don't load
this repo's instructions and don't show up in my own session statistics.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile


class LLMError(RuntimeError):
    pass


def ask(instruction: str, stdin: str, model: str = "haiku", timeout: int = 900) -> dict:
    """Run one prompt and return {"text", "model", "cost_usd", "usage"}."""
    exe = shutil.which("claude")
    if exe is None:
        raise LLMError("the `claude` CLI is not on PATH")
    # On Windows `claude` is a .cmd shim, and cmd.exe mangles multi-line or empty
    # arguments, so the whole prompt goes on stdin and "no tools" is `--tools=`.
    cmd = [exe, "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--tools="]
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(cmd, input=f"{instruction}\n\n{stdin}", capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=timeout)
    if proc.returncode != 0:
        raise LLMError(f"claude -p failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise LLMError(f"claude -p returned an error: {str(out.get('result'))[:500]}")
    usage = out.get("usage") or {}
    return {
        "text": out.get("result", ""),
        "model": next(iter(out.get("modelUsage") or {}), model),
        "cost_usd": out.get("total_cost_usd"),
        "usage": {k: usage.get(k) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")},
    }


def parse_json(text: str):
    """The first JSON object in a reply, tolerating code fences or a preamble."""
    match = re.search(r"\{.*\}", text, re.S)
    if match is None:
        raise LLMError(f"no JSON object in reply: {text[:200]!r}")
    return json.loads(match.group(0))
