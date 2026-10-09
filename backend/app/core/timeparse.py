"""Convert between `m:ss` text and whole seconds. Timed events are stored as integer seconds."""

import re

# Seconds need two digits ("15:05"), so "15:5" cannot be read as 15:50 or 15:05 by mistake.
_TIME = re.compile(r"(\d{1,3}):([0-5]\d)")


def parse_time(text: str) -> int:
    """Return whole seconds for `m:ss` text, for example `"15:40"` gives `940`.

    Raises `ValueError` for any other shape.
    """
    match = _TIME.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"time must look like m:ss, for example 15:40: {text!r}")
    minutes, seconds = match.groups()
    return int(minutes) * 60 + int(seconds)


def format_time(seconds: int) -> str:
    """Return `m:ss` text for whole seconds, for example `940` gives `"15:40"`."""
    if seconds < 0:
        raise ValueError(f"seconds must not be negative: {seconds}")
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}:{rest:02d}"
