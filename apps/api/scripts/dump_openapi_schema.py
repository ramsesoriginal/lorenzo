"""Dumps this app's current OpenAPI schema to a file - no live server, no
database, no env vars needed, since app.openapi() is a pure introspection
over already-registered routes/Pydantic models. Used by CI's openapi-diff
job (see .github/workflows/ci.yml) to compare a PR's schema against its base
branch's; main.py's stable operationIds (generate_unique_id_function) exist
specifically to make that diff meaningful.

Dev/CI-only - never shipped, never registered as a [project.scripts] entry
point.
"""

from __future__ import annotations

import argparse
import json

from lorenzo_api.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="openapi.json",
        help="File to write the schema to (default: openapi.json).",
    )
    args = parser.parse_args()

    with open(args.output, "w") as f:
        json.dump(app.openapi(), f, indent=2)
    print(f"Wrote OpenAPI schema to {args.output}")


if __name__ == "__main__":
    main()
