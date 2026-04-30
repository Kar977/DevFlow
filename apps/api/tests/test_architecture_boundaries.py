"""Architecture checks for the backend scaffold."""

import ast
from pathlib import Path

API_ROUTE_ROOT = Path("src/devflow_api/api/v1")
FORBIDDEN_ROUTE_IMPORTS = (
    "devflow_api.core.repositories",
    "devflow_api.core.integrations",
)


def _python_files(path: Path) -> list[Path]:
    """Return Python files below a path in deterministic order."""
    return sorted(path.rglob("*.py"))


def _imported_modules(file_path: Path) -> list[str]:
    """Extract imported module names from a Python source file."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    return imports


def test_api_routes_do_not_import_repositories_or_integrations_directly() -> None:
    """Route modules should delegate through services instead of lower layers."""
    violations: list[str] = []

    for file_path in _python_files(API_ROUTE_ROOT):
        for module in _imported_modules(file_path):
            if module.startswith(FORBIDDEN_ROUTE_IMPORTS):
                violations.append(f"{file_path}: {module}")

    assert violations == []
