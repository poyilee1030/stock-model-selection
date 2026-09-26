from datetime import date
from pathlib import Path

import pytest

from stock_model_selection.domain.calendar import TradingCalendar

FIXTURES = Path(__file__).parent / "fixtures"


def load_trading_days(path: Path) -> list[date]:
    lines = path.read_text().splitlines()
    return [date.fromisoformat(line) for line in lines if line and not line.startswith("#")]


@pytest.fixture(scope="session")
def calendar() -> TradingCalendar:
    return TradingCalendar(load_trading_days(FIXTURES / "trading_days.txt"))
