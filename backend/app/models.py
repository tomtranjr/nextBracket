"""Pydantic schemas shared by the scoring core, API, and agent tools.

The standards file schema lives here. A file that parses into `StandardsFile` has already
passed every structural check, so code that uses it can trust its shape ("parse, don't validate").
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sex = Literal["M", "F"]
SEXES: tuple[Sex, ...] = ("M", "F")


class _Strict(BaseModel):
    # strict: "63" is not an int. extra=forbid: a typo in a key fails loudly.
    # frozen: standards are reference data and must not change after loading.
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Bracket(_Strict):
    """One row of a chart. Meeting `threshold` earns `points`."""

    threshold: int = Field(ge=0)
    points: float = Field(ge=0)


class Component(_Strict):
    max_points: int = Field(gt=0)
    # True when the regulation sets a minimum per event (cardio, strength, core).
    has_minimum: bool
    events: list[str] = Field(min_length=1)


class EventTable(_Strict):
    """Scoring bracket list for one event, one sex, one age band."""

    sex: Sex
    # Bands are inclusive. The first band starts at 0 so "under 25" has no lower edge to invent.
    # `age_max=None` means open-ended (60 and over).
    age_min: int = Field(ge=0)
    age_max: int | None = Field(ge=0)
    event: str
    unit: str
    higher_is_better: bool
    # The `*` row from the chart. Required exactly when the component has a minimum.
    component_minimum: int | None = None
    # Listed best result first, as printed in the charts.
    brackets: list[Bracket] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_table(self) -> Self:
        if self.age_max is not None and self.age_max < self.age_min:
            raise ValueError(
                f"{self.event}: age_max {self.age_max} is below age_min {self.age_min}"
            )

        for better, worse in zip(self.brackets, self.brackets[1:], strict=False):
            # Thresholds must move strictly toward "worse", and so must points, or the
            # step function has ties or reversals.
            if self.higher_is_better:
                ordered = better.threshold > worse.threshold
            else:
                ordered = better.threshold < worse.threshold
            if not ordered or better.points <= worse.points:
                raise ValueError(
                    f"{self.event} {self.sex} {self.age_min}-{self.age_max}: brackets are not "
                    f"strictly ordered at thresholds {better.threshold} and {worse.threshold}"
                )

        if self.component_minimum is not None and self.component_minimum not in {
            b.threshold for b in self.brackets
        }:
            # The `*` sits on a chart row, so it must match one of the thresholds.
            raise ValueError(
                f"{self.event} {self.sex} {self.age_min}-{self.age_max}: component_minimum "
                f"{self.component_minimum} is not a bracket threshold"
            )
        return self


class AfspecwarEod(_Strict):
    """Members in AFSPECWAR/EOD use this sex and age band's tables for the listed events.

    The charts print one AFSPECWAR/EOD column per event, with no sex or age. Those columns equal
    the male under-25 tables, so the file points at that band instead of copying 7 more tables.
    """

    sex: Sex
    age_min: int = Field(ge=0)
    events: list[str] = Field(min_length=1)


class StandardsFile(_Strict):
    """One versioned set of scoring charts, e.g. `data/standards/2026-03-01.json`."""

    version: str = Field(min_length=1)
    effective_date: date
    source: str = Field(min_length=1)
    passing_total: int = Field(gt=0)
    components: dict[str, Component] = Field(min_length=1)
    afspecwar_eod: AfspecwarEod
    tables: list[EventTable] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_coverage(self) -> Self:
        event_to_component = self._map_events_to_components()
        self._check_tables_match_components(event_to_component)
        self._check_age_bands(event_to_component)
        self._check_afspecwar_eod(event_to_component)
        return self

    def _map_events_to_components(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for name, component in self.components.items():
            for event in component.events:
                if event in mapping:
                    raise ValueError(f"event {event!r} is in both {mapping[event]!r} and {name!r}")
                mapping[event] = name
        return mapping

    def _check_tables_match_components(self, event_to_component: dict[str, str]) -> None:
        for table in self.tables:
            component_name = event_to_component.get(table.event)
            if component_name is None:
                raise ValueError(f"table for unknown event {table.event!r}")
            component = self.components[component_name]
            where = f"{table.event} {table.sex} {table.age_min}-{table.age_max}"
            if component.has_minimum and table.component_minimum is None:
                raise ValueError(f"{where}: component has a minimum but the table has none")
            if not component.has_minimum and table.component_minimum is not None:
                raise ValueError(f"{where}: component has no minimum but the table sets one")
            if table.brackets[0].points > component.max_points:
                raise ValueError(
                    f"{where}: top bracket worth {table.brackets[0].points} points, "
                    f"above component max {component.max_points}"
                )

    def _check_age_bands(self, event_to_component: dict[str, str]) -> None:
        """Every event x sex must tile all ages with no gaps or overlaps, using the same bands."""
        reference: list[tuple[int, int | None]] | None = None
        for event in event_to_component:
            for sex in SEXES:
                bands = sorted(
                    (t.age_min, t.age_max) for t in self.tables if t.event == event and t.sex == sex
                )
                if not bands:
                    raise ValueError(f"missing table: event {event!r}, sex {sex!r}")
                self._check_contiguous(event, sex, bands)
                if reference is None:
                    reference = bands
                elif bands != reference:
                    raise ValueError(f"{event} {sex}: age bands {bands} differ from {reference}")

    def _check_afspecwar_eod(self, event_to_component: dict[str, str]) -> None:
        mapping = self.afspecwar_eod
        for event in mapping.events:
            if event not in event_to_component:
                raise ValueError(f"afspecwar_eod lists unknown event {event!r}")
            if not any(
                t.event == event
                and t.sex == mapping.sex
                and t.age_min <= mapping.age_min
                and (t.age_max is None or mapping.age_min <= t.age_max)
                for t in self.tables
            ):
                raise ValueError(
                    f"afspecwar_eod: no table for {event} {mapping.sex} age {mapping.age_min}"
                )

    @staticmethod
    def _check_contiguous(event: str, sex: Sex, bands: list[tuple[int, int | None]]) -> None:
        if bands[0][0] != 0:
            raise ValueError(f"{event} {sex}: first age band starts at {bands[0][0]}, not 0")
        for (_, prev_max), (next_min, _) in zip(bands, bands[1:], strict=False):
            if prev_max is None:
                raise ValueError(f"{event} {sex}: an open-ended band is followed by another band")
            if next_min != prev_max + 1:
                raise ValueError(
                    f"{event} {sex}: gap or overlap between age {prev_max} and age {next_min}"
                )
        if bands[-1][1] is not None:
            raise ValueError(f"{event} {sex}: last age band must be open-ended")


class Profile(_Strict):
    age: int = Field(ge=17, le=70)
    sex: Sex
    # True: the 7 non-WHtR events use the male under-25 tables (see `AfspecwarEod`).
    is_afspecwar_eod: bool = False


class Results(_Strict):
    """Raw results by event: reps, shuttles, or seconds. WHtR is in hundredths (0.49 is 49)."""

    # A member takes one event per component, so most keys are absent.
    values: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_values(self) -> Self:
        for event, value in self.values.items():
            if value < 0:
                raise ValueError(f"{event}: result must not be negative: {value}")
        return self


Category = Literal["excellent", "satisfactory", "unsatisfactory"]


class ComponentScore(_Strict):
    component: str
    event: str
    result: int
    points: float
    max_points: int
    # None when the component has no minimum (body composition).
    minimum_met: bool | None


class ScoreReport(_Strict):
    version: str
    effective_date: date
    components: list[ComponentScore]
    # Components with no result. With any of these, there is no total and no category.
    not_scored: list[str]
    total: float | None
    category: Category | None
    # Events whose result is below the component minimum.
    missed_minimums: list[str]


class ComponentStandards(_Strict):
    """One component with the chart tables a member may choose from (run or shuttle)."""

    component: str
    max_points: int
    has_minimum: bool
    # One table per alternative event, in the order the standards file lists them.
    tables: list[EventTable]


class StandardsTable(_Strict):
    """The charts that apply to one profile. Returned by `get_standards`."""

    version: str
    effective_date: date
    passing_total: int
    components: list[ComponentStandards]


class EventChange(_Strict):
    """One event that must improve, with the exact distance to travel."""

    component: str
    event: str
    unit: str
    # None when the member gave no result for this component. The plan then starts from the
    # component minimum, so there is no real starting result to report.
    from_result: int | None
    to_result: int
    # `to_result - from_result`: negative when lower is better (seconds to cut from a run).
    delta: int | None
    from_points: float
    to_points: float


class PlanOption(_Strict):
    """One way to reach the target."""

    kind: Literal["single_event", "quick_wins", "balanced"]
    changes: list[EventChange]
    projected_total: float


# A reachable target always has an option: raising every event to its best bracket reaches the
# best total, so the quick-wins walk cannot get stuck.
PlanStatus = Literal["already_met", "options", "impossible"]


class PlanResult(_Strict):
    """The answer to "what do I need to reach this total?". An impossible target is a status."""

    version: str
    effective_date: date
    target: float
    status: PlanStatus
    # Total with the given results. Components without a result are assumed at their minimum.
    current_total: float
    # The best total possible with the events in play. Above this, the target is impossible.
    max_total: float
    # Components with no result, planned from their minimum (body composition counts as 0 points).
    assumed_components: list[str]
    options: list[PlanOption]
