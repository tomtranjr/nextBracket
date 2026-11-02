"""Checks on the retrieval eval set and the metric code in `evals/run_retrieval_eval.py`."""

import pytest

from evals.run_retrieval_eval import (
    EvalCase,
    evaluate,
    first_hit_rank,
    keyword_search,
    load_cases,
    load_chunks,
)


@pytest.fixture(scope="module")
def cases() -> list[EvalCase]:
    return load_cases()


@pytest.fixture(scope="module")
def paragraphs() -> set[str]:
    return {c["paragraph"] for c in load_chunks()}


def test_every_expected_paragraph_exists_in_the_chunks(
    cases: list[EvalCase], paragraphs: set[str]
) -> None:
    missing = {(c.id, p) for c in cases for p in c.expected if p not in paragraphs}
    assert not missing


def test_eval_set_size_and_shape(cases: list[EvalCase]) -> None:
    assert 30 <= len(cases) <= 50
    assert len({c.id for c in cases}) == len(cases)
    assert len({c.question for c in cases}) == len(cases)
    for case in cases:
        assert case.question.strip() and case.topic
        assert case.expected
        assert len(set(case.expected)) == len(case.expected), case.id


def test_first_hit_rank() -> None:
    assert first_hit_rank(["1.1", "3.10.3", "3.8.2"], ["3.8.2", "3.10.3"]) == 2
    assert first_hit_rank(["1.1"], ["3.10.3"]) is None
    assert first_hit_rank([], ["3.10.3"]) is None


def test_evaluate_computes_recall_and_mrr() -> None:
    cases = [
        EvalCase("a", "q1", ("x",), "t"),  # hit at rank 1
        EvalCase("b", "q2", ("y",), "t"),  # hit at rank 2
        EvalCase("c", "q3", ("z",), "t"),  # miss
        EvalCase("d", "q4", ("w",), "t"),  # rank 6 is outside k, so a miss
    ]
    answers = {
        "q1": ["x", "n"],
        "q2": ["n", "y"],
        "q3": ["n"],
        "q4": ["n1", "n2", "n3", "n4", "n5", "w"],
    }

    report = evaluate(lambda q, k: answers[q], cases, k=5)

    assert report["recall_at_k"] == 0.5
    assert report["mrr_at_k"] == round((1 + 0.5) / 4, 4)
    assert [r["rank"] for r in report["per_case"]] == [1, 2, None, None]
    assert report["per_case"][3]["top"] == ["n1", "n2", "n3", "n4", "n5"]


def test_evaluate_rejects_an_empty_set() -> None:
    with pytest.raises(ValueError):
        evaluate(lambda q, k: [], [])


def test_keyword_search_ranks_by_shared_words_then_document_order() -> None:
    chunks = [
        {"paragraph": "1", "title": "Run", "text": "The run is two miles."},
        {"paragraph": "2", "title": "Walk", "text": "The walk replaces the run."},
        {"paragraph": "3", "title": "Plank", "text": "Hold the plank."},
    ]
    search = keyword_search(chunks)

    assert search("walk run", 5) == ["2", "1"]
    assert search("run", 5) == ["1", "2"]
    assert search("run", 1) == ["1"]
    assert search("the", 5) == []  # stopwords alone match nothing
