import pytest

from app.core.timeparse import format_time, parse_time


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("15:40", 940), ("0:00", 0), ("0:59", 59), ("1:00", 60), ("9:05", 545), (" 15:40 ", 940)],
)
def test_parse_time(text: str, seconds: int) -> None:
    assert parse_time(text) == seconds


@pytest.mark.parametrize("text", ["", "15", "15:5", "15:60", "-1:30", "1:2:3", "15:40.5", "ab:cd"])
def test_parse_time_rejects_bad_text(text: str) -> None:
    with pytest.raises(ValueError, match="m:ss"):
        parse_time(text)


@pytest.mark.parametrize(("seconds", "text"), [(940, "15:40"), (0, "0:00"), (545, "9:05")])
def test_format_time(seconds: int, text: str) -> None:
    assert format_time(seconds) == text


def test_format_time_rejects_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        format_time(-1)


def test_round_trip() -> None:
    assert all(parse_time(format_time(s)) == s for s in range(0, 3600))
