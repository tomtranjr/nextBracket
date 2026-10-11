from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_standards_files, get_today
from app.core.scoring import calculate_score
from app.core.standards import pick_standards
from app.models import ScoreReport, ScoreRequest, StandardsFile, VersionInfo, VersionsResponse

router = APIRouter()

StandardsFiles = Annotated[list[StandardsFile], Depends(get_standards_files)]
Today = Annotated[date, Depends(get_today)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/versions")
def versions(files: StandardsFiles, today: Today) -> VersionsResponse:
    try:
        default = pick_standards(files, today).version
    except ValueError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    return VersionsResponse(
        default=default,
        versions=[
            VersionInfo(version=f.version, effective_date=f.effective_date, source=f.source)
            for f in sorted(files, key=lambda f: f.effective_date)
        ],
    )


@router.post("/score")
def score(request: ScoreRequest, files: StandardsFiles, today: Today) -> ScoreReport:
    # Core raises ValueError for bad input (unknown version or event, two events in one
    # component). The client can fix all of these, so they are 422, like a bad field.
    try:
        standards = pick_standards(files, today, request.version)
        return calculate_score(standards, request.profile, request.results)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
