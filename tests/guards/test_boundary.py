from pathlib import Path

import pytest

from tests.guards.boundary import Violation, scan_pyproject, scan_python

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
VIOLATIONS = FIXTURES / "violations"


def found(violations: list[Violation]) -> set[tuple[int, str]]:
    return {(v.line, v.rule) for v in violations}


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("import_postgres.py", {(1, "forbidden-import")}),
        ("import_sqlalchemy.py", {(1, "forbidden-import")}),
        ("import_redis.py", {(1, "forbidden-import")}),
        ("import_eps_model.py", {(1, "forbidden-import")}),
        ("import_dynamic.py", {(3, "forbidden-import"), (4, "forbidden-import")}),
        ("raw_sql.py", {(1, "raw-sql"), (5, "raw-sql")}),
        ("table_name.py", {(2, "data-center-table")}),
    ],
)
def test_python_guard_flags_each_violation(fixture: str, expected: set[tuple[int, str]]) -> None:
    assert found(scan_python(VIOLATIONS / fixture)) == expected


def test_pyproject_guard_flags_forbidden_distributions() -> None:
    violations = scan_pyproject(VIOLATIONS / "pyproject.toml")
    assert {v.rule for v in violations} == {"forbidden-dependency"}
    assert sorted(v.detail for v in violations) == ["psycopg2-binary", "redis", "stock-eps-model"]


def test_clean_fixtures_have_no_false_positives() -> None:
    assert scan_python(FIXTURES / "clean" / "allowed.py") == []
    assert scan_pyproject(FIXTURES / "clean" / "pyproject.toml") == []


def test_repository_source_respects_boundaries() -> None:
    sources = sorted((ROOT / "src").rglob("*.py"))
    assert sources, "src/ has no Python files to scan"
    violations = [v for path in sources for v in scan_python(path)]
    violations += scan_pyproject(ROOT / "pyproject.toml")
    assert violations == []
