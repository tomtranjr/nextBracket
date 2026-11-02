"""Turn AFMAN 36-2905 into paragraph chunks in `data/regulation/chunks.jsonl`.

Run from `backend/`:

    uv run python -m scripts.extract_regulation

The input is the e-Publishing original. It has a text layer, so `pdfplumber` reads it and no OCR is
needed. The PDF is git-ignored. The JSONL output is committed, so later steps work without the PDF.

One chunk per numbered paragraph at any depth (3.7, 3.7.1, 3.7.1.1). A chunk holds only its own
text, up to the next number. Attachments with no numbered paragraphs become one chunk each (`A3`).
Attachment 1 is a glossary and splits on its section headings (`A1-terms`).

Left out: the front matter and table of contents, the signature block, Table 3.1 (it repeats the
walk values in the scoring charts), and Attachments 9 and 10 (body fat tables).

The script fails loudly on anything odd (a paragraph number out of order, text with no paragraph)
instead of guessing.
"""

import argparse
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pdfplumber

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_PDF = BACKEND / "data" / "sources" / "DAFMAN 36-2905 (e-Publishing).pdf"
DEFAULT_OUT = BACKEND / "data" / "regulation" / "chunks.jsonl"

# The 24 March 2026 issue is titled AFMAN 36-2905. It supersedes DAFMAN 36-2905 (22 April 2022).
SOURCE_DOC = "AFMAN 36-2905"
VERSION = "2026-03-24"

# Every page has a header, either "6 AFMAN36-2905 24 MARCH 2026" or "AFMAN36-2905 24 MARCH 2026 7".
PAGE_HEADER_RE = re.compile(r"^(\d+ )?AFMAN36-2905 24 MARCH 2026( \d+)?$")

# A paragraph number needs at least two parts and a period, then a space or the line end. This
# skips list items ("1. Disapproved memorandum") and wrapped references ("3.10.8 from the date").
PARAGRAPH_RE = re.compile(r"^((?:A\d+|\d+)(?:\.\d+)+)\.(?:\s+|$)")
# A cross-reference can wrap so that its number starts the next line: "in accordance with
# paragraph" / "2.28.1." (2.26.7). After a line that ends like this, a number is not a paragraph.
CROSS_REF_END_RE = re.compile(r"\bparagraphs?$")
HEADING_RE = re.compile(r"^(Chapter|Attachment) (\d+)$")
# A caption line is fully bold. A prose line can also start with "Table 4.1." (4.1).
CAPTION_RE = re.compile(r"^(?:Table|Figure) A?\d+\.\d+\.")

FIRST_CHAPTER = 1
# Attachment 9 is the first excluded part. Attachment 10 follows it and ends the document.
STOP_ATTACHMENT = 9

# Section headings inside Attachment 1 (the glossary), each mapped to its chunk key.
GLOSSARY_SECTIONS = {
    "References": "A1-references",
    "Prescribed Forms": "A1-prescribed-forms",
    "Adopted Forms": "A1-adopted-forms",
    "Abbreviations and Acronyms": "A1-abbreviations",
    "Terms": "A1-terms",
}

# Table 3.1 prints the 2 km walk times, which are already in the scoring charts. Scoring values
# come from data/standards/, never from retrieved text, so the table stays out of the corpus.
DROPPED_CAPTIONS = ("Table 3.1.",)

# The signature block between paragraph 8.4 and Attachment 1.
SIGNATURE_LINES = frozenset(
    {
        "BRIAN L. SCARLETT",
        "Principal Deputy Assistant Secretary",
        "Air Force for Manpower and Reserve Affairs",
    }
)

# Bold text that can open a paragraph but is not a run-in heading.
NOT_TITLES = ("Note", "(T-")


@dataclass(frozen=True)
class Line:
    text: str
    page: int
    # The leading run of bold text on the line. Run-in headings are bold, body text is not.
    bold_prefix: str = ""

    @property
    def all_bold(self) -> bool:
        return self.text != "" and self.bold_prefix == self.text


@dataclass
class Block:
    key: str
    page: int
    # (line, in_table). Prose lines join with spaces. Table lines keep their line breaks.
    lines: list[tuple[Line, bool]] = field(default_factory=list)
    # Set for blocks with no paragraph number: an attachment intro or a glossary section.
    title: str = ""


@dataclass(frozen=True)
class Chunk:
    paragraph: str
    title: str
    text: str
    source_doc: str
    version: str
    page: int


def clean(text: str) -> str:
    """Collapse runs of whitespace (including non-breaking spaces) into one space."""
    return " ".join(text.split())


def bold_prefix_of(text: str, chars: list[dict[str, object]]) -> str:
    """Return the part of `text` that the leading bold characters cover.

    `chars` has no space characters, so count the non-space characters of `text`.
    """
    bold = 0
    for char in chars:
        if not str(char["text"]).strip():
            continue
        if "Bold" not in str(char["fontname"]):
            break
        bold += 1
    seen = 0
    for i, ch in enumerate(text):
        if seen == bold:
            return text[:i].rstrip()
        if not ch.isspace():
            seen += 1
    return text


def read_lines(pdf_path: Path) -> list[Line]:
    lines: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            for raw in page.extract_text_lines(return_chars=True):
                text = clean(raw["text"])
                if text:
                    lines.append(Line(text, number, clean(bold_prefix_of(text, raw["chars"]))))
    return lines


def drop_page_headers(lines: Iterable[Line]) -> list[Line]:
    return [line for line in lines if not PAGE_HEADER_RE.match(line.text)]


def body_lines(lines: list[Line]) -> list[Line]:
    """Keep the text from the Chapter 1 heading up to the first excluded attachment."""
    start = stop = None
    for i, line in enumerate(lines):
        match = HEADING_RE.match(line.text)
        if not match or not line.all_bold:
            continue
        kind, number = match.group(1), int(match.group(2))
        if kind == "Chapter" and number == FIRST_CHAPTER and start is None:
            start = i
        if kind == "Attachment" and number == STOP_ATTACHMENT:
            stop = i
            break
    if start is None or stop is None:
        raise ValueError("cannot find the Chapter 1 heading or the Attachment 9 heading")
    body = [line for line in lines[start:stop] if line.text not in SIGNATURE_LINES]
    if len(body) != stop - start - len(SIGNATURE_LINES):
        raise ValueError("the signature block did not match exactly once")
    return body


def run_in_title(block_lines: list[Line], number: str) -> str:
    """Return the bold run-in heading after the paragraph number, or "" if there is none.

    A heading can wrap onto the next line (8.4 ends with "in" / "myFitness.").
    """
    first = block_lines[0]
    if not first.bold_prefix.startswith(number):
        return ""
    title = first.bold_prefix[len(number) + 1 :].strip()
    if first.all_bold and len(block_lines) > 1:
        title = f"{title} {block_lines[1].bold_prefix}".strip()
    if title.startswith(NOT_TITLES):
        return ""
    return title.rstrip(".").strip()


def split_blocks(lines: list[Line]) -> tuple[list[Block], dict[str, str]]:
    """Split the body into blocks. Also return the chapter and attachment titles by key."""
    blocks: list[Block] = []
    headings: dict[str, str] = {}
    current: Block | None = None
    heading_key: str | None = None  # "1" for Chapter 1, "A3" for Attachment 3
    reading_heading_title = in_table = dropping = False
    prev_text = ""

    for line in lines:
        text = line.text
        heading = HEADING_RE.match(text) if line.all_bold else None
        if heading:
            if current is not None:
                blocks.append(current)
            current = None
            prefix = "" if heading.group(1) == "Chapter" else "A"
            heading_key = f"{prefix}{heading.group(2)}"
            headings[heading_key] = ""
            reading_heading_title = True
            in_table = dropping = False
            continue
        # The heading title is the run of bold upper-case lines after the heading. It can wrap.
        if reading_heading_title and line.all_bold and text.upper() == text:
            assert heading_key is not None
            headings[heading_key] = clean(f"{headings[heading_key]} {text}")
            continue
        reading_heading_title = False
        if heading_key is None:
            raise ValueError(f"text before the first heading: {text!r}")

        paragraph = None if CROSS_REF_END_RE.search(prev_text) else PARAGRAPH_RE.match(text)
        prev_text = text
        glossary = GLOSSARY_SECTIONS.get(text) if heading_key == "A1" and line.all_bold else None
        if paragraph or glossary:
            if current is not None:
                blocks.append(current)
            in_table = dropping = False
            if glossary:
                current = Block(glossary, line.page, title=text)
                continue
            assert paragraph is not None
            current = Block(paragraph.group(1), line.page)
        elif CAPTION_RE.match(text) and line.all_bold:
            in_table = True
            dropping = text.startswith(DROPPED_CAPTIONS)
            if dropping:
                continue
        elif dropping:
            continue

        if current is None:
            # Unnumbered text right after an attachment title is that attachment's own chunk.
            if not heading_key.startswith("A"):
                raise ValueError(f"chapter {heading_key}: text with no paragraph number: {text!r}")
            current = Block(heading_key, line.page, title=headings[heading_key])
        current.lines.append((line, in_table))
    if current is not None:
        blocks.append(current)
    return blocks, headings


def join_lines(lines: list[tuple[Line, bool]]) -> str:
    out = ""
    for i, (line, in_table) in enumerate(lines):
        text = line.text
        if i == 0:
            out = text
        elif in_table or lines[i - 1][1]:
            out += "\n" + text
        elif out.endswith("-"):
            # A line that ends in a hyphen splits a compound word ("age-" / "agnostic"). Keep it.
            out += text
        else:
            out += " " + text
    return out


def parent_keys(key: str) -> list[str]:
    """Return the ancestors of a paragraph key, nearest first. 3.7.1 gives 3.7 then 3."""
    parts = key.split(".")
    return [".".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]


def to_chunks(blocks: list[Block], headings: dict[str, str]) -> list[Chunk]:
    titles: dict[str, str] = dict(headings)
    chunks: list[Chunk] = []
    for block in blocks:
        title = block.title or run_in_title([line for line, _ in block.lines[:2]], block.key)
        if title:
            titles[block.key] = title
        else:
            title = next((titles[p] for p in parent_keys(block.key) if titles.get(p)), "")
        if not title:
            raise ValueError(f"{block.key}: no title and no titled ancestor")
        text = join_lines(block.lines)
        if not block.title:
            # The paragraph number lives in `paragraph`, so drop it from the text.
            text = PARAGRAPH_RE.sub("", text, count=1)
        if not text.strip():
            raise ValueError(f"{block.key}: empty text")
        chunks.append(Chunk(block.key, title, text.strip(), SOURCE_DOC, VERSION, block.page))
    return chunks


def number_parts(key: str) -> tuple[str, tuple[int, ...]]:
    """Split "A2.3.1" into ("A", (2, 3, 1)) and "3.7" into ("", (3, 7))."""
    kind = "A" if key.startswith("A") else ""
    return kind, tuple(int(p) for p in key.removeprefix("A").split("."))


def follows(prev: tuple[int, ...], nxt: tuple[int, ...]) -> bool:
    """True if `nxt` can come right after `prev` in an outline.

    It can go one or more levels down (3.7 to 3.7.1), or move to the next sibling at any level and
    then go down (3.7.5 to 3.8, or 3.15.4.2 to 3.15.5).
    """
    if len(nxt) > len(prev) and nxt[: len(prev)] == prev:
        return all(p == 1 for p in nxt[len(prev) :])
    for k in range(len(prev), 0, -1):
        sibling = prev[: k - 1] + (prev[k - 1] + 1,)
        if nxt[:k] == sibling and all(p == 1 for p in nxt[k:]):
            return True
    return False


def check_order(keys: list[str]) -> None:
    """Fail on a duplicate key, or a paragraph number that breaks the outline order.

    Chapters (1.1 to 8.4) come first, then attachments (A1 to A8). An attachment key (A3) stands
    for the attachment itself. The glossary keys (A1-terms) all stand for A1.
    """
    seen: set[str] = set()
    last: dict[str, tuple[int, ...]] = {"": (0,), "A": (0,)}
    for key in keys:
        if key in seen:
            raise ValueError(f"duplicate paragraph {key}")
        seen.add(key)
        kind, parts = number_parts(key.split("-")[0])
        if kind == "" and last["A"] != (0,):
            raise ValueError(f"paragraph {key} comes after an attachment")
        prev = last[kind]
        same_glossary = "-" in key and parts == prev
        if not same_glossary and not follows(prev, parts):
            raise ValueError(f"paragraph {key} cannot follow {kind}{'.'.join(map(str, prev))}")
        last[kind] = parts


def extract_chunks(pdf_path: Path) -> list[Chunk]:
    lines = body_lines(drop_page_headers(read_lines(pdf_path)))
    blocks, headings = split_blocks(lines)
    chunks = to_chunks(blocks, headings)
    check_order([c.paragraph for c in chunks])
    return chunks


def write_jsonl(chunks: list[Chunk], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    chunks = extract_chunks(args.pdf)
    write_jsonl(chunks, args.out)
    longest = max(chunks, key=lambda c: len(c.text))
    print(f"wrote {len(chunks)} chunks to {args.out}")
    print(f"longest: {longest.paragraph} ({len(longest.text)} characters)")


if __name__ == "__main__":
    main()
