# heritage-cli

**Unified command-line interface for the HOARD heritage science ecosystem.**

This is an optional convenience tool. End users can run all HOARD functionality
directly via `hoard run`, `hoard export`, `hoard review`, etc. — `heritage-cli`
adds cross-tool orchestration and a unified entry point for users who work with
multiple ecosystem tools.

## Installation

```bash
pip install heritage-cli
```

## Commands

| Command | Routes to | Requires |
|---------|-----------|----------|
| `heritage run --project X` | `hoard run` | HOARD |
| `heritage run --project X --pipeline f.yaml` | Multi-tool pipeline | HOARD + optional tools |
| `heritage calibrate --project X` | `libby` | Libby |
| `heritage lithics --project X` | `dibble` | Dibble |
| `heritage review --project X` | Trowel GUI or HOARD TUI | Trowel or HOARD |
| `heritage matrix --project X` | `stratigraph` | StratiGraph |
| `heritage publish --project X` | HOARD Phase 5 export | HOARD |
| `heritage tools list` | Auto-discovery | — |

## Pipeline Orchestration

Declarative YAML pipeline files enable multi-tool workflows with human review
gates at key checkpoints:

```yaml
# pipeline.yaml
steps:
  - project: hoard
    phases: [0, 1, 2]
  - gate: review
    message: "Review the Harris Matrix in StratiGraph before proceeding"
  - project: hoard
    phases: [3, 4]
  - gate: review
    message: "Review the draft before final export"
  - project: hoard
    action: export
    formats: [docx, pdf]
```

```bash
heritage run --project stoneyfield_2026 --pipeline pipeline.yaml
```

Pipeline state is persisted to `pipeline_state.json` — resume after
interruption with the same command.

## Configuration

Shared settings in `~/.config/heritage/config.toml`:

```toml
[paths]
workspace = "~/heritage_workspace"

[defaults]
jurisdiction = "historic_england_cl3"
```

## Repository Architecture

This is an infrastructure repository. It is not a standalone product — it
provides cross-tool routing and orchestration for the HOARD ecosystem.

| Repository | Purpose |
|------------|---------|
| [HOARD](https://github.com/mabo-du/HOARD) | Main archaeological report pipeline |
| [heritage-types](https://github.com/mabo-du/heritage-types) | Shared data models and vocabulary |
| **heritage-cli** (this repo) | Unified CLI and pipeline orchestration |

## License

MIT
