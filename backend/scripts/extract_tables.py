"""Turn `PFRA Scoring Charts.pdf` into a versioned standards JSON file.

Run from `backend/`:

    uv run python -m scripts.extract_tables

The output is NOT trusted until a person has checked it against the PDF. This script only
removes typing; it does not prove the numbers are right. It fails loudly on anything odd
(unknown cell, wrong table shape, broken ordering) instead of guessing.

Pages 1 to 8 hold the 8 events by age band and sex. Page 10 is the AFSPECWAR/EOD chart. It has one
column per event and no sex or age. It is not copied. It is checked against the male under-25
tables, and the JSON records that those tables apply (`afspecwar_eod`). Page 11 is the 2 km walk:
one maximum time per sex and age band, with its own bands (`walk`).
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
from app.models import SEXES, Sex, StandardsFile, WalkStandard

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

# AFSPECWAR/EOD chart (page 10). One column per event: (points column, value column, unit, text
# that must appear in the column header). Strength and core share points column 0, cardio uses 7.
AFSPECWAR_PAGE_INDEX = 9
AFSPECWAR_TITLE = "AFSPECWAR/EOD"
AFSPECWAR_FIRST_DATA_ROW = 3

WALK_PAGE_INDEX = 10
WALK_TITLE = "2.0 Kilometer Walk"
WALK_HEADER = "Age (yrs)"
WALK_BANDS = 5
AFSPECWAR_COLUMNS: dict[str, tuple[int, int, str, str]] = {
    "push_up": (0, 1, "reps", "Push-up"),
    "hand_release_push_up": (0, 2, "reps", "Hand Release"),
    "sit_up": (0, 4, "reps", "Sit-up"),
    "cross_leg_reverse_crunch": (0, 5, "reps", "Reverse Crunch"),
    "forearm_plank": (0, 6, "seconds", "Forearm Plank"),
    "run_2mile": (7, 8, "seconds", "2 Mile Run"),
    "hamr_20m": (7, 9, "shuttles", "HAMR"),
}

# AFSPECWAR/EOD members score on the male under-25 tables for every event on their chart page
# (all but WHtR). The mapping lives in the JSON so a future chart can change it with data only.
AFSPECWAR_EOD: dict[str, Any] = {
    "sex": "M",
    "age_min": 0,
    "events": list(AFSPECWAR_COLUMNS),
}

# The AFSPECWAR/EOD chart equals the male under-25 tables except for one cell: the 2 mile run at
# 39.0 points prints 17:16 (1036 s) there and 17:13 (1033 s) in the main table. 17:13 fits the
# 19 s step of its column. Decision: use the main table. Confirm the true value with the source.
# The check fails if the PDF stops showing this difference, so the entry cannot go stale.
# Key: (event, points). Value: (AFSPECWAR threshold, main table threshold).
KNOWN_AFSPECWAR_DIFFS: dict[tuple[str, float], tuple[int, int]] = {
    ("run_2mile", 39.0): (1036, 1033),
}

# The printed chart has one tie: push-up, male, 30-34 prints 26 for both 3.0 and 2.5 points. The
# schema forbids ties. Decision (follow the printed table): keep the 3.0 row, drop the 2.5 row, and
# keep the minimum at 26 as printed. The 2.5 row is unreachable, so scores are the same as with
# both rows. The extractor fails if the PDF stops showing this tie, so the override cannot go stale.
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


def parse_walk_age_band(label: str) -> tuple[int, int | None]:
    """`< 30` -> (0, 29), `30-39` -> (30, 39), `60+` -> (60, None). Walk page labels only."""
    text = "".join(label.split())
    if match := re.fullmatch(r"<(\d+)", text):
        return 0, int(match.group(1)) - 1
    if match := re.fullmatch(r"(\d+)-(\d+)", text):
        return int(match.group(1)), int(match.group(2))
    if match := re.fullmatch(r"(\d+)\+", text):
        return int(match.group(1)), None
    raise ValueError(f"unknown walk age band label: {label!r}")


def extract_walk(rows: list[list[str | None]]) -> list[WalkStandard]:
    """Read the walk table: male band and time in columns 0-1, female band and time in 2-3.

    Bands are whole years, like the scoring charts, so age 30 is in "30-39". DAFMAN 36-2905 has no
    boundary rule for the walk.
    """
    header = next((i for i, row in enumerate(rows) if row[:1] == [WALK_HEADER]), None)
    if header is None or rows[header][2] != WALK_HEADER:
        raise ValueError(f"walk: no {WALK_HEADER!r} header for both sexes")
    data = rows[header + 1 :]
    if len(data) != WALK_BANDS:
        raise ValueError(f"walk: expected {WALK_BANDS} age bands, found {len(data)}")
    walk: list[WalkStandard] = []
    columns: tuple[tuple[Sex, int], ...] = (("M", 0), ("F", 2))
    for sex, col in columns:
        for row in data:
            label, time = (row[col], row[col + 1]) if len(row) == 4 else (None, None)
            if label is None or time is None:
                raise ValueError(f"walk: bad row {row!r}")
            age_min, age_max = parse_walk_age_band(label)
            max_time = parse_time(time.strip())
            walk.append(WalkStandard(sex=sex, age_min=age_min, age_max=age_max, max_time=max_time))
    return walk


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


@dataclass(frozen=True)
class AfspecwarColumn:
    brackets: list[tuple[int, float]]
    minimum: int | None


def extract_afspecwar_columns(rows: list[list[str | None]]) -> dict[str, AfspecwarColumn]:
    """Read the AFSPECWAR/EOD page table into one column of brackets per event."""
    out: dict[str, AfspecwarColumn] = {}
    for event, (points_col, value_col, unit, header) in AFSPECWAR_COLUMNS.items():
        if header not in (rows[AGE_ROW][value_col] or ""):
            raise ValueError(f"{event}: column {value_col} header is not {header!r}")
        brackets: list[tuple[int, float]] = []
        minimum: int | None = None
        for row in rows[AFSPECWAR_FIRST_DATA_ROW:]:
            if not row[points_col] and not row[value_col]:
                continue  # the cardio columns are shorter than the strength and core columns
            cell = parse_cell(row[value_col], unit)
            if cell.is_minimum:
                if minimum is not None:
                    raise ValueError(f"{event}: more than one * row")
                minimum = cell.threshold
            brackets.append((cell.threshold, _points(row[points_col])))
        out[event] = AfspecwarColumn(brackets, minimum)
    return out


def check_afspecwar_matches(
    columns: dict[str, AfspecwarColumn], tables: list[dict[str, Any]]
) -> None:
    """Raise unless every AFSPECWAR/EOD column equals the table the mapping points to.

    The only difference allowed is the one in `KNOWN_AFSPECWAR_DIFFS`.
    """
    mapped = AFSPECWAR_EOD
    seen: set[tuple[str, float]] = set()
    for event, column in columns.items():
        (table,) = (
            t
            for t in tables
            if t["event"] == event
            and t["sex"] == mapped["sex"]
            and t["age_min"] == mapped["age_min"]
        )
        main = [(b["threshold"], b["points"]) for b in table["brackets"]]
        if len(main) != len(column.brackets):
            raise ValueError(
                f"{event}: AFSPECWAR/EOD has {len(column.brackets)} rows, not {len(main)}"
            )
        if column.minimum != table["component_minimum"]:
            raise ValueError(
                f"{event}: AFSPECWAR/EOD minimum {column.minimum} differs from "
                f"{table['component_minimum']}"
            )
        for (afs_threshold, afs_points), (threshold, points) in zip(
            column.brackets, main, strict=True
        ):
            if afs_points != points:
                raise ValueError(f"{event}: point rows differ ({afs_points} vs {points})")
            if afs_threshold == threshold:
                continue
            key = (event, points)
            if KNOWN_AFSPECWAR_DIFFS.get(key) != (afs_threshold, threshold):
                raise ValueError(
                    f"{event} at {points} points: AFSPECWAR/EOD has {afs_threshold}, "
                    f"main table has {threshold}"
                )
            seen.add(key)
    stale = set(KNOWN_AFSPECWAR_DIFFS) - seen
    if stale:
        raise ValueError(f"KNOWN_AFSPECWAR_DIFFS no longer match the PDF: {sorted(stale)}")


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
        afspecwar_page = pdf.pages[AFSPECWAR_PAGE_INDEX]
        if AFSPECWAR_TITLE not in (afspecwar_page.extract_text() or ""):
            raise ValueError(f"page {AFSPECWAR_PAGE_INDEX + 1} is not the AFSPECWAR/EOD chart")
        found = afspecwar_page.extract_tables()
        if len(found) != 1:
            raise ValueError(f"AFSPECWAR/EOD: expected 1 table, found {len(found)}")
        check_afspecwar_matches(extract_afspecwar_columns(found[0]), tables)
        walk_page = pdf.pages[WALK_PAGE_INDEX]
        if WALK_TITLE not in (walk_page.extract_text() or ""):
            raise ValueError(f"page {WALK_PAGE_INDEX + 1} is not the 2 km walk chart")
        found = walk_page.extract_tables()
        if len(found) != 1:
            raise ValueError(f"walk: expected 1 table, found {len(found)}")
        walk = extract_walk(found[0])
    # Building the model runs every structural check from the schema.
    return StandardsFile.model_validate(
        {
            "version": VERSION,
            "effective_date": EFFECTIVE_DATE,
            "source": SOURCE,
            "passing_total": PASSING_TOTAL,
            "components": COMPONENTS,
            "afspecwar_eod": AFSPECWAR_EOD,
            "tables": tables,
            "walk": walk,
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
    text = re.sub(
        r'\{\s+"sex": "(\w)",\s+"age_min": (\d+),\s+'
        r'"age_max": (\d+|null),\s+"max_time": (\d+)\s+\}',
        r'{"sex": "\1", "age_min": \2, "age_max": \3, "max_time": \4}',
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
