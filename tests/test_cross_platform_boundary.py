"""Enforces cross-platform test invariants across the test suite."""

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent


def _is_win32_guard(test_node: ast.AST) -> bool:
    """Returns True if the expression checks sys.platform for win32."""
    unparsed = ast.unparse(test_node)
    return "win32" in unparsed


class _ModeGuardChecker(ast.NodeVisitor):
    """AST visitor that flags unguarded POSIX file mode assertions."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.guard_stack: list[bool] = []
        self.violations: list[tuple[str, int, str]] = []

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        has_skip_decorator = any("win32" in ast.unparse(d) for d in node.decorator_list)
        has_early_skip = any(
            isinstance(stmt, ast.If)
            and _is_win32_guard(stmt.test)
            and any(
                isinstance(sub, ast.Call) and "skip" in ast.unparse(sub)
                for sub in ast.walk(stmt)
            )
            for stmt in node.body[:5]
        )
        self.guard_stack.append(has_skip_decorator or has_early_skip)
        self.generic_visit(node)
        self.guard_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)

    def visit_If(self, node: ast.If) -> None:
        is_guarded = _is_win32_guard(node.test)
        self.guard_stack.append(is_guarded)
        for stmt in node.body:
            self.visit(stmt)
        self.guard_stack.pop()

        self.guard_stack.append(False)
        for stmt in node.orelse:
            self.visit(stmt)
        self.guard_stack.pop()

    def visit_Assert(self, node: ast.Assert) -> None:
        if any(self.guard_stack):
            return

        for n in ast.walk(node):
            if isinstance(n, ast.Compare):
                has_mode = any(
                    (
                        isinstance(sub, ast.Attribute)
                        and sub.attr in ("st_mode", "S_IMODE")
                    )
                    or (isinstance(sub, ast.Name) and sub.id in ("S_IMODE", "st_mode"))
                    for sub in ast.walk(n)
                )
                if has_mode:
                    for comp in [n.left, *n.comparators]:
                        # 511 is 0o777 (bitmask)
                        if (
                            isinstance(comp, ast.Constant)
                            and isinstance(comp.value, int)
                            and comp.value > 0
                            and comp.value != 511
                        ):
                            self.violations.append(
                                (self.filename, node.lineno, ast.unparse(node))
                            )


def test_posix_mode_assertions_are_guarded_for_windows() -> None:
    """Hardcoded POSIX file mode assertions must be guarded on Windows.

    Windows does not support POSIX permission bits (chmod only toggles read-only,
    and non-read-only files report mode 0o666 / 438). Any test asserting a specific
    mode integer (e.g. 0o640, 0o600, 0o755) must be guarded by `if sys.platform != 'win32':`
    or `pytest.mark.skipif(sys.platform == 'win32')`.
    """
    violations: list[tuple[str, int, str]] = []
    test_files = [
        p for p in sorted(TESTS_DIR.glob("test_*.py")) if p.name != Path(__file__).name
    ]

    for test_file in test_files:
        tree = ast.parse(test_file.read_text(), filename=str(test_file))
        checker = _ModeGuardChecker(test_file.name)
        checker.visit(tree)
        violations.extend(checker.violations)

    if violations:
        formatted = "\n".join(
            f"  {filename}:{lineno} -> {expr}" for filename, lineno, expr in violations
        )
        raise AssertionError(
            "Found unguarded POSIX file mode assertions in tests!\n"
            "Windows does not support POSIX file mode bits (chmod only toggles read-only,\n"
            "and files report 0o666/438). Guard these assertions with:\n"
            "    if sys.platform != 'win32':\n"
            "or assert relative mode invariance (mode == before) instead.\n\n"
            f"Violations:\n{formatted}"
        )


def test_mode_guard_checker_detects_unguarded_mode_assertions() -> None:
    """Verifies that the AST checker flags unguarded mode assertions and allows guarded ones."""
    source_violating = """
def test_something():
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert target.stat().st_mode & 0o777 == 0o755
"""
    tree = ast.parse(source_violating)
    checker = _ModeGuardChecker("dummy.py")
    checker.visit(tree)
    assert len(checker.violations) == 2
    assert checker.violations[0][1] == 3
    assert checker.violations[1][1] == 4

    source_guarded = """
def test_something():
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o640
"""
    tree2 = ast.parse(source_guarded)
    checker2 = _ModeGuardChecker("dummy.py")
    checker2.visit(tree2)
    assert len(checker2.violations) == 0

    source_invariance = """
def test_something():
    assert path.stat().st_mode == before
"""
    tree3 = ast.parse(source_invariance)
    checker3 = _ModeGuardChecker("dummy.py")
    checker3.visit(tree3)
    assert len(checker3.violations) == 0
