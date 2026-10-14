"""The smoke test finds every package a scaffold built from source."""

import json
import sys
from pathlib import Path

import pytest

from scripts import source_builds

LOCK = """\
version = 1

[[package]]
name = "demo"
version = "0.1.0"
source = { editable = "." }

[[package]]
name = "six"
version = "1.17.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.example/six-1.17.0.tar.gz" }
wheels = [
    { url = "https://files.example/six-1.17.0-py2.py3-none-any.whl" },
]

[[package]]
name = "watchdog"
version = "6.0.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.example/watchdog-6.0.0.tar.gz" }
wheels = [
    { url = "https://files.example/watchdog-6.0.0-cp313-cp313-macosx_11_0_arm64.whl" },
]

[[package]]
name = "sdist-only"
version = "2.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.example/sdist_only-2.0.tar.gz" }

[[package]]
name = "nvidia-cusparselt-cu13"
version = "0.8.1"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://files.example/nvidia_cusparselt_cu13-0.8.1-py3-none-manylinux2014_aarch64.whl" },
]

[[package]]
name = "local-version"
version = "1.0+cpu"
source = { registry = "https://download.example/whl" }
wheels = [
    { url = "https://download.example/local_version-1.0%2Bcpu-py3-none-any.whl" },
]
"""


def scaffold(tmp_path: Path, installed: dict[str, str]) -> Path:
    """A synced project whose environment holds each dist-info with its wheel tag."""
    (tmp_path / "uv.lock").write_text(LOCK, encoding="utf-8")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text(
        "home = /usr/bin\nversion_info = 3.13.2\n", encoding="utf-8"
    )
    site = venv / "lib/python3.13/site-packages"
    for dist_info, tag in installed.items():
        (site / dist_info).mkdir(parents=True)
        (site / dist_info / "WHEEL").write_text(
            f"Wheel-Version: 1.0\nGenerator: setuptools\nTag: {tag}\n",
            encoding="utf-8",
        )
    return tmp_path


def test_only_packages_with_no_matching_published_wheel_are_reported(tmp_path):
    project = scaffold(
        tmp_path,
        {
            "demo-0.1.0.dist-info": "py3-none-any",
            "six-1.17.0.dist-info": "py3-none-any",
            "watchdog-6.0.0.dist-info": "cp314-cp314-macosx_11_0_arm64",
            "sdist_only-2.0.dist-info": "py3-none-any",
            "local_version-1.0+cpu.dist-info": "py3-none-any",
            # Its WHEEL file names a tag its filename doesn't, but with no
            # sdist it can only have come from the published wheel.
            "nvidia_cusparselt_cu13-0.8.1.dist-info": "py3-none-manylinux2014_sbsa",
        },
    )
    assert source_builds.source_builds(project) == [
        "sdist-only==2.0",
        "watchdog==6.0.0",
    ]


def test_a_published_wheel_is_not_a_build(tmp_path):
    project = scaffold(
        tmp_path, {"watchdog-6.0.0.dist-info": "cp313-cp313-macosx_11_0_arm64"}
    )
    assert source_builds.source_builds(project) == []


def test_the_record_names_the_template_platform_and_environment_python(
    tmp_path, monkeypatch, capsys
):
    project = scaffold(tmp_path, {"sdist_only-2.0.dist-info": "py3-none-any"})
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    monkeypatch.setattr(
        sys, "argv", ["source_builds", str(project), "--template", "ml"]
    )
    source_builds.main()
    assert json.loads(capsys.readouterr().out) == {
        "template": "ml",
        "platform": "linux-arm64-py3.13",
        "packages": ["sdist-only==2.0"],
    }


@pytest.mark.parametrize("installed", [{}, {"six-1.17.0.dist-info": "py3-none-any"}])
def test_a_scaffold_that_built_nothing_prints_nothing(
    tmp_path, monkeypatch, capsys, installed
):
    project = scaffold(tmp_path, installed)
    monkeypatch.setattr(
        sys, "argv", ["source_builds", str(project), "--template", "lib"]
    )
    source_builds.main()
    assert capsys.readouterr().out == ""
