from __future__ import annotations

import importlib
import string
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st

from fwasset.core.settings import _find_app_root as _find_project_root


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "fwasset"


def test_src_package_layout_exists():
    assert PACKAGE_ROOT.is_dir()
    assert (PACKAGE_ROOT / "__init__.py").is_file()
    assert (PACKAGE_ROOT / "app.py").is_file()
    assert (PACKAGE_ROOT / "core").is_dir()


def test_legacy_root_entries_removed():
    assert not (REPO_ROOT / "app.py").exists()
    assert not (REPO_ROOT / "core").exists()
    assert not (REPO_ROOT / "tests" / "__init__.py").exists()


def test_import_fwasset_package():
    module = importlib.import_module("fwasset")
    assert module is not None


def test_run_py_uses_fwasset_main():
    content = (REPO_ROOT / "run.py").read_text(encoding="utf-8")
    assert "from fwasset.app import main" in content
    assert 'if __name__ == "__main__":' in content


def test_pyproject_has_src_layout_settings():
    content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'build-backend = "hatchling.build"' in content
    assert 'packages = ["src/fwasset"]' in content
    assert 'fwasset = "fwasset.app:main"' in content
    assert '--cov=src/fwasset' in content
    assert 'hypothesis>=6.0.0' in content


def test_no_bare_core_or_app_imports_in_src_and_tests():
    py_files = list(SRC_ROOT.rglob("*.py")) + list((REPO_ROOT / "tests").rglob("*.py"))
    forbidden = (
        "from core.",
        "import core.",
        "from app import App",
        'monkeypatch.setattr("app.',
        "monkeypatch.setattr('app.",
        'monkeypatch.setattr("core.',
        "monkeypatch.setattr('core.",
    )

    violations = []
    for path in py_files:
        if path.name == "test_src_layout.py":
            continue
        content = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in content:
                violations.append(f"{path.relative_to(REPO_ROOT)}: {marker}")

    assert violations == []


@given(parts=st.lists(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8), min_size=0, max_size=4))
def test_find_project_root_walks_up_to_pyproject(parts: list[str]):
    with TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir) / "repo"
        repo_root.mkdir()
        (repo_root / "pyproject.toml").write_text("[project]\nname=\"demo\"\n", encoding="utf-8")

        current = repo_root
        for part in parts:
            current = current / part
            current.mkdir()

        probe = current / "module.py"
        probe.write_text("", encoding="utf-8")

        assert _find_project_root(probe) == repo_root
