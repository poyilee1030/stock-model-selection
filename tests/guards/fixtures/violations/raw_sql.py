QUERY = "SELECT close_price FROM prices WHERE stock_id = %s"


def build(stock_id: str) -> str:
    return f"delete from prices where stock_id = '{stock_id}'"
