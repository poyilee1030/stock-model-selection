"""In-memory rows for the fake Data Center client, with builders for common fixtures.

Each stored row keeps the timestamps the fake filters on: `available_at` (when it became
public) and `known_at` (when Data Center recorded it; for stored derived rows, when they
were computed). Builders default to the release rules Data Center uses:

    daily data            D+1 03:00 Asia/Taipei (exchange_daily_settled@1)
    monthly revenue       its publication day 23:59:59
    corporate action      00:00 on its ex-date
    recorded / computed   when it became public, unless given (history was backfilled)
"""

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from stock_model_selection.data.datasets import DATASETS, DatasetKind
from stock_model_selection.data.schemas import Scalar
from stock_model_selection.domain.cohort import Month
from stock_model_selection.domain.time import DAILY_SETTLED_TIME, at_taipei, require_aware

Price = Decimal | None
REVENUE_PUBLIC_TIME = time(23, 59, 59)
PRICE_SOURCE = "twse_mi_index"


def daily_settled(day: date) -> datetime:
    return at_taipei(day + timedelta(days=1), DAILY_SETTLED_TIME)


@dataclass(frozen=True)
class StoredRow:
    row: Mapping[str, Any]
    keys: Mapping[str, str]
    period: date
    available_at: datetime | None
    known_at: datetime


@dataclass(frozen=True)
class StoredEvent:
    row: Mapping[str, Any]
    stock_id: str
    # the daily-price series it adjusts
    price_source: str
    ex_date: date
    close_before: Price
    reference_price: Price
    available_at: datetime
    known_at: datetime


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[str, list[StoredRow]] = defaultdict(list)
        self.events: list[StoredEvent] = []
        self.stocks: list[Mapping[str, Any]] = []
        self.trading_days: dict[date, Mapping[str, str]] = {}
        self._fetches = 0

    def provenance(self) -> dict[str, str]:
        self._fetches += 1
        digest = hashlib.sha256(f"fake fetch {self._fetches}".encode()).hexdigest()
        return {"fetch_id": f"fake-{self._fetches}", "raw_sha256": digest}

    def _add(
        self,
        dataset: str,
        keys: Mapping[str, str],
        period: date,
        fields: Mapping[str, Any],
        *,
        available_at: datetime | None,
        known_at: datetime,
    ) -> None:
        spec = DATASETS[dataset]
        expected = [k for k in spec.keys if k != spec.period]
        if sorted(keys) != sorted(expected):
            raise ValueError(f"{dataset} keys are {expected}, got {sorted(keys)}")
        row = {**keys, spec.period: period.isoformat(), **fields}
        self.rows[dataset].append(StoredRow(row, dict(keys), period, available_at, known_at))

    def add_observed(
        self,
        dataset: str,
        keys: Mapping[str, str],
        period: date,
        values: Mapping[str, Scalar],
        *,
        available_at: datetime,
        recorded_at: datetime | None = None,
    ) -> None:
        if DATASETS[dataset].kind is not DatasetKind.OBSERVED:
            raise ValueError(f"{dataset} is not observed")
        available = require_aware(available_at, "available_at")
        recorded = require_aware(recorded_at or available, "recorded_at")
        fields = {
            **values,
            "available_at": available.isoformat(),
            "recorded_at": recorded.isoformat(),
            "provenance": self.provenance(),
        }
        self._add(dataset, keys, period, fields, available_at=available, known_at=recorded)

    def add_daily_price(
        self,
        stock_id: str,
        trade_date: date,
        *,
        open: Price,
        high: Price,
        low: Price,
        close: Price,
        volume: int,
        source: str = PRICE_SOURCE,
        recorded_at: datetime | None = None,
    ) -> None:
        values = {
            "open_price": open,
            "high_price": high,
            "low_price": low,
            "close_price": close,
            "volume": volume,
        }
        self.add_observed(
            "daily-prices",
            {"stock_id": stock_id, "source": source},
            trade_date,
            values,
            available_at=daily_settled(trade_date),
            recorded_at=recorded_at,
        )

    def add_monthly_revenue(
        self,
        stock_id: str,
        revenue_month: str,
        revenue: Decimal,
        *,
        published_on: date,
        source: str = "mops_t21sc03_sii",
        available_at: datetime | None = None,
        recorded_at: datetime | None = None,
    ) -> None:
        """Public at the publication day's 23:59:59; a correction passes its own available_at."""
        self.add_observed(
            "monthly-revenues",
            {"stock_id": stock_id, "source": source},
            Month.parse(revenue_month).day(1),
            {"revenue": revenue},
            available_at=available_at or at_taipei(published_on, REVENUE_PUBLIC_TIME),
            recorded_at=recorded_at,
        )

    def add_derived(
        self,
        dataset: str,
        stock_id: str,
        period: date,
        values: Mapping[str, Scalar],
        *,
        source: str = PRICE_SOURCE,
        available_at: datetime | None = None,
        computed_at: datetime | None = None,
    ) -> None:
        """A stored derived row; `available_at` defaults to the daily rule."""
        if DATASETS[dataset].kind is not DatasetKind.DERIVED:
            raise ValueError(f"{dataset} is not a stored derived dataset")
        available = require_aware(available_at or daily_settled(period), "available_at")
        computed = require_aware(computed_at or available, "computed_at")
        fields = {
            **values,
            "computed_at": computed.isoformat(),
            "available_at": available.isoformat(),
        }
        keys = {"stock_id": stock_id, "source": source}
        self._add(dataset, keys, period, fields, available_at=available, known_at=computed)

    def add_rolling_indicators(
        self,
        stock_id: str,
        trade_date: date,
        values: Mapping[str, Scalar],
        *,
        source: str = PRICE_SOURCE,
        recorded_at: datetime | None = None,
    ) -> None:
        """A technical-indicators-pit row, computed as of its own trade date's release."""
        released = daily_settled(trade_date)
        known = require_aware(recorded_at or released, "recorded_at")
        fields = {
            "information_as_of": released.isoformat(),
            "input_count": 1,
            "input_fingerprint": hashlib.sha256(f"{stock_id} {trade_date}".encode()).hexdigest(),
            **values,
        }
        keys = {"stock_id": stock_id, "source": source}
        self._add(
            "technical-indicators-pit", keys, trade_date, fields, available_at=None, known_at=known
        )

    def add_corporate_action(
        self,
        stock_id: str,
        ex_date: date,
        *,
        close_before: Price,
        reference_price: Price,
        event_type: str = "息",
        source: str = "twse_twt49u",
        price_source: str = PRICE_SOURCE,
        available_at: datetime | None = None,
        recorded_at: datetime | None = None,
    ) -> None:
        """An event adjusting adjusted-prices-pit; public from 00:00 on its ex-date."""
        available = require_aware(available_at or at_taipei(ex_date, time(0)), "available_at")
        recorded = require_aware(recorded_at or available, "recorded_at")
        row = {
            "stock_id": stock_id,
            "source": source,
            "ex_date": ex_date.isoformat(),
            "recorded_at": recorded.isoformat(),
            "event_type": event_type,
            "close_before": close_before,
            "reference_price": reference_price,
            "available_at": available.isoformat(),
            "provenance": self.provenance(),
        }
        self.events.append(
            StoredEvent(
                row,
                stock_id,
                price_source,
                ex_date,
                close_before,
                reference_price,
                available,
                recorded,
            )
        )

    def add_stock(
        self,
        stock_id: str,
        name: str,
        *,
        industry: str | None,
        listings: Sequence[tuple[str, date | None, date | None]],
    ) -> None:
        """Listing spans as (market, listed_on, delisted_on); a delisted stock has no market."""
        spans = [
            {
                "market": market,
                "listed_on": listed.isoformat() if listed else None,
                "delisted_on": delisted.isoformat() if delisted else None,
                "provenance": self.provenance(),
            }
            for market, listed, delisted in listings
        ]
        current = spans[-1] if spans and spans[-1]["delisted_on"] is None else None
        self.stocks.append(
            {
                "stock_id": stock_id,
                "name": name,
                "industry": industry,
                "market": current["market"] if current else None,
                "listed_on": current["listed_on"] if current else None,
                "listings": spans,
                "provenance": self.provenance(),
            }
        )

    def add_trading_days(self, days: Iterable[date]) -> None:
        for day in days:
            self.trading_days[day] = self.provenance()
