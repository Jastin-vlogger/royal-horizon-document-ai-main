"""Architecture guard tests for the layered refactor."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

REMOVED_OLD_FOLDERS = {
    "core",
    "schemas",
    "routes",
    "prompts",
    "utils",
}

ALLOWED_LAYER_IMPORTS: dict[str, set[str]] = {
    "routers": {"containers", "dispatchers", "models"},
    "dispatchers": {"coordination", "models"},
    "coordination": {"orchestration", "models"},
    "orchestration": {"foundation", "processing", "models", "config"},
    "processing": {"models", "config"},
    "foundation": {"brokers", "models"},
    "brokers": {"models", "config"},
    "models": {"models"},
}


def _src_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
            imports.add(node.module)
    return imports


def test_old_live_folders_are_removed():
    for folder in REMOVED_OLD_FOLDERS:
        assert not (SRC / folder).exists(), f"old live folder still exists: src/{folder}"


def test_layer_import_direction_is_guarded():
    violations = []
    for path in SRC.rglob("*.py"):
        layer = path.relative_to(SRC).parts[0]
        if layer in {"containers", "main.py", "__init__.py"}:
            continue
        allowed = ALLOWED_LAYER_IMPORTS.get(layer)
        if allowed is None:
            continue
        for imported in _src_imports(path):
            imported_parts = imported.split(".")
            if len(imported_parts) < 2:
                continue
            imported_layer = imported_parts[1]
            if imported_layer == layer:
                continue
            if imported_layer not in allowed:
                violations.append(
                    f"{path.relative_to(ROOT)} imports {imported}"
                )
    assert not violations, "\n".join(violations)
