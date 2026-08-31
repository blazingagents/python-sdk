from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_ENVIRONMENT_ALLOWLIST = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
    "TEMP",
    "TMP",
    "TMPDIR",
    "UV_CACHE_DIR",
)


def _runtime_environment() -> dict[str, str]:
    return {
        name: value
        for name in _ENVIRONMENT_ALLOWLIST
        if (value := os.environ.get(name)) is not None
    }


def _read_ready(host: subprocess.Popen[str]) -> dict[str, str]:
    assert host.stdout is not None
    while True:
        line = host.stdout.readline()
        if not line:
            stderr = host.stderr.read() if host.stderr is not None else ""
            raise RuntimeError(f"Integration host exited before ready:\n{stderr}")
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if isinstance(payload, dict) and payload.get("type") == "ready":
            return {str(name): str(value) for name, value in payload.items()}


def _stop_host(host: subprocess.Popen[str]) -> None:
    if host.poll() is not None:
        return
    assert host.stdin is not None
    try:
        host.stdin.write("stop\n")
        host.stdin.flush()
    except BrokenPipeError:
        pass
    try:
        host.wait(timeout=30)
    except subprocess.TimeoutExpired:
        host.terminate()
        try:
            host.wait(timeout=10)
        except subprocess.TimeoutExpired:
            host.kill()
            host.wait()


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    repository = project.parents[1]
    test_file = repository / "tests/integration/python-sdk/test_local_stack.py"
    host_file = repository / "servers/api/tests/integration/python-sdk/host.mts"

    for workspace in (
        "@blazing-agents/core",
        "@blazing-agents/sandbox-sdk",
        "@blazing-agents/server-core",
    ):
        subprocess.run(
            ["npm", "--workspace", workspace, "run", "build"],
            cwd=repository,
            check=True,
        )

    for command in (
        [
            "npm",
            "--workspace",
            "@blazing-agents/python-sdk",
            "run",
            "typecheck:integration",
        ],
        [
            "npm",
            "--workspace",
            "@blazing-agents/python-sdk",
            "run",
            "lint:integration",
        ],
    ):
        subprocess.run(command, cwd=repository, check=True)

    with tempfile.TemporaryDirectory(
        prefix="blazing-agents-python-sdk-integration-"
    ) as raw:
        temporary = Path(raw)
        distribution = temporary / "dist"
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(distribution)],
            cwd=project,
            check=True,
        )
        wheel = next(distribution.glob("blazing_agents-*.whl"))

        host = subprocess.Popen(
            ["node", "--experimental-strip-types", str(host_file)],
            cwd=repository,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_runtime_environment(),
        )
        try:
            ready = _read_ready(host)
            environment = _runtime_environment()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            for name, value in ready.items():
                if name != "type":
                    environment[f"BA_PYTHON_INTEGRATION_{name.upper()}"] = str(value)
            command = [
                "uv",
                "run",
                "--isolated",
                "--no-project",
                "--with",
                str(wheel),
                "--with",
                "pytest>=8.4,<9",
                "--",
                "python",
                "-m",
                "pytest",
                str(test_file),
                "-q",
                "-p",
                "no:cacheprovider",
            ]
            result = subprocess.run(
                command,
                cwd=temporary,
                env=environment,
                check=False,
            )
            if result.returncode != 0:
                raise SystemExit(result.returncode)
        finally:
            _stop_host(host)
            if host.returncode not in (0, None):
                stderr = host.stderr.read() if host.stderr is not None else ""
                if stderr:
                    print(stderr, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, StopIteration, RuntimeError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
