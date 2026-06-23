"""StratiGraph command dispatch — Harris Matrix visualisation.

Registered as heritage_cli.commands.stratigraph in entry_points.
"""

tool_name = "stratigraph"
description = "Harris Matrix visualisation and validation"


def dispatch(args: list[str] | None = None) -> int:
    """Run stratigraph with the given CLI arguments.

    Returns subprocess exit code.
    """
    import shutil
    import subprocess
    import sys

    stratigraph_bin = shutil.which("stratigraph")
    if not stratigraph_bin:
        sys.stderr.write("StratiGraph is not installed.\n")
        sys.stderr.write("Install from: https://github.com/mabo-du/stratigraph\n")
        return 1

    cmd = [stratigraph_bin] + (args or sys.argv[2:])
    result = subprocess.run(cmd, check=True)
    return result.returncode
