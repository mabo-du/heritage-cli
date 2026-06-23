"""Libby command dispatch — Radiocarbon calibration.

Registered as heritage_cli.commands.libby in entry_points.
"""

tool_name = "libby"
description = "Radiocarbon calibration"


def dispatch(args: list[str] | None = None) -> int:
    """Run libby with the given CLI arguments.

    Returns subprocess exit code.
    """
    import shutil
    import subprocess
    import sys

    libby_bin = shutil.which("libby")
    if not libby_bin:
        sys.stderr.write("Libby is not installed.\n")
        sys.stderr.write("Install with: pip install libby\n")
        return 1

    cmd = [libby_bin] + (args or sys.argv[2:])
    result = subprocess.run(cmd, check=True)
    return result.returncode
