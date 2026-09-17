import ast
from pathlib import Path

SRC = Path(__file__).parents[2] / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _assert_layer_does_not_import(layer: str, forbidden_roots: set[str]) -> None:
    violations: list[str] = []
    for path in (SRC / layer).rglob("*.py"):
        for module in _imports(path):
            root = module.partition(".")[0]
            if root in forbidden_roots:
                violations.append(f"{path.relative_to(SRC)} -> {module}")
    assert not violations, "Invalid layer dependencies:\n" + "\n".join(sorted(violations))


def test_domain_is_independent() -> None:
    _assert_layer_does_not_import(
        "domain",
        {"adapter", "application", "config", "di", "port", "presentation"},
    )


def test_ports_depend_only_inward() -> None:
    _assert_layer_does_not_import(
        "port",
        {"adapter", "application", "config", "di", "presentation"},
    )


def test_application_does_not_depend_on_outer_layers() -> None:
    _assert_layer_does_not_import(
        "application",
        {"adapter", "config", "di", "presentation"},
    )


def test_presentation_uses_application_and_ports_not_adapters() -> None:
    _assert_layer_does_not_import(
        "presentation",
        {"adapter", "config", "di"},
    )


def test_presentation_support_modules_do_not_hide_use_case_calls() -> None:
    violations: list[str] = []
    for path in (SRC / "presentation").rglob("support.py"):
        for module in _imports(path):
            if module.partition(".")[0] == "application":
                violations.append(f"{path.relative_to(SRC)} -> {module}")
    assert not violations, "Support modules must stay presentation-only:\n" + "\n".join(violations)
