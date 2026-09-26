"""One Data Center request: a PitContext mapped to query parameters, within the API limits.

Splitting a large request into several that fit the limits is the adapter's job
(step-6); build_query only refuses a request that does not fit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from stock_model_selection.data.datasets import DatasetSpec, StockScope
from stock_model_selection.data.errors import RequestLimitError
from stock_model_selection.domain.pit import PitContext, require_market_pit
from stock_model_selection.domain.provenance import KnowledgeQuery

MAX_STOCK_IDS = 200
# a request without stock_id spans at most 31 days, both ends included
MAX_DAYS_WITHOUT_STOCK_ID = 31
CUTOFFS = ("information_as_of", "knowledge_as_of")


@dataclass(frozen=True)
class DatasetQuery:
    spec: DatasetSpec
    pit: PitContext
    params: tuple[tuple[str, str], ...]

    @property
    def sent_cutoffs(self) -> frozenset[str]:
        return frozenset(key for key, _ in self.params if key in CUTOFFS)

    def sent(self, key: str) -> str | None:
        return next((value for k, value in self.params if k == key), None)


def build_query(
    spec: DatasetSpec,
    pit: PitContext,
    start: date,
    end: date,
    stock_ids: Sequence[str] | None = None,
    *,
    sources: Sequence[str] | None = None,
    index_name: str | None = None,
) -> DatasetQuery:
    pit = require_market_pit(pit)
    assert pit.information_as_of is not None and pit.knowledge_as_of is not None
    if isinstance(stock_ids, str):
        # a str is a Sequence[str]; "2317" would become 2, 3, 1, 7
        raise RequestLimitError(f"{spec.name}: stock_ids must be a list, got {stock_ids!r}")
    ids = list(stock_ids or ())
    if end < start:
        raise RequestLimitError(f"{spec.name}: end {end} is before start {start}")
    if len(set(ids)) != len(ids):
        raise RequestLimitError(f"{spec.name}: repeated stock_id in {ids}")
    if spec.stock_scope is StockScope.ONE and len(ids) != 1:
        raise RequestLimitError(f"{spec.name} takes exactly one stock_id, got {ids}")
    if spec.stock_scope is StockScope.NONE and ids:
        raise RequestLimitError(f"{spec.name} takes no stock_id")
    if len(ids) > MAX_STOCK_IDS:
        raise RequestLimitError(f"{spec.name}: {len(ids)} stock_id, at most {MAX_STOCK_IDS}")
    if not ids and (end - start) >= timedelta(days=MAX_DAYS_WITHOUT_STOCK_ID):
        raise RequestLimitError(
            f"{spec.name}: without stock_id a request spans at most "
            f"{MAX_DAYS_WITHOUT_STOCK_ID} days, got {start} to {end}"
        )
    if index_name is not None and spec.stock_scope is not StockScope.NONE:
        raise RequestLimitError(f"{spec.name} takes no index_name")

    params: list[tuple[str, str]] = [("start", start.isoformat()), ("end", end.isoformat())]
    params += [("stock_id", stock_id) for stock_id in ids]
    params += [("source", source) for source in sources or ()]
    if index_name is not None:
        params.append(("index_name", index_name))
    params += spec.extra_params
    if spec.sends_information_as_of:
        params.append(("information_as_of", pit.information_as_of.isoformat()))
    knowledge = (
        "latest" if spec.knowledge is KnowledgeQuery.LATEST else pit.knowledge_as_of.isoformat()
    )
    params.append(("knowledge_as_of", knowledge))
    return DatasetQuery(spec, pit, tuple(params))
