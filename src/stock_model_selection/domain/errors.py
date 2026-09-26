"""Errors raised by the domain model; each one names a broken contract rule."""


class DomainError(Exception):
    pass


class MissingPitContextError(DomainError):
    """A feature or label API was called without a PIT context."""


class InvalidCutoffError(DomainError):
    """A cutoff is not a timezone-aware timestamp, or the cutoffs do not fit the mode."""


class CutoffOrderError(DomainError):
    """Cutoffs are in an order the contract forbids (time-and-cohort §5)."""


class AuditContextError(DomainError):
    """A system-cutoff context was used for features or labels (time-and-cohort §4)."""


class CalendarCoverageError(DomainError):
    """The trading calendar does not cover the day asked about."""


class InvalidCohortError(DomainError):
    """A cohort id is malformed or a cohort's dates break the calendar rules."""


class MissingDerivationVersionError(DomainError):
    """A derived dataset reference has no derivation_version."""
