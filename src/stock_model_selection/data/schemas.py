"""Data Center response schemas (ROADMAP §2 "Data Center API", recorded 2026-09-26).

Every answer is checked against the query that asked for it: the `pit` block must echo
the cutoffs that were sent and never list one of them as defaulted, and no row may be
newer than the PIT context allows. Row values stay as sent. Decimals arrive as JSON
numbers with their stored digits (1040.000000); decode_json reads them as Decimal, and a
binary float in a parsed body is refused.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from stock_model_selection.data.datasets import DatasetKind, DatasetSpec
from stock_model_selection.data.errors import (
    BadRequestError,
    DataCenterRequestError,
    MissingDerivationError,
    MissingProvenanceError,
    NotFoundError,
    PitViolationError,
    ResponseSchemaError,
    UnauthorizedError,
)
from stock_model_selection.data.query import DatasetQuery
from stock_model_selection.domain.calendar import TradingCalendar
from stock_model_selection.domain.errors import InvalidCutoffError
from stock_model_selection.domain.provenance import DerivationRef, ProvenanceRecord
from stock_model_selection.domain.time import DAILY_SETTLED_TIME, at_taipei, require_aware

Scalar = str | int | Decimal | None


def decode_json(text: str) -> Any:
    """Decode a response body; JSON numbers with a fraction become Decimal, not float."""
    return json.loads(text, parse_float=Decimal)


def error_from_response(status: int, body: object) -> DataCenterRequestError:
    detail = body.get("detail") if isinstance(body, dict) else None
    text = detail if isinstance(detail, str) else str(body)
    error = {400: BadRequestError, 401: UnauthorizedError, 404: NotFoundError}.get(
        status, DataCenterRequestError
    )
    return error(status, text)


# field readers


def _object(value: object, what: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ResponseSchemaError(f"{what} is not an object: {value!r}")
    return value


def _list(value: object, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResponseSchemaError(f"{what} is not a list: {value!r}")
    return value


def _str(obj: Mapping[str, Any], key: str, what: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise ResponseSchemaError(f"{what}.{key} is not a non-empty string: {value!r}")
    return value


def _parse_instant(value: object, what: str) -> datetime:
    if not isinstance(value, str):
        raise ResponseSchemaError(f"{what} is not a timestamp: {value!r}")
    try:
        return require_aware(datetime.fromisoformat(value), what)
    except (ValueError, InvalidCutoffError) as error:
        raise ResponseSchemaError(f"{what} is not a timestamp with an offset: {value!r}") from error


def _instant(obj: Mapping[str, Any], key: str, what: str) -> datetime:
    return _parse_instant(obj.get(key), f"{what}.{key}")


def _date(obj: Mapping[str, Any], key: str, what: str, *, nullable: bool = False) -> date | None:
    value = obj.get(key)
    if value is None and nullable and key in obj:
        return None
    if not isinstance(value, str):
        raise ResponseSchemaError(f"{what}.{key} is not a date: {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ResponseSchemaError(f"{what}.{key} is not a date: {value!r}") from error


def _required_date(obj: Mapping[str, Any], key: str, what: str) -> date:
    value = _date(obj, key, what)
    assert value is not None
    return value


@dataclass(frozen=True)
class RowProvenance:
    fetch_id: str
    raw_sha256: str


def _provenance(obj: Mapping[str, Any], what: str) -> RowProvenance:
    value = obj.get("provenance")
    if not isinstance(value, dict):
        raise MissingProvenanceError(f"{what} has no provenance")
    fields = []
    for key in ("fetch_id", "raw_sha256"):
        field = value.get(key)
        if not isinstance(field, str) or not field:
            raise MissingProvenanceError(f"{what} provenance has no {key}")
        fields.append(field)
    return RowProvenance(*fields)


def _values(row: Mapping[str, Any], taken: set[str], what: str) -> Mapping[str, Scalar]:
    values: dict[str, Scalar] = {}
    for key, value in row.items():
        if key in taken:
            continue
        if isinstance(value, float) or not isinstance(value, str | int | Decimal | None):
            raise ResponseSchemaError(f"{what}.{key} is not a scalar value: {value!r}")
        values[key] = value
    return values


# the pit block and the envelope


@dataclass(frozen=True)
class ResponsePit:
    mode: str
    # text instead of an instant when Data Center answers per row (view=rolling)
    information_as_of: datetime | str
    knowledge_as_of: datetime
    defaulted: tuple[str, ...]
    aliases: Mapping[str, str]


@dataclass(frozen=True)
class FetchProvenance:
    """What was asked (record, params) and what Data Center said it answered."""

    record: ProvenanceRecord
    response_pit: ResponsePit
    params: tuple[tuple[str, str], ...]


def _response_pit(value: object, query: DatasetQuery) -> ResponsePit:
    pit = _object(value, "pit")
    info_value = pit.get("information_as_of")
    info: datetime | str
    if "information_as_of" in query.sent_cutoffs:
        info = _parse_instant(info_value, "pit.information_as_of")
    elif isinstance(info_value, str):
        info = info_value
    else:
        raise ResponseSchemaError(f"pit.information_as_of is not text: {info_value!r}")
    defaulted = _list(pit.get("defaulted"), "pit.defaulted")
    aliases = _object(pit.get("aliases"), "pit.aliases")
    if not all(isinstance(k, str) for k in defaulted) or not all(
        isinstance(v, str) for v in aliases.values()
    ):
        raise ResponseSchemaError(f"pit.defaulted or pit.aliases is malformed: {pit!r}")
    return ResponsePit(
        mode=_str(pit, "mode", "pit"),
        information_as_of=info,
        knowledge_as_of=_instant(pit, "knowledge_as_of", "pit"),
        defaulted=tuple(defaulted),
        aliases=dict(aliases),
    )


def _check_pit_echo(pit: ResponsePit, query: DatasetQuery) -> None:
    name = query.spec.name
    defaulted = query.sent_cutoffs & set(pit.defaulted)
    if defaulted:
        raise PitViolationError(
            f"{name}: Data Center defaulted cutoffs that were sent: {defaulted}"
        )
    if "information_as_of" in query.sent_cutoffs and (
        pit.information_as_of != query.pit.information_as_of
    ):
        raise PitViolationError(
            f"{name}: answered for information_as_of {pit.information_as_of}, "
            f"asked {query.sent('information_as_of')}"
        )
    if query.sent("knowledge_as_of") == "latest":
        if pit.aliases.get("knowledge_as_of") != "latest":
            raise PitViolationError(f"{name}: knowledge_as_of=latest was not confirmed: {pit}")
    elif pit.knowledge_as_of != query.pit.knowledge_as_of:
        raise PitViolationError(
            f"{name}: answered for knowledge_as_of {pit.knowledge_as_of.isoformat()}, "
            f"asked {query.sent('knowledge_as_of')}"
        )


def _derivation(body: Mapping[str, Any], name: str) -> DerivationRef:
    block = body.get("derivation")
    if not isinstance(block, dict):
        raise MissingDerivationError(f"{name}: the response has no derivation block")
    fields = []
    for key in ("dataset_code", "derivation_version"):
        value = block.get(key)
        if not isinstance(value, str) or not value.strip():
            raise MissingDerivationError(f"{name}: the derivation block has no {key}: {value!r}")
        fields.append(value)
    return DerivationRef(*fields)


@dataclass(frozen=True)
class _Envelope:
    body: Mapping[str, Any]
    provenance: FetchProvenance
    derivation: DerivationRef | None
    rows: list[Any]


def _envelope(query: DatasetQuery, body: object, kinds: tuple[DatasetKind, ...]) -> _Envelope:
    spec = query.spec
    if spec.kind not in kinds:
        raise ResponseSchemaError(f"{spec.name} is {spec.kind}, not parsed as {kinds}")
    obj = _object(body, f"{spec.name} response")
    if obj.get("dataset") != spec.name:
        raise ResponseSchemaError(f"asked {spec.name}, answered {obj.get('dataset')!r}")
    if spec.kind is DatasetKind.OBSERVED:
        if "derivation" in obj:
            raise ResponseSchemaError(f"{spec.name}: an observed answer has a derivation block")
        derivation = None
    else:
        derivation = _derivation(obj, spec.name)
    pit = _response_pit(obj.get("pit"), query)
    _check_pit_echo(pit, query)
    record = ProvenanceRecord(
        dataset=spec.name, pit=query.pit, derivation=derivation, knowledge=spec.knowledge
    )
    return _Envelope(
        obj,
        FetchProvenance(record, pit, query.params),
        derivation,
        _list(obj.get("rows"), f"{spec.name} rows"),
    )


def _keys(row: Mapping[str, Any], spec: DatasetSpec, what: str) -> Mapping[str, str]:
    return {key: _str(row, key, what) for key in spec.keys if key != spec.period}


def _not_after(value: datetime, cutoff: datetime | None, what: str, name: str) -> None:
    if cutoff is not None and value > cutoff:
        raise PitViolationError(f"{what} {value.isoformat()} is after {name} {cutoff.isoformat()}")


# observed


@dataclass(frozen=True)
class ObservedRow:
    keys: Mapping[str, str]
    period: date
    available_at: datetime
    recorded_at: datetime
    provenance: RowProvenance
    values: Mapping[str, Scalar]


@dataclass(frozen=True)
class ObservedResponse:
    dataset: str
    provenance: FetchProvenance
    unsourced: Mapping[str, tuple[str, ...]]
    rows: tuple[ObservedRow, ...]


def _observed_row(row: Mapping[str, Any], query: DatasetQuery, what: str) -> ObservedRow:
    spec, pit = query.spec, query.pit
    parsed = ObservedRow(
        keys=_keys(row, spec, what),
        period=_required_date(row, spec.period, what),
        available_at=_instant(row, "available_at", what),
        recorded_at=_instant(row, "recorded_at", what),
        provenance=_provenance(row, what),
        values=_values(row, {*spec.keys, "available_at", "recorded_at", "provenance"}, what),
    )
    _not_after(parsed.available_at, pit.information_as_of, what, "information_as_of")
    _not_after(parsed.recorded_at, pit.knowledge_as_of, what, "knowledge_as_of")
    return parsed


def parse_observed(query: DatasetQuery, body: object) -> ObservedResponse:
    env = _envelope(query, body, (DatasetKind.OBSERVED,))
    unsourced = _object(env.body.get("unsourced", {}), "unsourced")
    name = query.spec.name
    return ObservedResponse(
        dataset=name,
        provenance=env.provenance,
        unsourced={k: tuple(_list(v, f"unsourced.{k}")) for k, v in unsourced.items()},
        rows=tuple(
            _observed_row(_object(r, f"{name} row {i}"), query, f"{name} row {i}")
            for i, r in enumerate(env.rows)
        ),
    )


# stored derived


@dataclass(frozen=True)
class DerivedRow:
    keys: Mapping[str, str]
    period: date
    available_at: datetime
    computed_at: datetime
    values: Mapping[str, Scalar]


@dataclass(frozen=True)
class DerivedResponse:
    dataset: str
    provenance: FetchProvenance
    derivation: DerivationRef
    inputs: str
    rows: tuple[DerivedRow, ...]


def parse_derived(query: DatasetQuery, body: object) -> DerivedResponse:
    env = _envelope(query, body, (DatasetKind.DERIVED,))
    spec, pit, name = query.spec, query.pit, query.spec.name
    rows = []
    for i, raw in enumerate(env.rows):
        what = f"{name} row {i}"
        row = _object(raw, what)
        parsed = DerivedRow(
            keys=_keys(row, spec, what),
            period=_required_date(row, spec.period, what),
            available_at=_instant(row, "available_at", what),
            computed_at=_instant(row, "computed_at", what),
            values=_values(row, {*spec.keys, "available_at", "computed_at"}, what),
        )
        _not_after(parsed.available_at, pit.information_as_of, what, "information_as_of")
        rows.append(parsed)
    assert env.derivation is not None
    return DerivedResponse(
        dataset=name,
        provenance=env.provenance,
        derivation=env.derivation,
        inputs=_str(env.body, "inputs", name),
        rows=tuple(rows),
    )


# technical-indicators-pit, view=rolling


@dataclass(frozen=True)
class RollingRow:
    keys: Mapping[str, str]
    period: date
    # the instant this row was computed as of: its own trade date's release
    information_as_of: datetime
    input_count: int
    input_fingerprint: str
    values: Mapping[str, Scalar]


@dataclass(frozen=True)
class TechnicalIndicatorsResponse:
    dataset: str
    provenance: FetchProvenance
    derivation: DerivationRef
    view: str
    rows: tuple[RollingRow, ...]


def parse_technical_indicators(query: DatasetQuery, body: object) -> TechnicalIndicatorsResponse:
    if query.spec.name != "technical-indicators-pit":
        raise ResponseSchemaError(f"{query.spec.name} is not technical-indicators-pit")
    env = _envelope(query, body, (DatasetKind.DERIVED_ON_DEMAND,))
    spec, pit, name = query.spec, query.pit, query.spec.name
    rows = []
    for i, raw in enumerate(env.rows):
        what = f"{name} row {i}"
        row = _object(raw, what)
        count = row.get("input_count")
        if not isinstance(count, int):
            raise ResponseSchemaError(f"{what}.input_count is not an integer: {count!r}")
        parsed = RollingRow(
            keys=_keys(row, spec, what),
            period=_required_date(row, spec.period, what),
            information_as_of=_instant(row, "information_as_of", what),
            input_count=count,
            input_fingerprint=_str(row, "input_fingerprint", what),
            values=_values(
                row,
                {*spec.keys, "information_as_of", "input_count", "input_fingerprint"},
                what,
            ),
        )
        # rows past the cohort's cutoff are computed from data the cohort cannot see
        _not_after(parsed.information_as_of, pit.information_as_of, what, "information_as_of")
        rows.append(parsed)
    assert env.derivation is not None
    return TechnicalIndicatorsResponse(
        dataset=name,
        provenance=env.provenance,
        derivation=env.derivation,
        view=_str(env.body, "view", name),
        rows=tuple(rows),
    )


# adjusted-prices-pit


@dataclass(frozen=True)
class AdjustedPriceRow:
    keys: Mapping[str, str]
    period: date
    values: Mapping[str, Scalar]


@dataclass(frozen=True)
class AdjustmentEvent:
    keys: Mapping[str, str]
    # ex_date
    period: date
    available_at: datetime
    recorded_at: datetime
    provenance: RowProvenance
    values: Mapping[str, Scalar]


@dataclass(frozen=True)
class AdjustedPricesResponse:
    dataset: str
    provenance: FetchProvenance
    derivation: DerivationRef
    rows: tuple[AdjustedPriceRow, ...]
    events: tuple[AdjustmentEvent, ...]


def parse_adjusted_prices(query: DatasetQuery, body: object) -> AdjustedPricesResponse:
    if query.spec.name != "adjusted-prices-pit":
        raise ResponseSchemaError(f"{query.spec.name} is not adjusted-prices-pit")
    env = _envelope(query, body, (DatasetKind.DERIVED_ON_DEMAND,))
    spec, pit, name = query.spec, query.pit, query.spec.name
    rows = []
    for i, raw in enumerate(env.rows):
        what = f"{name} row {i}"
        row = _object(raw, what)
        price = AdjustedPriceRow(
            keys=_keys(row, spec, what),
            period=_required_date(row, spec.period, what),
            values=_values(row, set(spec.keys), what),
        )
        # rows carry no available_at: a price is public from exchange_daily_settled@1
        public_at = at_taipei(price.period + timedelta(days=1), DAILY_SETTLED_TIME)
        _not_after(public_at, pit.information_as_of, f"{what} price public at", "information_as_of")
        rows.append(price)
    events = []
    for i, raw in enumerate(_list(env.body.get("events"), f"{name} events")):
        what = f"{name} event {i}"
        event = _object(raw, what)
        parsed = AdjustmentEvent(
            keys={key: _str(event, key, what) for key in ("stock_id", "source")},
            period=_required_date(event, "ex_date", what),
            available_at=_instant(event, "available_at", what),
            recorded_at=_instant(event, "recorded_at", what),
            provenance=_provenance(event, what),
            values=_values(
                event,
                {"stock_id", "source", "ex_date", "available_at", "recorded_at", "provenance"},
                what,
            ),
        )
        _not_after(parsed.available_at, pit.information_as_of, what, "information_as_of")
        _not_after(parsed.recorded_at, pit.knowledge_as_of, what, "knowledge_as_of")
        events.append(parsed)
    assert env.derivation is not None
    return AdjustedPricesResponse(
        dataset=name,
        provenance=env.provenance,
        derivation=env.derivation,
        rows=tuple(rows),
        events=tuple(events),
    )


# reference data: not PIT, but every row names its source file


@dataclass(frozen=True)
class Listing:
    market: str
    listed_on: date | None
    delisted_on: date | None
    provenance: RowProvenance


@dataclass(frozen=True)
class Stock:
    stock_id: str
    name: str
    # today's classification, null for delisted stocks (decisions D16)
    industry: str | None
    # null for a delisted stock; each listing span keeps its market
    market: str | None
    listed_on: date | None
    listings: tuple[Listing, ...]
    provenance: RowProvenance


@dataclass(frozen=True)
class StocksResponse:
    rows: tuple[Stock, ...]


def parse_stocks(body: object) -> StocksResponse:
    stocks = []
    for i, raw in enumerate(_list(_object(body, "stocks response").get("rows"), "stocks rows")):
        what = f"stocks row {i}"
        row = _object(raw, what)
        industry, market = row.get("industry"), row.get("market")
        if not all(v is None or isinstance(v, str) for v in (industry, market)):
            raise ResponseSchemaError(f"{what}: industry or market is not text: {row!r}")
        listings = []
        for j, span in enumerate(_list(row.get("listings"), f"{what}.listings")):
            span_what = f"{what} listing {j}"
            span_obj = _object(span, span_what)
            listings.append(
                Listing(
                    market=_str(span_obj, "market", span_what),
                    listed_on=_date(span_obj, "listed_on", span_what, nullable=True),
                    delisted_on=_date(span_obj, "delisted_on", span_what, nullable=True),
                    provenance=_provenance(span_obj, span_what),
                )
            )
        stocks.append(
            Stock(
                stock_id=_str(row, "stock_id", what),
                name=_str(row, "name", what),
                industry=industry,
                market=market,
                listed_on=_date(row, "listed_on", what, nullable=True),
                listings=tuple(listings),
                provenance=_provenance(row, what),
            )
        )
    return StocksResponse(tuple(stocks))


@dataclass(frozen=True)
class TradingDay:
    day: date
    provenance: RowProvenance


@dataclass(frozen=True)
class TradingDaysResponse:
    days: tuple[TradingDay, ...]

    def calendar(self) -> TradingCalendar:
        return TradingCalendar(d.day for d in self.days)


def parse_trading_days(body: object) -> TradingDaysResponse:
    rows = _list(_object(body, "trading-days response").get("rows"), "trading-days rows")
    days = []
    for i, raw in enumerate(rows):
        what = f"trading-days row {i}"
        row = _object(raw, what)
        days.append(TradingDay(_required_date(row, "trade_date", what), _provenance(row, what)))
    return TradingDaysResponse(tuple(days))
