"""Truth isolation: the platform's code never imports the simulator or the evaluation, and never names the
simulator's files. Only tmr.sim and tmr.evaluate may (and the CLI, which only dispatches)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = ["features", "text", "models", "policy", "agent", "serving", "monitor"]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add("." * node.level + mod)
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
    return out


def test_platform_code_does_not_import_the_simulator_or_the_evaluation():
    bad = []
    for pkg in PLATFORM:
        for f in (ROOT / "tmr" / pkg).rglob("*.py"):
            for imp in _imports(f):
                if any(x in imp for x in ("sim", "evaluate")):
                    bad.append(f"{f.relative_to(ROOT)}: {imp}")
    assert bad == []


def test_platform_code_does_not_name_the_truth():
    bad = []
    for pkg in PLATFORM:
        for f in (ROOT / "tmr" / pkg).rglob("*.py"):
            text = f.read_text()
            for word in ("world.yaml", "truth_dir", '"truth"', "market.pkl", "market_at_"):
                if word in text:
                    bad.append(f"{f.relative_to(ROOT)}: {word}")
    assert bad == []


def test_config_refuses_the_world_file():
    import pytest

    from tmr import config

    with pytest.raises(PermissionError):
        config.load("world")
