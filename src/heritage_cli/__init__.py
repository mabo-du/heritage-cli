"""heritage-cli — Unified CLI for the heritage science open-source ecosystem.

Provides a single `heritage` command that routes to sibling projects:
    heritage run       → hoard run (HOARD pipeline)
    heritage calibrate → libby (radiocarbon calibration)
    heritage lithics   → dibble (lithic analysis)
    heritage review    → trowel (review dashboard)
    heritage matrix    → stratigraph (Harris Matrix)
    heritage publish   → hoard export (final report)
    heritage tools     → list installed ecosystem tools

Usage:
    heritage --help
    heritage run --project X --phase 0
    heritage calibrate --project X --input samples.json
    heritage tools     → list installed ecosystem tools

Configuration: ~/.config/heritage/config.toml
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("heritage-cli")
except PackageNotFoundError:
    __version__ = "1.0.0"
