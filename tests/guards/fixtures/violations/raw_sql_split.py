def query(cols: str, day: str) -> str:
    return f"SELECT {cols} FROM prices WHERE trade_date = '{day}'"


LOWER = "select stock_id, close_price from prices"
JOINED = "SELECT close_price " + "FROM prices"
