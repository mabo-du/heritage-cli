"""Smoke tests — verify all modules import and all commands respond to --help."""

import pytest
from typer.testing import CliRunner

from heritage_cli.main import app

runner = CliRunner()


def test_app_version():
    """--version returns 0 and prints the version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "heritage-cli" in result.stdout


def test_app_help():
    """--help returns 0 and shows usage."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.stdout


COMMANDS = [
    ("run", ["run", "--help"]),
    ("calibrate", ["calibrate", "--help"]),
    ("lithics", ["lithics", "--help"]),
    ("review", ["review", "--help"]),
    ("matrix", ["matrix", "--help"]),
    ("publish", ["publish", "--help"]),
    ("pipeline-status", ["pipeline-status", "--help"]),
    ("tools", ["tools", "--help"]),
]


@pytest.mark.parametrize("name,args", COMMANDS)
def test_command_help(name: str, args: list[str]):
    """Each registered command responds to --help."""
    result = runner.invoke(app, args)
    assert result.exit_code == 0, (
        f"{name} --help failed: {result.stderr or result.stdout}"
    )
    assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()


def test_all_command_modules_import():
    """All entry-point command modules can be imported."""
    modules = ["hoard", "stratigraph", "trowel", "libby", "dibble"]
    for mod_name in modules:
        mod = __import__(f"heritage_cli.commands.{mod_name}", fromlist=["tool_name"])
        assert hasattr(mod, "tool_name"), f"{mod_name} missing tool_name"
        assert hasattr(mod, "dispatch"), f"{mod_name} missing dispatch"


def test_orchestrator_imports():
    """Core orchestrator symbols are importable."""
    from heritage_cli.orchestrator import (
        PipelineOrchestrator,
        PipelineState,
        PipelineStep,
        StepKind,
        StepStatus,
    )

    assert StepKind.HOARD.value == "hoard"
    assert StepKind.STRATIGRAPH.value == "stratigraph"
    assert StepKind.TROWEL.value == "trowel"
    assert len(StepKind) == 8


def test_config_defaults():
    """config_default returns fallback when no config file exists."""
    from heritage_cli.main import config_default

    assert config_default("nonexistent.key", "fallback_val") == "fallback_val"
    assert config_default("defaults.jurisdiction", "historic_england_cl3") in (
        "historic_england_cl3",
        None,
    )
