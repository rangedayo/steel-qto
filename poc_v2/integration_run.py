"""통합 메인 실행 CLI — 사람4 (안전 검사관).

도면 -> LLM 출력 YAML -> 검증 -> baseline 곱셈 -> CSV & HTML의 전체 흐름을
하나의 결정론적 스크립트로 자동화합니다.
원본 설정 파일(config/dedup_routing.yaml)은 덮어쓰지 않고 독립적으로 동작합니다.

사용법:
    # 단일 도면 구동
    python -m poc_v2.integration_run 도면4 config/dedup_routing.yaml
    
    # 5장 전체 일괄 구동
    python -m poc_v2.integration_run --all
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가하여 모듈 임포트 가능하도록 설정
# 이 파일은 poc_v2/ 하위에 위치하므로 부모 디렉토리가 PROJECT_ROOT가 됩니다.
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
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

ALL_DRAWINGS = ("도면1", "도면2", "도면3", "도면4", "도면5")

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


def print_yaml_summary(drawing: str, yaml_path: Path) -> None:
    """승인 대기 중인 YAML 라우팅의 핵심 정보를 터미널에 요약 출력합니다."""
    routes = routes_for_drawing(drawing, path=str(yaml_path))
    skips = skips_for_drawing(drawing, path=str(yaml_path))

    print("\n" + "=" * 60)
    print(f" 🔍 [도면 분석 설정 요약] - {drawing} ({yaml_path.name})")
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


def _generate_plotly_div(drawing: str) -> str:
    """도면에 매칭된 첫 번째 count dxf 파일을 Plotly go.Figure로 시각화한 div 코드를 반환합니다."""
    try:
        import plotly.graph_objects as go
        import plotly.io as pio
        from poc_v2.baseline2.export_baseline2_csv import small_drawing_files
        from poc_v2.baseline2.small_drawing_pipeline import process_small_drawing, _column_symbols
        from poc_v2.baseline2.visualize_small import _add_geometry, _add_count_overlay, _add_spec_overlay
    except ImportError:
        return "<div style='padding:20px;color:red;'>시각화를 위한 모듈 임포트 실패 (plotly / ezdxf 필요)</div>"

    # 1. 실제 QTO 계산에 활성화된(count_from) 시트명들을 수집
    approved_yaml = Path(PROJECT_ROOT) / "outputs" / "llm_routing" / f"{drawing}_approved.yaml"
    if not approved_yaml.exists():
        approved_yaml = Path(PROJECT_ROOT) / "config" / "dedup_routing.yaml"

    active_sheets = set()
    try:
        routes = routes_for_drawing(drawing, path=str(approved_yaml))
        for r in routes:
            if r.count_override is None and r.count_from:
                active_sheets.add(r.count_from)
    except Exception:
        pass

    files = small_drawing_files(drawing)
    target_file = None

    # 1순위: 계산에 실제로 쓰인 active_sheets와 매칭되는 count 시트 탐색
    for f in files:
        res = process_small_drawing(f)
        if res.kind == "count" and res.matched_sheet in active_sheets:
            target_file = f
            break

    # 2순위: (없으면) 기존처럼 첫 번째 count 시트 탐색
    if not target_file:
        for f in files:
            res = process_small_drawing(f)
            if res.kind == "count":
                target_file = f
                break

    # 3순위: (그것도 없으면) 첫 번째 파일 fallback
    if not target_file and files:
        target_file = files[0]

    if not target_file:
        return f"<div style='padding:20px;color:gray;'>{drawing} 에 대한 도면 파일(dxf)을 찾을 수 없습니다.</div>"

    fig = go.Figure()
    _add_geometry(fig, target_file)
    columns = _column_symbols(drawing)
    _add_count_overlay(fig, target_file, columns)
    _add_spec_overlay(fig, target_file, drawing)

    fig.update_layout(
        showlegend=True,
        plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        margin=dict(t=10, l=10, r=10, b=10),
        height=680,
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _export_html_report(drawing: str, weight_rows: list[WeightRow], yaml_name: str, base_out: Path) -> Path:
    """적산 결과와 도면 시각화가 결합된 프리미엄 HTML 보고서를 생성합니다."""
    # HTML 테이블 행 생성
    table_rows_html = []
    for r in weight_rows:
        table_rows_html.append(
            f"<tr>"
            f"<td>{r.symbol}</td>"
            f"<td>{r.count}</td>"
            f"<td>{r.length_mm:.0f}</td>"
            f"<td>{r.spec_normalized}</td>"
            f"<td>{r.total_weight_kg:.1f}</td>"
            f"</tr>"
        )
    
    t_weight = total_weight_kg(weight_rows)
    t_count = total_count(weight_rows)
    
    # 합계 행 추가
    table_rows_html.append(
        f"<tr class='total-row'>"
        f"<td>합계</td>"
        f"<td>{t_count}</td>"
        f"<td>-</td>"
        f"<td>-</td>"
        f"<td>{t_weight:.1f}</td>"
        f"</tr>"
    )
    
    # Plotly 도면 div 생성
    plotly_div = _generate_plotly_div(drawing)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>적산 결과 보고서 - {drawing}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Outfit', sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f4f6fa;
            color: #333;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        .left-pane {{
            width: 32%;
            min-width: 380px;
            background: #ffffff;
            box-shadow: 4px 0 15px rgba(0,0,0,0.05);
            padding: 25px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            border-right: 1px solid #eef2f6;
        }}
        .right-pane {{
            width: 68%;
            height: 100%;
            padding: 20px;
            box-sizing: border-box;
            background-color: #fdfdfd;
            display: flex;
            flex-direction: column;
        }}
        h1 {{
            font-size: 22px;
            font-weight: 800;
            margin-top: 0;
            color: #1a202c;
            border-bottom: 2px solid #3182ce;
            padding-bottom: 10px;
        }}
        .meta-info {{
            margin: 10px 0 20px 0;
            font-size: 13px;
            color: #718096;
            line-height: 1.6;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #3182ce 0%, #2b6cb0 100%);
            color: white;
            padding: 18px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(49,130,206,0.2);
        }}
        .summary-card .value {{
            font-size: 26px;
            font-weight: 800;
            margin-top: 5px;
        }}
        .summary-card .label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.8;
        }}
        .qto-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 13px;
        }}
        .qto-table th {{
            background-color: #f7fafc;
            color: #4a5568;
            text-align: left;
            padding: 10px;
            font-weight: 600;
            border-bottom: 2px solid #edf2f7;
        }}
        .qto-table td {{
            padding: 10px;
            border-bottom: 1px solid #edf2f7;
            color: #2d3748;
        }}
        .qto-table tr:hover {{
            background-color: #f8fafc;
        }}
        .qto-table tr.total-row {{
            font-weight: 700;
            background-color: #ebf8ff;
            border-top: 2px solid #bee3f8;
            border-bottom: 2px solid #bee3f8;
        }}
        .qto-table tr.total-row td {{
            color: #2b6cb0;
        }}
        .chart-header {{
            margin-bottom: 10px; 
            font-weight: 600; 
            color: #4a5568;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .badge {{
            background-color: #e2e8f0;
            color: #4a5568;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <div class="left-pane">
        <h1>📊 {drawing} 적산 보고서</h1>
        <div class="meta-info">
            도면 데이터 기반 실측 산출 결과<br>
            <strong>대상 부재:</strong> H빔 기둥<br>
            <strong>출처 설정:</strong> {yaml_name}
        </div>
        
        <div class="summary-card">
            <div class="label">총 중량 (Total Weight)</div>
            <div class="value">{t_weight:.1f} kg</div>
            <div class="label" style="margin-top:8px">총 수량: {t_count} 개</div>
        </div>
        
        <h3 style="margin-bottom: 5px; font-size: 15px;">🔍 상세 적산 내역</h3>
        <table class="qto-table">
            <thead>
                <tr>
                    <th>부호</th>
                    <th>개수</th>
                    <th>길이(mm)</th>
                    <th>규격</th>
                    <th>총중량(kg)</th>
                </tr>
            </thead>
            <tbody>
                {"".join(table_rows_html)}
            </tbody>
        </table>
    </div>
    <div class="right-pane">
        <div class="chart-header">
            <span>🗺️ 인터랙티브 도면 분석 시각화</span>
            <span class="badge">Plotly 뷰어</span>
        </div>
        <div style="flex-grow:1; background:white; border: 1px solid #edf2f7; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.02); overflow:hidden;">
            {plotly_div}
        </div>
    </div>
</body>
</html>
"""
    output_html_path = base_out / f"round_weight_llm_{drawing}.html"
    output_html_path.write_text(html_content, encoding="utf-8")
    return output_html_path.resolve()


def run_for_drawing(drawing: str, llm_yaml_path: Path, output_dir: Path | None = None) -> Path:
    """LLM yaml 검증 → baseline 곱셈 → CSV & HTML 저장.

    Args:
        drawing: 도면명 (예: 도면4)
        llm_yaml_path: 검증 대상 LLM yaml 파일의 경로
        output_dir: 결과물이 생성될 출력 디렉터리. 지정되지 않으면 PROJECT_ROOT/outputs 사용

    Returns:
        Path: 생성된 CSV 파일의 절대 경로

    Raises:
        ValueError: 검증 실패 시. 메시지에 validator 에러 목록 포함.
        FileNotFoundError: yaml 경로가 존재하지 않을 때.
    """
    if not llm_yaml_path.exists():
        raise FileNotFoundError(f"YAML 파일이 존재하지 않습니다: {llm_yaml_path}")

    # 단계 1: 검증 실행
    is_valid, errors = validate_yaml_file(str(llm_yaml_path))
    if not is_valid:
        error_msg = f"{drawing} YAML 검증 실패:\n" + "\n".join(f"  - {err}" for err in errors)
        raise ValueError(error_msg)

    # 기본 출력 디렉터리 설정
    base_out = output_dir or Path(PROJECT_ROOT) / "outputs"

    # 단계 2: 승인된 YAML 저장 (outputs/llm_routing/도면X_approved.yaml)
    approved_dir = base_out / "llm_routing"
    approved_dir.mkdir(parents=True, exist_ok=True)
    approved_yaml_path = approved_dir / f"{drawing}_approved.yaml"
    shutil.copyfile(llm_yaml_path, approved_yaml_path)

    # 단계 3: 베이스라인 계산 수행
    routes = routes_for_drawing(drawing, path=str(approved_yaml_path))
    skips = skips_for_drawing(drawing, path=str(approved_yaml_path))

    if not routes:
        raise ValueError(f"승인된 YAML 파일에 {drawing}에 대한 라우팅 정보가 없습니다.")

    count_p, length_p, spec_p, unit_fn = build_default_providers()
    all_rows = compute_weight_for_drawing(
        drawing,
        routes,
        skip_markers=skips,
        count_provider=count_p,
        length_provider=length_p,
        spec_provider=spec_p,
        unit_weight_fn=unit_fn,
    )

    weight_rows = [r for r in all_rows if isinstance(r, WeightRow)]

    # 단계 4: CSV 저장
    base_out.mkdir(parents=True, exist_ok=True)
    output_csv_path = base_out / f"round_weight_llm_{drawing}.csv"

    # CSV 작성 (UTF-8 BOM 포함, Excel 호환)
    with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        for row in weight_rows:
            writer.writerow(_row_to_csv(row))
        if weight_rows:
            writer.writerow(_total_row(weight_rows))

    # 단계 5: 시각화 HTML 보고서 추가 생성
    try:
        _export_html_report(drawing, weight_rows, llm_yaml_path.name, base_out)
    except Exception as e:
        print(f"[!] 시각화 HTML 보고서 생성 실패 (경고) - {drawing}: {e}")

    return output_csv_path.resolve()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="통합 실행 파이프라인 (사람4 - 안전 검사관)")
    parser.add_argument("drawing", nargs="?", default=None, help="분석 대상 단일 도면명 (예: 도면4)")
    parser.add_argument("llm_yaml", nargs="?", default=None, help="LLM이 생성한 YAML 초안 파일 경로")
    parser.add_argument("--all", action="store_true", help="전체 5장 도면 일괄 적산 수행")
    parser.add_argument("--llm-dir", default="outputs/llm_routing", help="일괄 수행 시 LLM YAML 파일들의 디렉토리")
    parser.add_argument("--approve", "-y", action="store_true", help="사용자 승인 게이트 우회 및 자동 승인")
    args = parser.parse_args()

    # 인자 검증
    if not args.all and (args.drawing is None or args.llm_yaml is None):
        parser.print_help()
        print("\n[!] 에러: 단일 도면을 실행하려면 도면명과 YAML 파일 경로를 위치 인자로 제공해야 하며, 전체를 실행하려면 --all 옵션을 제공해야 합니다.")
        sys.exit(1)

    # 1. 일괄 수행 모드 (--all)
    if args.all:
        llm_dir = Path(args.llm_dir)
        print(f"[*] 전체 5장 도면 일괄 적산 수행 시작 (탐색 디렉토리: {llm_dir})")
        
        # 각 도면별 파일 매칭 및 1차 검증
        target_yamls: dict[str, Path] = {}
        for dwg in ALL_DRAWINGS:
            # 1. outputs/llm_routing/도면X.yaml 탐색
            dwg_yaml = llm_dir / f"{dwg}.yaml"
            if not dwg_yaml.exists():
                # 2. outputs/llm_routing/도면X_test.yaml 등 대안 탐색
                dwg_yaml = llm_dir / f"{dwg}_test.yaml"
            
            if not dwg_yaml.exists():
                # 3. 없으면 원본 정답지 config/dedup_routing.yaml 로 흉내 (Fallback)
                fallback_yaml = Path(PROJECT_ROOT) / "config" / "dedup_routing.yaml"
                print(f"  - 경고: {dwg}에 대한 YAML 초안이 없어 정답 설정({fallback_yaml.name})으로 흉내 냅니다.")
                target_yamls[dwg] = fallback_yaml
            else:
                target_yamls[dwg] = dwg_yaml

        # 스키마 1차 검증 일괄 수행
        print("[*] 1단계: 전체 YAML 파일 스키마 일괄 검증 진행 중...")
        validation_failed = False
        for dwg, yaml_path in target_yamls.items():
            is_valid, errors = validate_yaml_file(str(yaml_path))
            if not is_valid:
                print(f"  [!] {dwg} 검증 실패 ({yaml_path.name}):")
                for err in errors:
                    print(f"    - {err}")
                validation_failed = True
        
        if validation_failed:
            print("[!] 일부 YAML 파일 검증 실패로 인해 작업을 중단합니다.")
            sys.exit(1)
            
        print("[+] 모든 YAML 파일 검증 완료!")

        # 5장 요약 리스팅 출력
        for dwg, yaml_path in target_yamls.items():
            print_yaml_summary(dwg, yaml_path)

        # 승인 게이트
        if args.approve:
            print("[*] 자동 승인 옵션(--approve)이 활성화되어 승인 단계를 건너뜁니다.")
            user_input = "y"
        else:
            try:
                user_input = input("[?] 위 설정대로 전체 5장 도면 일괄 적산을 진행하고 승인하시겠습니까? (y/N): ").strip().lower()
            except KeyboardInterrupt:
                print("\n[!] 사용자에 의해 중단되었습니다.")
                sys.exit(1)

        if user_input not in ("y", "yes"):
            print("[!] 승인이 취소되었습니다. 일괄 처리를 중단합니다.")
            sys.exit(0)

        # 일괄 실행 구동
        print("[*] 2단계: 전체 도면 일괄 적산 수행 중...")
        success_count = 0
        for dwg, yaml_path in target_yamls.items():
            try:
                print(f"  [*] {dwg} 진행 중... (입력: {yaml_path.name})")
                csv_path = run_for_drawing(dwg, yaml_path)
                html_path = csv_path.with_suffix(".html")
                print(f"    [+] {dwg} CSV 완료 -> {csv_path.name}")
                if html_path.exists():
                    print(f"    [+] {dwg} HTML 완료 -> {html_path.name}")
                success_count += 1
            except Exception as e:
                print(f"    [!] {dwg} 처리 중 에러 발생: {e}")
        
        print(f"\n[+] 일괄 작업 완료! (성공: {success_count}/{len(ALL_DRAWINGS)} 개)")
        return

    # 2. 단일 도면 수행 모드
    drawing = args.drawing
    yaml_path = Path(args.llm_yaml)

    print(f"[*] 단계 1: YAML 검증 시작 ({yaml_path})")
    
    is_valid, errors = validate_yaml_file(str(yaml_path))
    if not is_valid:
        print("[!] 검증 실패! 아래 에러 목록을 확인하고 수정해 주세요.")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("[+] 검증 통과!")

    # 2. 검토 게이트
    print_yaml_summary(drawing, yaml_path)
    
    if args.approve:
        print("[*] 자동 승인 옵션(--approve)이 활성화되어 승인 단계를 건너뜁니다.")
        user_input = "y"
    else:
        try:
            user_input = input("[?] 위 설정대로 베이스라인 계산을 진행하고 승인하시겠습니까? (y/N): ").strip().lower()
        except KeyboardInterrupt:
            print("\n[!] 사용자에 의해 중단되었습니다.")
            sys.exit(1)

    if user_input not in ("y", "yes"):
        print("[!] 승인이 취소되었습니다. 파이프라인 작동을 중단합니다.")
        sys.exit(0)

    # 3. 비즈니스 로직 함수 호출
    print("[*] 단계 2: 승인 처리 및 베이스라인 계산 수행 중...")
    try:
        csv_path = run_for_drawing(drawing, yaml_path)
        print(f"[+] 최종 결과 CSV 저장 완료 -> {csv_path}")
        
        # HTML 보고서 경로 출력
        html_path = csv_path.with_suffix(".html")
        if html_path.exists():
            print(f"[+] 시각화 HTML 보고서 생성 완료 -> {html_path}")
        
        # 합계 정보 요약 출력
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = list(csv.reader(f))
        if reader and reader[-1][2] == "합계":
            total_row = reader[-1]
            print(f"    - 총 개수: {total_row[3]}개")
            print(f"    - 총 중량: {total_row[7]}kg")

    except Exception as e:
        print(f"[!] 에러 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
