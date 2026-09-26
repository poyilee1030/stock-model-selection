"""A PIT-enforcing fake DataCenterClient for tests (ROADMAP step-5-b).

It answers like Data Center (Market PIT: for each key, the latest row with
available_at <= information_as_of and recorded_at <= knowledge_as_of), builds its
requests with build_query and passes every answer through the step-5-a parsers, so
it is held to the same limits and response contract as the real API. Faults inject
the answers a broken Data Center could give.
"""

import copy
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from stock_model_selection.data.datasets import DATASETS, DatasetKind
from stock_model_selection.data.fake_store import FakeStore, StoredEvent, StoredRow
from stock_model_selection.data.query import DatasetQuery, build_query
from stock_model_selection.data.schemas import (
    AdjustedPricesResponse,
    DerivedResponse,
    ObservedResponse,
    StocksResponse,
    TechnicalIndicatorsResponse,
    TradingDaysResponse,
    parse_adjusted_prices,
    parse_derived,
    parse_observed,
    parse_stocks,
    parse_technical_indicators,
    parse_trading_days,
)
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.time import TAIPEI

ROLLING_INFORMATION = "each date's own release instant"
PRICE_FIELDS = ("open_price", "high_price", "low_price", "close_price")
R = TypeVar("R")
StockIds = Sequence[str] | None


@dataclass(frozen=True)
class Faults:
    # dataset name -> the derivation_version to answer with
    derivation_versions: Mapping[str, str] = field(default_factory=dict)
    # datasets whose rows and events come back without provenance
    missing_provenance: frozenset[str] = frozenset()


def _latest(rows: Iterable[StoredRow]) -> list[StoredRow]:
    """For each key, the row known last (a later version replaces an earlier one)."""
    chosen: dict[tuple[tuple[str, str], ...], StoredRow] = {}
    for row in rows:
        key = (*sorted(row.keys.items()), ("", row.period.isoformat()))
        if key not in chosen or row.known_at >= chosen[key].known_at:
            chosen[key] = row
    return sorted(chosen.values(), key=lambda r: (sorted(r.keys.items()), r.period))


def _factor(event: StoredEvent) -> Decimal | None:
    if event.close_before is None or event.reference_price is None or not event.close_before:
        return None
    return event.reference_price / event.close_before


class FakeDataCenter:
    def __init__(
        self, store: FakeStore, *, faults: Faults | None = None, now: datetime | None = None
    ) -> None:
        self.store = store
        self.faults = faults or Faults()
        # the instant `knowledge_as_of=latest` resolves to
        self.now = now or datetime.now(TAIPEI)

    # the answer to one query

    def _visible(self, query: DatasetQuery, rows: Iterable[StoredRow]) -> list[StoredRow]:
        info, knowledge = query.pit.information_as_of, query.pit.knowledge_as_of
        assert info is not None and knowledge is not None
        kind = query.spec.kind
        return _latest(
            r
            for r in rows
            if (
                kind is DatasetKind.DERIVED_ON_DEMAND
                or r.available_at is None
                or r.available_at <= info
            )
            # stored derived rows are read as of `latest`: whatever is computed by now
            and r.known_at <= (self.now if kind is DatasetKind.DERIVED else knowledge)
        )

    def _selected(self, query: DatasetQuery, dataset: str) -> list[StoredRow]:
        params = query.params
        start, end = (
            date.fromisoformat(query.sent("start") or ""),
            date.fromisoformat(query.sent("end") or ""),
        )
        wanted = {
            key: {v for k, v in params if k == key} for key in ("stock_id", "source", "index_name")
        }
        return [
            r
            for r in self.store.rows[dataset]
            if start <= r.period <= end
            and all(not values or r.keys.get(key) in values for key, values in wanted.items())
        ]

    def _body(self, query: DatasetQuery, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        spec = query.spec
        knowledge = query.sent("knowledge_as_of")
        body: dict[str, Any] = {
            "dataset": spec.name,
            "pit": {
                "mode": "market",
                "information_as_of": query.sent("information_as_of") or ROLLING_INFORMATION,
                "knowledge_as_of": self.now.isoformat() if knowledge == "latest" else knowledge,
                "defaulted": [] if spec.sends_information_as_of else ["information_as_of"],
                "aliases": {"knowledge_as_of": "latest"} if knowledge == "latest" else {},
            },
            "query": [list(p) for p in query.params],
            "rows": [copy.deepcopy(dict(r)) for r in rows],
        }
        if spec.kind is DatasetKind.OBSERVED:
            body["unsourced"] = {}
        else:
            assert spec.derivation is not None
            body["derivation"] = {
                "dataset_code": spec.derivation.dataset_code,
                "derivation_version": self.faults.derivation_versions.get(
                    spec.name, spec.derivation.derivation_version
                ),
            }
        if spec.kind is DatasetKind.DERIVED:
            body["inputs"] = "latest"
        if spec.name == "technical-indicators-pit":
            body["view"] = "rolling"
        return body

    def _faulted(self, body: dict[str, Any]) -> dict[str, Any]:
        if body["dataset"] in self.faults.missing_provenance:
            for row in [*body["rows"], *body.get("events", [])]:
                row.pop("provenance", None)
        return body

    def _answer(
        self,
        parse: Callable[[DatasetQuery, object], R],
        name: str,
        start: date,
        end: date,
        stock_ids: StockIds,
        pit: PitContext,
        **extra: Any,
    ) -> R:
        query = build_query(DATASETS[name], pit, start, end, stock_ids, **extra)
        rows = self._visible(query, self._selected(query, name))
        return parse(query, self._faulted(self._body(query, [r.row for r in rows])))

    # adjusted-prices-pit, computed from the visible prices and events

    def _adjusted_body(self, query: DatasetQuery) -> dict[str, Any]:
        info, knowledge = query.pit.information_as_of, query.pit.knowledge_as_of
        assert info is not None and knowledge is not None
        stock_id = query.sent("stock_id")
        start, end = (
            date.fromisoformat(query.sent("start") or ""),
            date.fromisoformat(query.sent("end") or ""),
        )
        prices = [
            r
            for r in self.store.rows["daily-prices"]
            if r.keys["stock_id"] == stock_id
            and r.available_at is not None
            and r.available_at <= info
            and r.known_at <= knowledge
        ]
        rows: list[dict[str, Any]] = []
        applied: dict[int, StoredEvent] = {}
        for source in sorted({r.keys["source"] for r in prices}):
            series = _latest(r for r in prices if r.keys["source"] == source)
            last = series[-1].period
            # an event adjusts nothing until a price on or after its ex-date is visible
            visible = [
                e
                for e in self.store.events
                if e.stock_id == stock_id
                and e.price_source == source
                and e.ex_date <= last
                and e.available_at <= info
                and e.known_at <= knowledge
            ]
            # a corrected event replaces the original: keys stock_id, source, ex_date
            latest: dict[tuple[str, date], StoredEvent] = {}
            for event in sorted(visible, key=lambda e: e.known_at):
                latest[(event.row["source"], event.ex_date)] = event
            events = list(latest.values())
            for price in series:
                if not start <= price.period <= end:
                    continue
                later = [e for e in events if e.ex_date > price.period]
                applied.update((id(e), e) for e in later)
                factor: Decimal | None = Decimal(1)
                for event in later:
                    event_factor = _factor(event)
                    factor = (
                        None if factor is None or event_factor is None else factor * event_factor
                    )
                raw = {name: price.row.get(name) for name in PRICE_FIELDS}
                rows.append(
                    {
                        "stock_id": stock_id,
                        "source": source,
                        "trade_date": price.period.isoformat(),
                        **raw,
                        "adjustment_factor": factor,
                        **{
                            f"adjusted_{name}": None if v is None or factor is None else v * factor
                            for name, v in raw.items()
                        },
                    }
                )
        body = self._body(query, rows)
        body["events"] = [
            copy.deepcopy(dict(e.row)) for e in sorted(applied.values(), key=lambda e: e.ex_date)
        ]
        return body

    # observed

    def monthly_revenues(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "monthly-revenues", start, end, stock_ids, pit)

    def daily_prices(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "daily-prices", start, end, stock_ids, pit)

    def official_valuations(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "official-valuations", start, end, stock_ids, pit)

    def institutional_flows(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "institutional-flows", start, end, stock_ids, pit)

    def foreign_holdings(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "foreign-holdings", start, end, stock_ids, pit)

    def margin_trading(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "margin-trading", start, end, stock_ids, pit)

    def securities_lending(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(parse_observed, "securities-lending", start, end, stock_ids, pit)

    def shareholding_distributions(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(
            parse_observed, "shareholding-distributions", start, end, stock_ids, pit
        )

    def indices(
        self, source: str, index_name: str, start: date, end: date, *, pit: PitContext
    ) -> ObservedResponse:
        return self._answer(
            parse_observed,
            "indices",
            start,
            end,
            None,
            pit,
            sources=[source],
            index_name=index_name,
        )

    # stored derived

    def valuation_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(parse_derived, "valuation-metrics", start, end, stock_ids, pit)

    def institutional_streaks(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(parse_derived, "institutional-streaks", start, end, stock_ids, pit)

    def institutional_cumulative_flows(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(
            parse_derived, "institutional-cumulative-flows", start, end, stock_ids, pit
        )

    def shareholding_concentrations(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(
            parse_derived, "shareholding-concentrations", start, end, stock_ids, pit
        )

    def margin_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(parse_derived, "margin-metrics", start, end, stock_ids, pit)

    def short_interest_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse:
        return self._answer(parse_derived, "short-interest-metrics", start, end, stock_ids, pit)

    # computed on demand

    def technical_indicators_pit(
        self, stock_id: str, start: date, end: date, *, pit: PitContext
    ) -> TechnicalIndicatorsResponse:
        return self._answer(
            parse_technical_indicators, "technical-indicators-pit", start, end, [stock_id], pit
        )

    def adjusted_prices_pit(
        self, stock_id: str, start: date, end: date, *, pit: PitContext
    ) -> AdjustedPricesResponse:
        query = build_query(DATASETS["adjusted-prices-pit"], pit, start, end, [stock_id])
        return parse_adjusted_prices(query, self._faulted(self._adjusted_body(query)))

    # reference data

    def stocks(
        self, *, on: date | None = None, stock_ids: StockIds = None, market: str | None = None
    ) -> StocksResponse:
        def covers(span: Mapping[str, Any]) -> bool:
            listed, delisted = span["listed_on"], span["delisted_on"]
            return on is None or (
                (listed is None or date.fromisoformat(listed) <= on)
                and (delisted is None or on < date.fromisoformat(delisted))
            )

        rows = [
            copy.deepcopy(dict(stock))
            for stock in self.store.stocks
            if (stock_ids is None or stock["stock_id"] in stock_ids)
            and (
                (on is None and market is None)
                or any(covers(s) and market in (None, s["market"]) for s in stock["listings"])
            )
        ]
        return parse_stocks({"rows": rows})

    def trading_days(self, start: date, end: date) -> TradingDaysResponse:
        rows = [
            {"trade_date": day.isoformat(), "provenance": dict(provenance)}
            for day, provenance in sorted(self.store.trading_days.items())
            if start <= day <= end
        ]
        return parse_trading_days({"rows": rows})
