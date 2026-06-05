"""통합 파이프라인 회귀 테스트 — 사람4 (안전 검사관).

사양서 명세를 기반으로 가짜 LLM yaml을 이용한 계산 정합성, 스키마 검증 실패 차단,
그리고 원본 yaml 보존 및 디렉터리 격리 테스트를 자동 수행합니다.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.integration_run import run_for_drawing


def test_integration_run_도면4_total_weight(tmp_path):
    """도면4를 config/dedup_routing.yaml을 가짜 LLM 출력으로 사용해 돌렸을 때,

    생성된 CSV의 도면4 총중량 = 7,140 kg (±1 kg 허용)인지 검증합니다.
    """
    # 1. 원본 dedup_routing.yaml 경로 획득
    source_yaml = Path(PROJECT_ROOT) / "config" / "dedup_routing.yaml"
    
    # 2. 격리 폴더(tmp_path)를 출력 폴더로 지정하여 파이프라인 작동
    csv_path = run_for_drawing("도면4", source_yaml, output_dir=tmp_path)
    
    # 3. 결과 CSV 및 HTML 파일 존재성 확인
    assert csv_path.exists()
    assert csv_path.name == "round_weight_llm_도면4.csv"
    
    html_path = csv_path.with_suffix(".html")
    assert html_path.exists()
    
    # 4. CSV를 파싱하여 총중량 합계 검증 (정답지: 7140.4 kg)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))
        
    assert reader[0] == ["도면", "부재종류", "부호", "개수", "길이_mm", "규격", "단위중량_kg_per_m", "총중량_kg", "count_from", "spec_from", "length_from"]
    
    # 마지막 행은 합계 행이어야 함
    total_row = reader[-1]
    assert total_row[2] == "합계"
    assert total_row[3] == "18"  # SC1(14) + SC2(4) = 18
    
    # 총중량 값 검증 (7140 kg ± 1 kg 범위 안인지 단언)
    total_weight = float(total_row[7])
    assert total_weight == pytest.approx(7140.4, abs=1.0)


def test_integration_run_validation_failure(tmp_path):
    """일부러 깨뜨린 yaml(예: spec_from 누락) 입력 시 ValueError 발생 및 CSV 미생성 확인."""
    # 1. spec_from 키가 누락된 비정상 YAML 작성
    bad_yaml = tmp_path / "bad_routing.yaml"
    bad_yaml.write_text(
        "도면4:\n"
        "  기둥:\n"
        "    SC1:\n"
        "      count_from: \"1층 구조평면도\"\n",  # spec_from 누락
        encoding="utf-8"
    )
    
    # 2. run_for_drawing 실행 시 ValueError가 유발되는지 검사
    with pytest.raises(ValueError) as excinfo:
        run_for_drawing("도면4", bad_yaml, output_dir=tmp_path)
        
    # 에러 메시지에 스키마 위반 사항이 기록되어 있는지 확인
    assert "spec_from" in str(excinfo.value)
    
    # 3. 격리 폴더에 결과 CSV가 생성되지 않았어야 함
    csv_path = tmp_path / "round_weight_llm_도면4.csv"
    assert not csv_path.exists()


def test_integration_run_does_not_overwrite_dedup_routing(tmp_path):
    """실행 후 config/dedup_routing.yaml의 mtime/내용이 전혀 변경되지 않았음을 확인."""
    source_yaml = Path(PROJECT_ROOT) / "config" / "dedup_routing.yaml"
    
    # 실행 전 내용 및 수정 시각 저장
    initial_content = source_yaml.read_text(encoding="utf-8")
    initial_mtime = source_yaml.stat().st_mtime
    
    # 실행
    run_for_drawing("도면4", source_yaml, output_dir=tmp_path)
    
    # 실행 후 내용 및 수정 시각 동일성 비교
    assert source_yaml.read_text(encoding="utf-8") == initial_content
    assert source_yaml.stat().st_mtime == initial_mtime
