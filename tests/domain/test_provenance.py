"""DerivationRef and provenance records: docs/contracts/data-dependencies.md."""

from datetime import date, datetime
from typing import Any, cast

import pytest

from stock_model_selection.domain.errors import (
    InvalidCutoffError,
    MissingDerivationVersionError,
)
from stock_model_selection.domain.pit import PitContext
from stock_model_selection.domain.provenance import (
    DerivationRef,
    KnowledgeQuery,
    ProvenanceRecord,
)
from stock_model_selection.domain.time import TAIPEI

T_C = datetime(2024, 7, 11, 4, 0, tzinfo=TAIPEI)
LATER = datetime(2026, 9, 26, 12, 0, tzinfo=TAIPEI)


def test_derivation_ref_keeps_code_and_version() -> None:
    ref = DerivationRef(dataset_code="valuation_metrics", derivation_version="v1")
    assert (ref.dataset_code, ref.derivation_version) == ("valuation_metrics", "v1")


@pytest.mark.parametrize("version", [None, "", "   "])
def test_derivation_ref_without_version_is_rejected(version: object) -> None:
    with pytest.raises(MissingDerivationVersionError):
        DerivationRef(dataset_code="valuation_metrics", derivation_version=cast(Any, version))


def test_derivation_ref_without_version_argument_is_rejected() -> None:
    with pytest.raises(TypeError):
        DerivationRef(**cast(Any, {"dataset_code": "valuation_metrics"}))


@pytest.mark.parametrize("code", [None, "", "  "])
def test_derivation_ref_without_dataset_code_is_rejected(code: object) -> None:
    with pytest.raises(ValueError):
        DerivationRef(dataset_code=cast(Any, code), derivation_version="v1")


def test_derivation_version_is_compared_exactly() -> None:
    assert DerivationRef("valuation_metrics", "v1") != DerivationRef("valuation_metrics", "v2")
    assert DerivationRef("valuation_metrics", "v1") == DerivationRef("valuation_metrics", "v1")


def test_provenance_record_for_derived_dataset() -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    ref = DerivationRef("valuation_metrics", "v1")
    record = ProvenanceRecord(
        dataset="valuation-metrics", pit=pit, derivation=ref, knowledge=KnowledgeQuery.LATEST
    )
    assert record.pit is pit
    assert record.derivation == ref
    assert record.knowledge is KnowledgeQuery.LATEST


def test_provenance_record_for_observed_dataset_has_no_derivation() -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    record = ProvenanceRecord(
        dataset="daily-prices", pit=pit, derivation=None, knowledge=KnowledgeQuery.EXPLICIT
    )
    assert record.derivation is None


@pytest.mark.parametrize("pit", [None, date(2024, 7, 11), T_C])
def test_provenance_record_requires_a_pit_context(pit: object) -> None:
    with pytest.raises(InvalidCutoffError):
        ProvenanceRecord(
            dataset="daily-prices",
            pit=cast(Any, pit),
            derivation=None,
            knowledge=KnowledgeQuery.EXPLICIT,
        )


def test_provenance_record_requires_a_dataset_name() -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(ValueError):
        ProvenanceRecord(dataset="", pit=pit, derivation=None, knowledge=KnowledgeQuery.EXPLICIT)


# stored derived datasets only accept knowledge_as_of=latest (time-and-cohort §5);
# the PitContext stays explicit, the record says what was actually sent


def test_provenance_record_must_say_how_knowledge_was_queried() -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(TypeError):
        ProvenanceRecord(**cast(Any, {"dataset": "daily-prices", "pit": pit, "derivation": None}))


def test_latest_knowledge_is_only_for_derived_datasets() -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(ValueError):
        ProvenanceRecord(
            dataset="daily-prices", pit=pit, derivation=None, knowledge=KnowledgeQuery.LATEST
        )


def test_latest_knowledge_needs_a_market_context() -> None:
    audit = PitContext.audit(system_as_of=LATER)
    with pytest.raises(ValueError):
        ProvenanceRecord(
            dataset="valuation-metrics",
            pit=audit,
            derivation=DerivationRef("valuation_metrics", "v1"),
            knowledge=KnowledgeQuery.LATEST,
        )


@pytest.mark.parametrize("knowledge", ["latest", None])
def test_knowledge_query_must_be_the_enum(knowledge: object) -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(ValueError):
        ProvenanceRecord(
            dataset="daily-prices", pit=pit, derivation=None, knowledge=cast(Any, knowledge)
        )


@pytest.mark.parametrize("derivation", ["v1", ("valuation_metrics", ""), {"version": "v1"}])
def test_provenance_derivation_must_be_a_derivation_ref(derivation: object) -> None:
    pit = PitContext.reconstruction(information_as_of=T_C, knowledge_as_of=LATER)
    with pytest.raises(MissingDerivationVersionError):
        ProvenanceRecord(
            dataset="valuation-metrics",
            pit=pit,
            derivation=cast(Any, derivation),
            knowledge=KnowledgeQuery.EXPLICIT,
        )
