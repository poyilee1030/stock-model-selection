"""Mapping a PitContext to Data Center query parameters, and the API's request limits."""

from datetime import date, datetime
from typing import Any, cast

import pytest

from stock_model_selection.data.datasets import DATASETS
from stock_model_selection.data.errors import RequestLimitError
from stock_model_selection.data.query import build_query
from stock_model_selection.domain.errors import (
    AuditContextError,
    InvalidCutoffError,
    MissingPitContextError,
)
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.time import TAIPEI
from tests.data.conftest import recorded

T_C = datetime(2024, 7, 11, 4, 0, tzinfo=TAIPEI)
LABEL_AT = datetime(2024, 7, 11, 3, 0, tzinfo=TAIPEI)
T_RECON = datetime(2026, 9, 26, 12, 0, tzinfo=TAIPEI)
FEATURES = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=T_RECON)
LABELS = PitContext.reconstruction(information_as_of=LABEL_AT, knowledge_as_of=T_RECON)
TAIEX_TR = "報酬指數/臺灣證券交易所:發行量加權股價報酬指數"


def recorded_query(name: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(params build_query makes, params the recorded 200 response was asked with)."""
    rec = recorded(name)
    assert rec.status == 200
    got = dict(rec.params)
    start, end = date.fromisoformat(got["start"]), date.fromisoformat(got["end"])
    if name == "indices":
        query = build_query(
            DATASETS[name], LABELS, start, end, sources=["twse_mi_index"], index_name=TAIEX_TR
        )
    elif name == "adjusted-prices-pit":
        query = build_query(DATASETS[name], LABELS, start, end, stock_ids=["2330"])
    else:
        query = build_query(DATASETS[name], FEATURES, start, end, stock_ids=["2330"])
    return sorted(query.params), sorted(rec.params)


@pytest.mark.parametrize("name", sorted(DATASETS))
def test_query_matches_what_data_center_answered(name: str) -> None:
    built, asked = recorded_query(name)
    assert built == asked


def test_stored_derived_sends_latest_knowledge() -> None:
    query = build_query(
        DATASETS["valuation-metrics"], FEATURES, date(2024, 7, 10), date(2024, 7, 10), ["2330"]
    )
    assert ("knowledge_as_of", "latest") in query.params
    assert ("information_as_of", "2024-07-11T04:00:00+08:00") in query.params
    assert query.sent_cutoffs == {"information_as_of", "knowledge_as_of"}


def test_rolling_view_sends_no_information_as_of() -> None:
    query = build_query(
        DATASETS["technical-indicators-pit"],
        FEATURES,
        date(2024, 7, 1),
        date(2024, 7, 10),
        ["2330"],
    )
    assert "information_as_of" not in dict(query.params)
    assert query.sent_cutoffs == {"knowledge_as_of"}
    assert query.pit is FEATURES


def test_cutoffs_are_sent_with_their_offset() -> None:
    utc_ctx = PitContext.production(
        information_as_of=datetime.fromisoformat("2024-07-10T20:00:00+00:00"),
        knowledge_as_of=datetime.fromisoformat("2024-07-10T20:30:00+00:00"),
    )
    query = build_query(
        DATASETS["daily-prices"], utc_ctx, date(2024, 7, 10), date(2024, 7, 10), ["2330"]
    )
    params = dict(query.params)
    assert params["information_as_of"] == "2024-07-11T04:00:00+08:00"
    assert params["knowledge_as_of"] == "2024-07-11T04:30:00+08:00"


# the PIT context is mandatory and must be a market context


def test_query_without_pit_context_is_refused() -> None:
    with pytest.raises(MissingPitContextError):
        build_query(DATASETS["daily-prices"], cast(Any, None), date(2024, 7, 10), date(2024, 7, 10))


@pytest.mark.parametrize("value", [date(2024, 7, 11), T_C])
def test_query_with_a_date_instead_of_pit_context_is_refused(value: object) -> None:
    with pytest.raises(InvalidCutoffError):
        build_query(
            DATASETS["daily-prices"], cast(Any, value), date(2024, 7, 10), date(2024, 7, 10)
        )


def test_query_with_audit_context_is_refused() -> None:
    audit = PitContext.audit(system_as_of=T_RECON)
    with pytest.raises(AuditContextError):
        build_query(DATASETS["daily-prices"], audit, date(2024, 7, 10), date(2024, 7, 10))


# request limits (measured 2026-09-26)


def test_at_most_200_stock_ids() -> None:
    spec = DATASETS["daily-prices"]
    ids = [str(1000 + i) for i in range(201)]
    build_query(spec, FEATURES, date(2024, 7, 10), date(2024, 7, 10), ids[:200])
    with pytest.raises(RequestLimitError):
        build_query(spec, FEATURES, date(2024, 7, 10), date(2024, 7, 10), ids)


def test_without_stock_id_at_most_31_days() -> None:
    spec = DATASETS["monthly-revenues"]
    query = build_query(spec, FEATURES, date(2024, 7, 1), date(2024, 7, 31))
    assert "stock_id" not in dict(query.params)
    with pytest.raises(RequestLimitError):
        build_query(spec, FEATURES, date(2024, 7, 1), date(2024, 8, 1))


def test_indices_span_is_limited_like_any_query_without_stock_id() -> None:
    with pytest.raises(RequestLimitError):
        build_query(DATASETS["indices"], LABELS, date(2024, 7, 1), date(2024, 8, 1))


@pytest.mark.parametrize("name", ["technical-indicators-pit", "adjusted-prices-pit"])
def test_one_stock_datasets_need_exactly_one_stock_id(name: str) -> None:
    spec = DATASETS[name]
    with pytest.raises(RequestLimitError):
        build_query(spec, FEATURES, date(2024, 7, 1), date(2024, 7, 10), ["2330", "2317"])
    with pytest.raises(RequestLimitError):
        build_query(spec, FEATURES, date(2024, 7, 1), date(2024, 7, 10))


def test_indices_take_no_stock_id() -> None:
    with pytest.raises(RequestLimitError):
        build_query(DATASETS["indices"], LABELS, date(2024, 7, 10), date(2024, 7, 10), ["2330"])


def test_index_name_is_only_for_indices() -> None:
    with pytest.raises(RequestLimitError):
        build_query(
            DATASETS["daily-prices"],
            FEATURES,
            date(2024, 7, 10),
            date(2024, 7, 10),
            ["2330"],
            index_name=TAIEX_TR,
        )


def test_end_before_start_is_refused() -> None:
    with pytest.raises(RequestLimitError):
        build_query(DATASETS["daily-prices"], FEATURES, date(2024, 7, 10), date(2024, 7, 9))


def test_duplicate_stock_ids_are_refused() -> None:
    with pytest.raises(RequestLimitError):
        build_query(
            DATASETS["daily-prices"],
            FEATURES,
            date(2024, 7, 10),
            date(2024, 7, 10),
            ["2330", "2330"],
        )
