"""Derivation references and provenance records (docs/contracts/data-dependencies.md)."""

from dataclasses import dataclass
from enum import StrEnum

from stock_model_selection.domain.errors import (
    InvalidCutoffError,
    MissingDerivationVersionError,
)
from stock_model_selection.domain.pit import PitContext, PitMode


def _is_blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


@dataclass(frozen=True)
class DerivationRef:
    """A derived dataset's `derivation` block, e.g. ("valuation_metrics", "v1")."""

    dataset_code: str
    derivation_version: str

    def __post_init__(self) -> None:
        if _is_blank(self.dataset_code):
            raise ValueError(f"dataset_code must be a non-empty string: {self.dataset_code!r}")
        if _is_blank(self.derivation_version):
            raise MissingDerivationVersionError(
                f"{self.dataset_code} has no derivation_version: {self.derivation_version!r}"
            )


class KnowledgeQuery(StrEnum):
    """The knowledge_as_of actually sent to Data Center."""

    # the PitContext's knowledge_as_of
    EXPLICIT = "explicit"
    # `latest`: stored derived datasets refuse an explicit one (time-and-cohort §5)
    LATEST = "latest"


@dataclass(frozen=True, kw_only=True)
class ProvenanceRecord:
    """Which dataset was read, under which PIT context, at which derivation version.

    `pit` is the cohort's context and always explicit; `knowledge` says whether its
    knowledge_as_of was sent or replaced by `latest`. `derivation` is None for observed
    datasets. Response metadata (the returned `pit` block, fetch ids) is added with the
    response schemas in step-5-a.
    """

    dataset: str
    pit: PitContext
    derivation: DerivationRef | None
    knowledge: KnowledgeQuery

    def __post_init__(self) -> None:
        if _is_blank(self.dataset):
            raise ValueError(f"dataset must be a non-empty string: {self.dataset!r}")
        if not isinstance(self.pit, PitContext):
            raise InvalidCutoffError(f"provenance needs a PitContext, got {self.pit!r}")
        if self.derivation is not None and not isinstance(self.derivation, DerivationRef):
            raise MissingDerivationVersionError(
                f"{self.dataset} derivation must be a DerivationRef, got {self.derivation!r}"
            )
        if not isinstance(self.knowledge, KnowledgeQuery):
            raise ValueError(f"knowledge must be a KnowledgeQuery, got {self.knowledge!r}")
        if self.knowledge is KnowledgeQuery.LATEST:
            if self.derivation is None:
                raise ValueError(f"{self.dataset}: only derived datasets are read with latest")
            if self.pit.mode is PitMode.AUDIT:
                raise ValueError(f"{self.dataset}: latest knowledge needs a market PIT context")
