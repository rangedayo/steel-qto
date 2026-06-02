"""통합 메인 실행 CLI — 사람4 (안전 검사관).

사람3의 LLM 출력 YAML 초안을 받아와 사람2의 검증 코드로 검사하고,
사용자 승인(CLI)을 거쳐 최종 베이스라인 파이프라인을 작동하여 총중량을 CSV로 출력합니다.
원본 설정 파일(config/dedup_routing.yaml)은 덮어쓰지 않고 독립적으로 동작합니다.

사용법:
    python -m poc_v2.qto.integration_run --drawing 도면2 --llm-yaml outputs/llm_routing/도면2.yaml
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from typing import Optional

# 프로젝트 루트를 sys.path에 추가하여 모듈 임포트 가능하도록 설정
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from poc_v2.qto.dedup_loader import routes_for_drawing, skips_for_drawing
from poc_v2.qto.validator import validate_yaml_file
from poc_v2.qto.weight_pipeline import (
    WeightRow,
    build_default_providers,
    compute_weight_for_drawing,
    total_count,
    total_weight_kg,
)

# 1a 단일 도면 형식 (11열)
_HEADER = [
    "도면", "부재종류", "부호", "개수", "길이_mm", "규격",
    "단위중량_kg_per_m", "총중량_kg",
    "count_from", "spec_from", "length_from",
]
_BLANK = "-"


def _row_to_csv(row: WeightRow) -> list[str]:
    return [
        row.drawing, row.member_kind, row.symbol, str(row.count),
        f"{row.length_mm:.0f}", row.spec_normalized,
        f"{row.unit_weight_kg_per_m:.2f}", f"{row.total_weight_kg:.1f}",
        row.count_from_sheet, row.spec_from_sheet, row.length_from_sheet,
    ]


def _total_row(rows: list[WeightRow]) -> list[str]:
    drawing = rows[0].drawing if rows else ""
    kinds = {r.member_kind for r in rows}
    member_kind = next(iter(kinds)) if len(kinds) == 1 else "전체"
    return [
        drawing, member_kind, "합계", str(total_count(rows)),
        _BLANK, _BLANK, _BLANK, f"{total_weight_kg(rows):.1f}",
        _BLANK, _BLANK, _BLANK,
    ]


def print_yaml_summary(drawing: str, yaml_path: str) -> None:
    """승인 대기 중인 YAML 라우팅의 핵심 정보를 터미널에 요약 출력합니다."""
    routes = routes_for_drawing(drawing, path=yaml_path)
    skips = skips_for_drawing(drawing, path=yaml_path)

    print("\n" + "=" * 60)
    print(f" 🔍 [도면 분석 설정 요약] - {drawing}")
    print("=" * 60)

    if skips:
        print(" [제외 섹션 (Skip)]")
        for s in skips:
            sec = f"섹션: {s.section}" if s.section else "전체 섹션"
            print(f"  - {sec} | 사유: {s.reason}")
        print("-" * 60)

    if not routes:
        print("  경고: 해당 도면에 대한 라우팅 설정이 존재하지 않습니다.")
    else:
        print(f" {'부호':<8} | {'카운트 출처 (또는 고정값)':<30} | {'규격 출처':<20}")
        print("-" * 60)
        for r in routes:
            count_info = f"override: {r.count_override}" if r.count_override is not None else f"시트: {r.count_from}"
            print(f" {r.symbol:<8} | {count_info:<30} | 시트: {r.spec_from:<20}")
    print("=" * 60 + "\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="통합 실행 파이프라인 (사람4 - 안전 검사관)")
    parser.add_argument("--drawing", required=True, help="분석 대상 단일 도면명 (예: 도면2)")
    parser.add_argument("--llm-yaml", required=True, help="LLM이 생성한 YAML 초안 파일 경로")
    args = parser.parse_args()

    print(f"[*] 단계 1: YAML 검증 시작 ({args.llm-yaml})")
    is_valid, errors = validate_yaml_file(args.llm-yaml)
    if not is_valid:
        print("[!] 검증 실패! 아래 에러 목록을 확인하고 수정해 주세요.")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("[+] 검증 통과!")

    # 단계 2: 검토 게이트
    print_yaml_summary(args.drawing, args.llm-yaml)
    
    try:
        user_input = input("[?] 위 설정대로 베이스라인 계산을 진행하고 승인하시겠습니까? (y/N): ").strip().lower()
    except KeyboardInterrupt:
        print("\n[!] 사용자에 의해 중단되었습니다.")
        sys.exit(1)

    if user_input not in ("y", "yes"):
        print("[!] 승인이 취소되었습니다. 파이프라인 작동을 중단합니다.")
        sys.exit(0)

    # 단계 3: 승인된 YAML 저장
    approved_dir = os.path.join(PROJECT_ROOT, "outputs", "llm_routing")
    os.makedirs(approved_dir, exist_ok=True)
    approved_yaml_path = os.path.join(approved_dir, f"{args.drawing}_approved.yaml")
    
    print(f"[*] 단계 2: 승인 완료. YAML을 저장합니다 -> {approved_yaml_path}")
    shutil.copyfile(args.llm-yaml, approved_yaml_path)

    # 단계 4: 베이스라인 연동 및 CSV 출력
    print("[*] 단계 3: 베이스라인 계산 수행 중...")
    try:
        routes = routes_for_drawing(args.drawing, path=approved_yaml_path)
        skips = skips_for_drawing(args.drawing, path=approved_yaml_path)
        
        if not routes:
            print(f"[!] 에러: 승인된 YAML 파일에 {args.drawing}에 대한 라우팅 정보가 없습니다.")
            sys.exit(1)

        count_p, length_p, spec_p, unit_fn = build_default_providers()
        all_rows = compute_weight_for_drawing(
            args.drawing,
            routes,
            skip_markers=skips,
            count_provider=count_p,
            length_provider=length_p,
            spec_provider=spec_p,
            unit_weight_fn=unit_fn,
        )
        
        weight_rows = [r for r in all_rows if isinstance(r, WeightRow)]
        
        # CSV 출력 파일 경로 정의
        output_csv_path = os.path.join(PROJECT_ROOT, "outputs", f"round_weight_llm_{args.drawing}.csv")
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True)
        
        # CSV 작성
        with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(_HEADER)
            for row in weight_rows:
                writer.writerow(_row_to_csv(row))
            if weight_rows:
                writer.writerow(_total_row(weight_rows))
                
        print(f"[+] 최종 결과 CSV 저장 완료 -> {output_csv_path}")
        print(f"    - 총 개수: {total_count(weight_rows)}개")
        print(f"    - 총 중량: {total_weight_kg(weight_rows):.1f}kg")

    except Exception as e:
        print(f"[!] 베이스라인 파이프라인 구동 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
