from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# capa -> paquetes de primer nivel que nunca debe importar
FORBIDDEN = {
    "backend": {"services", "api", "frontend"},
    "services": {"api", "frontend"},
    "api": {"backend", "frontend"},
    "frontend": {"backend", "services", "api"},
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _sources(layer: str) -> list[Path]:
    return [p for p in (ROOT / layer).rglob("*.py") if "migrations" not in p.parts]


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_does_not_import_upper_or_sibling_layers(layer: str) -> None:
    violations = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _sources(layer)
        for name in _imports(path)
        if name.split(".")[0] in FORBIDDEN[layer]
    ]
    assert violations == []


def test_api_only_uses_container_and_models_from_services() -> None:
    allowed = {"services", "services.container", "services.models"}
    violations = [
        f"{path.relative_to(ROOT)} imports {name}"
        for path in _sources("api")
        for name in _imports(path)
        if name.startswith("services") and name not in allowed
    ]
    assert violations == []


def test_only_mappers_touch_orm_models_in_services() -> None:
    violations = [
        str(path.relative_to(ROOT))
        for path in _sources("services")
        if path.name != "mappers.py"
        and any(name.startswith("backend.models") for name in _imports(path))
    ]
    assert violations == []
