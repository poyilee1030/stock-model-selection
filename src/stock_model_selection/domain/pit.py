"""PIT context: the only thing feature and label APIs accept as "as of".

Modes and rules come from docs/contracts/time-and-cohort.md §4 and §5. There is
deliberately no way to build a PitContext from a plain date or an entry date.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from stock_model_selection.domain.errors import (
    AuditContextError,
    CutoffOrderError,
    InvalidCutoffError,
    MissingPitContextError,
)
from stock_model_selection.domain.time import require_aware


class PitMode(StrEnum):
    PRODUCTION = "production"
    RECONSTRUCTION = "reconstruction"
    # system_as_of only; for audit and debugging, never for features or labels
    AUDIT = "audit"


@dataclass(frozen=True, kw_only=True)
class PitContext:
    mode: PitMode
    information_as_of: datetime | None = None
    knowledge_as_of: datetime | None = None
    system_as_of: datetime | None = None

    def __post_init__(self) -> None:
        mode = PitMode(self.mode)
        object.__setattr__(self, "mode", mode)
        for name in ("information_as_of", "knowledge_as_of", "system_as_of"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_aware(value, name))

        if mode is PitMode.AUDIT:
            if self.system_as_of is None:
                raise InvalidCutoffError("an audit context needs system_as_of")
            if self.information_as_of is not None or self.knowledge_as_of is not None:
                raise InvalidCutoffError(
                    "system_as_of cannot be combined with information_as_of or knowledge_as_of"
                )
            return

        if self.system_as_of is not None:
            raise InvalidCutoffError(f"a {mode} context cannot carry system_as_of")
        if self.information_as_of is None or self.knowledge_as_of is None:
            raise InvalidCutoffError(
                f"a {mode} context needs both information_as_of and knowledge_as_of"
            )
        if mode is PitMode.PRODUCTION and self.knowledge_as_of < self.information_as_of:
            raise CutoffOrderError(
                f"production knowledge_as_of {self.knowledge_as_of.isoformat()} is before "
                f"information_as_of {self.information_as_of.isoformat()}"
            )

    @classmethod
    def production(cls, *, information_as_of: datetime, knowledge_as_of: datetime) -> "PitContext":
        return cls(
            mode=PitMode.PRODUCTION,
            information_as_of=information_as_of,
            knowledge_as_of=knowledge_as_of,
        )

    @classmethod
    def reconstruction(
        cls, *, information_as_of: datetime, knowledge_as_of: datetime
    ) -> "PitContext":
        return cls(
            mode=PitMode.RECONSTRUCTION,
            information_as_of=information_as_of,
            knowledge_as_of=knowledge_as_of,
        )

    @classmethod
    def audit(cls, *, system_as_of: datetime) -> "PitContext":
        return cls(mode=PitMode.AUDIT, system_as_of=system_as_of)


def require_market_pit(ctx: object) -> PitContext:
    """Entry check for every feature and label API: a production or reconstruction context."""
    if ctx is None:
        raise MissingPitContextError("a PitContext is required; there is no default cutoff")
    if not isinstance(ctx, PitContext):
        raise InvalidCutoffError(
            f"only a PitContext is accepted, never a date or timestamp; got {ctx!r}"
        )
    if ctx.mode is PitMode.AUDIT:
        raise AuditContextError("a system-cutoff (audit) context cannot be used here")
    return ctx
