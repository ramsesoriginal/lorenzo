"""Check native DTO assumptions; response additions are deliberately compatible."""
import json
import sys
from pathlib import Path


def shape(value):
    if "$ref" in value:
        return {"$ref": value["$ref"]}
    return {
        key: [shape(item) for item in value[key]]
        if key in ("anyOf", "oneOf")
        else shape(value[key]) if isinstance(value[key], dict) else value[key]
        for key in ("type", "format", "items", "anyOf", "oneOf", "enum")
        if key in value
    }


def check(schema_file):
    actual = json.loads(Path(schema_file).read_text())
    expected = json.loads((Path(__file__).parent.parent / "contracts/consumed.json").read_text())
    errors = []
    for name, contract in expected["schemas"].items():
        model = actual["components"]["schemas"].get(name, {})
        for field, field_shape in contract["fields"].items():
            found = model.get("properties", {}).get(field)
            if found is None or shape(found) != field_shape:
                errors.append(f"{name}.{field} changed its wire shape")
        if not set(contract["required"]).issubset(model.get("required", [])):
            errors.append(f"{name}: a consumed required response field became optional")
        if name in ("InformationCreate", "DeviceCodeCreate", "DeviceTokenRequest"):
            if set(model.get("required", [])) - set(contract["fields"]):
                errors.append(f"{name}: new required request field")
    for path, methods in expected["paths"].items():
        for method, request in methods.items():
            operation = actual["paths"].get(path, {}).get(method)
            if operation is None:
                errors.append(f"Missing {method.upper()} {path}")
            elif operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema") != request:
                errors.append(f"Request changed: {method.upper()} {path}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Mobile contracts match API {actual['info']['version']} ({len(expected['schemas'])} schemas).")


if __name__ == "__main__":
    check(sys.argv[1])
