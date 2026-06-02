"""통합 CLI 실행 회귀 테스트 — 사람4 (안전 검사관).

가짜 LLM yaml을 이용해 1(검증) -> 2(검토 게이트 Mocking) -> 3(CSV 출력)
흐름이 정상적으로 동작하는지 end-to-end로 테스트합니다.
"""
from __future__ import annotations

import csv
import os
import sys
from unittest.mock import patch

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.qto.integration_run import main
from poc_v2.qto.validator import validate_yaml_file


@pytest.fixture
def clean_outputs():
    """테스트 실행 전후로 outputs 내에 생성되는 임시 파일을 안전하게 관리하고 청소합니다."""
    targets = [
        os.path.join(PROJECT_ROOT, "outputs", "llm_routing", "도면4_approved.yaml"),
        os.path.join(PROJECT_ROOT, "outputs", "round_weight_llm_도면4.csv"),
    ]
    
    # 백업 및 사전 제거
    backups = {}
    for t in targets:
        if os.path.exists(t):
            backup_path = t + ".bak"
            try:
                import shutil
                shutil.copyfile(t, backup_path)
                backups[t] = backup_path
                os.remove(t)
            except Exception:
                pass
                
    yield
    
    # 테스트 완료 후 생성 파일 정리 및 백업 복원
    for t in targets:
        if os.path.exists(t):
            try:
                os.remove(t)
            except Exception:
                pass
        if t in backups and os.path.exists(backups[t]):
            try:
                import shutil
                shutil.copyfile(backups[t], t)
                os.remove(backups[t])
            except Exception:
                pass


def test_validator_with_bad_yaml(tmp_path):
    # 문법 에러가 있는 YAML
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("도면4:\n  기둥:\n    SC1: {count_from: 123", encoding="utf-8")
    
    is_valid, errors = validate_yaml_file(str(bad_yaml))
    assert not is_valid
    assert any("YAML 문법 오류" in err for err in errors)


def test_validator_with_non_dict_yaml(tmp_path):
    # 최상위가 dict가 아닌 YAML
    list_yaml = tmp_path / "list.yaml"
    list_yaml.write_text("- item1\n- item2\n", encoding="utf-8")
    
    is_valid, errors = validate_yaml_file(str(list_yaml))
    assert not is_valid
    assert any("매핑(dict)이어야 합니다" in err for err in errors)


def test_validator_with_valid_yaml(tmp_path):
    # 정상 YAML
    good_yaml = tmp_path / "good.yaml"
    good_yaml.write_text(
        "도면4:\n"
        "  기둥:\n"
        "    SC1: {count_from: \"1층 구조평면도\", spec_from: \"1층 구조평면도\"}\n"
        "    SC2: {count_from: \"1층 구조평면도\", spec_from: \"1층 구조평면도\"}\n",
        encoding="utf-8"
    )
    
    is_valid, errors = validate_yaml_file(str(good_yaml))
    assert is_valid
    assert len(errors) == 0


@pytest.mark.usefixtures("clean_outputs")
def test_integration_run_flow_approved(tmp_path):
    # 1. 가짜 LLM YAML 파일 작성 (도면4 대상)
    llm_yaml = tmp_path / "도면4_llm.yaml"
    llm_yaml.write_text(
        "도면4:\n"
        "  기둥:\n"
        "    SC1: {count_from: \"1층 구조평면도\", spec_from: \"1층 구조평면도\"}\n"
        "    SC2: {count_from: \"1층 구조평면도\", spec_from: \"1층 구조평면도\"}\n",
        encoding="utf-8"
    )

    # 2. CLI 인자 모킹 및 사용자 입력 'y' 모킹
    test_args = [
        "integration_run.py",
        "--drawing", "도면4",
        "--llm-yaml", str(llm_yaml)
    ]
    
    import io
    test_stdin = io.StringIO("y\n")
    with patch.object(sys, 'argv', test_args), \
         patch('sys.stdin', test_stdin):
        main()

    # 3. 승인된 YAML 파일 및 CSV 출력 확인
    approved_yaml = os.path.join(PROJECT_ROOT, "outputs", "llm_routing", "도면4_approved.yaml")
    output_csv = os.path.join(PROJECT_ROOT, "outputs", "round_weight_llm_도면4.csv")

    assert os.path.exists(approved_yaml)
    assert os.path.exists(output_csv)

    # CSV의 정합성 검증 (총중량 1a 도면4와 결과가 동일해야 함)
    with open(output_csv, encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))
        
    assert reader[0] == ["도면", "부재종류", "부호", "개수", "길이_mm", "규격", "단위중량_kg_per_m", "총중량_kg", "count_from", "spec_from", "length_from"]
    assert len(reader) == 4
    
    # 합계 확인
    total_row = reader[-1]
    assert total_row[2] == "합계"
    assert total_row[3] == "18"  # SC1(14) + SC2(4) = 18


@pytest.mark.usefixtures("clean_outputs")
def test_integration_run_flow_rejected(tmp_path):
    # 1. 가짜 LLM YAML 파일 작성
    llm_yaml = tmp_path / "도면4_llm.yaml"
    llm_yaml.write_text(
        "도면4:\n"
        "  기둥:\n"
        "    SC1: {count_from: \"1층 구조평면도\", spec_from: \"1층 구조평면도\"}\n",
        encoding="utf-8"
    )

    # 2. CLI 인자 모킹 및 사용자 입력 'n' 모킹
    test_args = [
        "integration_run.py",
        "--drawing", "도면4",
        "--llm-yaml", str(llm_yaml)
    ]
    
    import io
    test_stdin = io.StringIO("n\n")
    with patch.object(sys, 'argv', test_args), \
         patch('sys.stdin', test_stdin):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0

    # 3. 승인 및 CSV 파일이 생성되지 않았어야 함
    approved_yaml = os.path.join(PROJECT_ROOT, "outputs", "llm_routing", "도면4_approved.yaml")
    output_csv = os.path.join(PROJECT_ROOT, "outputs", "round_weight_llm_도면4.csv")

    assert not os.path.exists(approved_yaml)
    assert not os.path.exists(output_csv)
