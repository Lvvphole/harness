from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContractValidationError(ValueError):
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
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _validate(value: Any, schema: dict[str, Any], location: str = "contract") -> None:
    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        raise ContractValidationError(f"{location} must be {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractValidationError(f"{location} is not an allowed value")
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            raise ContractValidationError(f"{location} must be at least {minimum}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if minimum is not None and len(value) < minimum:
            raise ContractValidationError(f"{location} requires at least {minimum} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate(item, item_schema, f"{location}[{index}]")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ContractValidationError(f"{location}.{key} is required")
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise ContractValidationError(f"{location} has unexpected field {unexpected[0]}")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{location}.{key}")


def _validate_task_semantics(value: dict[str, Any]) -> None:
    if value.get("task_type") != "review-repair":
        return
    predicates = value.get("predicates")
    if not isinstance(predicates, dict) or not predicates or not all(
        predicate is True for predicate in predicates.values()
    ):
        raise ContractValidationError("review-repair requires all predicates true")


def load_contract(contract_path: Path, schema_path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        contract_bytes = contract_path.read_bytes()
        value = json.loads(contract_bytes)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError("valid active contract is required") from exc
    if not isinstance(value, dict) or not isinstance(schema, dict):
        raise ContractValidationError("valid active contract is required")
    try:
        _validate(value, schema)
        _validate_task_semantics(value)
    except ContractValidationError as exc:
        raise ContractValidationError(f"valid active contract is required: {exc}") from exc
    return value, contract_bytes
