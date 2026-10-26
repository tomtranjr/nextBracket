"""Checks on the committed `data/regulation/chunks.jsonl`.

These run in CI without the PDF. The expected text below was read by hand from AFMAN 36-2905.
"""

import json
from typing import Any

import pytest

from scripts.extract_regulation import DEFAULT_OUT, SOURCE_DOC, VERSION, check_order

FIELDS = ["paragraph", "title", "text", "source_doc", "version", "page"]


@pytest.fixture(scope="module")
def chunks() -> list[dict[str, Any]]:
    with DEFAULT_OUT.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def by_paragraph(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["paragraph"]: c for c in chunks}


def test_every_chunk_has_the_fields_and_none_are_empty(chunks: list[dict[str, Any]]) -> None:
    for chunk in chunks:
        assert list(chunk) == FIELDS
        assert all(chunk[f] for f in FIELDS), chunk["paragraph"]


def test_one_source_and_version(chunks: list[dict[str, Any]]) -> None:
    assert {c["source_doc"] for c in chunks} == {SOURCE_DOC}
    assert {c["version"] for c in chunks} == {VERSION}


def test_paragraphs_are_unique_and_in_outline_order(chunks: list[dict[str, Any]]) -> None:
    check_order([c["paragraph"] for c in chunks])


def test_pages_never_go_back(chunks: list[dict[str, Any]]) -> None:
    pages = [c["page"] for c in chunks]
    assert pages == sorted(pages)
    assert pages[0] == 6  # Chapter 1 starts on page 6


def test_known_paragraphs_exist(by_paragraph: dict[str, dict[str, Any]]) -> None:
    assert by_paragraph["3.6.1"]["text"].startswith(
        "The categories of PFRA scores when assessing all components are: Excellent (> 90),"
    )
    assert by_paragraph["3.7.3"]["text"].startswith("The 2-kilometer walk is a pass or fail")
    assert by_paragraph["3.15.4.2"]["text"].startswith(
        "Body Composition will be assessed using WHtR measurements. (T-1)"
    )


def test_whtr_truncation_rule_is_in_3_15_4_2(by_paragraph: dict[str, dict[str, Any]]) -> None:
    text = by_paragraph["3.15.4.2"]["text"]
    assert "truncated (not rounded) to the first two decimal points" in text
    assert by_paragraph["3.15.4.2"]["page"] == 35


def test_body_fat_tables_and_walk_chart_are_left_out(
    chunks: list[dict[str, Any]], by_paragraph: dict[str, dict[str, Any]]
) -> None:
    keys = {c["paragraph"] for c in chunks}
    assert not any(k.startswith(("A9", "A10")) for k in keys)
    text = "\n".join(c["text"] for c in chunks)
    assert "Table A9.1." not in text
    assert "Table A10.1." not in text
    assert "Table 3.1. Walk Standards" not in text
    # Table 3.1 follows 3.7.3 in the PDF. 16:16 is its male under-30 walk time.
    assert "16:16" not in by_paragraph["3.7.3"]["text"]


def test_no_page_headers_remain(chunks: list[dict[str, Any]]) -> None:
    assert not any("AFMAN36-2905 24 MARCH 2026" in c["text"] for c in chunks)


def test_attachments_present(by_paragraph: dict[str, dict[str, Any]]) -> None:
    for key in ["A1-terms", "A1-abbreviations", "A2.1", "A3", "A4", "A5.1", "A6", "A7.1", "A8"]:
        assert key in by_paragraph, key
