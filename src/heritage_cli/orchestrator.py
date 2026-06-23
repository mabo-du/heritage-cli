"""orchestrator.py — Pipeline orchestration engine with review gates.

Implements a checkpoint-based execution model where a declarative YAML
pipeline definition is run step by step, pausing at human review gates
for expert validation. Pipeline state is persisted to a JSON file for
resumability after interruption.

Pipeline YAML format:
    steps:
      - id: digitise
        project: hoard
        phases: [0, 1]
      - id: review
        gate: review
        message: "Review the Harris Matrix before proceeding"
        action: "stratigraph import --path output/01_digitised"
        depends_on: [digitise]
      - id: calibrate
        project: libby
        action: calibrate
        input: output/01_digitised/samples.json
        depends_on: [review]
      - id: draft
        project: hoard
        phases: [3, 4]
        depends_on: [calibrate]
      - id: final_review
        gate: review
        message: "Review the draft before final export"
        depends_on: [draft]
      - id: export
        project: hoard
        action: export
        formats: [docx, pdf]
        depends_on: [final_review]
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ── Step types ────────────────────────────────────────────────────────────────


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


class StepKind(str, Enum):
    HOARD = "hoard"  # Run HOARD pipeline phases
    GATE = "gate"  # Human review gate — pauses execution
    COMMAND = "command"  # Run an arbitrary shell command
    LIBBY = "libby"  # Calibrate samples
    DIBBLE = "dibble"  # Run lithic analysis
    STRATIGRAPH = "stratigraph"  # Harris Matrix visualisation
    TROWEL = "trowel"  # Desktop review dashboard
    EXPORT = "export"  # Final report export


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class PipelineStep:
    """A single step in the pipeline DAG."""

    id: str
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    message: str = ""  # For GATE steps: prompt shown to user
    action: str = ""  # For GATE steps: suggestion of what to do
    tool_args: dict[str, Any] = field(default_factory=dict)  # Phase-specific args
    depends_on: list[str] = field(default_factory=list)

    # Runtime fields (not serialised in pipeline.yaml)
    error: str = ""


@dataclass
class PipelineState:
    """Persistent state ledger for pipeline resumability."""

    project_id: str
    pipeline_path: str
    steps: dict[str, StepStatus] = field(default_factory=dict)
    started_at: str = ""
    updated_at: str = ""


# ── Orchestrator ──────────────────────────────────────────────────────────────


class PipelineOrchestrator:
    """Executes a pipeline definition step by step with review gates.

    Usage:
        orch = PipelineOrchestrator("path/to/pipeline.yaml", project_id="my_site")
        orch.run()
    """

    def __init__(
        self,
        pipeline_path: str | Path,
        project_id: str = "",
        workspace: str = "./erd_workspace",
        auto: bool = False,
        jurisdiction: str = "historic_england_cl3",
    ) -> None:
        self.pipeline_path = Path(pipeline_path)
        _validate_project_id(project_id)
        self.project_id = project_id
        self.workspace = Path(workspace)
        self.auto = auto  # If True, skip review gates automatically
        self.jurisdiction = jurisdiction
        self.started_at: str = ""  # Set on first _save_state
        self.steps: list[PipelineStep] = []
        self.state_dir = self.workspace / project_id
        self.state_file = self.state_dir / "pipeline_state.json"
        self._step_map: dict[str, PipelineStep] = {}

    # ── Loading ──────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load and parse a pipeline YAML definition."""
        import yaml

        if not self.pipeline_path.exists():
            raise FileNotFoundError(f"Pipeline file not found: {self.pipeline_path}")

        raw = yaml.safe_load(self.pipeline_path.read_text())
        if not raw or "steps" not in raw:
            raise ValueError("Pipeline file must contain a 'steps' list")

        steps_raw = raw["steps"]
        self.steps = []
        for i, step_raw in enumerate(steps_raw):
            step = self._parse_step(step_raw, i)
            self.steps.append(step)
            self._step_map[step.id] = step

    def _parse_step(self, raw: dict, index: int) -> PipelineStep:
        """Parse a single step from YAML."""
        # Determine kind
        if "gate" in raw:
            kind = StepKind.GATE
            step_id = raw.get("id", f"gate_{index}")
        elif "project" in raw:
            try:
                kind = StepKind(raw["project"])
            except ValueError:
                raise ValueError(
                    f"Unknown project type '{raw['project']}' in step "
                    f"'{raw.get('id', 'unknown')}'. Valid values: "
                    f"{[e.value for e in StepKind]}"
                ) from None
            step_id = raw.get("id", f"{kind.value}_{index}")
        else:
            kind = StepKind.COMMAND
            step_id = raw.get("id", f"cmd_{index}")

        return PipelineStep(
            id=step_id,
            kind=kind,
            message=raw.get("message", ""),
            action=raw.get("action", ""),
            tool_args=self._extract_args(raw, kind),
            depends_on=raw.get("depends_on", []),
        )

    def _extract_args(self, raw: dict, kind: StepKind) -> dict[str, Any]:
        """Extract tool-specific arguments from the step definition."""
        args: dict[str, Any] = {}
        if kind == StepKind.HOARD:
            args["phases"] = raw.get("phases", [])
            args["from_phase"] = raw.get("from_phase")
            args["extractor"] = raw.get("extractor", "glm-ocr")
            args["strict"] = raw.get("strict", False)
        elif kind == StepKind.LIBBY:
            args["input"] = raw.get("input", "")
            args["action"] = raw.get("action", "calibrate")
        elif kind == StepKind.DIBBLE:
            args["input"] = raw.get("input", "./scans")
            args["output"] = raw.get("output", "")
        elif kind == StepKind.EXPORT:
            args["formats"] = raw.get("formats", ["docx", "pdf"])
        elif kind == StepKind.COMMAND:
            args["command"] = raw.get("command", "")
        return args

    # ── State Management ─────────────────────────────────────────────────

    def _load_state(self) -> dict[str, StepStatus]:
        """Load pipeline state from disk for resumability."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                raw_steps = data.get("steps", {})
                return {k: StepStatus(v) for k, v in raw_steps.items()}
            except (json.JSONDecodeError, ValueError):
                console = _get_console()
                console.print(
                    f"  [yellow]⚠[/] Corrupt pipeline state file at {self.state_file} — starting fresh"
                )
        return {}

    def _save_state(self) -> None:
        """Persist current pipeline state to disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        is_first_save = not self.state_file.exists()
        if is_first_save and not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()
        state = {
            "project_id": self.project_id,
            "pipeline": str(self.pipeline_path),
            "steps": {s.id: s.status.value for s in self.steps},
            "started_at": self.started_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2))
        import shutil

        shutil.move(str(tmp), str(self.state_file))

    # ── Execution ────────────────────────────────────────────────────────

    def run(self) -> None:
        """Execute the entire pipeline, pausing at review gates."""
        # Restore state if resuming
        saved_state = self._load_state()
        if saved_state:
            self._apply_saved_state(saved_state)

        console = _get_console()

        console.print(f"[bold]Pipeline:[/] {self.pipeline_path}")
        console.print(f"[bold]Project:[/]  {self.project_id}")
        console.print(f"[bold]Steps:[/]    {len(self.steps)}")
        console.print()

        for step in self.steps:
            # Skip already completed steps
            if step.status == StepStatus.COMPLETE:
                console.print(f"  [dim]• {step.id}[/] [green](already complete)[/]")
                continue
            if step.status == StepStatus.SKIPPED:
                console.print(f"  [dim]• {step.id}[/] [yellow](skipped)[/]")
                continue

            if not self._dependencies_met(step):
                console.print(f"  [red]✗ {step.id}[/] dependencies not met — blocking")
                step.status = StepStatus.BLOCKED
                self._save_state()
                return

            if step.kind == StepKind.GATE:
                self._execute_gate(step)
            else:
                self._execute_step(step)

            self._save_state()

        console.print()
        console.print("[green]✓[/] Pipeline complete!")

    def _apply_saved_state(self, saved: dict[str, StepStatus]) -> None:
        """Apply previously saved state to steps for resume."""
        for step in self.steps:
            if step.id in saved:
                if saved[step.id] in (StepStatus.COMPLETE, StepStatus.SKIPPED):
                    step.status = saved[step.id]
                # PENDING/FAILED steps get re-executed

    def _dependencies_met(self, step: PipelineStep) -> bool:
        """Check if all dependency steps completed successfully."""
        for dep_id in step.depends_on:
            dep = self._step_map.get(dep_id)
            if dep and dep.status != StepStatus.COMPLETE:
                return False
        return True

    # ── Step Executors ───────────────────────────────────────────────────

    def _execute_step(self, step: PipelineStep) -> None:
        """Execute a non-gate step (HOARD, Libby, Dibble, Export, Command)."""
        console = _get_console()
        step.status = StepStatus.RUNNING
        self._save_state()

        console.print(f"  [blue]→[/] Running step: [bold]{step.id}[/]")

        try:
            if step.kind == StepKind.HOARD:
                self._run_hoard(step)
            elif step.kind == StepKind.LIBBY:
                self._run_libby(step)
            elif step.kind == StepKind.DIBBLE:
                self._run_dibble(step)
            elif step.kind == StepKind.EXPORT:
                self._run_export(step)
            elif step.kind == StepKind.COMMAND:
                self._run_command(step)
            else:
                console.print(
                    f"  [yellow]⚠[/] Unknown step kind: {step.kind} — skipping"
                )
                step.status = StepStatus.SKIPPED

            if step.status not in (StepStatus.SKIPPED, StepStatus.FAILED):
                step.status = StepStatus.COMPLETE
                console.print(f"  [green]✓[/] {step.id} complete")

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            console.print(f"  [red]✗[/] {step.id} failed: {e}")
            self._save_state()
            raise

    def _run_hoard(self, step: PipelineStep) -> None:
        """Execute HOARD pipeline phases."""
        args = step.tool_args
        phases = args.get("phases", [])
        extractor = args.get("extractor", "glm-ocr")
        strict = args.get("strict", False)

        import shutil

        hoard_bin = shutil.which("hoard")

        if hoard_bin:
            cmd = [
                hoard_bin,
                "run",
                "--project",
                self.project_id,
                "--workspace",
                str(self.workspace),
            ]
            if phases:
                for phase in phases:
                    phase_cmd = cmd + ["--phase", str(phase)]
                    if extractor:
                        phase_cmd.extend(["--extractor", extractor])
                    if strict:
                        phase_cmd.append("--strict")
                    _run_subprocess(phase_cmd, step.id)
            else:
                from_phase = args.get("from_phase")
                if from_phase is not None:
                    cmd.extend(["--from-phase", str(from_phase)])
                if extractor:
                    cmd.extend(["--extractor", extractor])
                if strict:
                    cmd.append("--strict")
                _run_subprocess(cmd, step.id)
        else:
            # Fallback: Python import
            from hoard.cli.run import run_single_phase
            from hoard.config import Config

            cfg = Config(
                project_id=self.project_id,
                project_name=self.project_id,
                jurisdiction=self.jurisdiction,
                workspace_root=self.workspace.resolve(),
                input_dir=(self.workspace / self.project_id / "input").resolve(),
                strict=strict,
                extractor=extractor,
            )
            if phases:
                for phase in phases:
                    run_single_phase(cfg, phase)
            else:
                from hoard.cli.run import run_pipeline

                run_pipeline(cfg)

    def _run_libby(self, step: PipelineStep) -> None:
        """Execute Libby radiocarbon calibration."""
        args = step.tool_args
        input_path = args.get("input", "") or str(
            self.workspace / self.project_id / "01_digitised" / "samples.json"
        )
        output_dir = str(self.workspace / self.project_id / "03_draft")

        import shutil

        libby_bin = shutil.which("libby")
        if libby_bin:
            _run_subprocess(
                [
                    libby_bin,
                    "calibrate",
                    "--input",
                    input_path,
                    "--output",
                    output_dir,
                ],
                step.id,
            )
        else:
            raise RuntimeError(
                "Libby not installed. Install with: pip install libby\n"
                f"  Or manually calibrate: {input_path}"
            )

    def _run_dibble(self, step: PipelineStep) -> None:
        """Execute Dibble lithic analysis."""
        args = step.tool_args
        input_dir = args.get("input", "./scans")
        output_dir = args.get("output", "") or str(
            self.workspace / self.project_id / "02_spatial" / "lithics"
        )

        import shutil

        dibble_bin = shutil.which("dibble")
        if dibble_bin:
            _run_subprocess(
                [
                    dibble_bin,
                    "process",
                    "--input",
                    input_dir,
                    "--output",
                    output_dir,
                ],
                step.id,
            )
        else:
            raise RuntimeError(
                "Dibble not installed. Install with: pip install dibble\n"
                "  Or skip lithic analysis by removing the step."
            )

    def _run_export(self, step: PipelineStep) -> None:
        """Execute HOARD Phase 5 export."""
        args = step.tool_args
        formats = args.get("formats", ["docx", "pdf"])

        try:
            from hoard.config import load_config

            cfg = load_config(self.project_id, self.workspace)
            if cfg is None:
                raise RuntimeError(f"Project '{self.project_id}' not initialised")
            from hoard.phases.phase5 import run_phase5

            result = run_phase5(cfg, formats=formats)
            if result is None:
                raise RuntimeError(
                    f"Project '{self.project_id}' export returned no result"
                )
            export_paths = result.get("export_paths", {})
            if export_paths:
                console = _get_console()
                for name, path in export_paths.items():
                    console.print(f"    • {name}: {path}")
        except ImportError:
            raise RuntimeError("HOARD not installed. Run: pip install hoard")

    def _run_command(self, step: PipelineStep) -> None:
        """Execute an arbitrary shell command."""
        cmd_str = step.tool_args.get("command", "")
        if not cmd_str:
            raise ValueError(
                f"Step '{step.id}' of kind 'command' has no 'command' field"
            )
        import shlex

        # Substitute placeholders before tokenizing to avoid argument injection
        cmd_str = cmd_str.replace("{project_id}", self.project_id).replace(
            "{workspace}", str(self.workspace)
        )
        cmd_parts = shlex.split(cmd_str)
        _run_subprocess(cmd_parts, step.id)

    # ── Review Gates ─────────────────────────────────────────────────────

    def _execute_gate(self, step: PipelineStep) -> None:
        """Pause execution for human review."""
        console = _get_console()

        console.print()
        console.print("=" * 60)
        console.print(f"[bold yellow]🔍 REVIEW GATE: {step.id}[/]")
        if step.message:
            console.print(f"  {step.message}")
        if step.action:
            console.print(f"  [dim]Suggested action:[/] {step.action}")
        console.print("=" * 60)

        if self.auto:
            console.print("  [yellow](auto mode — proceeding)[/]")
            step.status = StepStatus.COMPLETE
            return

        while True:
            try:
                response = (
                    input("  Continue? [Y]es / [s]kip / [q]uit: ").strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                console.print()
                console.print("[red]✗ Pipeline interrupted[/]")
                step.status = StepStatus.PENDING
                self._save_state()
                sys.exit(1)

            if response in ("", "y", "yes"):
                step.status = StepStatus.COMPLETE
                console.print("  [green]✓[/] Proceeding...")
                break
            elif response in ("s", "skip"):
                step.status = StepStatus.SKIPPED
                console.print("  [yellow]→[/] Gate skipped")
                break
            elif response in ("q", "quit"):
                console.print(
                    "  [red]✗ Pipeline paused — resume with 'heritage run --pipeline ...'[/]"
                )
                step.status = StepStatus.PENDING
                self._save_state()
                sys.exit(1)

    # ── Reporting ────────────────────────────────────────────────────────


# ── Helpers ────────────────────────────────────────────────────────────────────


def _run_subprocess(cmd: list[str], step_id: str, timeout: int = 3600) -> None:
    """Run a subprocess with passthrough stdout/stderr."""
    console = _get_console()
    console.print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    if result.returncode != 0:
        stderr_tail = result.stderr.strip()[-200:] if result.stderr else ""
        detail = (
            f"{stderr_tail}"
            if stderr_tail
            else result.stdout.strip()[-200:]
            if result.stdout
            else ""
        )
        msg = f"Step '{step_id}' exited with code {result.returncode}"
        if detail:
            msg += f": {detail}"
        raise RuntimeError(msg)


def _validate_project_id(project_id: str) -> None:
    """Reject project IDs that could traverse the filesystem."""
    if not project_id or ".." in project_id or "/" in project_id or "\\" in project_id:
        raise ValueError(
            f"Invalid project ID '{project_id}': must not contain '..', '/', or '\\'"
        )


def _get_console():
    """Get or create a cached Rich Console instance."""
    from rich.console import Console

    if not hasattr(_get_console, "_instance"):
        _get_console._instance = Console()
    return _get_console._instance
