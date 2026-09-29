"""Every entry in the OPS table matches apps/api's real OpenAPI document (ADR 0137).

apps/api/openapi.json is git-ignored, so this needs it dumped first (`mise run
//apps/api:openapi-schema`). `mise run check-schema` dumps it and sets LORENZO_REQUIRE_SCHEMA, so
in CI a missing schema fails instead of skipping.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest

from lorenzo_cli.client.ops import ALL_OPS, Op

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "api" / "openapi.json"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    if not SCHEMA_PATH.exists():
        if os.environ.get("LORENZO_REQUIRE_SCHEMA"):
            pytest.fail(
                f"{SCHEMA_PATH} is missing: dump it with `mise run //apps/api:openapi-schema`."
            )
        pytest.skip(
            "apps/api/openapi.json isn't dumped; run `mise run check-schema` to check the ops."
        )
    loaded: dict[str, Any] = json.loads(SCHEMA_PATH.read_text())
    return loaded


def _normal(name: str) -> str:
    """Schema names and generated class names differ in punctuation only (`Page_X_` / `PageX`)."""
    return re.sub(r"\W|_", "", name)


def _ref_name(schema_part: dict[str, Any] | None) -> str | None:
    if not schema_part:
        return None
    if "$ref" in schema_part:
        return _normal(schema_part["$ref"].rsplit("/", 1)[-1])
    if schema_part.get("type") == "array":
        inner = _ref_name(schema_part.get("items"))
        return f"list[{inner}]"
    return None


def _expected_name(response_type: Any) -> str | None:
    if response_type is None:
        return None
    if get_origin(response_type) is list:
        return f"list[{_normal(get_args(response_type)[0].__name__)}]"
    return _normal(response_type.__name__)


@pytest.mark.parametrize("op", ALL_OPS, ids=lambda op: op.operation_id)
def test_op_matches_the_schema(op: Op[Any], schema: dict[str, Any]) -> None:
    path_item = schema["paths"].get(op.path)
    assert path_item is not None, f"{op.path} is not a path in the schema"
    operation = path_item.get(op.method.lower())
    assert operation is not None, f"{op.method} {op.path} is not an operation in the schema"
    assert operation["operationId"] == op.operation_id

    in_path = {p["name"] for p in operation.get("parameters", []) if p["in"] == "path"}
    assert set(re.findall(r"{(\w+)}", op.path)) == in_path

    body = operation.get("requestBody")
    if op.request_type is None:
        assert body is None
    else:
        assert body is not None
        actual = _ref_name(body["content"]["application/json"]["schema"])
        assert actual == _normal(op.request_type.__name__)

    success = next(code for code in operation["responses"] if code.startswith("2"))
    content = operation["responses"][success].get("content", {})
    actual_response = _ref_name(content.get("application/json", {}).get("schema"))
    assert actual_response == _expected_name(op.response_type)
