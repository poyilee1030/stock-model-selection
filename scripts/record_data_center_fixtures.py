"""Record real Data Center responses as test fixtures for the response schemas.

Usage (needs STOCKDC_BASE_URL and STOCKDC_API_KEY, e.g. `set -a && . ./.env && set +a`):

    uv run python scripts/record_data_center_fixtures.py

Writes tests/data/fixtures/responses/<name>.json as {"status", "request", "body"}, where
"request" omits the API key and the base URL, and "body" is the response text as sent, so
decimals keep their stored digits. Tests read these files and never go online.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "data" / "fixtures" / "responses"

T_C = "2024-07-11T04:00:00+08:00"  # cohort 2024-07
T_RECON = "2026-09-26T12:00:00+08:00"
LABEL_AT = "2024-07-11T03:00:00+08:00"  # label_available_at of cohort 2024-06
TAIEX_TR = "報酬指數/臺灣證券交易所:發行量加權股價報酬指數"

Params = list[tuple[str, str]]


def feature(start: str, end: str, knowledge: str = T_RECON) -> Params:
    return [
        ("start", start),
        ("end", end),
        ("stock_id", "2330"),
        ("information_as_of", T_C),
        ("knowledge_as_of", knowledge),
    ]


DAYS = ("2024-07-09", "2024-07-10")
CASES: dict[str, tuple[str, Params]] = {
    **{
        name: (f"/v1/datasets/{name}", feature(*DAYS))
        for name in (
            "daily-prices",
            "official-valuations",
            "institutional-flows",
            "foreign-holdings",
            "margin-trading",
            "securities-lending",
        )
    },
    "monthly-revenues": ("/v1/datasets/monthly-revenues", feature("2024-06-01", "2024-06-30")),
    "shareholding-distributions": (
        "/v1/datasets/shareholding-distributions",
        feature("2024-07-01", "2024-07-10"),
    ),
    **{
        name: (f"/v1/datasets/{name}", feature(*DAYS, knowledge="latest"))
        for name in (
            "institutional-streaks",
            "institutional-cumulative-flows",
            "margin-metrics",
            "short-interest-metrics",
            "valuation-metrics",
        )
    },
    "shareholding-concentrations": (
        "/v1/datasets/shareholding-concentrations",
        feature("2024-07-01", "2024-07-10", knowledge="latest"),
    ),
    "technical-indicators-pit": (
        "/v1/datasets/technical-indicators-pit",
        [
            ("start", DAYS[0]),
            ("end", DAYS[1]),
            ("stock_id", "2330"),
            ("view", "rolling"),
            ("knowledge_as_of", T_RECON),
        ],
    ),
    "adjusted-prices-pit": (
        "/v1/datasets/adjusted-prices-pit",
        [
            ("start", "2024-06-12"),
            ("end", "2024-06-14"),
            ("stock_id", "2330"),
            ("information_as_of", LABEL_AT),
            ("knowledge_as_of", T_RECON),
        ],
    ),
    "indices": (
        "/v1/datasets/indices",
        [
            ("start", DAYS[0]),
            ("end", DAYS[1]),
            ("source", "twse_mi_index"),
            ("index_name", TAIEX_TR),
            ("information_as_of", LABEL_AT),
            ("knowledge_as_of", T_RECON),
        ],
    ),
    "stocks": (
        "/v1/stocks",
        [("stock_id", "2330"), ("stock_id", "2448"), ("date", "2021-01-05")],
    ),
    "trading-days": ("/v1/trading-days", [("start", "2024-07-22"), ("end", "2024-07-29")]),
    # knowledge_as_of left out: Data Center defaults it and lists it in pit.defaulted
    "defaulted-knowledge": (
        "/v1/datasets/daily-prices",
        [("start", DAYS[1]), ("end", DAYS[1]), ("stock_id", "2330"), ("information_as_of", T_C)],
    ),
    "error-400-naive-cutoff": (
        "/v1/datasets/daily-prices",
        feature(*DAYS)[:3] + [("information_as_of", "2024-07-11T04:00:00")],
    ),
    "error-400-explicit-knowledge-on-stored-derived": (
        "/v1/datasets/valuation-metrics",
        feature(*DAYS),
    ),
    "error-404-unknown-dataset": ("/v1/datasets/no-such-dataset", feature(*DAYS)),
}


def fetch(base: str, key: str | None, path: str, params: Params) -> tuple[int, str]:
    url = f"{base.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"
    headers = {"X-API-Key": key} if key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def main() -> int:
    base, key = os.environ.get("STOCKDC_BASE_URL"), os.environ.get("STOCKDC_API_KEY")
    if not base or not key:
        print("STOCKDC_BASE_URL and STOCKDC_API_KEY must be set", file=sys.stderr)
        return 2
    cases = {**CASES, "error-401-no-key": ("/v1/datasets/daily-prices", feature(*DAYS))}
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (path, params) in cases.items():
        status, body = fetch(base, None if name == "error-401-no-key" else key, path, params)
        meta = json.dumps(
            {"status": status, "request": {"path": path, "params": params}}, ensure_ascii=False
        )
        (OUT / f"{name}.json").write_text(f'{meta[:-1]}, "body": {body.strip()}}}\n')
        parsed = json.loads(body)
        rows = parsed.get("rows") if isinstance(parsed, dict) else None
        print(f"{status} {name}" + (f" rows={len(rows)}" if isinstance(rows, list) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
