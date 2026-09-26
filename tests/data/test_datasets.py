"""The dataset registry must match docs/contracts/data-dependencies.md, read from the doc."""

import re
from pathlib import Path

from stock_model_selection.data.datasets import DATASETS, DatasetKind, StockScope
from stock_model_selection.domain.provenance import DerivationRef, KnowledgeQuery

CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "data-dependencies.md"
ROW = re.compile(r"^\| `([a-z-]+)`")
KIND = re.compile(r"\b(derived_on_demand|observed|derived)\b")
CODE = re.compile(r"`([a-z_]+)` (v\d+)")


def contract_sections() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in CONTRACT.read_text().splitlines():
        if line.startswith("## "):
            current = line.split(".")[0].removeprefix("## ")
        sections.setdefault(current, []).append(line)
    return sections


def contract_datasets() -> dict[str, tuple[str, DerivationRef | None]]:
    """Name -> (kind, derivation) for every dataset in §3 to §5."""
    found: dict[str, tuple[str, DerivationRef | None]] = {}
    for section in ("3", "4", "5"):
        for line in contract_sections()[section]:
            row = ROW.match(line)
            if row is None:
                continue
            kind = KIND.search(line)
            assert kind is not None, line
            code = CODE.search(line)
            ref = DerivationRef(code[1], code[2]) if code else None
            found.setdefault(row[1], (kind[1], ref))
    return found


def test_contract_parser_sees_the_tables() -> None:
    names = contract_datasets()
    assert len(names) == 17
    assert names["valuation-metrics"] == ("derived", DerivationRef("valuation_metrics", "v1"))
    assert names["indices"] == ("observed", None)


def test_registry_lists_exactly_the_contract_datasets() -> None:
    assert set(DATASETS) == set(contract_datasets())


def test_registry_kind_and_derivation_match_the_contract() -> None:
    for name, (kind, ref) in contract_datasets().items():
        spec = DATASETS[name]
        assert spec.name == name
        assert spec.kind == DatasetKind(kind), name
        assert spec.derivation == ref, name


def test_datasets_the_contract_excludes_are_not_registered() -> None:
    excluded = {m[1] for line in contract_sections()["6"] if (m := ROW.match(line))}
    assert excluded == {
        "technical-indicators",
        "financial-reports",
        "corporate-actions",
        "institutional-market-flows",
    }
    assert not excluded & set(DATASETS)


def test_only_stored_derived_datasets_are_read_with_latest_knowledge() -> None:
    for spec in DATASETS.values():
        expected = (
            KnowledgeQuery.LATEST if spec.kind is DatasetKind.DERIVED else KnowledgeQuery.EXPLICIT
        )
        assert spec.knowledge is expected, spec.name


def test_request_shapes_follow_the_api() -> None:
    one = {n for n, s in DATASETS.items() if s.stock_scope is StockScope.ONE}
    none = {n for n, s in DATASETS.items() if s.stock_scope is StockScope.NONE}
    assert one == {"technical-indicators-pit", "adjusted-prices-pit"}
    assert none == {"indices"}
    rolling = DATASETS["technical-indicators-pit"]
    assert not rolling.sends_information_as_of
    assert rolling.extra_params == (("view", "rolling"),)
    assert all(s.sends_information_as_of for n, s in DATASETS.items() if s is not rolling)
