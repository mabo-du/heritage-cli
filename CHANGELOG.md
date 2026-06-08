# Changelog

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
- **Tool discovery** — `heritage tools list` auto-detects installed ecosystem
  tools via `shutil.which` and reports version/status
- **Centralised config** — reads `~/.config/heritage/config.toml` for shared
  ecosystem settings (workspace root, defaults, per-tool overrides)

[1.0.0]: https://github.com/mabo-du/heritage-cli/releases/tag/v1.0.0
