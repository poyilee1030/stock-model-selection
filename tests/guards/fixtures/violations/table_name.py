def fragment(day: str) -> str:
    return f"join monthly_revenues r on r.revenue_month = '{day}'"
