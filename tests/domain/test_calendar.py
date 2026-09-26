"""TradingCalendar: /v1/trading-days is the only source of trading days (contract §2)."""

from datetime import date, datetime
from typing import Any, cast

import pytest

from stock_model_selection.domain.calendar import TradingCalendar
from stock_model_selection.domain.errors import CalendarCoverageError


def test_fixture_calendar_matches_known_holidays(calendar: TradingCalendar) -> None:
    assert calendar.first == date(2020, 1, 2)
    assert calendar.last == date(2026, 9, 15)
    assert not calendar.is_trading_day(date(2024, 6, 10))  # Dragon Boat Festival
    assert not calendar.is_trading_day(date(2024, 7, 24))  # typhoon
    assert not calendar.is_trading_day(date(2024, 7, 25))  # typhoon
    assert calendar.is_trading_day(date(2024, 7, 26))


def test_navigation(calendar: TradingCalendar) -> None:
    assert calendar.next_on_or_after(date(2024, 6, 10)) == date(2024, 6, 11)
    assert calendar.next_on_or_after(date(2024, 6, 11)) == date(2024, 6, 11)
    assert calendar.next_after(date(2024, 6, 11)) == date(2024, 6, 12)
    assert calendar.next_after(date(2024, 7, 23)) == date(2024, 7, 26)
    assert calendar.previous_before(date(2024, 7, 26)) == date(2024, 7, 23)
    assert calendar.previous_before(date(2024, 8, 13)) == date(2024, 8, 12)


def test_trading_days_between_is_inclusive(calendar: TradingCalendar) -> None:
    days = calendar.trading_days_between(date(2024, 7, 22), date(2024, 7, 29))
    assert days == (date(2024, 7, 22), date(2024, 7, 23), date(2024, 7, 26), date(2024, 7, 29))


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.is_trading_day(date(2019, 12, 31)),
        lambda c: c.is_trading_day(date(2026, 9, 16)),
        lambda c: c.next_on_or_after(date(2026, 9, 16)),
        lambda c: c.next_on_or_after(date(2019, 12, 31)),
        lambda c: c.next_after(date(2026, 9, 15)),
        lambda c: c.next_after(date(2019, 12, 31)),
        lambda c: c.previous_before(date(2020, 1, 2)),
        lambda c: c.previous_before(date(2026, 9, 17)),
        lambda c: c.trading_days_between(date(2026, 9, 1), date(2026, 9, 30)),
        lambda c: c.trading_days_between(date(2019, 12, 1), date(2020, 1, 31)),
    ],
)
def test_questions_outside_coverage_fail_instead_of_guessing(
    calendar: TradingCalendar, call: Any
) -> None:
    with pytest.raises(CalendarCoverageError):
        call(calendar)


def test_last_covered_day_can_be_asked_about(calendar: TradingCalendar) -> None:
    assert calendar.next_on_or_after(date(2026, 9, 15)) == date(2026, 9, 15)
    assert calendar.previous_before(date(2026, 9, 16)) == date(2026, 9, 15)


def test_empty_calendar_is_rejected() -> None:
    with pytest.raises(ValueError):
        TradingCalendar([])


def test_timestamps_are_not_trading_days() -> None:
    with pytest.raises(TypeError):
        TradingCalendar(cast(Any, [datetime(2024, 7, 11, 0, 0)]))
