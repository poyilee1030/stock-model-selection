"""Monthly cohorts and their label horizons (docs/contracts/time-and-cohort.md §3, §5, §7).

A Cohort holds what is fixed at decision time and needs the trading calendar only
through its playbook date. A LabelHorizon adds the exit date and needs the calendar
through the next cohort's playbook date, which the decision itself never waits for.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from stock_model_selection.domain.calendar import TradingCalendar
from stock_model_selection.domain.errors import CutoffOrderError, InvalidCohortError
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.time import (
    DAILY_SETTLED_TIME,
    INFORMATION_CUTOFF_TIME,
    MARKET_OPEN_TIME,
    at_taipei,
    require_aware,
)

REVENUE_DEADLINE_DAY = 10
_MONTH_PATTERN = re.compile(r"(\d{4})-(\d{2})")


@dataclass(frozen=True, order=True)
class Month:
    """A calendar month; as a cohort id it prints as "YYYY-MM"."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise InvalidCohortError(f"month out of range: {self.year}-{self.month}")

    @classmethod
    def parse(cls, text: str) -> "Month":
        match = _MONTH_PATTERN.fullmatch(text)
        if match is None:
            raise InvalidCohortError(f"a cohort id is 'YYYY-MM', got {text!r}")
        return cls(int(match[1]), int(match[2]))

    def next(self) -> "Month":
        return Month(self.year + self.month // 12, self.month % 12 + 1)

    def previous(self) -> "Month":
        return Month(self.year - (self.month == 1), (self.month - 2) % 12 + 1)

    def day(self, day: int) -> date:
        return date(self.year, self.month, day)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True, kw_only=True)
class Cohort:
    cohort_id: Month
    # D_M: the 10th, rolled forward to a trading day
    revenue_deadline: date
    # P_M: the first trading day strictly after D_M; also the entry date E_C
    playbook_date: date
    # T_C: P_M at 04:00 Asia/Taipei
    information_cutoff: datetime

    def __post_init__(self) -> None:
        if (self.playbook_date.year, self.playbook_date.month) != (
            self.cohort_id.year,
            self.cohort_id.month,
        ):
            raise InvalidCohortError(
                f"cohort {self.cohort_id} has playbook date {self.playbook_date} outside its month"
            )
        if not self.cohort_id.day(REVENUE_DEADLINE_DAY) <= self.revenue_deadline:
            raise InvalidCohortError(
                f"cohort {self.cohort_id} revenue deadline {self.revenue_deadline} is before "
                f"the {REVENUE_DEADLINE_DAY}th"
            )
        if not self.revenue_deadline < self.playbook_date:
            raise InvalidCohortError(
                f"cohort {self.cohort_id} playbook date {self.playbook_date} is not after "
                f"its revenue deadline {self.revenue_deadline}"
            )
        cutoff = require_aware(self.information_cutoff, "information_cutoff")
        if cutoff != at_taipei(self.playbook_date, INFORMATION_CUTOFF_TIME):
            raise InvalidCohortError(
                f"cohort {self.cohort_id} information cutoff {cutoff.isoformat()} is not "
                f"{self.playbook_date} {INFORMATION_CUTOFF_TIME} Asia/Taipei"
            )
        object.__setattr__(self, "information_cutoff", cutoff)

    @property
    def revenue_month(self) -> Month:
        """The monthly revenue the decision uses: month M-1."""
        return self.cohort_id.previous()

    @property
    def entry_date(self) -> date:
        return self.playbook_date

    def production_context(self, run_at: datetime) -> PitContext:
        """Features as of T_C, known at run time, with T_C <= run_at < the entry trade."""
        run_at = require_aware(run_at, "run_at")
        entry_trade = at_taipei(self.playbook_date, MARKET_OPEN_TIME)
        if not run_at < entry_trade:
            raise CutoffOrderError(
                f"cohort {self.cohort_id} production run at {run_at.isoformat()} is not before "
                f"the entry trade at {entry_trade.isoformat()}"
            )
        # PitContext rejects run_at < T_C
        return PitContext.production(
            information_as_of=self.information_cutoff, knowledge_as_of=run_at
        )

    def reconstruction_context(self, reconstructed_at: datetime) -> PitContext:
        return PitContext.reconstruction(
            information_as_of=self.information_cutoff, knowledge_as_of=reconstructed_at
        )


@dataclass(frozen=True, kw_only=True)
class LabelHorizon:
    cohort: Cohort
    # X_C: the trading day before the next cohort's playbook date
    exit_date: date
    # trading days in [E_C, X_C]
    trading_days: int
    # the exchange_daily_settled@1 rule: X_C's next calendar day at 03:00 Asia/Taipei.
    # A lower bound; the exit price row's actual available_at can only be later (§7).
    label_available_at: datetime

    def production_context(self, run_at: datetime) -> PitContext:
        """Label prices as of label_available_at (decisions D12), known at run time."""
        return PitContext.production(
            information_as_of=self.label_available_at, knowledge_as_of=run_at
        )

    def reconstruction_context(self, reconstructed_at: datetime) -> PitContext:
        return PitContext.reconstruction(
            information_as_of=self.label_available_at, knowledge_as_of=reconstructed_at
        )


def build_cohort(cohort_id: Month | str, calendar: TradingCalendar) -> Cohort:
    month = Month.parse(cohort_id) if isinstance(cohort_id, str) else cohort_id
    deadline = calendar.next_on_or_after(month.day(REVENUE_DEADLINE_DAY))
    playbook = calendar.next_after(deadline)
    return Cohort(
        cohort_id=month,
        revenue_deadline=deadline,
        playbook_date=playbook,
        information_cutoff=at_taipei(playbook, INFORMATION_CUTOFF_TIME),
    )


def build_label_horizon(cohort: Cohort, calendar: TradingCalendar) -> LabelHorizon:
    following = build_cohort(cohort.cohort_id.next(), calendar)
    exit_date = calendar.previous_before(following.playbook_date)
    if exit_date < cohort.entry_date:
        raise InvalidCohortError(f"cohort {cohort.cohort_id} exits before it enters")
    return LabelHorizon(
        cohort=cohort,
        exit_date=exit_date,
        trading_days=len(calendar.trading_days_between(cohort.entry_date, exit_date)),
        label_available_at=at_taipei(exit_date + timedelta(days=1), DAILY_SETTLED_TIME),
    )
