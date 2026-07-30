from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACEABILITY = ROOT / "requirements" / "traceability.yaml"
REQUIREMENT = re.compile(r"^  ([A-Z]+(?:-[A-Z]+)*-\d+):$", re.MULTILINE)
PATH_ITEM = re.compile(r'"([^"]+\.(?:py|yaml|json))"')


def main() -> int:
    content = TRACEABILITY.read_text(encoding="utf-8")
    requirements = REQUIREMENT.findall(content)
    if not requirements:
        raise SystemExit("traceability file contains no requirements")

    missing: list[str] = []
    for relative in PATH_ITEM.findall(content):
        if not (ROOT / relative).is_file():
            missing.append(relative)

    if missing:
        raise SystemExit(
            "traceability references missing files: " + ", ".join(sorted(set(missing)))
        )

    tests = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py")
    )
    untested = [
        requirement
        for requirement in requirements
        if requirement not in tests and requirement.replace("-", "_") not in tests
    ]
    if untested:
        raise SystemExit("requirements missing from tests: " + ", ".join(untested))

    print(f"traceability ok: {len(requirements)} requirements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
