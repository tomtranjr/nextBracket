"""Parse and look up standards. Pure: callers read the file and pass the text in."""

from app.models import EventTable, Sex, StandardsFile


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
