"""Cohort calendar rules: docs/contracts/time-and-cohort.md §3, §5, §7, §12 (5, 6).

Expected dates come from the contract's worked tables, not from this implementation.
"""

from datetime import date, datetime, timedelta

import pytest

from stock_model_selection.domain.calendar import TradingCalendar
from stock_model_selection.domain.cohort import (
    Cohort,
    Month,
    build_cohort,
    build_label_horizon,
)
from stock_model_selection.domain.errors import (
    CalendarCoverageError,
    CutoffOrderError,
    InvalidCohortError,
)
from stock_model_selection.domain.pit import PitMode
from stock_model_selection.domain.time import TAIPEI


def taipei(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=TAIPEI)


# Month: the "YYYY-MM" cohort id


def test_month_parses_and_prints_yyyy_mm() -> None:
    assert str(Month.parse("2024-07")) == "2024-07"
    assert Month.parse("2024-07") == Month(2024, 7)


@pytest.mark.parametrize("text", ["2024-7", "2024-13", "2024-00", "202407", "2024-07-01", ""])
def test_malformed_cohort_id_is_rejected(text: str) -> None:
    with pytest.raises(InvalidCohortError):
        Month.parse(text)


def test_month_arithmetic_crosses_years() -> None:
    assert Month(2024, 12).next() == Month(2025, 1)
    assert Month(2025, 1).previous() == Month(2024, 12)
    assert Month(2024, 12) < Month(2025, 1)


# §12.5: revenue deadline D_M and playbook date P_M (§3 table)


@pytest.mark.parametrize(
    ("cohort_id", "deadline", "playbook"),
    [
        ("2024-06", date(2024, 6, 11), date(2024, 6, 12)),  # 10th is Dragon Boat Festival
        ("2024-07", date(2024, 7, 10), date(2024, 7, 11)),
        ("2024-08", date(2024, 8, 12), date(2024, 8, 13)),  # 10th is a Saturday
        ("2024-09", date(2024, 9, 10), date(2024, 9, 11)),
    ],
)
def test_revenue_deadline_and_playbook_date(
    calendar: TradingCalendar, cohort_id: str, deadline: date, playbook: date
) -> None:
    cohort = build_cohort(cohort_id, calendar)
    assert cohort.revenue_deadline == deadline
    assert cohort.playbook_date == playbook
    assert cohort.entry_date == playbook


@pytest.mark.parametrize(
    ("cohort_id", "playbook"),
    [
        ("2020-02", date(2020, 2, 11)),  # §8
        ("2021-01", date(2021, 1, 12)),  # decisions D14
        ("2022-02", date(2022, 2, 11)),  # §8
        ("2023-04", date(2023, 4, 11)),  # §8
        ("2026-06", date(2026, 6, 11)),  # §8
    ],
)
def test_playbook_dates_quoted_elsewhere_in_the_contract(
    calendar: TradingCalendar, cohort_id: str, playbook: date
) -> None:
    assert build_cohort(cohort_id, calendar).playbook_date == playbook


@pytest.mark.parametrize(
    ("cohort_id", "cutoff"),
    [
        ("2024-03", taipei(2024, 3, 12, 4)),  # §10 Q4 table
        ("2024-04", taipei(2024, 4, 11, 4)),
        ("2024-06", taipei(2024, 6, 12, 4)),  # §10 ex-dividend example
        ("2024-07", taipei(2024, 7, 11, 4)),  # §10 timeline
        ("2024-08", taipei(2024, 8, 13, 4)),
        ("2026-03", taipei(2026, 3, 11, 4)),
        ("2026-04", taipei(2026, 4, 13, 4)),
    ],
)
def test_information_cutoff_is_playbook_date_0400_taipei(
    calendar: TradingCalendar, cohort_id: str, cutoff: datetime
) -> None:
    info = build_cohort(cohort_id, calendar).information_cutoff
    assert info == cutoff
    assert info.isoformat() == cutoff.isoformat()


def test_decision_uses_previous_month_revenue(calendar: TradingCalendar) -> None:
    assert build_cohort("2024-07", calendar).revenue_month == Month(2024, 6)
    assert build_cohort("2025-01", calendar).revenue_month == Month(2024, 12)


def test_information_cutoff_precedes_entry_trade(calendar: TradingCalendar) -> None:
    cohort = build_cohort("2024-07", calendar)
    market_open = taipei(2024, 7, 11, 9)
    assert cohort.information_cutoff < market_open
    assert cohort.information_cutoff.date() == cohort.entry_date


# §12.5: exit date X_C and label_available_at (§7, §10)


@pytest.mark.parametrize(
    ("cohort_id", "exit_date", "label_available_at"),
    [
        ("2024-06", date(2024, 7, 10), taipei(2024, 7, 11, 3)),  # §10: period 06-12..07-10
        ("2024-07", date(2024, 8, 12), taipei(2024, 8, 13, 3)),  # §7 and §10
        ("2024-08", date(2024, 9, 10), taipei(2024, 9, 11, 3)),  # P_2024-09 = 09-11 (§3)
        ("2024-12", date(2025, 1, 10), taipei(2025, 1, 11, 3)),  # Friday exit -> Saturday 03:00
    ],
)
def test_exit_date_and_label_available_at(
    calendar: TradingCalendar, cohort_id: str, exit_date: date, label_available_at: datetime
) -> None:
    horizon = build_label_horizon(build_cohort(cohort_id, calendar), calendar)
    assert horizon.exit_date == exit_date
    assert horizon.label_available_at == label_available_at


def test_label_period_length_counts_trading_days(calendar: TradingCalendar) -> None:
    # 2024-07-11 .. 2024-08-12 without the 07-24/25 typhoon closures
    horizon = build_label_horizon(build_cohort("2024-07", calendar), calendar)
    assert horizon.trading_days == 21


# §12.6 over every cohort the fixture calendar can answer


def all_cohort_ids(first: Month, last: Month) -> list[Month]:
    months = [first]
    while months[-1] < last:
        months.append(months[-1].next())
    return months


def test_label_period_lengths_stay_in_the_documented_range(calendar: TradingCalendar) -> None:
    lengths = {
        month: build_label_horizon(build_cohort(month, calendar), calendar).trading_days
        for month in all_cohort_ids(Month(2020, 1), Month(2026, 8))
    }
    # §7: 12–23 trading days; 70 of 80 cohorts fall in 19–23, Lunar New Year ones are shorter
    assert all(12 <= n <= 23 for n in lengths.values()), lengths
    assert sum(19 <= n <= 23 for n in lengths.values()) == 70
    assert lengths[Month(2026, 2)] == 12


def test_every_label_is_complete_before_the_next_cutoff(calendar: TradingCalendar) -> None:
    months = all_cohort_ids(Month(2020, 1), Month(2026, 8))
    assert len(months) == 80
    for month in months:
        cohort = build_cohort(month, calendar)
        horizon = build_label_horizon(cohort, calendar)
        following = build_cohort(month.next(), calendar)
        assert horizon.exit_date < following.playbook_date
        assert calendar.next_after(horizon.exit_date) == following.playbook_date
        assert horizon.label_available_at < following.information_cutoff, month
        assert cohort.playbook_date.month == month.month
        assert cohort.revenue_deadline < cohort.playbook_date


# calendar coverage: fail rather than guess


def test_cohort_needs_calendar_through_its_playbook_date(calendar: TradingCalendar) -> None:
    assert build_cohort("2026-09", calendar).playbook_date == date(2026, 9, 11)
    with pytest.raises(CalendarCoverageError):
        build_cohort("2026-10", calendar)
    with pytest.raises(CalendarCoverageError):
        build_cohort("2019-12", calendar)


def test_label_horizon_needs_next_months_playbook_date(calendar: TradingCalendar) -> None:
    cohort = build_cohort("2026-09", calendar)
    with pytest.raises(CalendarCoverageError):
        build_label_horizon(cohort, calendar)


def test_playbook_date_outside_its_month_is_rejected() -> None:
    sparse = TradingCalendar([date(2024, 7, 1), date(2024, 8, 1), date(2024, 8, 2)])
    with pytest.raises(InvalidCohortError):
        build_cohort("2024-07", sparse)


def test_hand_built_inconsistent_cohort_is_rejected(calendar: TradingCalendar) -> None:
    good = build_cohort("2024-07", calendar)
    with pytest.raises(InvalidCohortError):
        Cohort(
            cohort_id=good.cohort_id,
            revenue_deadline=good.revenue_deadline,
            playbook_date=good.playbook_date,
            information_cutoff=good.information_cutoff + timedelta(hours=4),
        )
    with pytest.raises(InvalidCohortError):
        Cohort(
            cohort_id=Month(2024, 8),
            revenue_deadline=good.revenue_deadline,
            playbook_date=good.playbook_date,
            information_cutoff=good.information_cutoff,
        )


# §5: PIT contexts for a cohort's features and for its label (decisions D12)


def test_reconstruction_context_uses_the_cohort_cutoff(calendar: TradingCalendar) -> None:
    cohort = build_cohort("2024-07", calendar)
    t_recon = taipei(2026, 9, 26, 12)
    ctx = cohort.reconstruction_context(t_recon)
    assert ctx.mode is PitMode.RECONSTRUCTION
    assert ctx.information_as_of == taipei(2024, 7, 11, 4)
    assert ctx.knowledge_as_of == t_recon


def test_production_run_must_fall_between_cutoff_and_entry_trade(
    calendar: TradingCalendar,
) -> None:
    cohort = build_cohort("2024-07", calendar)
    ok = cohort.production_context(taipei(2024, 7, 11, 8, 59, 59))
    assert ok.mode is PitMode.PRODUCTION
    assert ok.information_as_of == taipei(2024, 7, 11, 4)
    assert cohort.production_context(taipei(2024, 7, 11, 4)).knowledge_as_of == taipei(
        2024, 7, 11, 4
    )
    with pytest.raises(CutoffOrderError):
        cohort.production_context(taipei(2024, 7, 11, 3, 59, 59))
    with pytest.raises(CutoffOrderError):
        cohort.production_context(taipei(2024, 7, 11, 9))


def test_label_context_reads_at_label_available_at(calendar: TradingCalendar) -> None:
    horizon = build_label_horizon(build_cohort("2024-07", calendar), calendar)
    t_recon = taipei(2026, 9, 26, 12)
    ctx = horizon.reconstruction_context(t_recon)
    assert ctx.information_as_of == taipei(2024, 8, 13, 3)
    assert ctx.knowledge_as_of == t_recon
    assert horizon.production_context(taipei(2024, 8, 13, 3)).mode is PitMode.PRODUCTION
    with pytest.raises(CutoffOrderError):
        horizon.production_context(taipei(2024, 8, 13, 2, 59, 59))
