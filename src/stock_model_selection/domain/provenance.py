"""Derivation references and provenance records (docs/contracts/data-dependencies.md)."""

from dataclasses import dataclass

from stock_model_selection.domain.errors import (
    InvalidCutoffError,
    MissingDerivationVersionError,
)
from stock_model_selection.domain.pit import PitContext


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


@dataclass(frozen=True, kw_only=True)
class ProvenanceRecord:
    """Which dataset was read, under which PIT context, at which derivation version.

    `derivation` is None for observed datasets. Response metadata (the returned `pit`
    block, fetch ids) is added with the response schemas in step-5-a.
    """

    dataset: str
    pit: PitContext
    derivation: DerivationRef | None

    def __post_init__(self) -> None:
        if _is_blank(self.dataset):
            raise ValueError(f"dataset must be a non-empty string: {self.dataset!r}")
        if not isinstance(self.pit, PitContext):
            raise InvalidCutoffError(f"provenance needs a PitContext, got {self.pit!r}")
