"""Topic classification for practitioner posts: a cheap baseline and an LLM.

Labels in data/posts.json were assigned when the posts were curated for the
AI Engineer Log. data/labels.json holds my own reviewed labels; where a post
has one, it overrides the curation label as the reference.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

from . import ROOT
from . import llm

TOPICS = {
    "agent-workflow": "How to drive coding agents day to day: planning, sessions, parallel agents, tool choice.",
    "token-cost": "Token use, context size, caching and what agent work costs.",
    "instructions-context": "Instruction files (AGENTS.md, CLAUDE.md), skills, rules and what context to give an agent.",
    "review-evals": "Reviewing agent output: code review, tests, hooks, guardrails and evals.",
    "career": "Jobs, hiring and skills for AI engineers.",
}
POSTS = ROOT / "data" / "posts.json"
LABELS = ROOT / "data" / "labels.json"
EVAL = ROOT / "reports" / "topic-eval.json"
LLM_CACHE = ROOT / "reports" / "llm-labels.json"


def load_posts(path: Path = POSTS) -> list[dict]:
    posts = json.loads(path.read_text(encoding="utf-8"))["posts"]
    reviewed = json.loads(LABELS.read_text(encoding="utf-8")).get("labels", {}) if LABELS.exists() and path == POSTS else {}
    for p in posts:
        p["reference"] = reviewed.get(p["id"], p["topic"])
        p["reviewed"] = p["id"] in reviewed
    return posts


def text(post: dict) -> str:
    return " ".join(filter(None, [post.get("summary"), post.get("tip")]))


def metrics(gold: list[str], pred: list[str]) -> dict:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

    labels = [t for t in TOPICS if t in set(gold) | set(pred)]
    per_class = f1_score(gold, pred, labels=labels, average=None, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(gold, pred)), 3),
        "macro_f1": round(float(f1_score(gold, pred, labels=labels, average="macro", zero_division=0)), 3),
        "f1_by_topic": {t: round(float(f), 3) for t, f in zip(labels, per_class)},
        "confusion": {"labels": labels, "matrix": confusion_matrix(gold, pred, labels=labels).tolist()},
    }


def baseline(posts: list[dict], seed: int = 0) -> dict:
    """TF-IDF + logistic regression, scored with stratified cross-validation."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline

    gold = [p["reference"] for p in posts]
    folds = max(2, min(5, min(Counter(gold).values())))
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )
    pred = cross_val_predict(model, [text(p) for p in posts], gold, cv=StratifiedKFold(folds, shuffle=True, random_state=seed))
    majority = Counter(gold).most_common(1)[0][1] / len(gold)
    return {
        "method": f"TF-IDF (1-2 grams) + logistic regression, {folds}-fold stratified CV, seed {seed}",
        "majority_class_accuracy": round(majority, 3),
        **metrics(gold, list(pred)),
        "predictions": dict(zip([p["id"] for p in posts], map(str, pred))),
    }


def _instruction() -> str:
    topics = "\n".join(f"- {k}: {v}" for k, v in TOPICS.items())
    return (
        "You label short summaries of social media posts by practitioners. "
        "The posts are the JSON list of {id, text} at the end. Give each item exactly one topic from this list:\n"
        f"{topics}\n"
        'Reply with only JSON, no prose: {"labels": [{"id": "...", "topic": "..."}]}'
    )


def llm_labels(posts: list[dict], model: str = "haiku", refresh: bool = False) -> dict:
    """Label every post in one call, cached by prompt and model."""
    payload = json.dumps([{"id": p["id"], "text": text(p)} for p in posts], ensure_ascii=False)
    instruction = _instruction()
    key = hashlib.sha256(f"{model}\n{instruction}\n{payload}".encode()).hexdigest()[:16]
    if LLM_CACHE.exists() and not refresh:
        cached = json.loads(LLM_CACHE.read_text(encoding="utf-8"))
        if cached.get("key") == key:
            return cached
    reply = llm.ask(instruction, payload, model=model)
    labels = {item["id"]: item["topic"] for item in llm.parse_json(reply["text"])["labels"]}
    result = {
        "key": key,
        "date": date.today().isoformat(),
        "model": reply["model"],
        "cost_usd": reply["cost_usd"],
        "usage": reply["usage"],
        "labels": labels,
    }
    LLM_CACHE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def evaluate_llm(posts: list[dict], result: dict) -> dict:
    gold = [p["reference"] for p in posts]
    pred = [result["labels"].get(p["id"], "missing") for p in posts]
    return {
        "method": f"Zero-shot labelling by {result['model']} via claude -p, one call for all posts",
        "cost_usd": result["cost_usd"],
        **metrics(gold, pred),
        "disagreements": [p["id"] for p, g, y in zip(posts, gold, pred) if g != y],
    }


def write_eval(posts: list[dict], base: dict, llm_eval: dict | None) -> dict:
    report = {
        "date": date.today().isoformat(),
        "posts": len(posts),
        "languages": dict(Counter(p["lang"] for p in posts)),
        "topics": dict(Counter(p["reference"] for p in posts)),
        "reviewed_labels": sum(p["reviewed"] for p in posts),
        "baseline": base,
        "llm": llm_eval,
    }
    EVAL.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
