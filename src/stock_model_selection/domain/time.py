"""Clock times from docs/contracts/time-and-cohort.md §2, §4, §7."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from stock_model_selection.domain.errors import InvalidCutoffError

TAIPEI = ZoneInfo("Asia/Taipei")

# T_C is the playbook date at this time (§4)
INFORMATION_CUTOFF_TIME = time(4, 0)
# exchange_daily_settled@1: day D's daily rows are available at D+1 03:00 (§7)
DAILY_SETTLED_TIME = time(3, 0)
# the entry trade is the playbook date's open (decisions D12)
MARKET_OPEN_TIME = time(9, 0)


def at_taipei(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, tzinfo=TAIPEI)


def require_aware(value: object, name: str) -> datetime:
    """Return value in Asia/Taipei, or fail unless it is a timezone-aware datetime."""
    if not isinstance(value, datetime):
        raise InvalidCutoffError(
            f"{name} must be a timezone-aware datetime, got {type(value).__name__}: {value!r}"
        )
    if value.utcoffset() is None:
        raise InvalidCutoffError(f"{name} has no UTC offset: {value.isoformat()}")
    return value.astimezone(TAIPEI)
