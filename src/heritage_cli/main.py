"""main.py — Heritage CLI entry point and command tree.

Uses Typer for the command hierarchy with Rich for output formatting.
Routes commands to sibling project executables or Python packages.

Usage:
    heritage --help
    heritage run --project X --phase 0
    heritage run --project X --auto
    heritage calibrate --project X
    heritage lithics --project X --input ./scans/
    heritage review --project X
    heritage matrix --project X
    heritage publish --project X --format docx,pdf
    heritage tools list
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from heritage_cli import __version__

app = typer.Typer(
    name="heritage",
    help="Heritage science ecosystem CLI — orchestrates HOARD, StratiGraph, Trowel, Libby, and Dibble",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# ── Version callback ─────────────────────────────────────────────────────────


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"heritage-cli v{__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        callback=_version_callback,
    ),
) -> None:
    """Heritage science ecosystem CLI."""


# ── Config ───────────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Load ~/.config/heritage/config.toml, returning defaults on failure."""
    import tomllib

    config_path = Path.home() / ".config" / "heritage" / "config.toml"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def config_default(key: str, fallback: str) -> str:
    """Read a dotted key from heritage config.toml, returning fallback on miss.

    Key format: "section.key", e.g. "defaults.jurisdiction", "paths.workspace".
    """
    cfg = load_config()
    parts = key.split(".")
    node = cfg
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return fallback
    return node if isinstance(node, str) else fallback


def find_tool(name: str) -> str | None:
    """Find an installed tool's executable path via shutil.which."""
    import shutil

    return shutil.which(name)


# ── Commands ─────────────────────────────────────────────────────────────────


@app.command()
def run(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    phase: int | None = typer.Option(None, "--phase", help="Run a single phase only"),
    from_phase: int | None = typer.Option(
        None, "--from-phase", help="Run from this phase onward"
    ),
    pipeline: str | None = typer.Option(
        None, "--pipeline", "-P", help="Path to pipeline YAML file"
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Run full pipeline from Phase 0 (or skip review gates with --pipeline)",
    ),
    input_dir: str = typer.Option("./input", "--input", "-i", help="Input directory"),
    strict: bool = typer.Option(
        False, "--strict", "-s", help="Halt on schema validation failure"
    ),
    extractor: str = typer.Option(
        "glm-ocr", "--extractor", "-e", help="Extraction model"
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Run the HOARD pipeline (or a single phase, or a multi-tool pipeline).

    Use --pipeline to run a declarative multi-tool pipeline YAML with
    automated steps and human review gates.

    Examples:
        heritage run --project X --phase 0       # Single phase
        heritage run --project X --auto           # Full HOARD pipeline
        heritage run --project X --pipeline pipe.yaml   # Multi-tool pipeline
    """
    if ".." in project or "/" in project or "\\" in project:
        console.print(
            f"[red]✗[/] Invalid project ID '{project}': must not contain '..', '/', or '\\'"
        )
        raise typer.Exit(1)
    if pipeline:
        from heritage_cli.orchestrator import PipelineOrchestrator

        orch = PipelineOrchestrator(
            pipeline_path=pipeline,
            project_id=project,
            workspace=workspace,
            auto=auto,
            jurisdiction=config_default(
                "defaults.jurisdiction", "historic_england_cl3"
            ),
        )
        try:
            orch.load()
            orch.run()
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]✗[/] {e}")
            raise typer.Exit(1)
        return

    hoard_bin = find_tool("hoard")
    if hoard_bin:
        import subprocess

        cmd = [hoard_bin, "run", "--project", project, "--workspace", workspace]
        if phase is not None:
            cmd.extend(["--phase", str(phase)])
        if from_phase is not None:
            cmd.extend(["--from-phase", str(from_phase)])
        if input_dir:
            cmd.extend(["--input", input_dir])
        if strict:
            cmd.append("--strict")
        if extractor:
            cmd.extend(["--extractor", extractor])
        if auto:
            if phase is not None or from_phase is not None:
                console.print(
                    "[yellow]⚠[/] --auto is incompatible with --phase and --from-phase"
                )
                console.print(
                    "  Use either --auto for full pipeline or --phase/--from-phase for a specific range"
                )
                raise typer.Exit(1)
            cmd.extend(["--from-phase", "0"])
        console.print(f"[blue]→[/] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=3600)
    else:
        # Fallback: import and run HOARD directly
        try:
            from hoard.cli.run import run_pipeline, run_single_phase
            from hoard.config import Config

            cfg = Config(
                project_id=project,
                project_name=project,
                jurisdiction=config_default(
                    "defaults.jurisdiction", "historic_england_cl3"
                ),
                workspace_root=Path(workspace).resolve(),
                input_dir=Path(input_dir).resolve(),
                strict=strict,
                extractor=extractor,
            )
            if phase is not None:
                run_single_phase(cfg, phase)
            else:
                run_pipeline(cfg)
        except ImportError:
            console.print("[red]✗[/] HOARD not installed. Run: pip install hoard")


@app.command()
def calibrate(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    input_file: str = typer.Option("", "--input", "-i", help="Samples JSON file path"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Calibrate radiocarbon samples using Libby.

    Reads sample data from the project workspace or specified input file,
    runs Libby calibration, and writes calibrated dates back to the workspace.
    """
    libby_bin = find_tool("libby")
    if libby_bin:
        import subprocess

        input_path = input_file or f"{workspace}/{project}/01_digitised/samples.json"
        cmd = [
            libby_bin,
            "calibrate",
            "--input",
            input_path,
            "--workspace",
            f"{workspace}/{project}",
        ]
        console.print(f"[blue]→[/] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=300)
    else:
        console.print(
            "[yellow]ℹ[/] Libby not installed. Install with: pip install libby"
        )
        console.print("  Or manually calibrate samples at a Libby web instance.")


@app.command(name="lithics")
def lithics(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    input_dir: str = typer.Option(
        "./scans", "--input", "-i", help="Directory with 3D scans or photos"
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Run lithic analysis using Dibble.

    Processes 3D scans or photographs through Dibble's classification pipeline
    and writes results into the project workspace for HOARD Phase 3 consumption.
    """
    dibble_bin = find_tool("dibble")
    if dibble_bin:
        import subprocess

        cmd = [
            dibble_bin,
            "process",
            "--input",
            input_dir,
            "--output",
            f"{workspace}/{project}/02_spatial/lithics/",
        ]
        console.print(f"[blue]→[/] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=3600)
    else:
        console.print(
            "[yellow]ℹ[/] Dibble not installed. Install with: pip install dibble"
        )
        console.print("  Or manually add lithic analysis to the specialist appendices.")


@app.command()
def review(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r", help="Reset all review decisions"
    ),
) -> None:
    """Open the interactive review dashboard.

    Delegates to Trowel (if installed as desktop app) or HOARD's terminal
    review dashboard (CLI fallback). Both share the same flag data format.
    """
    trowel_bin = find_tool("trowel")
    if trowel_bin:
        import subprocess

        cmd = [trowel_bin, "open", "--project", project, "--workspace", workspace]
        if reset:
            cmd.append("--reset")
        console.print(f"[blue]→[/] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=300)
    else:
        # Fallback: use HOARD's review dashboard
        try:
            from hoard.config import Config

            hoard_cfg = Config(
                project_id=project,
                project_name=project,
                jurisdiction=config_default(
                    "defaults.jurisdiction", "historic_england_cl3"
                ),
                workspace_root=Path(workspace).resolve(),
                input_dir=Path("./input"),
            )
            from hoard.review import ReviewSession

            session = ReviewSession(hoard_cfg)
            session.load()
            if session.total == 0:
                console.print(f"[yellow]ℹ[/] No flagged items for project '{project}'.")
                return
            session.run_interactive()
        except ImportError:
            console.print(
                "[red]✗[/] Neither Trowel nor HOARD review dashboard available."
            )
            console.print("  Install HOARD: pip install hoard")


@app.command()
def matrix(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Open the Harris Matrix in StratiGraph.

    Imports HOARD Phase 1 context data into StratiGraph for interactive
    Harris Matrix visualisation, validation, and EEDP export.
    """
    stratigraph_bin = find_tool("stratigraph")
    if stratigraph_bin:
        import subprocess

        cmd = [
            stratigraph_bin,
            "import",
            "--data",
            f"{workspace}/{project}/01_digitised/",
        ]
        console.print(f"[blue]→[/] Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=300)
    else:
        console.print("[yellow]ℹ[/] StratiGraph not installed.")
        console.print("  Install from: https://github.com/mabo-du/stratigraph")
        console.print(f"  Or import {workspace}/{project}/01_digitised/ manually.")


@app.command()
def publish(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    fmt: str = typer.Option(
        "docx,pdf", "--format", "-f", help="Output formats (comma-separated)"
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Publish the final report (Phase 5 assembly + export).

    Delegates to HOARD's Phase 5 export, which generates DOCX, PDF/A-2b,
    TEI-XML, and ZIP outputs from the assembled report data.
    """
    try:
        from hoard.config import load_config

        cfg = load_config(project, Path(workspace))
        if cfg is None:
            console.print(f"[red]✗[/] Project '{project}' not found at {workspace}")
            console.print("  Run 'hoard init' first.")
            raise typer.Exit(1)

        from hoard.phases.phase5 import run_phase5

        formats = [f.strip() for f in fmt.split(",")]
        console.print(
            f"[blue]→[/] Publishing [bold]{project}[/] as: {', '.join(formats)}"
        )
        result = run_phase5(cfg, formats=formats)
        if result is None:
            console.print("[yellow]ℹ[/] No output generated. Run the pipeline first.")
            raise typer.Exit(1)
        export_paths = result.get("export_paths", {})
        if export_paths:
            console.print("[green]✓[/] Published:")
            for name, path in export_paths.items():
                console.print(f"  • {name}: {path}")
        else:
            console.print("[yellow]ℹ[/] No output generated. Run the pipeline first.")
    except ImportError:
        console.print("[red]✗[/] HOARD not installed. Run: pip install hoard")


# ── Pipeline Status ──────────────────────────────────────────────────────────


@app.command(name="pipeline-status")
def pipeline_status(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w", help="Workspace root"
    ),
) -> None:
    """Show the status of the most recent pipeline run for a project."""

    # Find the most recent pipeline state file
    state_dir = Path(workspace) / project
    state_file = state_dir / "pipeline_state.json"
    if not state_file.exists():
        console.print(f"[yellow]ℹ[/] No pipeline state found for project '{project}'")
        console.print(
            f"  Run [bold]heritage run --project {project} --pipeline <file>[/] first"
        )
        return

    try:
        import json

        data = json.loads(state_file.read_text())
        console.print(f"[bold]Pipeline Status:[/] {data.get('project_id', project)}")
        console.print(f"  State file:  {state_file}")
        console.print(f"  Pipeline:    {data.get('pipeline', 'unknown')}")
        console.print(f"  Last update: {data.get('updated_at', 'unknown')}")
        console.print()
        steps = data.get("steps", {})
        console.print(f"[bold]Steps ({len(steps)}):[/]")
        for step_id, status in steps.items():
            icon = {
                "pending": "○",
                "running": "→",
                "complete": "✓",
                "skipped": "−",
                "failed": "✗",
                "blocked": "⊘",
            }
            marker = icon.get(status, "?")
            console.print(f"  {marker} {step_id}: {status}")
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[red]✗[/] Failed to read pipeline state: {e}")
        raise typer.Exit(1)


# ── Tools sub-command ────────────────────────────────────────────────────────


@app.command(name="tools")
def tools_list() -> None:
    """List installed heritage ecosystem tools and their status."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    table = Table(title="Heritage Ecosystem Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Installed", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Description")

    tools = [
        ("hoard", find_tool("hoard"), "HOARD pipeline"),
        ("stratigraph", find_tool("stratigraph"), "Harris Matrix editor"),
        ("trowel", find_tool("trowel"), "Desktop report drafter"),
        ("libby", find_tool("libby"), "Radiocarbon calibration"),
        ("dibble", find_tool("dibble"), "Lithic analysis"),
    ]

    # Fetch versions in parallel to avoid serial 5s timeouts
    def _get_version(name: str) -> str:
        import subprocess

        try:
            result = subprocess.run(
                [name, "--version"], capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip() or result.stderr.strip()
            version = version[:30]
            if "Traceback" in version or "Error" in version:
                version = "?"
            return version
        except (OSError, subprocess.TimeoutExpired):
            return "?"

    versions: dict[str, str] = {}
    installed_names = [t[0] for t in tools if t[1]]
    if installed_names:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(_get_version, name): name for name in installed_names}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    versions[name] = future.result()
                except Exception:
                    versions[name] = "?"

    for name, installed, desc in tools:
        status = "[green]✓[/]" if installed else "[red]✗[/]"
        version = versions.get(name, "-") if installed else "-"
        table.add_row(name, status, version or "-", desc)

    console.print(table)
    console.print("\n[yellow]ℹ[/] Run [bold]pip install <tool>[/] for tools marked ✗")


# ── Entry point ──────────────────────────────────────────────────────────────


if __name__ == "__main__":
    app()
