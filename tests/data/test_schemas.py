"""Response schemas, grown from recorded Data Center responses.

Each recorded response must parse. Each break of a rule the ROADMAP names (missing
derivation version, missing provenance, defaulted cutoff, PIT violation) is made on a
copy of a real response and must be refused.
"""

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from stock_model_selection.data.datasets import DATASETS, DatasetKind
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
from stock_model_selection.data.query import DatasetQuery, build_query
from stock_model_selection.data.schemas import (
    AdjustedPricesResponse,
    DerivedResponse,
    ObservedResponse,
    TechnicalIndicatorsResponse,
    decode_json,
    error_from_response,
    parse_adjusted_prices,
    parse_derived,
    parse_observed,
    parse_stocks,
    parse_technical_indicators,
    parse_trading_days,
)
from stock_model_selection.domain.errors import MissingDerivationVersionError
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.provenance import DerivationRef, KnowledgeQuery
from stock_model_selection.domain.time import TAIPEI
from tests.data.conftest import recorded

T_C = datetime(2024, 7, 11, 4, 0, tzinfo=TAIPEI)
LABEL_AT = datetime(2024, 7, 11, 3, 0, tzinfo=TAIPEI)
T_RECON = datetime(2026, 9, 26, 12, 0, tzinfo=TAIPEI)
FEATURES = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=T_RECON)
LABELS = PitContext.reconstruction(information_as_of=LABEL_AT, knowledge_as_of=T_RECON)
TAIEX_TR = "報酬指數/臺灣證券交易所:發行量加權股價報酬指數"

Parser = Callable[[DatasetQuery, Any], Any]


def query_for(name: str, pit: PitContext | None = None) -> DatasetQuery:
    """The query each recorded response was asked with."""
    params = dict(recorded(name).params)
    start, end = date.fromisoformat(params["start"]), date.fromisoformat(params["end"])
    spec = DATASETS[name]
    if name == "indices":
        return build_query(
            spec, pit or LABELS, start, end, sources=["twse_mi_index"], index_name=TAIEX_TR
        )
    default = LABELS if name == "adjusted-prices-pit" else FEATURES
    return build_query(spec, pit or default, start, end, stock_ids=["2330"])


def parser_for(name: str) -> Parser:
    if name == "technical-indicators-pit":
        return parse_technical_indicators
    if name == "adjusted-prices-pit":
        return parse_adjusted_prices
    if DATASETS[name].kind is DatasetKind.DERIVED:
        return parse_derived
    return parse_observed


def parse(name: str, body: Any = None, pit: PitContext | None = None) -> Any:
    rec = recorded(name)
    return parser_for(name)(query_for(name, pit), rec.body if body is None else body)


OBSERVED = sorted(n for n, s in DATASETS.items() if s.kind is DatasetKind.OBSERVED)
DERIVED = sorted(n for n, s in DATASETS.items() if s.kind is DatasetKind.DERIVED)


# every recorded response parses


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_every_recorded_dataset_response_parses(name: str) -> None:
    response = parse(name)
    assert response.dataset == name
    assert len(response.rows) == len(recorded(name).body["rows"])
    assert response.provenance.record.dataset == name
    assert response.provenance.record.pit is query_for(name).pit
    assert response.provenance.record.knowledge is DATASETS[name].knowledge
    assert response.provenance.record.derivation == DATASETS[name].derivation


def test_observed_row_keeps_timestamps_provenance_and_exact_values() -> None:
    response = parse("daily-prices")
    assert isinstance(response, ObservedResponse)
    row = response.rows[1]
    assert row.keys == {"stock_id": "2330", "source": "twse_mi_index"}
    assert row.period == date(2024, 7, 10)
    assert row.available_at == datetime(2024, 7, 11, 3, 0, tzinfo=TAIPEI)
    assert row.available_at.isoformat() == "2024-07-11T03:00:00+08:00"
    assert row.recorded_at.tzinfo is not None
    assert row.provenance.raw_sha256.startswith("369e2d05")
    assert row.values["close_price"] == Decimal("1045.000000")
    assert str(row.values["close_price"]) == "1045.000000"
    assert row.values["volume"] == 51810372
    assert "available_at" not in row.values
    assert "provenance" not in row.values


def test_response_pit_block_is_kept() -> None:
    response = parse("daily-prices")
    pit = response.provenance.response_pit
    assert pit.mode == "market"
    assert pit.information_as_of == T_C
    assert pit.knowledge_as_of == T_RECON
    assert pit.defaulted == ()


def test_stored_derived_response_records_latest_and_the_resolved_instant() -> None:
    response = parse("valuation-metrics")
    assert isinstance(response, DerivedResponse)
    assert response.derivation == DerivationRef("valuation_metrics", "v1")
    assert response.inputs == "latest"
    assert response.provenance.record.knowledge is KnowledgeQuery.LATEST
    assert response.provenance.response_pit.aliases == {"knowledge_as_of": "latest"}
    assert response.provenance.response_pit.knowledge_as_of.isoformat().startswith("2026-09-26")
    row = response.rows[0]
    assert row.values["ttm_eps"] == Decimal("33.06")
    assert row.computed_at.tzinfo is not None
    assert row.available_at == datetime(2024, 7, 10, 3, 0, tzinfo=TAIPEI)


def test_rolling_response_keeps_each_rows_release_instant() -> None:
    response = parse("technical-indicators-pit")
    assert isinstance(response, TechnicalIndicatorsResponse)
    assert response.view == "rolling"
    assert response.derivation == DerivationRef("technical_indicators_pit", "v1")
    # information_as_of was not sent, so its default is allowed and it is not an instant
    assert response.provenance.response_pit.defaulted == ("information_as_of",)
    assert response.provenance.response_pit.information_as_of == "each date's own release instant"
    row = response.rows[1]
    assert row.information_as_of == datetime(2024, 7, 11, 3, 0, tzinfo=TAIPEI)
    assert row.input_count > 0
    assert len(row.input_fingerprint) == 64


def test_adjusted_prices_keep_their_events() -> None:
    response = parse("adjusted-prices-pit")
    assert isinstance(response, AdjustedPricesResponse)
    assert [r.period for r in response.rows] == [
        date(2024, 6, 12),
        date(2024, 6, 13),
        date(2024, 6, 14),
    ]
    assert response.rows[0].values["adjusted_close_price"] == Decimal("905.5")
    (event,) = response.events
    assert event.period == date(2024, 6, 13)
    assert event.values["event_type"] == "息"
    assert event.available_at == datetime(2024, 6, 13, 0, 0, tzinfo=TAIPEI)
    assert event.provenance.fetch_id


def test_stocks_response_parses_listing_spans() -> None:
    rows = parse_stocks(recorded("stocks").body).rows
    tsmc = next(r for r in rows if r.stock_id == "2330")
    assert tsmc.market == "sii"
    assert tsmc.listed_on is None
    assert tsmc.listings[0].delisted_on is None
    delisted = next(r for r in rows if r.stock_id == "2448")
    # a delisted stock has no current market; its spans keep theirs
    assert delisted.market is None
    assert delisted.listings[-1].market == "sii"
    assert delisted.listings[-1].delisted_on == date(2021, 1, 6)


def test_trading_days_response_becomes_a_calendar() -> None:
    response = parse_trading_days(recorded("trading-days").body)
    assert [d.day for d in response.days] == [
        date(2024, 7, 22),
        date(2024, 7, 23),
        date(2024, 7, 26),
        date(2024, 7, 29),
    ]
    assert not response.calendar().is_trading_day(date(2024, 7, 24))


def test_decimals_are_never_binary_floats() -> None:
    value = decode_json('{"a": 1234.50, "b": 7, "c": "1.10"}')
    assert value == {"a": Decimal("1234.50"), "b": 7, "c": "1.10"}
    assert str(value["a"]) == "1234.50"


# missing derivation version


@pytest.mark.parametrize("name", [*DERIVED, "technical-indicators-pit", "adjusted-prices-pit"])
def test_derived_response_without_derivation_version_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    del body["derivation"]["derivation_version"]
    with pytest.raises(MissingDerivationError):
        parse(name, body)
    body["derivation"]["derivation_version"] = ""
    with pytest.raises(MissingDerivationVersionError):
        parse(name, body)


@pytest.mark.parametrize("name", [*DERIVED, "technical-indicators-pit", "adjusted-prices-pit"])
def test_derived_response_without_derivation_block_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    del body["derivation"]
    with pytest.raises(MissingDerivationError):
        parse(name, body)


# missing provenance


@pytest.mark.parametrize("name", OBSERVED)
@pytest.mark.parametrize("field", [None, "fetch_id", "raw_sha256"])
def test_observed_row_without_provenance_is_refused(name: str, field: str | None) -> None:
    body = recorded(name).fresh_body()
    if field is None:
        del body["rows"][0]["provenance"]
    else:
        del body["rows"][0]["provenance"][field]
    with pytest.raises(MissingProvenanceError):
        parse(name, body)


def test_adjustment_event_without_provenance_is_refused() -> None:
    body = recorded("adjusted-prices-pit").fresh_body()
    del body["events"][0]["provenance"]
    with pytest.raises(MissingProvenanceError):
        parse("adjusted-prices-pit", body)


def test_stock_and_listing_without_provenance_are_refused() -> None:
    body = recorded("stocks").fresh_body()
    del body["rows"][0]["provenance"]
    with pytest.raises(MissingProvenanceError):
        parse_stocks(body)
    body = recorded("stocks").fresh_body()
    del body["rows"][1]["listings"][0]["provenance"]["raw_sha256"]
    with pytest.raises(MissingProvenanceError):
        parse_stocks(body)


def test_trading_day_without_provenance_is_refused() -> None:
    body = recorded("trading-days").fresh_body()
    del body["rows"][2]["provenance"]
    with pytest.raises(MissingProvenanceError):
        parse_trading_days(body)


# a cutoff the caller sent must not come back as defaulted


def test_defaulted_cutoff_that_was_sent_is_refused() -> None:
    # Data Center answered with knowledge_as_of defaulted to "now" (it was not sent);
    # a client that did send it must not accept this answer
    rec = recorded("defaulted-knowledge")
    assert rec.body["pit"]["defaulted"] == ["knowledge_as_of"]
    query = build_query(
        DATASETS["daily-prices"], FEATURES, date(2024, 7, 10), date(2024, 7, 10), ["2330"]
    )
    with pytest.raises(PitViolationError):
        parse_observed(query, rec.body)


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_any_defaulted_sent_cutoff_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    body["pit"]["defaulted"] = sorted(query_for(name).sent_cutoffs)
    with pytest.raises(PitViolationError):
        parse(name, body)


# the answer must be for the context that was asked


@pytest.mark.parametrize("name", [n for n in sorted(DATASETS) if n != "technical-indicators-pit"])
def test_answer_for_another_information_cutoff_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    body["pit"]["information_as_of"] = "2024-07-12T04:00:00+08:00"
    with pytest.raises(PitViolationError):
        parse(name, body)


@pytest.mark.parametrize("name", [*OBSERVED, "technical-indicators-pit", "adjusted-prices-pit"])
def test_answer_for_another_knowledge_cutoff_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    body["pit"]["knowledge_as_of"] = "2026-09-27T12:00:00+08:00"
    with pytest.raises(PitViolationError):
        parse(name, body)


@pytest.mark.parametrize("name", DERIVED)
def test_stored_derived_answer_must_confirm_latest(name: str) -> None:
    body = recorded(name).fresh_body()
    body["pit"]["aliases"] = {}
    with pytest.raises(PitViolationError):
        parse(name, body)


# rows the PIT context should not have seen


@pytest.mark.parametrize("name", [*OBSERVED, *DERIVED])
def test_row_public_after_information_cutoff_is_refused(name: str) -> None:
    pit = LABELS if name == "indices" else FEATURES
    cutoff = LABEL_AT if name == "indices" else T_C
    at_cutoff = recorded(name).fresh_body()
    at_cutoff["rows"][0]["available_at"] = cutoff.isoformat()
    parse(name, at_cutoff, pit)
    after = recorded(name).fresh_body()
    after["rows"][0]["available_at"] = cutoff.replace(second=1).isoformat()
    with pytest.raises(PitViolationError):
        parse(name, after, pit)


@pytest.mark.parametrize("name", OBSERVED)
def test_row_recorded_after_knowledge_cutoff_is_refused(name: str) -> None:
    body = recorded(name).fresh_body()
    body["rows"][0]["recorded_at"] = "2026-09-26T12:00:01+08:00"
    with pytest.raises(PitViolationError):
        parse(name, body)


def test_rolling_row_computed_after_information_cutoff_is_refused() -> None:
    body = recorded("technical-indicators-pit").fresh_body()
    body["rows"][1]["information_as_of"] = "2024-07-11T04:00:01+08:00"
    with pytest.raises(PitViolationError):
        parse("technical-indicators-pit", body)


def test_adjustment_event_public_after_cutoff_is_refused() -> None:
    body = recorded("adjusted-prices-pit").fresh_body()
    body["events"][0]["available_at"] = "2024-07-11T03:00:01+08:00"
    with pytest.raises(PitViolationError):
        parse("adjusted-prices-pit", body)


# malformed answers


@pytest.mark.parametrize(
    "breakage",
    [
        lambda b: b.update(dataset="daily-prices-2"),
        lambda b: b.pop("rows"),
        lambda b: b.pop("pit"),
        lambda b: b["rows"][0].update(available_at="2024-07-10T03:00:00"),
        lambda b: b["rows"][0].pop("available_at"),
        lambda b: b["rows"][0].pop("recorded_at"),
        lambda b: b["rows"][0].pop("trade_date"),
        lambda b: b["rows"][0].pop("source"),
        lambda b: b["rows"][0].update(close_price={"nested": 1}),
        lambda b: b["rows"][0].update(close_price=1040.0),
    ],
)
def test_malformed_observed_answer_is_refused(breakage: Callable[[Any], object]) -> None:
    body = recorded("daily-prices").fresh_body()
    breakage(body)
    with pytest.raises(ResponseSchemaError):
        parse("daily-prices", body)


def test_answer_parsed_with_the_wrong_parser_is_refused() -> None:
    with pytest.raises(ResponseSchemaError):
        parse_observed(query_for("valuation-metrics"), recorded("valuation-metrics").body)
    with pytest.raises(ResponseSchemaError):
        parse_derived(query_for("daily-prices"), recorded("daily-prices").body)


# HTTP errors


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("error-400-naive-cutoff", BadRequestError),
        ("error-400-explicit-knowledge-on-stored-derived", BadRequestError),
        ("error-401-no-key", UnauthorizedError),
        ("error-404-unknown-dataset", NotFoundError),
    ],
)
def test_http_errors_become_typed_errors(name: str, error: type[Exception]) -> None:
    rec = recorded(name)
    exc = error_from_response(rec.status, rec.body)
    assert type(exc) is error
    assert isinstance(exc, DataCenterRequestError)
    assert exc.status == rec.status
    assert exc.detail == rec.body["detail"]


def test_unexpected_error_status_keeps_its_body() -> None:
    exc = error_from_response(503, "upstream down")
    assert type(exc) is DataCenterRequestError
    assert exc.status == 503
    assert exc.detail == "upstream down"
