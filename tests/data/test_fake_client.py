"""The PIT-enforcing fake Data Center client (ROADMAP step-5-b).

Every answer goes through the step-5-a parsers, so the fake is held to the same
response contract as the real API. Expected values come from the time-and-cohort
contract and from recorded Data Center answers, not from the fake itself.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from stock_model_selection.data.client import DataCenterClient
from stock_model_selection.data.errors import (
    MissingProvenanceError,
    PitViolationError,
    RequestLimitError,
)
from stock_model_selection.data.fake_client import FakeDataCenter, Faults
from stock_model_selection.data.fake_store import FakeStore
from stock_model_selection.domain.calendar import TradingCalendar
from stock_model_selection.domain.cohort import build_cohort
from stock_model_selection.domain.errors import AuditContextError
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.provenance import DerivationRef, KnowledgeQuery
from stock_model_selection.domain.time import TAIPEI
from tests.domain.conftest import FIXTURES, load_trading_days


def taipei(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=TAIPEI)


CALENDAR = TradingCalendar(load_trading_days(FIXTURES / "trading_days.txt"))
COHORT = build_cohort("2024-07", CALENDAR)  # T_C = 2024-07-11 04:00
T_C = COHORT.information_cutoff
BACKFILL = taipei(2026, 9, 16, 12, 32)  # when Data Center recorded its history
T_RECON = taipei(2026, 9, 26, 12)
RECON = COHORT.reconstruction_context(T_RECON)


def client(store: FakeStore, faults: Faults | None = None) -> FakeDataCenter:
    return FakeDataCenter(store, faults=faults, now=T_RECON)


def prices(store: FakeStore, days: list[date], recorded_at: datetime | None = BACKFILL) -> None:
    for i, day in enumerate(days):
        close = Decimal(1000 + i)
        store.add_daily_price(
            "2330",
            day,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            recorded_at=recorded_at,
        )


def test_fake_is_a_data_center_client() -> None:
    fake: DataCenterClient = client(FakeStore())
    assert isinstance(fake, FakeDataCenter)
    protocol = {n for n in vars(DataCenterClient) if not n.startswith("_")}
    assert protocol <= set(dir(FakeDataCenter))


# rows public after the information cutoff are hidden


def test_daily_price_is_public_from_the_next_day_0300() -> None:
    store = FakeStore()
    prices(store, [date(2024, 7, 9), date(2024, 7, 10), date(2024, 7, 11)])
    rows = client(store).daily_prices(date(2024, 7, 1), date(2024, 7, 31), ["2330"], pit=RECON).rows
    assert [r.period for r in rows] == [date(2024, 7, 9), date(2024, 7, 10)]
    assert rows[-1].available_at == taipei(2024, 7, 11, 3)


def test_row_public_exactly_at_the_cutoff_is_visible() -> None:
    store = FakeStore()
    prices(store, [date(2024, 7, 10)])
    at = PitContext.reconstruction(
        information_as_of=taipei(2024, 7, 11, 3), knowledge_as_of=T_RECON
    )
    before = PitContext.reconstruction(
        information_as_of=taipei(2024, 7, 11, 2, 59, 59), knowledge_as_of=T_RECON
    )
    fake = client(store)
    assert len(fake.daily_prices(date(2024, 7, 10), date(2024, 7, 10), ["2330"], pit=at).rows) == 1
    assert fake.daily_prices(date(2024, 7, 10), date(2024, 7, 10), ["2330"], pit=before).rows == ()


# rows recorded after the knowledge cutoff are hidden (time-and-cohort §5)


def test_backfilled_history_is_invisible_to_an_earlier_knowledge_cutoff() -> None:
    # 2330's 2024-07 prices were recorded 2026-09-16: knowledge_as_of 2026-09-01 sees none
    store = FakeStore()
    prices(store, [date(2024, 7, 9), date(2024, 7, 10)])
    early = COHORT.reconstruction_context(taipei(2026, 9, 1))
    fake = client(store)
    assert fake.daily_prices(date(2024, 7, 1), date(2024, 7, 31), ["2330"], pit=early).rows == ()
    assert (
        len(fake.daily_prices(date(2024, 7, 1), date(2024, 7, 31), ["2330"], pit=RECON).rows) == 2
    )


def test_production_sees_rows_recorded_when_they_became_public() -> None:
    store = FakeStore()
    prices(store, [date(2024, 7, 10)], recorded_at=None)  # recorded on release
    run = COHORT.production_context(taipei(2024, 7, 11, 4, 30))
    rows = client(store).daily_prices(date(2024, 7, 10), date(2024, 7, 10), ["2330"], pit=run).rows
    assert [r.recorded_at for r in rows] == [taipei(2024, 7, 11, 3)]


def test_correction_is_seen_only_once_recorded_and_public() -> None:
    store = FakeStore()
    store.add_monthly_revenue("2330", "2024-06", Decimal(100), published_on=date(2024, 7, 10))
    corrected_at = taipei(2024, 7, 20, 9)
    store.add_monthly_revenue(
        "2330",
        "2024-06",
        Decimal(101),
        published_on=date(2024, 7, 10),
        available_at=corrected_at,
        recorded_at=corrected_at,
    )
    fake = client(store)

    def revenue(pit: PitContext) -> object:
        (row,) = fake.monthly_revenues(date(2024, 6, 1), date(2024, 6, 30), ["2330"], pit=pit).rows
        return row.values["revenue"]

    assert revenue(COHORT.production_context(taipei(2024, 7, 11, 5))) == Decimal(100)
    later = PitContext.production(
        information_as_of=taipei(2024, 7, 21), knowledge_as_of=taipei(2024, 7, 21)
    )
    assert revenue(later) == Decimal(101)
    # a later knowledge cutoff cannot make the correction public earlier
    assert revenue(COHORT.reconstruction_context(T_RECON)) == Decimal(100)


# step-1's revenue delay (time-and-cohort §3, §8, §10)


def test_revenue_published_after_the_cutoff_keeps_the_stock_out() -> None:
    store = FakeStore()
    # 2330 published its 2024-06 revenue on the deadline, 2024-07-10: public 23:59:59
    store.add_monthly_revenue(
        "2330", "2024-06", Decimal(207_868_693), published_on=date(2024, 7, 10)
    )
    # published on the playbook date itself: public at 23:59:59, after T_C 04:00
    store.add_monthly_revenue("1101", "2024-06", Decimal(9_000_000), published_on=date(2024, 7, 11))
    rows = (
        client(store)
        .monthly_revenues(date(2024, 6, 1), date(2024, 6, 30), ["2330", "1101"], pit=RECON)
        .rows
    )
    assert [r.keys["stock_id"] for r in rows] == ["2330"]
    assert rows[0].available_at == taipei(2024, 7, 10, 23, 59, 59)
    assert COHORT.revenue_month.month == rows[0].period.month


# stored derived datasets: latest knowledge, row-level PIT


def test_stored_derived_rows_use_latest_computation_and_row_availability() -> None:
    store = FakeStore()
    for day in (date(2024, 7, 10), date(2024, 7, 11)):
        store.add_derived("valuation-metrics", "2330", day, {"ttm_eps": Decimal("33.06")})
    store.add_derived(
        "valuation-metrics",
        "2330",
        date(2024, 7, 10),
        {"ttm_eps": Decimal("33.10")},
        computed_at=taipei(2026, 9, 25, 11),
    )
    response = client(store).valuation_metrics(
        date(2024, 7, 1), date(2024, 7, 31), ["2330"], pit=RECON
    )
    assert [(r.period, r.values["ttm_eps"]) for r in response.rows] == [
        (date(2024, 7, 10), Decimal("33.10"))
    ]
    assert response.provenance.record.knowledge is KnowledgeQuery.LATEST
    assert response.derivation == DerivationRef("valuation_metrics", "v1")


# technical-indicators-pit, view=rolling


def test_rolling_rows_carry_their_release_and_stop_at_the_cutoff() -> None:
    store = FakeStore()
    for day in (date(2024, 7, 9), date(2024, 7, 10), date(2024, 7, 11)):
        store.add_rolling_indicators("2330", day, {"ma5": Decimal("1012.8")}, recorded_at=BACKFILL)
    fake = client(store)
    response = fake.technical_indicators_pit("2330", date(2024, 7, 1), date(2024, 7, 10), pit=RECON)
    assert [r.information_as_of for r in response.rows] == [
        taipei(2024, 7, 10, 3),
        taipei(2024, 7, 11, 3),
    ]
    # like Data Center, rolling ignores information_as_of; asking past P_C - 1 is caught
    with pytest.raises(PitViolationError):
        fake.technical_indicators_pit("2330", date(2024, 7, 1), date(2024, 7, 11), pit=RECON)
    early = COHORT.reconstruction_context(taipei(2026, 9, 1))
    assert (
        fake.technical_indicators_pit("2330", date(2024, 7, 1), date(2024, 7, 10), pit=early).rows
        == ()
    )


# adjusted-prices-pit: factors change as events become visible (measured 2026-09-26)

JUNE = [date(2024, 6, 11), date(2024, 6, 12), date(2024, 6, 13)]
CLOSE = {JUNE[0]: Decimal("883.00"), JUNE[1]: Decimal("909.00"), JUNE[2]: Decimal("919.00")}


def june_store() -> FakeStore:
    store = FakeStore()
    for day in JUNE:
        c = CLOSE[day]
        store.add_daily_price(
            "2330", day, open=c, high=c, low=c, close=c, volume=1, recorded_at=BACKFILL
        )
    store.add_corporate_action(
        "2330",
        date(2024, 6, 13),
        close_before=Decimal("909.00"),
        reference_price=Decimal("905.50"),
        recorded_at=BACKFILL,
    )
    return store


def adjusted(store: FakeStore, info: datetime) -> dict[date, tuple[object, object]]:
    pit = PitContext.reconstruction(information_as_of=info, knowledge_as_of=T_RECON)
    response = client(store).adjusted_prices_pit(
        "2330", date(2024, 6, 10), date(2024, 6, 14), pit=pit
    )
    return {
        r.period: (r.values["adjustment_factor"], r.values["adjusted_close_price"])
        for r in response.rows
    }


def test_event_does_not_adjust_until_a_price_on_its_ex_date_is_visible() -> None:
    # Data Center at 2024-06-13 03:00: the event is public since 00:00, yet nothing is adjusted
    got = adjusted(june_store(), taipei(2024, 6, 13, 3))
    assert got == {
        JUNE[0]: (Decimal(1), Decimal("883.00")),
        JUNE[1]: (Decimal(1), Decimal("909.00")),
    }


def test_event_adjusts_earlier_prices_once_its_ex_date_price_is_visible() -> None:
    # Data Center at 2024-06-14 03:00: factor 0.9961496149614961, 06-12 adjusted close 905.5
    got = adjusted(june_store(), taipei(2024, 6, 14, 3))
    factor = Decimal("905.50") / Decimal("909.00")
    assert got[JUNE[2]] == (Decimal(1), Decimal("919.00"))
    for day in JUNE[:2]:
        f, close = got[day]
        assert isinstance(f, Decimal) and isinstance(close, Decimal)
        assert abs(f - Decimal("0.9961496149614961")) < Decimal("1e-15")
        assert f == factor
    assert got[JUNE[1]][1] == Decimal("905.5")
    assert abs(got[JUNE[0]][1] - Decimal("879.6001100110011")) < Decimal("1e-12")  # type: ignore[operator]


def test_adjusted_answer_lists_the_events_it_applied() -> None:
    pit = PitContext.reconstruction(
        information_as_of=taipei(2024, 6, 14, 3), knowledge_as_of=T_RECON
    )
    response = client(june_store()).adjusted_prices_pit(
        "2330", date(2024, 6, 10), date(2024, 6, 14), pit=pit
    )
    assert [e.period for e in response.events] == [date(2024, 6, 13)]
    assert response.events[0].available_at == taipei(2024, 6, 13)
    only_after = client(june_store()).adjusted_prices_pit(
        "2330", date(2024, 6, 13), date(2024, 6, 13), pit=pit
    )
    assert only_after.events == ()


def test_event_missing_its_reference_price_nulls_every_earlier_factor() -> None:
    store = june_store()
    store.add_daily_price(
        "2330",
        date(2024, 6, 14),
        open=None,
        high=None,
        low=None,
        close=None,
        volume=0,
        recorded_at=BACKFILL,
    )
    store.add_corporate_action(
        "2330",
        date(2024, 6, 14),
        close_before=Decimal("919.00"),
        reference_price=None,
        recorded_at=BACKFILL,
    )
    got = adjusted(store, taipei(2024, 6, 15, 3))
    assert got[JUNE[0]] == (None, None)
    assert got[JUNE[2]] == (None, None)
    assert got[date(2024, 6, 14)] == (Decimal(1), None)  # no trade that day


# reference data


def test_stocks_follow_listing_spans() -> None:
    store = FakeStore()
    store.add_stock(
        "2448", "晶電", industry=None, listings=[("sii", date(2001, 5, 25), date(2021, 1, 6))]
    )
    store.add_stock(
        "6770", "力積電", industry="半導體業", listings=[("sii", date(2021, 12, 6), None)]
    )
    store.add_stock(
        "3443",
        "創意",
        industry="半導體業",
        listings=[
            ("otc", date(2006, 11, 14), date(2014, 11, 13)),
            ("sii", date(2014, 11, 13), None),
        ],
    )
    fake = client(store)

    def on(day: date) -> list[str]:
        return sorted(s.stock_id for s in fake.stocks(on=day).rows)

    assert on(date(2021, 1, 5)) == ["2448", "3443"]  # delisted later: still eligible
    assert on(date(2021, 1, 6)) == ["3443"]  # delisted from its delisting day
    assert on(date(2022, 1, 3)) == ["3443", "6770"]  # listed later: absent before
    assert {s.stock_id: s.market for s in fake.stocks().rows} == {
        "2448": None,
        "6770": "sii",
        "3443": "sii",
    }
    spans = next(s for s in fake.stocks(stock_ids=["3443"]).rows).listings
    assert [(x.market, x.delisted_on) for x in spans] == [
        ("otc", date(2014, 11, 13)),
        ("sii", None),
    ]


def test_trading_days_come_from_the_store() -> None:
    store = FakeStore()
    store.add_trading_days([date(2024, 7, 22), date(2024, 7, 23), date(2024, 7, 26)])
    days = client(store).trading_days(date(2024, 7, 23), date(2024, 7, 31)).days
    assert [d.day for d in days] == [date(2024, 7, 23), date(2024, 7, 26)]


# the request rules of step-5-a hold for the fake too


def test_fake_refuses_what_data_center_refuses() -> None:
    fake = client(FakeStore())
    with pytest.raises(RequestLimitError):
        fake.daily_prices(date(2024, 7, 1), date(2024, 8, 1), pit=RECON)
    with pytest.raises(AuditContextError):
        fake.daily_prices(
            date(2024, 7, 10),
            date(2024, 7, 10),
            ["2330"],
            pit=PitContext.audit(system_as_of=T_RECON),
        )


# fault injection


def test_wrong_derivation_version_reaches_the_caller() -> None:
    store = FakeStore()
    store.add_derived("valuation-metrics", "2330", date(2024, 7, 10), {"ttm_eps": Decimal("33.06")})
    fake = client(store, Faults(derivation_versions={"valuation-metrics": "v2"}))
    response = fake.valuation_metrics(date(2024, 7, 10), date(2024, 7, 10), ["2330"], pit=RECON)
    assert response.derivation == DerivationRef("valuation_metrics", "v2")
    assert response.provenance.record.derivation == DerivationRef("valuation_metrics", "v2")


@pytest.mark.parametrize("dataset", ["daily-prices", "adjusted-prices-pit"])
def test_missing_provenance_is_refused(dataset: str) -> None:
    fake = client(june_store(), Faults(missing_provenance=frozenset({dataset})))
    pit = PitContext.reconstruction(
        information_as_of=taipei(2024, 6, 14, 3), knowledge_as_of=T_RECON
    )
    with pytest.raises(MissingProvenanceError):
        if dataset == "daily-prices":
            fake.daily_prices(date(2024, 6, 10), date(2024, 6, 14), ["2330"], pit=pit)
        else:
            fake.adjusted_prices_pit("2330", date(2024, 6, 10), date(2024, 6, 14), pit=pit)


def test_fault_free_answers_are_untouched_by_faults_for_other_datasets() -> None:
    fake = client(june_store(), Faults(missing_provenance=frozenset({"monthly-revenues"})))
    pit = PitContext.reconstruction(
        information_as_of=taipei(2024, 6, 14, 3), knowledge_as_of=T_RECON
    )
    assert len(fake.daily_prices(date(2024, 6, 10), date(2024, 6, 14), ["2330"], pit=pit).rows) == 3


def test_event_published_late_adjusts_only_once_public() -> None:
    store = FakeStore()
    for day in JUNE:
        c = CLOSE[day]
        store.add_daily_price(
            "2330", day, open=c, high=c, low=c, close=c, volume=1, recorded_at=BACKFILL
        )
    late = taipei(2024, 6, 20, 9)
    store.add_corporate_action(
        "2330",
        date(2024, 6, 13),
        close_before=Decimal("909.00"),
        reference_price=Decimal("905.50"),
        available_at=late,
        recorded_at=late,
    )
    assert adjusted(store, taipei(2024, 6, 14, 3))[JUNE[1]][0] == Decimal(1)
    assert adjusted(store, taipei(2024, 6, 21))[JUNE[1]][0] != Decimal(1)


def test_event_recorded_after_the_knowledge_cutoff_does_not_adjust() -> None:
    store = FakeStore()
    for day in JUNE:
        c = CLOSE[day]
        # recorded on release, as in production
        store.add_daily_price("2330", day, open=c, high=c, low=c, close=c, volume=1)
    store.add_corporate_action(
        "2330",
        date(2024, 6, 13),
        close_before=Decimal("909.00"),
        reference_price=Decimal("905.50"),
        recorded_at=taipei(2024, 6, 20, 9),
    )

    def factor_0612(knowledge: datetime) -> object:
        pit = PitContext.production(
            information_as_of=taipei(2024, 6, 14, 3), knowledge_as_of=knowledge
        )
        rows = client(store).adjusted_prices_pit("2330", JUNE[0], JUNE[2], pit=pit).rows
        return {r.period: r.values["adjustment_factor"] for r in rows}[JUNE[1]]

    assert factor_0612(taipei(2024, 6, 19)) == Decimal(1)
    assert factor_0612(taipei(2024, 6, 21)) != Decimal(1)
