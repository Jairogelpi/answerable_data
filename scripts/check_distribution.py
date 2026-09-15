"""Install the built wheel and check its public interfaces outside the checkout."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    wheels = list((Path(__file__).resolve().parents[1] / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel in dist; build in a clean checkout.")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    with tempfile.TemporaryDirectory(prefix="answerable-wheel-") as folder:
        root = Path(folder)
        venv = root / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, env=env)
        bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        python = str(bin_dir / ("python.exe" if os.name == "nt" else "python"))
        cli = str(bin_dir / ("answerable.exe" if os.name == "nt" else "answerable"))

        def run(args: list[str]) -> None:
            subprocess.run(args, check=True, cwd=root, env=env)

        run([python, "-m", "pip", "install", f"{wheels[0]}[mcp]"])
        run(
            [
                python,
                "-c",
                "import json, subprocess, sys; from pathlib import Path; "
                "from importlib.metadata import version; import answerable; "
                "v=version('answerable-data'); "
                "assert Path(answerable.__file__).is_relative_to(Path(sys.prefix)); "
                "assert answerable.__version__ == v; "
                "d=json.loads(subprocess.check_output([sys.argv[1], '--json', 'doctor'])); "
                "assert d['version'] == v and d['status'] == 'ready'; "
                "from answerable.interfaces.mcp_stdio import build_server; build_server(); "
                "print('Installed wheel versions, CLI and MCP: PASS', v)",
                cli,
            ]
        )
        run([cli, "benchmark", "mutations", "--output", str(root / "benchmark")])


if __name__ == "__main__":
    main()
