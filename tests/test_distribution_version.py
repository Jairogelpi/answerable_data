"""FR-CLI-001: public version identifiers agree with the installed distribution."""

import json
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

import answerable
from answerable.cli import main


def test_FR_CLI_001_public_versions_match_distribution(capsys: pytest.CaptureFixture[str]) -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert main(("--json", "doctor")) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert answerable.__version__ == version("answerable-data")
    assert doctor["version"] == project["project"]["version"] == answerable.__version__
