"""Docstrings may say: SELECT the stocks FROM the universe, then insert into a list."""

import collections
import redistricting  # a module whose name only starts with "redis"

DATASET = "daily-prices"
DERIVATION_CODE = "valuation_metrics"
MESSAGE = "choose a cohort from the list"


def counts() -> collections.Counter[str]:
    """Update the counter, then set it aside."""
    return collections.Counter([DATASET, DERIVATION_CODE, MESSAGE, redistricting.__name__])
