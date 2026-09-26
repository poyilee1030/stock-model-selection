"""Recorded Data Center responses (scripts/record_data_center_fixtures.py)."""

import copy
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

RESPONSES = Path(__file__).parent / "fixtures" / "responses"


@dataclass(frozen=True)
class Recorded:
    status: int
    path: str
    params: list[tuple[str, str]]
    body: Any

    def fresh_body(self) -> Any:
        """A deep copy that a test may break."""
        return copy.deepcopy(self.body)


def recorded(name: str) -> Recorded:
    raw = json.loads((RESPONSES / f"{name}.json").read_text(), parse_float=Decimal)
    request = raw["request"]
    params = [(key, value) for key, value in request["params"]]
    return Recorded(raw["status"], request["path"], params, raw["body"])
