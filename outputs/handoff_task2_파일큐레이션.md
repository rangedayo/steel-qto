# 핸드오프 작업-2 — 파일 큐레이션 표

> 작업 디렉터리(`construction-ai-estimator`) → 신규 레포(`steel-qto`) 이전 대상 정리.
> 명세 §4 기준. **실제 스캔 결과**로 보강하고, 명세와의 편차는 아래 §편차에 명시.
> 최종 "실제 가져간 / 두고 간" 결과는 작업 9·10 완료 후 갱신.

---

## 1. 가져갈 (필수)

| 경로 | 비고 |
|---|---|
| `config/symbol_rules.yaml` | 부호 화이트리스트 |
| `config/length_routing.yaml` | 길이 측정 라우팅 |
| `config/sheet_name_overrides.yaml` | 시트명 매칭 fallback |
| `config/dedup_routing.yaml` | 중복 판별 라우팅 |
| `config/unit_weight_table.yaml` | **단위중량 표 — 회귀 필수** (total_weight.py·unit_weight.py·test_unit_weight_calc.py 참조). 명세 §4.1은 "yaml 4종"이나 실제 5종 ← 편차, 아래 §편차 참조 |
| `poc_v2/` 전체 | tests / length / baseline2 / qto + requirements.txt (investigate_*.py 포함 — 아래 주 참조) |
| `reference_materials/도면_정답지.xlsx` | 카운트 정답지 (회귀 의존) |
| `reference_materials/도면_길이_정답지.xlsx` | 길이·규격 정답지 (회귀 의존) |
| `pyproject.toml` | Python 3.11 핀. **`name = "construction-ai-estimator"` → `"steel-qto"` 변경 후 이전** |
| `.python-version` | 3.11.9 |
| `.gitignore` (정비 후) | 작업 7 |
| `README.md` (재작성) | 작업 3 (9섹션) |
| `LICENSE` (신규) | 작업 8 (MIT, Copyright rangedayo) |
| `docs/round_history.md` (신규) | 작업 4 |
| `docs/domain_rules_seed.md` (신규) | 작업 5 |
| `outputs/handoff_task1_보고서.md` | 환경 재현성 검증 결과물 |
| `outputs/handoff_task2_파일큐레이션.md` (본 문서) | 작업 2 산출물 |
| `outputs/handoff_task2_보고서.md` (신규) | 작업 12 결과물 |

> **주 — `poc_v2/tests/investigate_*.py` 3종** (`investigate_도면2_sc.py`, `investigate_도면3.py`, `investigate_도면5.py`):
> `test_` 함수가 없어 **pytest 미수집**(회귀 무관). 디버깅 스크립트지만, 명세 §13.1 "poc_v2/ 무수정" 원칙상 **삭제 없이 통째로 carry** 권장. (제거하면 poc_v2/ 변경이 되어 원칙 위배)

---

## 2. 가져갈 (선택 — 사용자 결정, 권장값 표기)

| 경로 | 권장 | 사유 |
|---|---|---|
| `outputs/prompts/round_*.md` (round2~10, baseline1~7, length1·4, spec1, weight1a·1b) | **가져가기** | 라운드 명세 — round_history.md 의 근거 |
| `outputs/prompts/handoff_task1_환경검증_prompt.md` | **가져가기** | 핸드오프 명세 (보고서와 짝) |
| `outputs/prompts/handoff_task2_문서레포정리_prompt.md` | **가져가기** | 핸드오프 명세 (보고서와 짝). ※ 현재 작업트리 미추적 상태 |
| `outputs/prompts/llm-wiki_prompt.md` | **가져가기** | domain_rules_seed.md 근거 자료 (명세 §7 참조) |
| `outputs/prompts/claude_code_prompt.md` | 두고 갈(약) | 초기 일반 프롬프트, 역사성 낮음 (가져가도 무해) |
| `outputs/reports/round*.md` (진단리포트·사전진단·보고서 등 11종) | **가져가기** | 라운드 보고서 — 역사 기록 |
| `outputs/round_baseline{2..7}_보고서.md`, `round_weight1a·1b_보고서.md` | **가져가기** | 라운드 보고서 |
| `outputs/round_weight1b_5장_총중량.csv` | **가져가기** | **PoC v1 deliverable** |
| `outputs/round_weight1a_도면4_총중량.csv` | **가져가기** | 중간 검증물 |
| `outputs/round_baseline{2..6}_시트별_결과.csv`, `round_baseline7_분리본검증.csv` | **가져가기** | 라운드 결과 데이터 |
| `outputs/results/round_spec1_규격추출.csv` | **가져가기** | 규격 추출 결과 데이터 |
| `outputs/visualize/*.html` (~45개) | **두고 갈** | 용량 큼·재생성 가능 (명세 §4.2 권장) |

---

## 3. 두고 갈 (포함 금지)

| 경로 | 사유 |
|---|---|
| `outputs/notes/*.md` (round3·4·5·6 진단, round_length4 사전조사, llm_wiki_룰북, 기둥길이_재기) | 작업 중 사적·진단 메모 — 외부 공유 부적합 (§4.3). 공개용 규칙은 docs/domain_rules_seed.md 로 정제 |
| `outputs/diagnose/round_length4_도면1_table.{py,txt}` | 진단 스크립트·로그 — 재생성 가능 |
| `outputs/archive/images/철골물량_PoC_진행보고.html` | 내부 진행보고 (§4.3) |
| `outputs/archive/poc_v3/` (pytest 캐시 등) | 폐기된 v3 아카이브 |
| `outputs/visualize/*.html` | 위 §2 (재생성 가능·용량) |
| `reference_materials/dxf_anal7.py` | 일회성 분석 스크립트 — 정답지 xlsx 2종만 보존 (§8) |
| `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` | 환경·캐시 (gitignore) |
| `sample_data/*.dxf` | 기밀 입력 — Notion 별도 채널 (gitignore, 작업 7) |
| 〔부재〕 `기타_참고_내용.md`·`제안서.pdf`·`QTO_sample_data.png` 등 | 명세 §4.3 에 거명됐으나 **현 작업트리에 존재하지 않음** (확인 완료) |

---

## 명세 대비 편차 (작업 2 발견)

1. **config yaml 4종 → 5종**: `unit_weight_table.yaml` 추가 필수. baseline-1 단위중량 테스트(29건)·`length/total_weight.py`·`unit_weight.py` 가 참조. 빠지면 회귀 깨짐 → 명세 §13 "회귀 보존" 우선 적용.
2. **baseline 회귀 수 234 → 263 passed**: 명세·task-1 보고서의 "234 passed"는 `qto/tests/test_unit_weight_calc.py`(29건, baseline-1부터 커밋됨)를 누락 집계한 값. 실측 **263 passed / 2 known-fail**(도면2 SC1·SC2). 깨진 테스트 0건. 사용자 승인 하에 **263 을 진짜 baseline 으로 채택** → 신규 문서 전부 263 표기.
3. **§4.3 거명 파일 일부 부재**: `기타_참고_내용.md`·`실제_계획_참고_내용.md`·`1단계_기둥_개수_세기.md`·`건설파트너_프로젝트_제안서.pdf`·`QTO_sample_data.png` 는 현 작업트리에 없음 (이미 정리됨/미존재). 누락 위험 0.

---

## 실제 가져간 / 두고 간 결과 (작업 10 후 갱신)

초기 임포트 PR **#1** (squash merged, 2026-05-31) 기준 — `git ls-files` **128 파일**.

**가져감 (128)**: 루트 5(README·LICENSE·.gitignore·.python-version·pyproject) + config 5 yaml +
poc_v2 58 + docs 2 + reference_materials xlsx 2 + outputs 56.

**두고 감**: sample_data/*.dxf(기밀) · outputs/visualize(~45) · outputs/notes · outputs/diagnose ·
outputs/archive · reference_materials/dxf_anal7.py · outputs/prompts/claude_code_prompt.md · 캐시류.

**PR diff 점검**: 금지 패턴·dxf·캐시·외부URL·이메일 0건. LICENSE Copyright=rangedayo. reference_materials xlsx 2종만.

> 본 보고서(handoff_task2_보고서.md)와 본 큐레이션 doc의 이 최종값은 임포트 머지 후 작성되어,
> 후속 PR #2 로 신규 레포에 반영됨.
