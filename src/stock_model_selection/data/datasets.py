"""The Data Center datasets v1 may use: docs/contracts/data-dependencies.md §3 to §5.

To use another dataset, add it to the contract first; tests/data/test_datasets.py reads
the contract and fails when this registry differs from it.
"""

from dataclasses import dataclass
from enum import StrEnum

from stock_model_selection.domain.provenance import DerivationRef, KnowledgeQuery


class DatasetKind(StrEnum):
    OBSERVED = "observed"
    # stored, computed from the latest inputs; only knowledge_as_of=latest is accepted
    DERIVED = "derived"
    # computed per request under the caller's PIT context
    DERIVED_ON_DEMAND = "derived_on_demand"


class StockScope(StrEnum):
    # up to 200 stock_id per request; none at all limits the span to 31 days
    MANY = "many"
    # exactly one stock_id per request
    ONE = "one"
    # no stock_id (market-level rows); the span is limited to 31 days
    NONE = "none"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    kind: DatasetKind
    keys: tuple[str, ...]
    period: str
    stock_scope: StockScope = StockScope.MANY
    derivation: DerivationRef | None = None
    sends_information_as_of: bool = True
    extra_params: tuple[tuple[str, str], ...] = ()

    @property
    def knowledge(self) -> KnowledgeQuery:
        """What is sent as knowledge_as_of (time-and-cohort §5)."""
        if self.kind is DatasetKind.DERIVED:
            return KnowledgeQuery.LATEST
        return KnowledgeQuery.EXPLICIT


STOCK_DAY = ("stock_id", "source", "trade_date")
STOCK_SNAPSHOT = ("stock_id", "source", "snapshot_date")


def _observed(name: str, keys: tuple[str, ...] = STOCK_DAY) -> DatasetSpec:
    return DatasetSpec(name, DatasetKind.OBSERVED, keys, keys[-1])


def _derived(name: str, code: str, keys: tuple[str, ...] = STOCK_DAY) -> DatasetSpec:
    return DatasetSpec(
        name, DatasetKind.DERIVED, keys, keys[-1], derivation=DerivationRef(code, "v1")
    )


_SPECS = (
    _observed("monthly-revenues", ("stock_id", "source", "revenue_month")),
    _observed("daily-prices"),
    _observed("official-valuations"),
    _observed("institutional-flows"),
    _observed("foreign-holdings"),
    _observed("margin-trading"),
    _observed("securities-lending"),
    _observed("shareholding-distributions", STOCK_SNAPSHOT),
    DatasetSpec(
        "indices",
        DatasetKind.OBSERVED,
        ("source", "index_name", "trade_date"),
        "trade_date",
        stock_scope=StockScope.NONE,
    ),
    _derived("valuation-metrics", "valuation_metrics"),
    _derived("institutional-streaks", "institutional_streaks"),
    _derived("institutional-cumulative-flows", "institutional_cumulative_flow"),
    _derived("shareholding-concentrations", "shareholding_concentration", STOCK_SNAPSHOT),
    _derived("margin-metrics", "margin_metrics"),
    _derived("short-interest-metrics", "short_interest_metrics"),
    # view=rolling computes each date at its own release instant and refuses
    # information_as_of; rows carry their own information_as_of instead
    DatasetSpec(
        "technical-indicators-pit",
        DatasetKind.DERIVED_ON_DEMAND,
        STOCK_DAY,
        "trade_date",
        stock_scope=StockScope.ONE,
        derivation=DerivationRef("technical_indicators_pit", "v1"),
        sends_information_as_of=False,
        extra_params=(("view", "rolling"),),
    ),
    DatasetSpec(
        "adjusted-prices-pit",
        DatasetKind.DERIVED_ON_DEMAND,
        STOCK_DAY,
        "trade_date",
        stock_scope=StockScope.ONE,
        derivation=DerivationRef("adjusted_prices_pit", "v1"),
    ),
)

DATASETS: dict[str, DatasetSpec] = {spec.name: spec for spec in _SPECS}
