# steel-qto

건설 도면(DXF)에서 철골 부재 물량을 자동 산출하는 PoC.

## 1. 개요

도면 한 장(또는 여러 장)에서 철골 기둥의 **부호 개수 · 길이 · 규격**을 측정하고,
단면적 기반 단위중량을 곱해 **부재별·도면별 총중량 CSV**를 만든다.

- **현재 done**: 5장 통합 기둥 총중량 CSV — **188,726.7 kg / 109개** (PoC v1 deliverable).
- **다음 후보**: 보(beam) 부재 통합, 단면적 식 정확화(KS 표 룩업), 측정 라우팅 LLM 자동화.

회귀 안전망: clean clone → install → DXF 배치 → `pytest` 한 사이클에서
**263 passed / 2 known-fail**(도면2 SC1·SC2) 재현.

## 2. 파이프라인

```
   측정 3종                       dedup yaml            중량 산출           산출물
 ┌───────────┐                 ┌─────────────┐      ┌──────────────┐    ┌──────────┐
 │ 카운트     │                 │             │      │              │    │          │
 │ 길이       │ ──────────────▶ │ dedup_routing├────▶│weight_pipeline├──▶│ 총중량 CSV│
 │ 규격       │                 │  (중복 판별) │      │ (단면적×7850) │    │          │
 └───────────┘                 └─────────────┘      └──────────────┘    └──────────┘
   ▲ baseline-1~7 누적             ▲ 사람이 손으로 채운 yaml 4종         ▲ 중량-1a/1b
   └──────────────────────────────┴──────────────────────────────────────┘
   (LLM 라우팅 자리 = 현재 사람이 임시로 채움 — 다음 라운드 후보)
```

측정 도구는 **측정만**, 중복·라우팅 **결정**은 사람이 채운 yaml이 담당한다.
yaml의 결정 슬롯은 향후 LLM이 대체할 자리다.

## 3. 환경 세팅 (4단계)

> Python **3.11** 기준 (`<3.12`).

```bash
# 1) 클론
git clone https://github.com/rangedayo/steel-qto.git
cd steel-qto

# 2) venv + 의존성
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r poc_v2/requirements.txt

# 3) DXF 5종 배치 (기밀 — Notion 비공개 채널에서 받아 sample_data/ 에)
#    도면1~5.dxf 및 분리본 dxf (채널 안내대로)
#    ※ 정답지 xlsx 2종은 클론에 이미 포함됨

# 4) 회귀 확인
pytest -v poc_v2/               # → 263 passed / 2 known-fail
```

`sample_data/*.dxf`는 기밀이라 git에 포함하지 않는다. 비공개 채널에서 받아 배치해야 회귀가 돈다.

## 4. 빠른 시작 (1분)

```bash
# 도면4 한 장 총중량 CSV 생성
python -m poc_v2.qto.export_weight_csv --drawing 도면4

# 5장 통합 PoC v1 deliverable 재생성
python -m poc_v2.qto.export_weight_csv --all
```

## 5. 코드 구조

```
config/                   yaml 설정 5종 (사람이 채우는 결정 슬롯)
  symbol_rules.yaml         부호 화이트리스트 / 제외 규칙
  length_routing.yaml       시트별 길이 측정 라우팅
  sheet_name_overrides.yaml 시트명 매칭 fallback
  dedup_routing.yaml        중복 판별 (count_from / spec_from / by_section / skip / count_override)
  unit_weight_table.yaml    단위중량 참조 표 (레거시 룩업)
poc_v2/
  ├── tests/        1단계 부호 카운트 회귀
  ├── length/       길이·규격 측정 (+ tests/)
  ├── baseline2/    작은 도면 입력 모듈 (baseline-2~7) (+ tests/)
  ├── qto/          중량 산출 (중량-1a/1b) ← PoC 본 deliverable (+ tests/)
  ├── app.py        Streamlit UI
  └── requirements.txt
reference_materials/      정답지 xlsx 2종 (회귀 의존)
sample_data/              DXF 입력 — gitignored, Notion 비공개 채널
outputs/                  라운드 프롬프트·보고서·결과 CSV
docs/                     round_history.md, domain_rules_seed.md
```

## 6. 새 도면 yaml 채우는 법

새 도면을 추가할 때 사람이 채우는 결정은 config/ yaml 4종에 모인다.

- **symbol_rules.yaml** — 부재 부호 화이트리스트에 추가. 기초·철근·상세참조·두께·통심선은 제외 규칙으로 자동 거름.
- **length_routing.yaml** — 도면별로 길이를 측정할 시트(소스 파일)와 적용 부호를 등록. 세로 DIMENSION 최댓값 룰.
- **sheet_name_overrides.yaml** — 자동 매칭(exact/partial)이 실패하는 케이스만 fallback으로 등록. 최소화 원칙.
- **dedup_routing.yaml** — 같은 부호가 여러 시트에 나올 때 어느 시트를 본체로 칠지 라우팅:
  - `count_from` / `spec_from` — 카운트·규격을 가져올 시트 분리
  - `by_section` — 동(棟)별 분리 산출 (도면1)
  - `skip` — 측정 소스가 없는 동/구역 제외
  - `count_override` — 측정 한계 케이스를 정답지 값으로 격리

자세한 도메인 규칙은 [docs/domain_rules_seed.md](docs/domain_rules_seed.md) 참조.

## 7. 알려진 한계

| # | 한계 | 격리 방법 |
|---|---|---|
| 1 | 도면2 SC1·SC2 카운트 측정 0 (블록 내부 split-TEXT 데이터 한계) | `count_override`로 정답지 값 격리 (known-fail 2건) |
| 2 | 도면1 1동 기둥 길이 산출 불가 (골구도/단면도 시트 부재) | `skip`으로 산출 대상 제외 |
| 3 | 도면5 Y1축열 길이 측정 (측정 소스 차이) | 라우팅에서 주단면도 소스로 처리 |
| 4 | 단위중량 식 KS 표 대비 -2~3% (4세그먼트 단면적 근사) | 멘토 확정 — 현재 식 유지, KS 룩업은 후속 후보 |

## 8. 라운드 이력

총 14개 라운드(1단계 → 길이 → 규격 → baseline-1~7 → 중량-1a/1b → 핸드오프)를 거쳐
PoC v1(5장 통합 총중량 CSV)을 완성했다. 라운드별 결정 흐름은
[docs/round_history.md](docs/round_history.md) 참조.

## 9. 참고

- **단위중량 계산식**: 단면(H형강) 4세그먼트 단면적 × 7,850 kg/m³.
- **참고 표준**: KS D 3502 (H형강 표준 단면). 현재 식은 표 대비 -2~3% 근사.
- **의사결정 원칙**:
  - AI/사람은 **결정**만, 도구는 **측정**만 한다.
  - 회귀 안전망은 절대 깨지 않는다.
  - 도면별 하드코딩보다 **보편 룰**을 우선한다.
  - 측정 한계는 숨기지 않고 **솔직히 격리**한다(`skip`·`count_override`).
