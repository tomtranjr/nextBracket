"""FastAPI dependencies. This is the only place the API reads files or the clock.

Tests replace these with `app.dependency_overrides`, so core and routes stay pure.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.core.standards import parse_standards
from app.models import StandardsFile


def load_standards_dir(path: Path) -> list[StandardsFile]:
    """Parse every `*.json` file in `path`. Raises `ValueError` if none or two share a version."""
    files = [parse_standards(p.read_bytes()) for p in sorted(path.glob("*.json"))]
    if not files:
        raise ValueError(f"no standards files in {path}")
    versions = [f.version for f in files]
    if len(set(versions)) != len(versions):
        raise ValueError(f"duplicate standards versions in {path}: {versions}")
    return files


@lru_cache
def get_standards_files() -> list[StandardsFile]:
    # Cached: the files are read-only reference data, so one parse per process is enough.
    return load_standards_dir(get_settings().standards_dir)


def get_today() -> date:
    return date.today()
