#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file.

Usage:
    python scripts/export_openapi.py [output_path]

Defaults to writing ``openapi.json`` in the repository root.
"""

import json
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent.parent / "openapi.json"
schema = app.openapi()
output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
print(f"OpenAPI schema written to {output}")
