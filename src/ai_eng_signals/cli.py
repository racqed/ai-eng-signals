"""Command line: `signals <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from . import ROOT


def cmd_sessions(args) -> int:
    from .privacy import check_report
    from .report import markdown, summarise
    from .sessions import collect

    rows = collect()
    summary = summarise(rows)
    data = {"summary": summary, "sessions": [r.row() for r in sorted(rows, key=lambda r: (r.date, r.session))]}
    if problems := check_report(data["sessions"]):
        print("\n".join(problems), file=sys.stderr)
        return 1
    (ROOT / "reports" / "sessions.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "reports" / "sessions.md").write_text(markdown(summary), encoding="utf-8")
    print(f"{len(rows)} transcripts -> reports/sessions.json, reports/sessions.md")
    return 0


def cmd_topics(args) -> int:
    from . import posts as P

    items = P.load_posts()
    base = P.baseline(items)
    llm_eval = None
    if not args.no_llm:
        llm_eval = P.evaluate_llm(items, P.llm_labels(items, model=args.model, refresh=args.refresh))
    report = P.write_eval(items, base, llm_eval)
    print(f"baseline accuracy {base['accuracy']:.0%} (majority {base['majority_class_accuracy']:.0%})", end="")
    print(f", LLM {llm_eval['accuracy']:.0%}" if llm_eval else "", "->", P.EVAL.relative_to(ROOT).as_posix())
    return 0 if report else 1


def cmd_model_card(args) -> int:
    from .modelcard import CARD, write

    write()
    print("->", CARD.relative_to(ROOT).as_posix())
    return 0


def cmd_check_privacy(args) -> int:
    from .privacy import check

    problems = check(staged=args.staged)
    if problems:
        print("Privacy check failed:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 1
    print("Privacy check passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signals", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sessions", help="aggregate local session logs into reports/").set_defaults(func=cmd_sessions)
    t = sub.add_parser("topics", help="score the topic classifiers into reports/topic-eval.json")
    t.add_argument("--no-llm", action="store_true", help="baseline only, no claude -p call")
    t.add_argument("--refresh", action="store_true", help="ignore cached LLM labels")
    t.add_argument("--model", default="haiku")
    t.set_defaults(func=cmd_topics)
    sub.add_parser("model-card", help="regenerate the model card").set_defaults(func=cmd_model_card)
    c = sub.add_parser("check-privacy", help="scan files about to be committed")
    c.add_argument("--staged", action="store_true", help="only staged files (used by the pre-commit hook)")
    c.set_defaults(func=cmd_check_privacy)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
