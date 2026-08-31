from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

PACKAGE_FILES = {
    "blazing_agents/__init__.py",
    "blazing_agents/_chat.py",
    "blazing_agents/_client.py",
    "blazing_agents/_completion.py",
    "blazing_agents/_downloads.py",
    "blazing_agents/_errors.py",
    "blazing_agents/_models.py",
    "blazing_agents/_object.py",
    "blazing_agents/_resources.py",
    "blazing_agents/_responses.py",
    "blazing_agents/_transport.py",
    "blazing_agents/_types.py",
    "blazing_agents/_version.py",
    "blazing_agents/py.typed",
}


def inspect_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        dist_info = metadata_name.removesuffix("METADATA")
        expected = PACKAGE_FILES | {
            f"{dist_info}METADATA",
            f"{dist_info}RECORD",
            f"{dist_info}WHEEL",
        }
        if names != expected:
            unexpected = sorted(names - expected)
            missing = sorted(expected - names)
            details = {"unexpected": unexpected, "missing": missing}
            msg = f"Unexpected wheel contents: {details}"
            raise RuntimeError(msg)
        metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_name))

    expected_metadata = {
        "Name": "blazing_agents",
        "Requires-Python": ">=3.11",
    }
    for name, expected_value in expected_metadata.items():
        if metadata[name] != expected_value:
            msg = f"Wheel metadata {name} must be {expected_value!r}"
            raise RuntimeError(msg)
    if metadata.get_all("Requires-Dist") != [
        "httpx<1,>=0.27",
        "pydantic<3,>=2",
    ]:
        raise RuntimeError("Wheel must have exactly HTTPX and Pydantic dependencies")


def _function_entries(
    source: Path,
    statement_lines: set[int],
) -> list[int]:
    entries: list[int] = []
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            if node.body.lineno in statement_lines:
                entries.append(node.body.lineno)
            continue
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if any(
            isinstance(decorator, ast.Name) and decorator.id == "overload"
            for decorator in node.decorator_list
        ):
            continue
        entry = next(
            (
                statement.lineno
                for statement in node.body
                if statement.lineno in statement_lines
            ),
            None,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def inspect_coverage(report: Path) -> None:
    coverage = json.loads(report.read_text())
    totals = coverage["totals"]
    statement_percent = (
        100 * totals["covered_lines"] / totals["num_statements"]
        if totals["num_statements"]
        else 100
    )
    line_percent = statement_percent
    branch_percent = (
        100 * totals["covered_branches"] / totals["num_branches"]
        if totals["num_branches"]
        else 100
    )
    function_count = 0
    covered_function_count = 0
    for filename, file_coverage in coverage["files"].items():
        executed_lines = set(file_coverage["executed_lines"])
        statement_lines = executed_lines | set(file_coverage["missing_lines"])
        entries = _function_entries(Path(filename), statement_lines)
        function_count += len(entries)
        covered_function_count += sum(entry in executed_lines for entry in entries)
    function_percent = (
        100 * covered_function_count / function_count if function_count else 100
    )
    if min(line_percent, statement_percent, branch_percent, function_percent) < 99:
        msg = (
            "Coverage must be at least 99% independently: "
            f"lines={line_percent:.2f}%, "
            f"statements={statement_percent:.2f}%, "
            f"branches={branch_percent:.2f}%, "
            f"functions={function_percent:.2f}%"
        )
        raise RuntimeError(msg)
    print(
        "Independent coverage: "
        f"lines={line_percent:.2f}%, "
        f"statements={statement_percent:.2f}%, "
        f"branches={branch_percent:.2f}%, "
        f"functions={function_percent:.2f}% "
        f"({covered_function_count}/{function_count})"
    )


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="blazing-agents-python-sdk-") as raw:
        temporary = Path(raw)
        distribution = temporary / "dist"
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(distribution)],
            cwd=project,
            check=True,
        )
        wheel = next(distribution.glob("blazing_agents-*.whl"))
        inspect_wheel(wheel)
        coverage_report = temporary / "coverage.json"
        command = [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            str(wheel),
            "--with",
            "pytest>=8.4,<9",
            "--with",
            "pytest-cov>=6.2,<7",
            "--",
            "python",
            "-m",
            "pytest",
            str(project / "tests"),
            "--cov=blazing_agents",
            "--cov-branch",
            "--cov-report=term-missing",
            f"--cov-report=json:{coverage_report}",
            "--cov-fail-under=99",
        ]
        environment = dict(os.environ)
        environment["COVERAGE_FILE"] = str(temporary / ".coverage")
        subprocess.run(command, cwd=temporary, env=environment, check=True)
        inspect_coverage(coverage_report)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
