"""PitContext invariants: docs/contracts/time-and-cohort.md §4, §5, §12 (1–4)."""

from dataclasses import fields
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, cast

import pytest

from stock_model_selection.domain.errors import (
    AuditContextError,
    CutoffOrderError,
    InvalidCutoffError,
    MissingPitContextError,
)
from stock_model_selection.domain.pit import PitContext, PitMode, require_market_pit
from stock_model_selection.domain.time import TAIPEI

T_C = datetime(2024, 7, 11, 4, 0, tzinfo=TAIPEI)
LATER = datetime(2026, 9, 26, 12, 0, tzinfo=TAIPEI)


def as_any(value: object) -> Any:
    return cast(Any, value)


# §12.1: a plain date, or the entry date, never becomes a cutoff


@pytest.mark.parametrize(
    "build",
    [
        lambda d: PitContext.production(information_as_of=d, knowledge_as_of=LATER),
        lambda d: PitContext.production(information_as_of=T_C, knowledge_as_of=d),
        lambda d: PitContext.reconstruction(information_as_of=d, knowledge_as_of=LATER),
        lambda d: PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=d),
        lambda d: PitContext.audit(system_as_of=d),
    ],
)
def test_plain_date_cutoff_is_rejected(build: Any) -> None:
    with pytest.raises(InvalidCutoffError):
        build(date(2024, 7, 11))


@pytest.mark.parametrize("value", ["2024-07-11T04:00:00+08:00", 1720641600, None])
def test_non_datetime_cutoff_is_rejected(value: object) -> None:
    with pytest.raises(InvalidCutoffError):
        PitContext.reconstruction(information_as_of=as_any(value), knowledge_as_of=LATER)


def test_pit_context_cannot_be_built_from_entry_date() -> None:
    with pytest.raises(TypeError):
        PitContext(**as_any({"mode": PitMode.RECONSTRUCTION, "entry_date": date(2024, 7, 11)}))
    with pytest.raises(TypeError):
        PitContext.reconstruction(**as_any({"entry_date": date(2024, 7, 11)}))


def test_pit_context_has_no_entry_date_field_or_constructor() -> None:
    names = {f.name for f in fields(PitContext)} | set(dir(PitContext))
    assert not [name for name in names if "entry" in name or "trade_date" in name]


# §12.2: cutoffs carry a UTC offset


@pytest.mark.parametrize(
    "build",
    [
        lambda t: PitContext.production(information_as_of=t, knowledge_as_of=LATER),
        lambda t: PitContext.production(information_as_of=T_C, knowledge_as_of=t),
        lambda t: PitContext.reconstruction(information_as_of=t, knowledge_as_of=LATER),
        lambda t: PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=t),
        lambda t: PitContext.audit(system_as_of=t),
    ],
)
def test_naive_cutoff_is_rejected(build: Any) -> None:
    with pytest.raises(InvalidCutoffError):
        build(datetime(2024, 7, 11, 4, 0))


def test_cutoffs_compare_as_absolute_times() -> None:
    utc = datetime(2024, 7, 10, 20, 0, tzinfo=UTC)
    plus_nine = datetime(2024, 7, 11, 5, 0, tzinfo=timezone(timedelta(hours=9)))
    ctx = PitContext.production(information_as_of=utc, knowledge_as_of=plus_nine)
    assert ctx.information_as_of == T_C
    assert ctx.knowledge_as_of == T_C


def test_cutoffs_are_normalised_to_taipei() -> None:
    ctx = PitContext.reconstruction(
        information_as_of=datetime(2024, 7, 10, 20, 0, tzinfo=UTC), knowledge_as_of=LATER
    )
    assert ctx.information_as_of is not None
    assert ctx.information_as_of.isoformat() == "2024-07-11T04:00:00+08:00"


# §12.3: the system cutoff is for audit only, never mixed with market cutoffs


def test_audit_context_cannot_carry_market_cutoffs() -> None:
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=PitMode.AUDIT, system_as_of=LATER, information_as_of=T_C)
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=PitMode.AUDIT, system_as_of=LATER, knowledge_as_of=LATER)
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=PitMode.AUDIT)


@pytest.mark.parametrize("mode", [PitMode.PRODUCTION, PitMode.RECONSTRUCTION])
def test_market_context_cannot_carry_system_cutoff(mode: PitMode) -> None:
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=mode, information_as_of=T_C, knowledge_as_of=LATER, system_as_of=LATER)


@pytest.mark.parametrize("mode", [PitMode.PRODUCTION, PitMode.RECONSTRUCTION])
def test_market_context_needs_both_market_cutoffs(mode: PitMode) -> None:
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=mode, information_as_of=T_C)
    with pytest.raises(InvalidCutoffError):
        PitContext(mode=mode, knowledge_as_of=LATER)


def test_audit_context_is_refused_for_features_and_labels() -> None:
    audit = PitContext.audit(system_as_of=LATER)
    with pytest.raises(AuditContextError):
        require_market_pit(audit)


# the feature/label entry guard: only a PitContext is accepted


def test_missing_pit_context_is_refused() -> None:
    with pytest.raises(MissingPitContextError):
        require_market_pit(None)


@pytest.mark.parametrize(
    "value", [date(2024, 7, 11), T_C, "2024-07-11T04:00:00+08:00", {"information_as_of": T_C}]
)
def test_dates_and_timestamps_are_refused_in_place_of_pit_context(value: object) -> None:
    with pytest.raises(InvalidCutoffError):
        require_market_pit(value)


@pytest.mark.parametrize(
    "ctx",
    [
        PitContext.production(information_as_of=T_C, knowledge_as_of=T_C),
        PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER),
    ],
)
def test_market_contexts_pass_the_guard(ctx: PitContext) -> None:
    assert require_market_pit(ctx) is ctx


# §12.4: production knows nothing before it is public


def test_production_knowledge_before_information_is_rejected() -> None:
    with pytest.raises(CutoffOrderError):
        PitContext.production(information_as_of=T_C, knowledge_as_of=T_C - timedelta(seconds=1))


def test_production_knowledge_equal_to_information_is_allowed() -> None:
    ctx = PitContext.production(information_as_of=T_C, knowledge_as_of=T_C)
    assert ctx.mode is PitMode.PRODUCTION


def test_pit_context_is_immutable() -> None:
    ctx = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(AttributeError):
        as_any(ctx).information_as_of = LATER
