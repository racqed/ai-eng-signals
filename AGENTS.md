# Agent guide

What works with coding agents: practitioner posts (what people claim) and my own Claude Code and Codex session logs (what I actually do). Python 3.11, package in `src/ai_eng_signals/`, CLI `signals`.

## Open only the file you need

| Request | File |
| --- | --- |
| Session parsing (Claude Code, Codex) | `src/ai_eng_signals/sessions.py` |
| Session report numbers or wording | `src/ai_eng_signals/report.py` |
| Topic classifier, topics, LLM prompt | `src/ai_eng_signals/posts.py` |
| `claude -p` calls | `src/ai_eng_signals/llm.py` |
| Privacy checks | `src/ai_eng_signals/privacy.py` |
| Which logs may be read, project aliases | `config/sources.toml` |
| Posts | `data/posts.json` (copied from the AI Engineer Log's community page) |

`reports/` and `models/*/MODEL_CARD.md` are generated. Regenerate them; never edit them by hand.

## Commands

```
.venv/Scripts/python -m pytest -q     # tests (bin/ instead of Scripts/ outside Windows)
signals sessions                      # local logs -> reports/sessions.{json,md}
signals topics [--no-llm] [--refresh] # classifiers -> reports/topic-eval.json
signals model-card                    # -> models/topic-classifier/MODEL_CARD.md
signals check-privacy                 # what the pre-commit hook runs
```

## Rules

1. **Privacy comes first.** Raw session logs never leave this machine and are never committed, quoted or summarised in prose. Only the numeric fields in `ROW_FIELDS` are published. Don't widen what `sessions.py` keeps (no prompt text, file paths, commands or session ids) without asking me.
2. Read only the folders allowlisted in `config/sources.toml`. Work projects are deliberately excluded; never add them.
3. My real name and work email never appear in this repo, its history or anything published from it. The only name is "K.Wright". Don't write them anywhere, including this file. The privacy check reads them from the untracked `.private-terms`; never commit or print that file. Commits are authored `K.Wright <347319057+racqed@users.noreply.github.com>` (repo git config); check `git log --format='%an <%ae>'` before pushing. All GitHub work goes through the `racqed` account.
4. Enable the hook once per clone: `git config core.hooksPath .githooks`. Never bypass it with `--no-verify`.
5. **Never invent numbers.** Every figure in a report or the README comes from a generated report. If the sample is too small to support a claim, say so.
6. `data/labels.json` holds labels I reviewed myself. Don't add to it unless I give you the label.
7. `signals topics` calls `claude -p` and costs money. Results are cached in `reports/llm-labels.json`; use `--refresh` only when the prompt, model or posts change on purpose.
8. Plain British English, short sentences, no hype.

## Before you finish

Run the tests and `signals check-privacy`. Don't hand back work while either fails. Don't push unless asked.
