import shutil
from pathlib import Path

from ai_eng_signals.report import markdown, summarise
from ai_eng_signals.sessions import ROW_FIELDS, collect, parse_claude, parse_codex

FIX = Path(__file__).parent / "fixtures"


def test_claude_counts_each_api_message_once():
    s = parse_claude(FIX / "claude_session.jsonl")
    assert s.api_calls == 2
    assert s.input_tokens == 13 and s.output_tokens == 60  # m1 max(5, 40) + m2 20
    assert s.cache_read_tokens == 2500 and s.cache_write_tokens == 200


def test_claude_prompts_tools_errors_and_compactions():
    s = parse_claude(FIX / "claude_session.jsonl")
    assert s.human_prompts == 2  # meta reminders and command output don't count
    assert s.tools == {"Read": 1, "Bash": 1}
    assert s.tool_errors == 1
    assert s.compactions == 1
    assert s.project == "demo" and s.kind == "main" and s.date == "2026-10-20"
    assert s.minutes == 10.0


def test_codex_splits_cached_tokens_out_of_input():
    s = parse_codex(FIX / "codex_session.jsonl")
    assert s.input_tokens == 500 and s.cache_read_tokens == 2500  # cumulative totals
    assert s.human_prompts == 2 and s.api_calls == 2
    assert s.tool_errors is None
    assert s.tools == {"shell": 1, "apply_patch": 1}


def test_rows_hold_numbers_not_text():
    row = parse_claude(FIX / "claude_session.jsonl").row()
    assert set(row) == set(ROW_FIELDS)
    flat = repr(row)
    assert "Add a test" not in flat and "/work/" not in flat and "s-1" not in flat


def test_collect_reads_only_allowlisted_folders(tmp_path):
    projects = tmp_path / ".claude" / "projects"
    (projects / "x-orca-projects-demo").mkdir(parents=True)
    (projects / "x-work-secret").mkdir(parents=True)
    shutil.copy(FIX / "claude_session.jsonl", projects / "x-orca-projects-demo" / "a.jsonl")
    shutil.copy(FIX / "claude_session.jsonl", projects / "x-work-secret" / "b.jsonl")
    codex = tmp_path / ".codex" / "sessions" / "2026"
    codex.mkdir(parents=True)
    shutil.copy(FIX / "codex_session.jsonl", codex / "r.jsonl")
    sources = {"claude": {"folders": ["*-orca-projects-*"]}, "codex": {"cwd_contains": ["/elsewhere/"]}, "aliases": {"demo": "public-demo"}}
    rows = collect(tmp_path, sources)
    assert len(rows) == 1 and rows[0].project == "public-demo"


def test_summary_and_markdown():
    rows = [parse_claude(FIX / "claude_session.jsonl"), parse_codex(FIX / "codex_session.jsonl")]
    summary = summarise(rows)
    assert summary["agents"]["claude-code"]["tool_error_rate"] == 0.5
    assert summary["agents"]["codex"]["tool_error_rate"] is None
    md = markdown(summary)
    assert "| Tool calls that failed | 50% | – |" in md
