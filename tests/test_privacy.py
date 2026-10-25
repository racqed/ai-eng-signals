from ai_eng_signals.privacy import check_report, scan_text


def test_flags_local_user_paths():
    # Split so this file doesn't trip the check it is testing.
    samples = ["C:" + "\\Users\\someone\\x", "c:" + "/Users/someone", "/Us" + "ers/someone/repo", "/ho" + "me/dev/repo", "C-" + "-Users-someone-orca"]
    for text in samples:
        assert scan_text("f", text, []), text


def test_allows_ordinary_paths_and_its_own_patterns():
    assert scan_text("f", "/work/orca/projects/demo and ~/.claude/projects", []) == []
    assert scan_text("f", r'[A-Za-z]:[\\/]+Users[\\/]+\w and r"/Users/\w[\w.-]*/"', []) == []


def test_private_terms_are_case_insensitive_and_not_echoed():
    problems = scan_text("notes.md", "Written by Jane Example", ["jane example"])
    assert problems == ["notes.md: private term #1 from .private-terms"]


def test_report_rows_must_use_allowlisted_fields():
    assert check_report([{"session": "a", "tool_calls": 1}]) == []
    assert check_report([{"session": "a", "prompt": "secret"}])
