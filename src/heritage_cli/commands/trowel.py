"""Trowel command dispatch — Desktop report review dashboard.

Registered as heritage_cli.commands.trowel in entry_points.
"""

tool_name = "trowel"
description = "Desktop report review dashboard"


def dispatch(args: list[str] | None = None) -> int:
    """Run trowel with the given CLI arguments.

    Returns subprocess exit code.
    """
    import shutil
    import subprocess
    import sys

    trowel_bin = shutil.which("trowel")
    if not trowel_bin:
        sys.stderr.write("Trowel is not installed.\n")
        sys.stderr.write("Install from: https://github.com/mabo-du/trowel\n")
        return 1

    cmd = [trowel_bin] + (args or sys.argv[2:])
    result = subprocess.run(cmd, check=True)
    return result.returncode
