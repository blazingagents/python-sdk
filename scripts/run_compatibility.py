from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Run the installed wheel's behavioral suite for one Python interpreter."""
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(
        prefix="blazing-agents-python-sdk-compatibility-"
    ) as raw:
        temporary = Path(raw)
        distribution = temporary / "dist"
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(distribution)],
            cwd=project,
            check=True,
        )
        wheel = next(distribution.glob("blazing_agents-*.whl"))
        subprocess.run(
            [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--python",
                sys.executable,
                "--with",
                str(wheel),
                "--with",
                "pytest>=8.4,<9",
                "--",
                "python",
                "-m",
                "pytest",
                str(project / "tests"),
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            cwd=temporary,
            check=True,
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, StopIteration, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            sys.exit(error.returncode)
        print(error, file=sys.stderr)
        sys.exit(1)
