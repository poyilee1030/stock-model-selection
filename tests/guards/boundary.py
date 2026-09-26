"""Static boundary guards: no direct DB/Redis access, no stock-eps-model dependency.

The guards parse files and never import them, so they also run on fixtures
that import modules which are not installed.
"""

import ast
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# Top-level import names of PostgreSQL drivers, SQLAlchemy, Redis clients, stock-eps-model.
FORBIDDEN_MODULES = frozenset(
    {
        "aioredis",
        "asyncpg",
        "hiredis",
        "pg8000",
        "psycopg",
        "psycopg2",
        "psycopg_binary",
        "psycopg_c",
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

_NAME = r"[\w.\"`]+"
_ACI = re.IGNORECASE | re.DOTALL

RAW_SQL = [
    # SQL keywords written in capitals, the usual way to write a query.
    re.compile(r"\bSELECT\b.+?\bFROM\b", re.DOTALL),
    re.compile(r"\bINSERT\s+INTO\b"),
    re.compile(r"\bUPDATE\s+\S+\s+SET\b"),
    re.compile(r"\bDELETE\s+FROM\b"),
    re.compile(r"\b(?:CREATE|DROP|ALTER|TRUNCATE)\s+TABLE\b"),
    # Any case, but only with the shape of a statement, so English such as
    # "Select a model from the registry" or "delete from the list" passes.
    re.compile(
        rf"\bselect\s+(?:distinct\s+)?(?:\*|{_NAME}(?:\s*,\s*{_NAME})*)\s+from\s+{_NAME}\s*"
        r"(?:$|;|\)|\b(?:where|join|inner|left|right|full|cross|group|order|limit|union)\b)",
        _ACI,
    ),
    re.compile(rf"\binsert\s+into\s+{_NAME}\s*(?:\(|\bvalues\b|\bselect\b)", _ACI),
    re.compile(rf"\bupdate\s+{_NAME}\s+set\s+{_NAME}\s*=", _ACI),
    re.compile(rf"\bdelete\s+from\s+{_NAME}\s*(?:$|;|\bwhere\b)", _ACI),
    re.compile(rf"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?{_NAME}\s*\(", _ACI),
    re.compile(rf"\b(?:drop|truncate)\s+table\s+(?:if\s+exists\s+)?{_NAME}\s*(?:$|;)", _ACI),
    re.compile(rf"\balter\s+table\s+{_NAME}\s+(?:add|drop|rename|alter)\b", _ACI),
]

# A table name only counts in SQL position, so a bare dataset code such as
# "valuation_metrics" (used by DerivationRef) is allowed.
TABLE_IN_SQL = re.compile(
    r"\b(?:from|join|into|update|table)\s+[\"`]?(?:\w+\.)?(?:"
    + "|".join(DATA_CENTER_TABLES)
    + r")\b",
    re.IGNORECASE,
)

# Stands in for each {value} of an f-string, so "SELECT {cols} FROM t" reads as a query.
_PLACEHOLDER = "x"


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: str
    detail: str


def scan_python(path: Path) -> list[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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

    for node, text in _string_expressions(tree):
        if TABLE_IN_SQL.search(text):
            add(node, "data-center-table", text)
        elif any(p.search(text) for p in RAW_SQL):
            add(node, "raw-sql", text)
    return sorted(violations, key=lambda v: (v.line, v.rule))


def scan_pyproject(path: Path) -> list[Violation]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    requirements: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        requirements += group
    for group in data.get("dependency-groups", {}).values():
        requirements += [r for r in group if isinstance(r, str)]
    # Deprecated, but uv still installs it.
    requirements += data.get("tool", {}).get("uv", {}).get("dev-dependencies", [])
    violations = []
    for requirement in requirements:
        name = _distribution_name(requirement)
        if name in FORBIDDEN_DISTRIBUTIONS:
            violations.append(Violation(path, 0, "forbidden-dependency", name))
    return sorted(violations, key=lambda v: v.detail)


def scan_lockfile(path: Path) -> list[Violation]:
    """Catch forbidden packages pulled in indirectly by another dependency."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    names = {_distribution_name(p.get("name", "")) for p in data.get("package", [])}
    return [
        Violation(path, 0, "forbidden-dependency", name)
        for name in sorted(names & FORBIDDEN_DISTRIBUTIONS)
    ]


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


def _string_expressions(tree: ast.Module) -> Iterator[tuple[ast.expr, str]]:
    """Yield each outermost string expression (literal, f-string, + of those) and its text.

    Docstrings are skipped.
    """
    docstrings = _docstring_nodes(tree)
    inner: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.expr) or id(node) in inner or id(node) in docstrings:
            continue
        text = _text(node)
        if text is None:
            continue
        inner.update(id(child) for child in ast.walk(node) if child is not node)
        yield node, text


def _text(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts = [_text(v) if isinstance(v, ast.Constant) else _PLACEHOLDER for v in node.values]
        return "".join(p or "" for p in parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _text(node.left), _text(node.right)
        if left is not None and right is not None:
            return left + right
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
