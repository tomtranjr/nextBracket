"""Parse and look up standards. Pure: callers read the file and pass the text in."""

from collections.abc import Sequence
from datetime import date

from app.models import EventTable, Sex, StandardsFile


def pick_standards(
    files: Sequence[StandardsFile], today: date, version: str | None = None
) -> StandardsFile:
    """Choose one standards file. The API layer loads the files and passes them in.

    With `version`, return that exact file. Without it, return the file with the newest
    `effective_date` on or before `today`, so a chart that is not yet in force is never used.
    Raises `ValueError` for an unknown version, or when no file is in force yet.
    """
    if version is not None:
        for standards in files:
            if standards.version == version:
                return standards
        raise ValueError(f"unknown standards version: {version!r}")
    in_force = [s for s in files if s.effective_date <= today]
    if not in_force:
        raise ValueError(f"no standards in force on {today}")
    return max(in_force, key=lambda s: s.effective_date)


def parse_standards(raw: str | bytes) -> StandardsFile:
    """Turn standards JSON into a validated `StandardsFile`.

    Raises `pydantic.ValidationError` if the JSON is malformed or any structural check fails.
    JSON mode (not a dict) is used so strict typing still accepts ISO date strings.
    """
    return StandardsFile.model_validate_json(raw)


def find_table(
    standards: StandardsFile,
    event: str,
    sex: Sex,
    age: int,
    *,
    is_afspecwar_eod: bool = False,
) -> EventTable:
    """Return the scoring table for one event, sex, and age.

    AFSPECWAR/EOD members use the band named in `standards.afspecwar_eod` for the events it
    lists, whatever their own sex and age. Other events (WHtR) still use their own.
    Raises `ValueError` for an unknown event or a negative age.
    """
    if age < 0:
        raise ValueError(f"age must not be negative: {age}")
    mapping = standards.afspecwar_eod
    if is_afspecwar_eod and event in mapping.events:
        sex, age = mapping.sex, mapping.age_min
    for table in standards.tables:
        if (
            table.event == event
            and table.sex == sex
            and table.age_min <= age
            and (table.age_max is None or age <= table.age_max)
        ):
            return table
    # The schema guarantees full coverage of ages, so only an unknown event reaches here.
    raise ValueError(f"unknown event: {event!r}")
