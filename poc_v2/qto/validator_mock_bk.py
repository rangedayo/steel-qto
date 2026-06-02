"""YAML 스키마 검증 모듈 (뼈대).

이건 뼈대 파일이며, 실제 상세 스키마 검증(jsonschema/Pydantic 등)은 사람2가 완성할 예정입니다.
현재 jsonschema 호출 부분은 비어 있으며, 파일 존재성 및 YAML 문법 파싱 성공 여부만 1차로 확인합니다.
"""
from __future__ import annotations

import os
import yaml
from typing import Any


def validate_yaml_file(path: str) -> tuple[bool, list[str]]:
    """지정한 YAML 파일의 양식이 올바른지 검증합니다.

    Args:
        path: 검증 대상 YAML 파일의 절대 또는 상대 경로.

    Returns:
        tuple[bool, list[str]]: (검증 성공 여부, 에러 메시지 리스트)
    """
    errors: list[str] = []

    # 1. 파일 존재 여부 검사
    if not os.path.exists(path):
        errors.append(f"파일이 존재하지 않습니다: {path}")
        return False, errors

    # 2. YAML 파싱 검사
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"YAML 문법 오류 발생: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"파일을 읽는 중 알 수 없는 오류 발생: {e}")
        return False, errors

    # 3. 최상위 데이터 타입 검사
    if data is None:
        errors.append("YAML 파일이 비어 있습니다.")
        return False, errors

    if not isinstance(data, dict):
        errors.append(f"최상위 요소는 매핑(dict)이어야 합니다. (현재 타입: {type(data).__name__})")
        return False, errors

    # =========================================================================
    # [사람2 구현 영역]
    # 아래 영역에 jsonschema 등을 활용한 실제 YAML 상세 양식 검증 로직을 추가합니다.
    # =========================================================================

    if errors:
        return False, errors

    return True, []
