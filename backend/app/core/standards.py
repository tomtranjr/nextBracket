"""Parse and validate a standards file. Pure: callers read the file and pass the text in."""

from app.models import StandardsFile


def parse_standards(raw: str | bytes) -> StandardsFile:
    """Turn standards JSON into a validated `StandardsFile`.

    Raises `pydantic.ValidationError` if the JSON is malformed or any structural check fails.
    JSON mode (not a dict) is used so strict typing still accepts ISO date strings.
    """
    return StandardsFile.model_validate_json(raw)
