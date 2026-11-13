from __future__ import annotations

from typing import Any, Mapping


class SchemaValidationError(ValueError):
    pass


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_schema(value: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    """Validate the JSON-schema subset used by DragonZpyder capability contracts.

    The kernel intentionally owns a small deterministic validator instead of letting a
    model or provider decide whether an invocation/result matches its contract. The
    supported subset is enough for capability boundaries: type, required, properties,
    additionalProperties, items, enum, min/max, and string/array length constraints.
    """

    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_matches_type(value, str(item)) for item in expected):
            raise SchemaValidationError(f"{path} has an invalid type")
    elif isinstance(expected, str) and not _matches_type(value, expected):
        raise SchemaValidationError(f"{path} must be {expected}")

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path} is not an allowed value")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required if isinstance(required, list) else []:
            if key not in value:
                raise SchemaValidationError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise SchemaValidationError(
                    f"{path} contains unsupported fields: {', '.join(unknown)}"
                )
        for key, child in properties.items():
            if key in value and isinstance(child, dict):
                validate_schema(value[key], child, path=f"{path}.{key}")

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            raise SchemaValidationError(f"{path} must contain at least {minimum} items")
        if isinstance(maximum, int) and len(value) > maximum:
            raise SchemaValidationError(f"{path} must contain at most {maximum} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                validate_schema(item, item_schema, path=f"{path}[{index}]")

    if isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            raise SchemaValidationError(f"{path} is too short")
        if isinstance(maximum, int) and len(value) > maximum:
            raise SchemaValidationError(f"{path} is too long")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise SchemaValidationError(f"{path} is below the minimum")
        if isinstance(maximum, (int, float)) and value > maximum:
            raise SchemaValidationError(f"{path} is above the maximum")
