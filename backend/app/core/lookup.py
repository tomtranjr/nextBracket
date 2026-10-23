"""Look up the charts that apply to a member. Pure: no I/O, no LLM."""

from app.core.standards import find_table, find_walk_standard
from app.models import WALK_EVENT, ComponentStandards, Profile, StandardsFile, StandardsTable


def get_standards(
    standards: StandardsFile, profile: Profile, event: str | None = None
) -> StandardsTable:
    """Return the tables for `profile`, one list per component.

    Alternative events (run or shuttle) sit together in their component, so the caller can
    compare them. With `event`, the result holds only that event, inside its component.
    The tables are the file's own, so the band and AFSPECWAR/EOD rules match `calculate_score`.
    The 2 km walk row comes with the full set, or alone when `event` is `walk_2km`.
    Raises `ValueError` for an unknown event.
    """
    known = {e for comp in standards.components.values() for e in comp.events}
    if event is not None and event not in known and event != WALK_EVENT:
        raise ValueError(f"unknown event: {event!r}")
    walk = None
    if event is None or event == WALK_EVENT:
        walk = find_walk_standard(standards, profile.sex, profile.age)

    components: list[ComponentStandards] = []
    for name, comp in standards.components.items():
        events = [e for e in comp.events if event is None or e == event]
        if not events:
            continue
        components.append(
            ComponentStandards(
                component=name,
                max_points=comp.max_points,
                has_minimum=comp.has_minimum,
                tables=[
                    find_table(
                        standards,
                        e,
                        profile.sex,
                        profile.age,
                        is_afspecwar_eod=profile.is_afspecwar_eod,
                    )
                    for e in events
                ],
            )
        )
    return StandardsTable(
        version=standards.version,
        effective_date=standards.effective_date,
        passing_total=standards.passing_total,
        components=components,
        walk=walk,
    )
