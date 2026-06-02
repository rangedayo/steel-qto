"""JSON Schema validator for LLM-generated routing YAML.

This file lives in the experiment workspace and is intended to be reused by
the future integration code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to validate routing YAML.") from exc

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_routing_yaml(yaml_path: str | Path, schema_path: str | Path | None = None) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("jsonschema is required to validate routing YAML.") from exc

    yaml_file = Path(yaml_path)
    schema_file = Path(schema_path) if schema_path else Path(__file__).with_name("routing.schema.json")

    instance = _load_yaml(yaml_file)
    schema = _load_schema(schema_file)
    jsonschema.validate(instance=instance, schema=schema)


def validate_yaml_file(path: str) -> tuple[bool, list[str]]:
    """Validate one YAML file and return `(ok, errors)`.

    Returns:
        `(True, [])` when validation passes.
        `(False, [messages...])` when validation fails.
    """
    try:
        import jsonschema
        import yaml
    except ImportError as exc:
        return (False, [f"필수 라이브러리 누락: {exc}"])

    yaml_file = Path(path)
    if not yaml_file.exists():
        return (False, [f"파일 없음: {path}"])

    schema_file = Path(__file__).with_name("routing.schema.json")

    try:
        with yaml_file.open("r", encoding="utf-8") as handle:
            instance = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        return (False, [f"YAML 파싱 실패: {exc}"])
    except OSError as exc:
        return (False, [f"YAML 파일 읽기 실패: {exc}"])

    try:
        schema = _load_schema(schema_file)
    except OSError as exc:
        return (False, [f"스키마 파일 읽기 실패: {exc}"])
    except json.JSONDecodeError as exc:
        return (False, [f"스키마 JSON 파싱 실패: {exc}"])

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))

    if not errors:
        return (True, [])

    messages = [
        f"[{'/'.join(str(part) for part in err.absolute_path) or '루트'}] {err.message}"
        for err in errors
    ]
    return (False, messages)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate routing YAML against routing.schema.json")
    parser.add_argument("yaml_path", help="Path to the YAML file to validate")
    parser.add_argument(
        "--schema",
        dest="schema_path",
        default=None,
        help="Optional path to routing.schema.json"
    )
    args = parser.parse_args()

    validate_routing_yaml(args.yaml_path, args.schema_path)
    print("Validation passed.")
