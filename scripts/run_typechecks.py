from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(
    command: list[str],
    *,
    cwd: Path,
    expected_success: bool,
) -> None:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=cwd,
        text=True,
    )
    if (result.returncode == 0) != expected_success:
        expectation = "pass" if expected_success else "reject the example"
        output = f"{result.stdout}{result.stderr}".strip()
        msg = f"{' '.join(command)} did not {expectation}\n{output}"
        raise RuntimeError(msg)


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    valid = project / "typing" / "valid.py"
    invalid = [
        project / "typing" / "invalid_ambiguous.py",
        project / "typing" / "invalid_artifacts_user_id.py",
        project / "typing" / "invalid_chat_regenerate_client.py",
        project / "typing" / "invalid_chat_regenerate.py",
        project / "typing" / "invalid_chat_version.py",
        project / "typing" / "invalid_agent_configuration.py",
        project / "typing" / "invalid_request_literal.py",
        project / "typing" / "invalid_request_unknown.py",
        project / "typing" / "invalid_simultaneous.py",
        project / "typing" / "invalid_workspace_none.py",
        project / "typing" / "invalid_workspace_none_request.py",
    ]
    run(
        ["mypy", "--no-incremental", "src", "tests", str(valid)],
        cwd=project,
        expected_success=True,
    )
    run(
        ["pyright", "src", "tests", str(valid)],
        cwd=project,
        expected_success=True,
    )
    for example in invalid:
        run(
            ["mypy", "--no-incremental", str(example)],
            cwd=project,
            expected_success=False,
        )
        run(["pyright", str(example)], cwd=project, expected_success=False)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
