# heritage-cli

Unified command-line orchestrator for the heritage science open-source ecosystem. Runs multi-tool archaeological workflows as a single command.

## What It Does

`heritage` is a thin orchestration layer. It reads a declarative `pipeline.yaml` file and invokes HOARD, StratiGraph, Libby, and other tools in the correct order, passing workspace paths between them and pausing at human review gates.

It does **not** do any data processing itself — that stays in the individual tools.

## Installation

```bash
pip install heritage-cli
```

Requires the tools you intend to use to also be installed (`hoard`, `libby`, etc.).

Or install with specific tool dependencies:

```bash
pip install heritage-cli[hoard,libby,stratigraph,dibble,trowel]
```

Install all ecosystem tools at once:

```bash
pip install heritage-cli[hoard,libby,stratigraph,dibble,trowel]
```

## Usage

```bash
# Run a full pipeline from a definition file
heritage run --pipeline pipeline.yaml --project my_site_2026

# If interrupted, heritage automatically resumes from the last completed step

# List installed and discoverable heritage tools
heritage tools

# Run tools individually (requires the tool to be installed)
heritage calibrate --project my_site_2026
heritage lithics --project my_site_2026
heritage review --project my_site_2026
heritage matrix --project my_site_2026
heritage publish --project my_site_2026
```

## Pipeline Definition

See `pipeline.example.yaml` for a full example. The basic structure:

```yaml
steps:
  - id: digitise
    project: hoard
    phases: [0, 1]

  - id: review_digitisation
    gate: review
    message: "Review digitised context sheets before proceeding"
    action: "hoard review --project {project_id}"
    depends_on: [digitise]

  - id: spatial
    project: hoard
    phases: [2]
    depends_on: [review_digitisation]

  - id: calibrate
    project: libby
    action: calibrate
    input: output/01_digitised/samples.json
    depends_on: [review_digitisation]

  - id: draft
    project: hoard
    phases: [3, 4]
    depends_on: [spatial, calibrate]

  - id: review_draft
    gate: review
    message: "Review the draft before final export"
    depends_on: [draft]

  - id: export
    project: hoard
    action: export
    formats: [docx, pdf]
    depends_on: [review_draft]
```

## Pipeline State

Progress is saved to `$XDG_DATA_HOME/heritage/workspaces/{project_id}/pipeline_state.json`. If a run is interrupted, the next `heritage run` invocation automatically resumes from the last completed step.

## Ecosystem

`heritage-cli` is part of a wider open-source heritage science toolkit:

| Tool | Purpose |
|------|---------|
| [hoard](https://github.com/mabo-du/hoard) | AI-powered archaeological report generation |
| [stratigraph](https://github.com/mabo-du/stratigraph) | Harris Matrix visualisation |
| [libby](https://github.com/mabo-du/libby) | Radiocarbon calibration |
| [cache-and-carry](https://github.com/mabo-du/cache-and-carry) | Collections & vocabulary management |
| [heritage-types](https://github.com/mabo-du/heritage-types) | Shared data schemas |

## Status

| Command | Status |
|---------|--------|
| `heritage run` | ✅ Implemented |
| `heritage calibrate` | ✅ Implemented |
| `heritage lithics` | ✅ Implemented |
| `heritage review` | ✅ Implemented |
| `heritage matrix` | ✅ Implemented |
| `heritage publish` | ✅ Implemented |
| `heritage tools` | ✅ Implemented |
| `heritage pipeline-status` | ✅ Implemented |

## License

MIT

## Development

```bash
# Clone and install in dev mode
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Type check
mypy src/
```
