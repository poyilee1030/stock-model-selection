"""The DataCenterClient protocol: one method per contract dataset, PIT only via PitContext."""

import inspect
from datetime import date, datetime
from typing import get_type_hints

from stock_model_selection.data.client import DataCenterClient
from stock_model_selection.data.datasets import DATASETS
from stock_model_selection.domain.pit import PitContext

REFERENCE = {"stocks", "trading_days"}


def methods() -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(DataCenterClient, inspect.isfunction)
        if not name.startswith("_")
    }


def test_one_method_per_contract_dataset_plus_reference_data() -> None:
    expected = {name.replace("-", "_") for name in DATASETS} | REFERENCE
    assert set(methods()) == expected


def test_no_method_takes_an_entry_date_or_a_bare_cutoff() -> None:
    for name, signature in methods().items():
        hints = get_type_hints(getattr(DataCenterClient, name))
        for param in signature.parameters:
            assert "entry" not in param, (name, param)
            assert not param.endswith("_as_of"), (name, param)
            assert hints.get(param) is not datetime, (name, param)


def test_every_dataset_method_requires_a_pit_context() -> None:
    for name, signature in methods().items():
        if name in REFERENCE:
            continue
        hints = get_type_hints(getattr(DataCenterClient, name))
        assert "pit" in signature.parameters, name
        assert hints["pit"] is PitContext, name
        pit = signature.parameters["pit"]
        assert pit.default is inspect.Parameter.empty, name
        assert pit.kind is inspect.Parameter.KEYWORD_ONLY, name


def test_dates_are_only_the_query_range() -> None:
    for name, signature in methods().items():
        hints = get_type_hints(getattr(DataCenterClient, name))
        dated = {p for p in signature.parameters if hints.get(p) in (date, date | None)}
        allowed = {"on"} if name == "stocks" else {"start", "end"}
        assert dated <= allowed, (name, dated)


def test_reference_data_takes_no_pit_context() -> None:
    for name in REFERENCE:
        assert "pit" not in methods()[name].parameters
