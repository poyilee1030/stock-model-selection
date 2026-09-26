"""Trading calendar built from /v1/trading-days (decisions D3).

Coverage runs from the first to the last trading day given. Inside it, a missing
day is a non-trading day; outside it, nothing is known, so every question that
would need a day outside coverage raises CalendarCoverageError.
"""

from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from stock_model_selection.domain.errors import CalendarCoverageError


class TradingCalendar:
    def __init__(self, days: Iterable[date]) -> None:
        unique = set(days)
        for day in unique:
            if isinstance(day, datetime) or not isinstance(day, date):
                raise TypeError(f"trading days must be dates, got {day!r}")
        if not unique:
            raise ValueError("a trading calendar needs at least one trading day")
        self._days = tuple(sorted(unique))

    @property
    def first(self) -> date:
        return self._days[0]

    @property
    def last(self) -> date:
        return self._days[-1]

    def _check_covered(self, day: date) -> None:
        if not self.first <= day <= self.last:
            raise CalendarCoverageError(
                f"{day} is outside the trading calendar ({self.first} to {self.last})"
            )

    def is_trading_day(self, day: date) -> bool:
        self._check_covered(day)
        i = bisect_left(self._days, day)
        return self._days[i] == day

    def next_on_or_after(self, day: date) -> date:
        self._check_covered(day)
        return self._days[bisect_left(self._days, day)]

    def next_after(self, day: date) -> date:
        self._check_covered(day)
        i = bisect_right(self._days, day)
        if i == len(self._days):
            raise CalendarCoverageError(f"the trading calendar ends on {self.last}")
        return self._days[i]

    def previous_before(self, day: date) -> date:
        if day - timedelta(days=1) > self.last:
            # the days in (last, day) are unknown
            raise CalendarCoverageError(f"the trading calendar ends on {self.last}")
        i = bisect_left(self._days, day)
        if i == 0:
            raise CalendarCoverageError(f"the trading calendar starts on {self.first}")
        return self._days[i - 1]

    def trading_days_between(self, start: date, end: date) -> tuple[date, ...]:
        """Trading days in [start, end]."""
        self._check_covered(start)
        self._check_covered(end)
        return self._days[bisect_left(self._days, start) : bisect_right(self._days, end)]
