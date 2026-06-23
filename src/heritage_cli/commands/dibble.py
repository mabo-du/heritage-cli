"""Dibble command dispatch — Lithic analysis.

Registered as heritage_cli.commands.dibble in entry_points.
"""

tool_name = "dibble"
description = "Lithic analysis"


def dispatch(args: list[str] | None = None) -> int:
    """Run dibble with the given CLI arguments.

    Returns subprocess exit code.
    """
    import shutil
    import subprocess
    import sys

    dibble_bin = shutil.which("dibble")
    if not dibble_bin:
        sys.stderr.write("Dibble is not installed.\n")
        sys.stderr.write("Install with: pip install dibble\n")
        return 1

    cmd = [dibble_bin] + (args or sys.argv[2:])
    result = subprocess.run(cmd, check=True)
    return result.returncode
