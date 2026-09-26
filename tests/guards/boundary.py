"""Static boundary guards: no direct DB/Redis access, no stock-eps-model dependency.

The guards parse files and never import them, so they also run on fixtures
that import modules which are not installed.
"""

import ast
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Top-level import names of PostgreSQL drivers, SQLAlchemy, Redis clients, stock-eps-model.
FORBIDDEN_MODULES = frozenset(
    {
        "aioredis",
        "asyncpg",
        "pg8000",
        "psycopg",
        "psycopg2",
        "psycopg_pool",
        "redis",
        "sqlalchemy",
        "sqlmodel",
        "stock_eps_model",
    }
)

# The same packages as distribution names, normalized per PEP 503.
FORBIDDEN_DISTRIBUTIONS = frozenset(
    {
        "aioredis",
        "asyncpg",
        "hiredis",
        "pg8000",
        "psycopg",
        "psycopg-binary",
        "psycopg-c",
        "psycopg-pool",
        "psycopg2",
        "psycopg2-binary",
        "redis",
        "sqlalchemy",
        "sqlmodel",
        "stock-eps-model",
    }
)

# Data Center dataset names (snake_case) and derivation dataset codes, the likely table names.
DATA_CENTER_TABLES = (
    "adjusted_prices_pit",
    "corporate_actions",
    "daily_prices",
    "financial_reports",
    "foreign_holdings",
    "institutional_cumulative_flows?",
    "institutional_flows",
    "institutional_market_flows",
    "institutional_streaks",
    "margin_metrics",
    "margin_trading",
    "monthly_revenues",
    "official_valuations",
    "securities_lending",
    "shareholding_concentrations?",
    "shareholding_distributions",
    "short_interest_metrics",
    "technical_indicators(?:_pit)?",
    "valuation_metrics",
)

RAW_SQL = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in (
        r"\bselect\b.+?\bfrom\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+\w+\s+set\b",
        r"\bdelete\s+from\b",
        r"\b(?:create|drop|alter|truncate)\s+table\b",
    )
]

# A table name only counts in SQL position, so a bare dataset code such as
# "valuation_metrics" (used by DerivationRef) is allowed.
TABLE_IN_SQL = re.compile(
    r"\b(?:from|join|into|update|table)\s+[\"`]?(?:\w+\.)?(?:"
    + "|".join(DATA_CENTER_TABLES)
    + r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: str
    detail: str


def scan_python(path: Path) -> list[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(tree)
    violations: list[Violation] = []

    def add(node: ast.expr | ast.stmt, rule: str, detail: str) -> None:
        violations.append(Violation(path, node.lineno, rule, detail))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _top(alias.name) in FORBIDDEN_MODULES:
                    add(node, "forbidden-import", alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and _top(node.module) in FORBIDDEN_MODULES:
                add(node, "forbidden-import", node.module)
        elif isinstance(node, ast.Call):
            name = _dynamic_import_target(node)
            if name is not None and _top(name) in FORBIDDEN_MODULES:
                add(node, "forbidden-import", name)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            if TABLE_IN_SQL.search(node.value):
                add(node, "data-center-table", node.value)
            elif any(p.search(node.value) for p in RAW_SQL):
                add(node, "raw-sql", node.value)
    return sorted(violations, key=lambda v: (v.line, v.rule))


def scan_pyproject(path: Path) -> list[Violation]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    requirements: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        requirements += group
    for group in data.get("dependency-groups", {}).values():
        requirements += [r for r in group if isinstance(r, str)]
    violations = []
    for requirement in requirements:
        name = _distribution_name(requirement)
        if name in FORBIDDEN_DISTRIBUTIONS:
            violations.append(Violation(path, 0, "forbidden-dependency", name))
    return sorted(violations, key=lambda v: v.detail)


def _top(module: str) -> str:
    return module.split(".", 1)[0]


def _dynamic_import_target(call: ast.Call) -> str | None:
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name not in {"import_module", "__import__"} or not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _docstring_nodes(tree: ast.Module) -> set[int]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def _distribution_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    if match is None:
        return ""
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()
