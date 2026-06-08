"""HOARD command dispatch — run pipeline phases.

Registered as heritage_cli.commands.hoard in entry_points.
"""

tool_name = "hoard"
description = "Heritage Observation And Report Drafter — AI pipeline"


def dispatch(args: list[str] | None = None) -> int:
    """Run hoard with the given CLI arguments.

    Returns subprocess exit code.
    """
    import subprocess
    import sys
    cmd = ["hoard"] + (args or sys.argv[2:])
    result = subprocess.run(cmd)
    return result.returncode
