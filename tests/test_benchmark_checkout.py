"""INV-006: external snapshots retain their recorded bytes on Windows checkouts."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def test_INV_006_external_snapshots_survive_autocrlf_checkout(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
    shutil.copyfile(root / ".gitattributes", repository / ".gitattributes")
    sources = json.loads((root / "benchmarks/external/manifest.json").read_text())["sources"]
    for source in sources:
        relative = Path("benchmarks/external") / source["path"]
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    subprocess.run(["git", "-c", "core.autocrlf=false", "add", "."], cwd=repository, check=True)
    checkout = tmp_path / "checkout"
    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=true",
            "checkout-index",
            "--all",
            f"--prefix={checkout.as_posix()}/",
        ],
        cwd=repository,
        check=True,
    )
    for source in sources:
        data = (checkout / "benchmarks/external" / source["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == source["sha256"]
