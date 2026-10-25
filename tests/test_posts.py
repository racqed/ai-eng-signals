from ai_eng_signals import llm
from ai_eng_signals.posts import TOPICS, baseline, evaluate_llm, load_posts, metrics


def test_posts_have_known_topics():
    posts = load_posts()
    assert len(posts) >= 30
    assert {p["reference"] for p in posts} <= set(TOPICS)


def test_baseline_is_reproducible_and_complete():
    posts = load_posts()
    a, b = baseline(posts), baseline(posts)
    assert a["predictions"] == b["predictions"]
    assert set(a["predictions"]) == {p["id"] for p in posts}
    assert 0 <= a["accuracy"] <= 1


def test_metrics_perfect_and_confusion_shape():
    m = metrics(["career", "token-cost"], ["career", "token-cost"])
    assert m["accuracy"] == 1.0 and m["macro_f1"] == 1.0
    assert m["confusion"]["matrix"] == [[1, 0], [0, 1]]


def test_llm_eval_marks_missing_labels_as_disagreements():
    posts = [{"id": "t1", "reference": "career"}, {"id": "t2", "reference": "token-cost"}]
    result = {"model": "m", "cost_usd": 0.01, "labels": {"t1": "career"}}
    out = evaluate_llm(posts, result)
    assert out["disagreements"] == ["t2"] and out["accuracy"] == 0.5


def test_parse_json_tolerates_fences():
    assert llm.parse_json('```json\n{"labels": []}\n```') == {"labels": []}
