from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas"
REQUIRED_KEYS = {"$schema", "$id", "title", "type", "required", "properties"}


def main() -> int:
    paths = sorted(SCHEMA_ROOT.glob("v*/*.schema.json"))
    if not paths:
        raise SystemExit("no public schemas found")

    identifiers: set[str] = set()
    for path in paths:
        schema = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED_KEYS - set(schema)
        if missing:
            raise SystemExit(f"{path}: missing keys {sorted(missing)}")
        identifier = schema["$id"]
        if identifier in identifiers:
            raise SystemExit(f"duplicate schema id: {identifier}")
        identifiers.add(identifier)
        if schema["$schema"] != "https://json-schema.org/draft/2020-12/schema":
            raise SystemExit(f"{path}: unsupported JSON Schema dialect")
        if schema.get("additionalProperties") is not False:
            raise SystemExit(f"{path}: public root must reject unknown properties")

    print(f"schemas ok: {len(paths)} files, {len(identifiers)} unique ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
