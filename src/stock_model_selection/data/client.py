"""The Data Center boundary: one method per dataset in docs/contracts/data-dependencies.md.

Every dataset method takes the PIT context as a required keyword `pit`, never a date:
feature methods get a cohort's context (Cohort.*_context), label and backtest methods a
label horizon's (LabelHorizon.*_context, information_as_of = label_available_at, D12).
`start` / `end` only select the rows' period. Implementations build each request with
data.query.build_query and check each answer with the data.schemas parsers; the fake
client is step-5-b, the HTTP adapter step-6.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from stock_model_selection.data.schemas import (
    AdjustedPricesResponse,
    DerivedResponse,
    ObservedResponse,
    StocksResponse,
    TechnicalIndicatorsResponse,
    TradingDaysResponse,
)
from stock_model_selection.domain.pit import PitContext

StockIds = Sequence[str] | None


class DataCenterClient(Protocol):
    # observed, read as of the context's information_as_of and knowledge_as_of

    def monthly_revenues(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def daily_prices(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def official_valuations(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def institutional_flows(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def foreign_holdings(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def margin_trading(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def securities_lending(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def shareholding_distributions(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> ObservedResponse: ...

    def indices(
        self, source: str, index_name: str, start: date, end: date, *, pit: PitContext
    ) -> ObservedResponse: ...

    # stored derived: sent with knowledge_as_of=latest (time-and-cohort §5)

    def valuation_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    def institutional_streaks(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    def institutional_cumulative_flows(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    def shareholding_concentrations(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    def margin_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    def short_interest_metrics(
        self, start: date, end: date, stock_ids: StockIds = None, *, pit: PitContext
    ) -> DerivedResponse: ...

    # computed on demand, one stock per request

    def technical_indicators_pit(
        self, stock_id: str, start: date, end: date, *, pit: PitContext
    ) -> TechnicalIndicatorsResponse: ...

    def adjusted_prices_pit(
        self, stock_id: str, start: date, end: date, *, pit: PitContext
    ) -> AdjustedPricesResponse: ...

    # reference data, not PIT

    def stocks(
        self,
        *,
        on: date | None = None,
        stock_ids: StockIds = None,
        market: str | None = None,
    ) -> StocksResponse: ...

    def trading_days(self, start: date, end: date) -> TradingDaysResponse: ...
