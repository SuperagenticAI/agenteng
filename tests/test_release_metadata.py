import importlib.util
from pathlib import Path
import shutil
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
OTHER_VERSION = "99.0.0" if VERSION != "99.0.0" else "99.0.1"
spec = importlib.util.spec_from_file_location(
    "release_metadata", ROOT / "scripts/check-release-metadata.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def release_root(tmp_path):
    for name in [
        "pyproject.toml",
        "uv.lock",
        "src/agenteng/__init__.py",
        "src/agenteng/data/install.sh",
    ]:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    return tmp_path


def test_current_metadata_and_matching_tag(release_root):
    assert checker.release_metadata_errors(release_root) == []
    assert checker.release_metadata_errors(release_root, "v" + VERSION) == []


@pytest.mark.parametrize(
    "tag",
    [
        "v" + OTHER_VERSION,
        VERSION,
        "main",
        "v0.1",
        "v" + VERSION + "\n",
        "v" + VERSION + "+local",
        "v" + VERSION + "; echo injected",
        "$(touch danger)",
    ],
)
def test_mismatched_or_unsafe_tags_are_rejected(release_root, tag):
    assert any(
        f"expected v{VERSION}" in error
        for error in checker.release_metadata_errors(release_root, tag)
    )


@pytest.mark.parametrize(
    "name,old,new",
    [
        (
            "src/agenteng/__init__.py",
            f'__version__ = "{VERSION}"',
            f'__version__ = "{OTHER_VERSION}"',
        ),
        (
            "uv.lock",
            f'name = "agenteng"\nversion = "{VERSION}"',
            f'name = "agenteng"\nversion = "{OTHER_VERSION}"',
        ),
        ("src/agenteng/data/install.sh", f"VERSION={VERSION}", f"VERSION={OTHER_VERSION}"),
        ("src/agenteng/data/install.sh", f"releases/{VERSION}", f"releases/{OTHER_VERSION}"),
        ("pyproject.toml", 'name = "agenteng"', 'name = "wrong-package"'),
        ("pyproject.toml", 'agenteng = "agenteng.cli:main"', 'agenteng = "wrong:main"'),
    ],
)
def test_version_identity_or_installer_drift_blocks_release(release_root, name, old, new):
    path = release_root / name
    assert old in path.read_text()
    path.write_text(path.read_text().replace(old, new, 1))
    assert checker.release_metadata_errors(release_root, "v" + VERSION)


@pytest.mark.parametrize("version", ["0.2.0rc1", "0.2.0a1", "0.2.0b1", "0.2.0.post1", "0.2.0.dev1"])
def test_canonical_prereleases_and_postreleases(release_root, version):
    for name in [
        "pyproject.toml",
        "uv.lock",
        "src/agenteng/__init__.py",
        "src/agenteng/data/install.sh",
    ]:
        path = release_root / name
        path.write_text(path.read_text().replace(VERSION, version))
    assert checker.release_metadata_errors(release_root, "v" + version) == []
