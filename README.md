# ai-eng-signals

What actually works with coding agents? Practitioners on Threads share plenty of advice: plan first, keep instruction files short, clear the context often. This project collects those claims and checks them against the one dataset I can fully trust: my own Claude Code and Codex sessions.

It supports my public career log, the [AI Engineer Log](https://ai-engineer-log.latteboo99.workers.dev/en/), and is the repository I use to practise agent-ready engineering: short rules, a privacy guardrail that runs on every commit, generated reports and a model card.

## Two signals

**What practitioners say.** 35 public Threads posts about coding agents, tokens, instruction files, review and AI engineering careers, summarised in my own words (`data/posts.json`). A topic classifier files new posts so the community page stays organised.

| Topic classifier (35 posts) | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Always guess the most common topic | 26% | – |
| TF-IDF + logistic regression, 5-fold CV | 69% | 0.64 |
| Claude Haiku, zero-shot, one call ($0.0024 in total) | 91% | 0.90 |

The reference labels were assigned when the posts were curated with an agent's help, so "accuracy" here means agreement until I've reviewed them myself. Details and limits: [model card](models/topic-classifier/MODEL_CARD.md).

**What I actually do.** Every session log from my personal projects, reduced to numbers: tokens, cache reads, tool calls and failures, compactions, sub-agent use. First snapshot (24–25 Oct 2026, 10 Claude Code sessions with 20 sub-agent transcripts, 5 Codex sessions):

- 98% of all input tokens were read from cache, for both agents.
- 3.5% of Claude Code tool calls failed.
- Sub-agents used 11% of Claude Code's input tokens.

Full, regenerated numbers: [reports/sessions.md](reports/sessions.md). Two days of data is a description, not evidence; claims get tested as sessions accumulate.

## Privacy by design

Session logs contain everything: prompts, code and file paths. So:

- Only folders allowlisted in `config/sources.toml` are opened. Work projects are excluded.
- A parsed session keeps counts, token totals, model and tool names, and a project name. No text. Session ids are hashed.
- `signals check-privacy` runs as a pre-commit hook. It blocks raw logs, local home-directory paths, and private terms listed in a git-ignored file (so the check never publishes what it protects), and it rejects report rows with fields outside an allowlist.

## Use

```
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # .venv/bin on macOS/Linux
git config core.hooksPath .githooks
echo "your name" > .private-terms                   # one private term per line

signals sessions      # local logs -> reports/sessions.{json,md}
signals topics        # baseline + LLM labels (cached) -> reports/topic-eval.json
signals model-card    # -> models/topic-classifier/MODEL_CARD.md
python -m pytest -q
```

LLM calls go through headless Claude Code (`claude -p`) on my subscription, with no tools and no saved session, so they don't load this repo's context or show up in my own statistics.

## Next

1. Review the topic labels myself, starting with the three posts where the LLM disagrees.
2. Agent-ready kit: a reusable `AGENTS.md` template, two skills (retrain-and-validate, model-card update) and a hook that trims test output, then a before/after comparison on ten scripted maintenance tasks.
3. Turn the practitioner claims into measurable questions about my sessions, for example whether compacting or clearing the context changes tokens per prompt.
