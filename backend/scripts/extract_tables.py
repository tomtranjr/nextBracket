"""Turn `PFRA Scoring Charts.pdf` into a versioned standards JSON file.

Run from `backend/`:

    uv run python -m scripts.extract_tables

The output is NOT trusted until a person has checked it against the PDF. This script only
removes typing; it does not prove the numbers are right. It fails loudly on anything odd
(unknown cell, wrong table shape, broken ordering) instead of guessing.

Only pages 1 to 8 are read. They hold the 8 events by age band and sex. The AFSPECWAR/EOD page and
the 2 km walk page use other layouts and are out of scope here.
"""

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pdfplumber

from app.core.standards import parse_standards
from app.models import SEXES, StandardsFile

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_PDF = BACKEND / "data" / "sources" / "PFRA Scoring Charts.pdf"
DEFAULT_OUT = BACKEND / "data" / "standards" / "2026-03-01.json"

VERSION = "2026-03-01"
EFFECTIVE_DATE = date(2026, 3, 1)
SOURCE = "PFRA Scoring Charts.pdf (Final USAF PFRA Scoring, effective 1 Mar 26)"
PASSING_TOTAL = 75

COMPONENTS: dict[str, dict[str, Any]] = {
    "cardio": {"max_points": 50, "has_minimum": True, "events": ["run_2mile", "hamr_20m"]},
    "strength": {
        "max_points": 15,
        "has_minimum": True,
        "events": ["push_up", "hand_release_push_up"],
    },
    "core": {
        "max_points": 15,
        "has_minimum": True,
        "events": ["sit_up", "cross_leg_reverse_crunch", "forearm_plank"],
    },
    "body_comp": {"max_points": 20, "has_minimum": False, "events": ["whtr"]},
}


@dataclass(frozen=True)
class EventPage:
    event: str
    unit: str
    higher_is_better: bool
    # Text that must appear in the page title. Guards against the pages being reordered.
    title: str


# One entry per PDF page, in page order.
PAGES: tuple[EventPage, ...] = (
    EventPage("whtr", "hundredths", False, "WAIST TO HEIGHT RATIO"),
    EventPage("push_up", "reps", True, "PUSH-UP SCORING"),
    EventPage("hand_release_push_up", "reps", True, "HAND RELEASE PUSH-UP"),
    EventPage("sit_up", "reps", True, "SIT-UP SCORING"),
    EventPage("cross_leg_reverse_crunch", "reps", True, "CROSS-LEG REVERSE CRUNCH"),
    EventPage("forearm_plank", "seconds", True, "FOREARM PLANK"),
    EventPage("run_2mile", "seconds", False, "2 MILE RUN"),
    EventPage("hamr_20m", "shuttles", True, "20-METER HAMR"),
)

# The printed chart has one tie: push-up, male, 30-34 prints 26 for both 3.0 and 2.5 points. The
# schema forbids ties, and we must not guess the intended number. Decision: keep the 3.0 row, drop
# the unreachable 2.5 row, and keep the minimum at 26 as printed. Confirm the true value with the
# source. The extractor fails if the PDF stops showing this tie, so the override cannot go stale.
KNOWN_TIES: frozenset[tuple[str, str, int]] = frozenset({("push_up", "M", 30)})

# Table layout: rows 0-1 are titles, row 2 the age bands, row 3 the sexes, then the data rows.
AGE_ROW = 2
SEX_ROW = 3
FIRST_DATA_ROW = 4
EXPECTED_COLUMNS = 20  # left Points, 9 bands x 2 sexes, right Points


@dataclass(frozen=True)
class Cell:
    threshold: int
    is_minimum: bool
    # "≥" or "≤" if the cell prints one, else None. Only the top and bottom rows print it.
    comparator: str | None


def parse_time(text: str) -> int:
    """`3:40` -> 220, `:55` -> 55. The charts drop the leading zero minute."""
    match = re.fullmatch(r"(\d*):(\d{2})", text)
    if match is None:
        raise ValueError(f"not a mm:ss time: {text!r}")
    minutes = int(match.group(1) or 0)
    return minutes * 60 + int(match.group(2))


def parse_ratio(text: str) -> int:
    """`0.49` -> 49. WHtR is stored in hundredths. Only two decimals are allowed."""
    match = re.fullmatch(r"(\d)\.(\d{2})", text)
    if match is None:
        raise ValueError(f"not a two-decimal ratio: {text!r}")
    return int(match.group(1)) * 100 + int(match.group(2))


def parse_cell(raw: str | None, unit: str) -> Cell:
    """Read one chart cell such as `≥ 67`, `30*`, `19:45*`, `≤ 0.49`, or `3:35`."""
    if raw is None:
        raise ValueError("empty cell")
    text = raw.strip()
    comparator: str | None = None
    if text[:1] in ("≥", "≤"):
        comparator = text[0]
        text = text[1:].strip()
    is_minimum = text.endswith("*")
    text = text.removesuffix("*").strip()
    if unit == "seconds" or ":" in text:
        threshold = parse_time(text)
    elif unit == "hundredths":
        threshold = parse_ratio(text)
    elif re.fullmatch(r"\d+", text):
        threshold = int(text)
    else:
        raise ValueError(f"cannot read cell {raw!r} as unit {unit!r}")
    return Cell(threshold, is_minimum, comparator)


def parse_age_band(label: str) -> tuple[int, int | None]:
    """`Under 25` -> (0, 24), `25-29` -> (25, 29), `60 and Over` -> (60, None)."""
    text = " ".join(label.split())
    if match := re.fullmatch(r"Under (\d+)", text):
        return 0, int(match.group(1)) - 1
    if match := re.fullmatch(r"(\d+)-(\d+)", text):
        return int(match.group(1)), int(match.group(2))
    if match := re.fullmatch(r"(\d+) and Over", text):
        return int(match.group(1)), None
    raise ValueError(f"unknown age band label: {label!r}")


def _column_keys(
    rows: list[list[str | None]],
) -> dict[int, tuple[str, int, int | None]]:
    """Map each data column index to (sex, age_min, age_max)."""
    keys: dict[int, tuple[str, int, int | None]] = {}
    band: tuple[int, int | None] | None = None
    for col in range(1, EXPECTED_COLUMNS - 1):
        label = rows[AGE_ROW][col]
        if label:  # the band label sits over the first of its two columns (M)
            band = parse_age_band(label)
        sex = rows[SEX_ROW][col]
        if band is None or sex not in SEXES:
            raise ValueError(f"column {col}: bad header (band={band}, sex={sex!r})")
        keys[col] = (sex, band[0], band[1])
    return keys


def _points(text: str | None) -> float:
    if text is None or not re.fullmatch(r"\d+(\.\d)?", text.strip()):
        raise ValueError(f"bad points label: {text!r}")
    return float(text)


def _drop_tied_minimum_row(
    event: str, brackets: list[dict[str, Any]], minimum: int | None
) -> list[dict[str, Any]]:
    """Apply the `KNOWN_TIES` decision. Raises if the table does not have the expected tie."""
    *rest, last = brackets
    if not rest or rest[-1]["threshold"] != last["threshold"] or last["threshold"] != minimum:
        raise ValueError(f"{event}: listed in KNOWN_TIES but the last row is not a tied minimum")
    return rest


def extract_event_tables(rows: list[list[str | None]], spec: EventPage) -> list[dict[str, Any]]:
    """Turn one page's raw table into a list of `EventTable` dicts (18 per event)."""
    if any(len(r) != EXPECTED_COLUMNS for r in rows):
        raise ValueError(f"{spec.event}: expected {EXPECTED_COLUMNS} columns in every row")
    keys = _column_keys(rows)
    data_rows = [r for r in rows[FIRST_DATA_ROW:] if r[0]]
    if not data_rows:
        raise ValueError(f"{spec.event}: no data rows")

    # The first row prints the best-result comparator. It must agree with the direction we
    # recorded for the event, or the page is not what we think it is.
    best_symbol = "≥" if spec.higher_is_better else "≤"

    out: list[dict[str, Any]] = []
    for col, (sex, age_min, age_max) in keys.items():
        brackets: list[dict[str, Any]] = []
        minimum: int | None = None
        for row in data_rows:
            points = _points(row[0])
            if _points(row[-1]) != points:
                raise ValueError(f"{spec.event}: left and right points differ in row {row}")
            cell = parse_cell(row[col], spec.unit)
            if row is data_rows[0] and cell.comparator != best_symbol:
                raise ValueError(f"{spec.event} col {col}: top row comparator {cell.comparator!r}")
            if cell.is_minimum:
                if minimum is not None:
                    raise ValueError(f"{spec.event} col {col}: more than one * row")
                minimum = cell.threshold
            brackets.append({"threshold": cell.threshold, "points": points})
        if (spec.event, sex, age_min) in KNOWN_TIES:
            brackets = _drop_tied_minimum_row(spec.event, brackets, minimum)
        out.append(
            {
                "sex": sex,
                "age_min": age_min,
                "age_max": age_max,
                "event": spec.event,
                "unit": spec.unit,
                "higher_is_better": spec.higher_is_better,
                "component_minimum": minimum,
                "brackets": brackets,
            }
        )
    return out


def extract_standards(pdf_path: Path) -> StandardsFile:
    tables: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page, spec in zip(pdf.pages, PAGES, strict=False):
            text = page.extract_text() or ""
            if spec.title not in text:
                raise ValueError(f"page for {spec.event} does not contain {spec.title!r}")
            found = page.extract_tables()
            if len(found) != 1:
                raise ValueError(f"{spec.event}: expected 1 table, found {len(found)}")
            tables.extend(extract_event_tables(found[0], spec))
    # Building the model runs every structural check from the schema.
    return StandardsFile.model_validate(
        {
            "version": VERSION,
            "effective_date": EFFECTIVE_DATE,
            "source": SOURCE,
            "passing_total": PASSING_TOTAL,
            "components": COMPONENTS,
            "tables": tables,
        }
    )


def render_json(standards: StandardsFile) -> str:
    """Pretty JSON with one bracket per line, so a person can compare it to the PDF."""
    text = json.dumps(standards.model_dump(mode="json"), indent=2, ensure_ascii=False)
    # Collapse each bracket object onto one line. Otherwise the file has about 17,000 lines.
    text = re.sub(
        r'\{\s+"threshold": (\d+),\s+"points": ([\d.]+)\s+\}',
        r'{"threshold": \1, "points": \2}',
        text,
    )
    return text + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    standards = extract_standards(args.pdf)
    text = render_json(standards)
    # Round trip through the same parser the app uses, so the file on disk is known to load.
    parse_standards(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(standards.tables)} tables)")


if __name__ == "__main__":
    main()
