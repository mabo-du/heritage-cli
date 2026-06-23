# Changelog

## [1.0.2] — 2026-06-23

### Added

- **HOARD API contract tests** — 14 integration tests validate that all 6 symbols
  heritage-cli imports from HOARD (`Config`, `load_config`, `run_pipeline`,
  `run_single_phase`, `ReviewSession`, `run_phase5`) match the actual API signatures.
  Parameter names verified (`config` not `cfg`), kwargs accepted, methods present.
- **Entry-point plugin discovery tests** — verifies all 5 `heritage.tools` entry
  points resolve to importable modules with correct `tool_name` and `dispatch()`.
- **Pipeline end-to-end tests** — parses the shipped `pipeline.example.yaml`,
  validates all step kinds present (HOARD, GATE, EXPORT), and round-trips state
  with all 6 `StepStatus` values.
- **pytest markers** — `integration` marker for tests requiring sibling packages;
  CI runs unit tests on every tag, integration tests on demand.

### Fixed

- **CI publish workflow** — removed `--system` flag from `uv pip install`
  (`setup-uv` provides a managed venv; `--system` was rejected). Added
  `uv pip install -e .` step so the test suite can import `heritage_cli`.
- **`pipeline.example.yaml`** — export step now uses `project: export` (matches
  `StepKind.EXPORT`) instead of non-functional `project: hoard` with `action: export`.

## [1.0.1] — 2026-06-23

### Fixed

- **PyYAML dependency** — added `pyyaml>=6` to required dependencies; the headline
  `--pipeline` feature no longer crashes with `ModuleNotFoundError` on a clean install
- **Subprocess exit codes** — all `subprocess.run` calls now use `check=True` or
  inspect `returncode`; child tool failures are no longer silently discarded
- **Entry-point plugin modules** — `stratigraph.py`, `trowel.py`, `libby.py`,
  `dibble.py` command stubs now ship; all 5 `heritage.tools` entry points resolve
- **README pipeline schema** — pipeline YAML example corrected to match the
  actual parser (`project:`, `phases:`, `gate:`, `depends_on:`)
- **`--resume` flag** — removed from documentation (resume is automatic via saved state)
- **`heritage tools list`** — corrected to `heritage tools` in all docs
- **State file key** — `pipeline-status` now reads the correct key `project_id`
- **`StepKind` enum** — added `STRATIGRAPH` and `TROWEL` values; pipeline steps
  referencing these tools no longer crash at parse time
- **Config wiring** — `load_config()` now actually reads from `~/.config/heritage/config.toml`;
  jurisdiction, extractor, and workspace defaults are no longer hardcoded
- **Argument injection** — `{project_id}` and `{workspace}` placeholders are now
  substituted before `shlex.split`, preventing flag injection via crafted IDs
- **Subprocess timeouts** — all delegated tool calls now have explicit timeouts
  (3600s for pipelines, 300s for interactive tools)
- **Gate quit exit code** — quitting a review gate now exits 1 instead of 0
- **State file atomicity** — `_save_state` uses `shutil.move` instead of `Path.rename`
  for cross-filesystem safety
- **None-guard** — `publish` command handles `run_phase5` returning `None` gracefully
- **`--auto` + `--phase` conflict** — passing both flags together now errors with
  a clear message instead of sending conflicting arguments to the child tool
- **StepKind validation** — unknown `project:` values in pipeline YAML now raise
  a clear error listing valid options, instead of silently skipping
- **`started_at` timestamp** — pipeline state JSON now records when a run first started
- **Corrupt state handling** — `_load_state` warns when a state file is corrupt
  instead of silently starting fresh
- **`pipeline-status` exit code** — exits 1 on corrupt state files
- **Console caching** — Rich Console instance reused instead of recreated per call
- **`fritts`/`argus`** — undocumented tools removed from `heritage tools` listing
- **`.gitignore`** — added `.ruff_cache/`, `.pytest_cache/`, `.benchmarks/`,
  `.beads/`, `.ctx/` patterns

### Added

- **Test suite** — 27 tests covering smoke checks, parser validation, state
  persistence, project ID validation, and argument injection prevention
- **CI test step** — `publish.yml` runs tests before building/publishing
- **Project ID validation** — `project_id` values containing `..`, `/`, or `\`
  are rejected to prevent path traversal
- **Optional dependency extras** — `heritage-cli[hoard]`, `[libby]`, etc. for
  per-tool dependency management
- **`[tool.mypy]`** — mypy type checker configuration in `pyproject.toml`

### Changed

- **Parallel version probes** — `heritage tools` fetches tool versions concurrently
  instead of serially (worst-case from 35s to 5s)
- **GitHub Actions pinned to SHAs** — all action references use full commit SHAs
- **Dependencies** — removed unused `platformdirs` and `tomli`
- **Removed dead code** — `entry_point()`, `status_report()`, `print()` debug
  statements removed

### Security

- **Argument injection** — `{project_id}` substitution reordered to prevent
  flag injection (see Fixes above)
- **Path traversal** — `project_id` validated before directory creation
- **Subprocess timeouts** — prevents hung child processes from blocking the CLI indefinitely

## [1.0.0] — 2026-06-09

### Added

- **Unified CLI** — single `heritage` command routing to all ecosystem tools:
  `heritage run` (HOARD pipeline), `calibrate` (Libby), `lithics` (Dibble),
  `review` (Trowel/HOARD dashboard), `matrix` (StratiGraph), `publish` (HOARD export)
- **Binary-first dispatch** — tries installed tool binary first, falls back to
  Python import
- **Pipeline orchestration** — `heritage run --pipeline <file>` for declarative
  multi-tool YAML pipelines with checkpoint-based execution, human review gates,
  state persistence for resumability, and graceful degradation for missing tools
- **Tool discovery** — `heritage tools` auto-detects installed ecosystem
  tools via `shutil.which` and reports version/status
- **Centralised config** — reads `~/.config/heritage/config.toml` for shared
  ecosystem settings (workspace root, defaults, per-tool overrides)

[1.0.2]: https://github.com/mabo-du/heritage-cli/releases/tag/v1.0.2
[1.0.1]: https://github.com/mabo-du/heritage-cli/releases/tag/v1.0.1
[1.0.0]: https://github.com/mabo-du/heritage-cli/releases/tag/v1.0.0
