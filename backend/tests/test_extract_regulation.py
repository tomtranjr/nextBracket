"""Tests for `scripts/extract_regulation.py`.

The fixtures are short, hand-written copies of lines from AFMAN 36-2905, so these tests run without
the PDF. Bold text is marked with `bold()`, since run-in headings and headings are bold in the PDF.
"""

import json

import pytest

from scripts.extract_regulation import (
    DEFAULT_OUT,
    DEFAULT_PDF,
    PARAGRAPH_RE,
    Block,
    Chunk,
    Line,
    body_lines,
    bold_prefix_of,
    check_order,
    drop_page_headers,
    extract_chunks,
    follows,
    join_lines,
    parent_keys,
    run_in_title,
    split_blocks,
    to_chunks,
)


def plain(text: str, page: int = 1) -> Line:
    return Line(text, page)


def bold(text: str, page: int = 1) -> Line:
    return Line(text, page, bold_prefix=text)


def lead(text: str, bold_part: str, page: int = 1) -> Line:
    """A line that starts with bold text, like a run-in heading."""
    return Line(text, page, bold_prefix=bold_part)


def chunks_of(lines: list[Line]) -> dict[str, Chunk]:
    blocks, headings = split_blocks(lines)
    return {c.paragraph: c for c in to_chunks(blocks, headings)}


# --- reading lines ---


def test_bold_prefix_of_counts_only_leading_bold_characters() -> None:
    text = "3.7. Scoring. Body"
    bold_chars: list[dict[str, object]] = [
        {"text": c, "fontname": "X+TimesNewRomanPS-BoldMT"} for c in "3.7.Scoring."
    ]
    plain_chars: list[dict[str, object]] = [
        {"text": c, "fontname": "X+TimesNewRomanPSMT"} for c in "Body"
    ]
    chars = bold_chars + plain_chars
    assert bold_prefix_of(text, chars) == "3.7. Scoring."


def test_bold_prefix_of_whole_line() -> None:
    chars: list[dict[str, object]] = [{"text": c, "fontname": "Bold"} for c in "Chapter3"]
    assert bold_prefix_of("Chapter 3", chars) == "Chapter 3"


def test_bold_prefix_of_no_bold() -> None:
    chars: list[dict[str, object]] = [{"text": "x", "fontname": "Regular"}]
    assert bold_prefix_of("x", chars) == ""


def test_drop_page_headers_removes_both_header_forms() -> None:
    lines = [
        bold("6 AFMAN36-2905 24 MARCH 2026"),
        plain("1.1. Overview."),
        bold("AFMAN36-2905 24 MARCH 2026 7"),
        plain("text that names AFMAN36-2905 24 MARCH 2026 inside a sentence"),
    ]
    assert [line.text for line in drop_page_headers(lines)] == [
        "1.1. Overview.",
        "text that names AFMAN36-2905 24 MARCH 2026 inside a sentence",
    ]


def test_body_lines_skips_front_matter_signature_and_attachment_9() -> None:
    lines = [
        plain("Chapter 1—GENERAL INFORMATION 6"),  # table of contents entry, not a heading
        bold("Chapter 1"),
        bold("GENERAL INFORMATION"),
        plain("8.4. Last paragraph."),
        plain("BRIAN L. SCARLETT"),
        plain("Principal Deputy Assistant Secretary"),
        plain("Air Force for Manpower and Reserve Affairs"),
        bold("Attachment 8"),
        plain("Attachment 9 to the member"),  # wrapped prose, not a heading
        bold("Attachment 9"),
        plain("body fat table"),
    ]
    assert [line.text for line in body_lines(lines)] == [
        "Chapter 1",
        "GENERAL INFORMATION",
        "8.4. Last paragraph.",
        "Attachment 8",
        "Attachment 9 to the member",
    ]


def test_body_lines_fails_without_attachment_9() -> None:
    with pytest.raises(ValueError, match="Attachment 9"):
        body_lines([bold("Chapter 1"), plain("1.1. Text.")])


def test_body_lines_fails_if_the_signature_block_is_missing() -> None:
    with pytest.raises(ValueError, match="signature"):
        body_lines([bold("Chapter 1"), plain("1.1. Text."), bold("Attachment 9")])


# --- paragraph numbers ---


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("3.7.1. Members achieve a composite score", "3.7.1"),
        ("1.2. Required Physical Conditioning Program (PCP).", "1.2"),
        ("3.1.2.1.1. Members that are identified", "3.1.2.1.1"),
        ("A2.1. Verbal Air Force Fitness Assessment Instructions.", "A2.1"),
        ("2.28.1.", "2.28.1"),
    ],
)
def test_paragraph_re_matches_numbers(text: str, number: str) -> None:
    match = PARAGRAPH_RE.match(text)
    assert match is not None
    assert match.group(1) == number


@pytest.mark.parametrize(
    "text",
    [
        "1. Disapproved memorandum from the member",  # list item
        "3.10.8 from the date they arrived on station",  # wrapped reference, no period
        "2.0 mile run",
        "36- 2501, Officer Promotions",
    ],
)
def test_paragraph_re_skips_non_paragraphs(text: str) -> None:
    assert PARAGRAPH_RE.match(text) is None


# --- titles ---


def test_run_in_title_reads_the_bold_heading() -> None:
    line = lead(
        "2.1. Chief of Staff of the Air Force. Directs", "2.1. Chief of Staff of the Air Force."
    )
    assert run_in_title([line], "2.1") == "Chief of Staff of the Air Force"


def test_run_in_title_follows_a_wrapped_heading() -> None:
    lines = [
        bold("8.4. Correcting Administrative Errors on Fitness Assessment Scores in"),
        lead("myFitness. Administrative errors are limited", "myFitness."),
    ]
    assert run_in_title(lines, "8.4") == (
        "Correcting Administrative Errors on Fitness Assessment Scores in myFitness"
    )


def test_run_in_title_is_empty_without_bold() -> None:
    assert run_in_title([plain("3.7.1. Members achieve a composite score")], "3.7.1") == ""


def test_run_in_title_ignores_bold_notes_and_tiers() -> None:
    line = lead("3.4.5. Note: text", "3.4.5. Note:")
    assert run_in_title([line], "3.4.5") == ""


def test_parent_keys_nearest_first() -> None:
    assert parent_keys("3.15.4.2") == ["3.15.4", "3.15", "3"]
    assert parent_keys("A2.1") == ["A2"]


# --- splitting into chunks ---

CHAPTER_3 = [
    bold("Chapter 3"),
    bold("OFFICIAL FITNESS ASSESSMENT"),
    bold("3.7. Scoring."),
    plain("3.7.1. Members achieve a composite score from 0 to 100 based on the following maximum"),
    plain("component scores with component minimums.", page=2),
    plain("3.7.2. Appoints managers in accordance with paragraph"),
    bold("2.28.1."),
    plain("3.7.3. The 2-kilometer walk is a pass or fail assessment. The body composition is age-"),
    plain("agnostic."),
    bold("Table 3.1. Walk Standards (2 Kilometer)."),
    plain("< 30 16:16 <30 17:22"),
    bold("Table 3.2. Body Fat Assessment (BFA) Standards."),
    bold("Male Standard Female Standard"),
    plain("with Table 4.1. Exemptions for medical reasons"),
    lead("3.7.4. Excellent (> 90) (Ready). All members", "3.7.4. Excellent (> 90) (Ready)."),
]


def test_split_chunks_paragraphs_and_titles() -> None:
    chunks = chunks_of(CHAPTER_3)
    assert list(chunks) == ["3.7", "3.7.1", "3.7.2", "3.7.3", "3.7.4"]
    assert chunks["3.7"].title == "Scoring"
    # No run-in heading, so the title comes from the parent.
    assert chunks["3.7.1"].title == "Scoring"
    assert chunks["3.7.4"].title == "Excellent (> 90) (Ready)"


def test_split_joins_wrapped_lines_and_drops_the_number() -> None:
    chunk = chunks_of(CHAPTER_3)["3.7.1"]
    assert chunk.text == (
        "Members achieve a composite score from 0 to 100 based on the following maximum "
        "component scores with component minimums."
    )
    assert chunk.page == 1


def test_split_keeps_a_wrapped_cross_reference_in_its_paragraph() -> None:
    chunk = chunks_of(CHAPTER_3)["3.7.2"]
    assert chunk.text == "Appoints managers in accordance with paragraph 2.28.1."


def test_split_drops_table_3_1_and_keeps_table_3_2_as_lines() -> None:
    text = chunks_of(CHAPTER_3)["3.7.3"].text
    assert "16:16" not in text
    assert "Walk Standards" not in text
    assert text == (
        "The 2-kilometer walk is a pass or fail assessment. The body composition is age-agnostic.\n"
        "Table 3.2. Body Fat Assessment (BFA) Standards.\n"
        "Male Standard Female Standard\n"
        "with Table 4.1. Exemptions for medical reasons"
    )


def test_split_attachment_intro_and_glossary_sections() -> None:
    lines = [
        bold("Attachment 1"),
        bold("GLOSSARY OF REFERENCES AND SUPPORTING INFORMATION"),
        bold("References"),
        plain("DoDI 1308.03, DoD Physical Fitness/Body Composition Program, 10 March 2022"),
        bold("Terms"),
        plain("Unit Fitness Program Manager—Appointed by unit commander."),
        bold("Attachment 3"),
        bold("ALTITUDE TIME CORRECTION FOR 2.0 MILE RUN, 2.0 KILOMETER WALK, AND"),
        bold("20-METER HAMR"),
        bold("Table A3.1. Altitude Time Correction for 2.0 Mile Run."),
        plain("Group 1 Group 2"),
        bold("Attachment 5"),
        bold("ADMINISTRATIVE AND PERSONNEL ACTIONS"),
        lead("A5.1. General. This attachment provides", "A5.1. General."),
    ]
    chunks = chunks_of(lines)
    assert list(chunks) == ["A1-references", "A1-terms", "A3", "A5.1"]
    assert chunks["A1-terms"].title == "Terms"
    assert chunks["A1-terms"].text == "Unit Fitness Program Manager—Appointed by unit commander."
    assert chunks["A3"].title == (
        "ALTITUDE TIME CORRECTION FOR 2.0 MILE RUN, 2.0 KILOMETER WALK, AND 20-METER HAMR"
    )
    assert chunks["A3"].text == (
        "Table A3.1. Altitude Time Correction for 2.0 Mile Run.\nGroup 1 Group 2"
    )
    assert chunks["A5.1"].title == "General"


def test_split_fails_on_chapter_text_with_no_number() -> None:
    with pytest.raises(ValueError, match="no paragraph number"):
        split_blocks([bold("Chapter 2"), bold("ROLES"), plain("stray text")])


def test_to_chunks_fails_without_any_title() -> None:
    block = Block("9.1", 1, [(plain("9.1. Text."), False)])
    with pytest.raises(ValueError, match="no title"):
        to_chunks([block], {})


def test_join_lines_keeps_table_breaks() -> None:
    lines = [(plain("a"), False), (plain("b"), True), (plain("c"), True)]
    assert join_lines(lines) == "a\nb\nc"


# --- order ---


@pytest.mark.parametrize(
    ("prev", "nxt"),
    [
        ((3, 7), (3, 7, 1)),
        ((3, 7, 5), (3, 8)),
        ((3, 15, 4, 2), (3, 15, 5)),
        ((2, 30, 4), (3, 1)),
        ((1, 2, 4), (1, 2, 4, 1, 1)),
    ],
)
def test_follows_accepts_outline_steps(prev: tuple[int, ...], nxt: tuple[int, ...]) -> None:
    assert follows(prev, nxt)


@pytest.mark.parametrize(
    ("prev", "nxt"),
    [
        ((3, 7), (3, 9)),  # skips 3.8
        ((3, 7), (3, 7, 2)),  # skips 3.7.1
        ((3, 7, 1), (3, 7, 1)),  # repeats
        ((3, 8), (3, 7, 1)),  # goes back
    ],
)
def test_follows_rejects_breaks(prev: tuple[int, ...], nxt: tuple[int, ...]) -> None:
    assert not follows(prev, nxt)


def test_check_order_accepts_chapters_then_attachments() -> None:
    check_order(
        ["1.1", "1.1.1", "1.2", "2.1", "A1-references", "A1-terms", "A2.1", "A3", "A4", "A5.1"]
    )


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        (["1.1", "1.3"], "cannot follow"),
        (["1.1", "1.1"], "duplicate"),
        (["1.1", "A1-terms", "1.2"], "after an attachment"),
        (["1.1", "A2.1", "A2.3"], "cannot follow"),
    ],
)
def test_check_order_rejects(keys: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_order(keys)


# --- the real PDF (local only; the PDF is git-ignored) ---


@pytest.mark.skipif(not DEFAULT_PDF.exists(), reason="AFMAN PDF is git-ignored")
def test_committed_jsonl_matches_a_fresh_extract() -> None:
    fresh = [json.dumps(c.__dict__, ensure_ascii=False) for c in extract_chunks(DEFAULT_PDF)]
    committed = DEFAULT_OUT.read_text(encoding="utf-8").splitlines()
    assert fresh == committed
