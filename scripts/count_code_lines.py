"""Count implementation code lines the way ROADMAP §4 sizes a step.

A code line holds at least one token that is not a comment; blank lines, comment-only
lines and docstrings are not counted. Usage:

    uv run python scripts/count_code_lines.py src/stock_model_selection/data [...]
"""

import ast
import io
import sys
import tokenize
from pathlib import Path

SKIPPED = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
}


def docstring_lines(source: str) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def code_lines(path: Path) -> int:
    source = path.read_text()
    lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in SKIPPED:
            lines.update(range(token.start[0], token.end[0] + 1))
    return len(lines - docstring_lines(source))


def main(args: list[str]) -> int:
    files = sorted(
        f for arg in args for f in (Path(arg).rglob("*.py") if Path(arg).is_dir() else [Path(arg)])
    )
    total = 0
    for file in files:
        n = code_lines(file)
        total += n
        print(f"{n:6}  {file}")
    print(f"{total:6}  total")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
