"""Integration tests — validate contracts with sibling ecosystem packages.

These tests verify that heritage-cli's assumptions about the HOARD Python API
and the entry-point plugin system match reality. They require sibling packages
to be installed and are skipped gracefully when unavailable.

Run with:  python -m pytest tests/ -m integration -v
"""

from pathlib import Path

import pytest

# ── HOARD API contract validation ───────────────────────────────────────

HOARD_SYMBOLS = {
    "hoard.config.Config": "Config",
    "hoard.config.load_config": "load_config",
    "hoard.cli.run.run_pipeline": "run_pipeline",
    "hoard.cli.run.run_single_phase": "run_single_phase",
    "hoard.review.dashboard.ReviewSession": "ReviewSession",
    "hoard.phases.phase5.run_phase5": "run_phase5",
}


def _hoard_available() -> bool:
    """Check if the hoard package is importable."""
    try:
        import hoard  # noqa: F401
    except ImportError:
        return False
    return True


hoard_available = _hoard_available()
requires_hoard = pytest.mark.skipif(
    not hoard_available, reason="HOARD is not installed"
)


@pytest.mark.integration
class TestHoardContract:
    """Verify every symbol heritage-cli imports from HOARD exists and matches."""

    @requires_hoard
    def test_all_symbols_importable(self):
        """All 6 HOARD symbols heritage-cli relies on are importable."""
        for full_path, name in HOARD_SYMBOLS.items():
            mod_path, attr = full_path.rsplit(".", 1)
            mod = __import__(mod_path, fromlist=[attr])
            obj = getattr(mod, attr)
            assert obj is not None, f"{full_path} imported but is None"
            assert callable(obj) or hasattr(obj, "__init__"), (
                f"{full_path} is not callable/constructable"
            )

    @requires_hoard
    def test_config_accepts_expected_kwargs(self):
        """hoard.config.Config accepts all kwargs heritage-cli passes."""
        from hoard.config import Config

        # kwargs passed by main.py:run (Phase 1 fallback)
        cfg = Config(
            project_id="test_integration",
            project_name="Test Project",
            jurisdiction="historic_england_cl3",
            workspace_root=Path("/tmp/heritage_test_ws"),
            input_dir=Path("/tmp/heritage_test_input"),
            strict=False,
            extractor="glm-ocr",
        )
        assert cfg is not None
        assert cfg.project_id == "test_integration"
        assert cfg.project_name == "Test Project"

    @requires_hoard
    def test_config_accepts_minimal_kwargs(self):
        """hoard.config.Config accepts the minimal kwargs from main.py:review."""
        from hoard.config import Config

        cfg = Config(
            project_id="test_minimal",
            project_name="test_minimal",
            jurisdiction="historic_england_cl3",
            workspace_root=Path("/tmp/heritage_test_ws"),
            input_dir=Path("/tmp/heritage_test_input"),
        )
        assert cfg is not None

    @requires_hoard
    def test_load_config_signature(self):
        """hoard.config.load_config accepts (project, workspace)."""
        from hoard.config import load_config

        result = load_config("nonexistent_project", Path("/tmp/nonexistent"))
        # Returns Config or None for missing projects
        assert result is None or hasattr(result, "project_id")

    @requires_hoard
    def test_run_pipeline_signature(self):
        """hoard.cli.run.run_pipeline accepts a Config."""
        from inspect import signature

        from hoard.cli.run import run_pipeline

        sig = signature(run_pipeline)
        params = list(sig.parameters)
        assert "config" in params, (
            f"run_pipeline expects 'config' parameter, got: {params}"
        )

    @requires_hoard
    def test_run_single_phase_signature(self):
        """hoard.cli.run.run_single_phase accepts (config, phase, gui_mode)."""
        from inspect import signature

        from hoard.cli.run import run_single_phase

        sig = signature(run_single_phase)
        params = list(sig.parameters)
        # HOARD uses 'config' as the parameter name (heritage-cli passes positionally)
        assert "config" in params, (
            f"run_single_phase expects 'config' parameter, got: {params}"
        )
        assert "phase" in params, (
            f"run_single_phase expects 'phase' parameter, got: {params}"
        )

    @requires_hoard
    def test_review_session_api(self):
        """ReviewSession has .load(), .total, .run_interactive()."""
        from hoard.config import Config
        from hoard.review.dashboard import ReviewSession

        cfg = Config(
            project_id="test_review",
            project_name="test_review",
            jurisdiction="historic_england_cl3",
            workspace_root=Path("/tmp/heritage_review_test"),
            input_dir=Path("/tmp/heritage_review_input"),
        )
        session = ReviewSession(cfg)
        assert hasattr(session, "load"), "ReviewSession missing .load()"
        assert hasattr(session, "total"), "ReviewSession missing .total"
        assert hasattr(session, "run_interactive"), (
            "ReviewSession missing .run_interactive()"
        )

    @requires_hoard
    def test_run_phase5_signature(self):
        """hoard.phases.phase5.run_phase5 accepts (config, formats)."""
        from inspect import signature

        from hoard.phases.phase5 import run_phase5

        sig = signature(run_phase5)
        params = list(sig.parameters)
        # HOARD uses 'config' as the parameter name (heritage-cli passes positionally)
        assert "config" in params, (
            f"run_phase5 expects 'config' parameter, got: {params}"
        )
        assert "formats" in params, (
            f"run_phase5 expects 'formats' parameter, got: {params}"
        )


# ── Entry-point plugin system ───────────────────────────────────────────


@pytest.mark.integration
class TestPluginDiscovery:
    """Verify the heritage.tools entry-point group is correctly populated."""

    def test_entry_points_discoverable(self):
        """All 5 tools are declared as entry points and import to valid modules."""
        from importlib import metadata

        entry_points = list(metadata.entry_points(group="heritage.tools"))

        expected_tools = {"hoard", "stratigraph", "trowel", "libby", "dibble"}
        discovered = {ep.name for ep in entry_points}

        assert expected_tools == discovered, (
            f"Entry point mismatch. Expected {expected_tools}, got {discovered}"
        )

    def test_all_entry_points_resolve_to_importable_modules(self):
        """Each entry point module actually imports without error."""
        from importlib import metadata

        for ep in metadata.entry_points(group="heritage.tools"):
            mod = ep.load()
            assert hasattr(mod, "tool_name"), f"Module for {ep.name} missing tool_name"
            assert hasattr(mod, "dispatch"), f"Module for {ep.name} missing dispatch()"
            assert callable(mod.dispatch), f"dispatch() in {ep.name} is not callable"


# ── CLI binary detection ────────────────────────────────────────────────


@pytest.mark.integration
class TestBinaryDispatch:
    """Verify that binary-first dispatch works for installed tools."""

    def _which(self, name: str) -> bool:
        import shutil

        return shutil.which(name) is not None

    @pytest.mark.skipif(
        not _hoard_available(),
        reason="HOARD is not installed (binary may still be available)",
    )
    def test_hoard_binary_or_python_available(self):
        """HOARD is reachable via binary or Python import."""
        import shutil

        has_binary = shutil.which("hoard") is not None
        has_python = _hoard_available()
        assert has_binary or has_python, (
            "HOARD not found as binary on PATH or as Python import"
        )

    def test_tools_list_finds_installed(self):
        """heritage tools runs without error and reports status."""
        from typer.testing import CliRunner

        from heritage_cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        # Should at minimum list hoard in the table
        assert "hoard" in result.stdout.lower()


# ── End-to-end: pipeline YAML to orchestrator with real StepKind ────────


@pytest.mark.integration
class TestPipelineIntegration:
    """End-to-end pipeline parsing with all supported tool types."""

    def test_pipeline_example_yaml_parses(self):
        """The shipped pipeline.example.yaml parses without errors."""
        from heritage_cli.orchestrator import PipelineOrchestrator

        example = Path(__file__).parent.parent / "pipeline.example.yaml"
        assert example.exists(), "pipeline.example.yaml is missing"

        orch = PipelineOrchestrator(
            pipeline_path=example,
            project_id="test_proj_integration",
            workspace="/tmp/heritage_integration_ws",
        )
        orch.load()

        assert len(orch.steps) > 0
        kinds = {s.kind for s in orch.steps}
        # Should contain HOARD and GATE steps at minimum
        from heritage_cli.orchestrator import StepKind

        assert StepKind.HOARD in kinds, "No HOARD steps in example pipeline"
        assert StepKind.GATE in kinds, "No GATE steps in example pipeline"
        assert StepKind.EXPORT in kinds, "No EXPORT step in example pipeline"

    def test_state_roundtrip_with_all_statuses(self):
        """PipelineState persists and restores all 6 status values."""
        import json

        from heritage_cli.orchestrator import (
            PipelineOrchestrator,
            PipelineStep,
            StepKind,
            StepStatus,
        )

        orch = PipelineOrchestrator(
            pipeline_path=Path("/tmp/test_pipe.yaml"),
            project_id="state_integration_test",
            workspace="/tmp/heritage_state_test",
        )
        # Create a dummy pipeline file so load() doesn't fail
        Path("/tmp/test_pipe.yaml").write_text("steps: []")

        orch.steps = [
            PipelineStep(id="s1", kind=StepKind.HOARD, status=StepStatus.COMPLETE),
            PipelineStep(id="s2", kind=StepKind.GATE, status=StepStatus.PENDING),
            PipelineStep(id="s3", kind=StepKind.COMMAND, status=StepStatus.FAILED),
            PipelineStep(id="s4", kind=StepKind.LIBBY, status=StepStatus.SKIPPED),
            PipelineStep(id="s5", kind=StepKind.DIBBLE, status=StepStatus.RUNNING),
            PipelineStep(id="s6", kind=StepKind.HOARD, status=StepStatus.BLOCKED),
        ]
        orch._save_state()
        assert orch.state_file.exists()

        restored = orch._load_state()
        assert restored["s1"] == StepStatus.COMPLETE
        assert restored["s2"] == StepStatus.PENDING
        assert restored["s3"] == StepStatus.FAILED
        assert restored["s4"] == StepStatus.SKIPPED
        assert restored["s5"] == StepStatus.RUNNING
        assert restored["s6"] == StepStatus.BLOCKED

        # Verify JSON structure
        raw = json.loads(orch.state_file.read_text())
        assert "started_at" in raw
        assert "updated_at" in raw
        assert raw["project_id"] == "state_integration_test"
