from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas" / "v1"


class PublicSchemaTests(unittest.TestCase):
    def test_phase_2_all_public_schemas_are_valid_json_with_stable_ids(self) -> None:
        paths = sorted(SCHEMAS.glob("*.schema.json"))
        self.assertEqual(len(paths), 21)
        for path in paths:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(
                schema["$id"],
                f"https://answerable.dev/schemas/v1/{path.name}",
            )
            self.assertFalse(schema["additionalProperties"])
            self.assertTrue(schema["required"])

    def test_phase_2_schema_ids_are_unique(self) -> None:
        schemas = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(SCHEMAS.glob("*.schema.json"))
        ]
        identifiers = [schema["$id"] for schema in schemas]
        self.assertEqual(len(identifiers), len(set(identifiers)))


if __name__ == "__main__":
    unittest.main()
