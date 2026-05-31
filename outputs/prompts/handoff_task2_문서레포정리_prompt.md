# 핸드오프 작업-2 명세서 — 문서·레포 정리 (steel-qto 신규 레포)

> **작성 목적**: PoC v1을 팀원들이 클론해서 바로 회귀 234 PASS 되는 깨끗한 public 레포로
> 정제·이전. 처음부터 **public + branch protection** 셋업, 모든 변경은 PR 워크플로우.
>
> **읽는 순서**: 0 → 1 → 2 → (제약 §13 먼저) → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

---

## 0. TL;DR

| 항목 | 내용 |
|---|---|
| **목표** | steel-qto public 레포 생성, branch protection 셋업, PoC v1 정제·PR로 이전, 검증 |
| **새 레포** | `steel-qto` (https://github.com/rangedayo/steel-qto), **public**, main branch protection 즉시 셋업 |
| **워크플로우** | 자동 생성된 main 위에 feature 브랜치 생성 → PR diff 점검 → 셀프 머지 (직접 push 금지) |
| **노출 안전 전제** | 회사명·고객사명 없음 (사용자 확정). 도면 식별자는 이미 익명화(`도면1`~`도면5`) |
| **원본 영향** | 본선 코드·yaml·정답지·테스트 **무수정**. 정제는 outputs/·문서 영역만 |
| **회귀 안전망** | clean clone → install → DXF 배치 → pytest 한 사이클에서 **234 passed / 2 known-fail** 재현 |
| **산출물** | 새 레포 (PR 1개로 초기 임포트) + README + docs/ 2종 + LICENSE + 검증 보고서 |
| **금지** | 본선·yaml·정답지 수정, 회귀 깨뜨리기, main에 직접 push, PR diff 점검 없이 머지 |

---

## 1. 현재 상태 baseline 기록

작업 시작 전 현 작업 디렉터리에서 회귀 PASS 재확인:

```bash
pytest -v poc_v2/
# → 234 passed / 2 known-fail (도면2 SC1·SC2) 기대
```

핸드오프 작업-1 시점과 동일해야 함. 다르면 중단하고 원인 추적.

---

## 2. 작업 0 — 선결 안전 점검 (최소 점검)

회사명 없음은 사용자 확정. 다만 의도치 않은 누설 한 번 더 점검:

```bash
# 회사명·이메일·연락처
grep -ri "고객사\|발주처\|@gmail\|@naver\|@daum" \
  config/ poc_v2/ reference_materials/ outputs/ README.md 2>/dev/null

# 외부 URL (Notion·드라이브 등 사적 URL 누설 점검)
grep -rni "notion.so\|drive.google\|dropbox\|onedrive" \
  config/ poc_v2/ reference_materials/ outputs/ README.md 2>/dev/null

# 비밀 정보 (API 키·토큰·패스워드) — public 전 필수 점검
grep -rni "password\|secret\|api[_-]key\|access[_-]token\|bearer " \
  config/ poc_v2/ outputs/ README.md 2>/dev/null

# 흔한 API 키 prefix 패턴 (OpenAI sk-, GitHub PAT ghp_/gho_ 등)
grep -rE "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}" \
  config/ poc_v2/ outputs/ README.md 2>/dev/null
```

결과 있으면 사용자 보고 후 결정. 결과 없으면 통과.

> 정답지 xlsx 2종은 grep으로 안 잡히는 셀이 있을 수 있어 별도로 openpyxl로 시트
> 탭명·비고 셀 텍스트 점검 (작업 5에서 정리하며 같이 확인).

---

## 3. 작업 1 — 새 GitHub 레포 생성 + Branch Protection (사용자 직접, 완료됨)

### 3.1 레포 셋업

| 항목 | 값 |
|---|---|
| 이름 | `steel-qto` (`pyproject.toml` 의 `name` 도 동일하게 변경 — 작업 2에서) |
| URL | `https://github.com/rangedayo/steel-qto.git` |
| **공개 범위** | **Public** |
| 설명 | "건설 도면(DXF)에서 철골 부재 물량을 자동 산출하는 PoC" |
| **Initialize with README** | **ON** ← main 브랜치 자동 생성용 (작업 2에서 덮어씀) |
| .gitignore 템플릿 | None (작업 7에서 직접 작성) |
| License | None (작업 8에서 직접 추가) |

### 3.2 Branch Protection 셋업 (즉시)

Settings → Branches → Add branch protection rule:

| 설정 | 값 | 이유 |
|---|---|---|
| Branch name pattern | `main` | main 보호 대상 |
| Require a pull request before merging | ✅ | main 직접 push 차단 |
| Require approvals | **체크 해제** (초기 임포트·셀프 머지 단계) → 팀 합류 시 체크 + `1` 로 변경 | GitHub UI에 `0` 옵션 없음. 승인자 불필요 시 체크박스 자체를 해제 |
| Require linear history | ✅ | history 깔끔 (squash/rebase 권장) |
| Allow force pushes | ❌ | history 보호 |
| Allow deletions | ❌ | 실수 방지 |
| Include administrators | ❌ | 비상시 사용자 직접 push 허용 |

이 셋업 후 모든 변경(사용자·팀원 동일)은 feature 브랜치 → PR → 머지 흐름.

---

## 4. 작업 2 — 파일 큐레이션 (가져갈 / 두고 갈)

작업 디렉터리 전체 스캔 후 표로 정리. **신규 레포 초기 커밋 직전** 단계.

### 4.1 가져갈 (필수)

| 경로 | 비고 |
|---|---|
| `config/` (yaml 4종) | symbol_rules / length_routing / sheet_name_overrides / dedup_routing |
| `poc_v2/` 전체 | tests / length / baseline2 / qto + requirements.txt |
| `reference_materials/도면_정답지.xlsx` | 카운트 정답지 (회귀 의존) |
| `reference_materials/도면_길이_정답지.xlsx` | 길이·규격 정답지 (회귀 의존) |
| `pyproject.toml` | Python 3.11 핀. **`name = "construction-ai-estimator"` → `"steel-qto"` 로 변경 후 이전** |
| `.python-version` | 3.11.9 |
| `.gitignore` (정비 후) | 작업 7에서 |
| `README.md` (재작성) | 작업 3에서 |
| `LICENSE` (신규) | 작업 9에서 |
| `docs/round_history.md` (신규) | 작업 4에서 |
| `docs/domain_rules_seed.md` (신규) | 작업 5에서 |
| `outputs/handoff_task1_보고서.md` | 환경 재현성 검증 결과물 |
| `outputs/handoff_task2_보고서.md` (신규) | 본 작업 결과물 |

### 4.2 가져갈 (선택 — 사용자 결정)

| 경로 | 권장 | 사유 |
|---|---|---|
| `outputs/prompts/round_*.md` | 가져가기 | 라운드 14개 명세 — round_history.md 의 근거 |
| `outputs/prompts/handoff_task1_환경검증_prompt.md` | 가져가기 | 핸드오프 명세 (보고서와 짝) |
| `outputs/prompts/handoff_task2_문서레포정리_prompt.md` | 가져가기 | 핸드오프 명세 (보고서와 짝) |
| `outputs/round_*_보고서.md` | 가져가기 | 라운드 보고서 — 역사 기록 |
| `outputs/round_weight1b_5장_총중량.csv` | 가져가기 | **PoC v1 deliverable** |
| `outputs/round_weight1a_도면4_총중량.csv` | 가져가기 | 중간 검증물 |
| `outputs/round_*_검증.csv`, `*_시트별_결과.csv` 등 | 가져가기 | 라운드 결과 데이터 |
| `outputs/visualize/*.html` (~40개) | **두고 갈** 권장 | 용량 큼·재생성 가능. 필요 시 한두 개 샘플만 |

### 4.3 두고 갈 (절대 포함 금지)

| 경로 | 사유 |
|---|---|
| `기타_참고_내용.md`, `실제_계획_참고_내용.md`, `1단계_기둥_개수_세기.md`, `기둥길이_재기.md` | 컨텍스트 메모 — 작업 중 사적 메모, 외부 공유 부적합 |
| `철골물량_PoC_진행보고.html` | 내부 진행보고 |
| `QTO_sample_data.png` | 외부 출처 이미지 |
| `건설파트너_프로젝트_제안서.pdf` | 사업 제안서 |
| `.venv/`, `__pycache__/`, `*.pyc` | 환경·캐시 |
| `sample_data/*.dxf` | gitignore로 자동 제외 (작업 7) |

### 4.4 산출물

`outputs/handoff_task2_파일큐레이션.md` — 위 3종 표를 그대로 정리 + 실제 가져간 / 두고 간 결과 기록.

---

## 5. 작업 3 — README.md 9섹션 재작성

대상 파일: 신규 레포 루트의 `README.md` (현 작업 디렉터리 README는 참조용).

### 섹션별 분량·내용 지침

```
1. 개요 (3~5 줄)
   - 무엇을 하는 PoC인지 한 줄
   - 현재 done: 5장 통합 기둥 총중량 CSV (188,726.7 kg / 109개)
   - 다음 후보: 보 부재, 단면적 식 정확화, LLM 라우팅

2. 파이프라인 그림 (ASCII)
   측정 3종(카운트·길이·규격) → dedup yaml → weight_pipeline → 총중량 CSV
   ┃                                    ┃
   ┃ baseline-1~7 누적                  ┃ 중량-1a/1b
   ┗━━ 사람이 손으로 채운 yaml 4종 ━━━━━┛
   (LLM 라우팅 자리 = 사람이 임시 차지 — 다음 라운드 후보)

3. 환경 세팅 (정확히 4단계)
   1) git clone <repo-url>
   2) python -m venv .venv && .venv/Scripts/activate (Windows) 또는 source .venv/bin/activate
      pip install -r poc_v2/requirements.txt
   3) Notion 비공개 채널에서 sample_data/*.dxf 5종 받아 sample_data/ 에 배치
      ※ 정답지 xlsx 2종은 클론에 이미 포함
   4) pytest -v poc_v2/  → 234 passed / 2 known-fail 확인

4. 빠른 시작 (1분 안에 첫 결과 보기)
   # 도면4 한 장 총중량 CSV 생성
   python -m poc_v2.qto.export_weight_csv --drawing 도면4
   # 5장 통합 PoC v1 deliverable 재생성
   python -m poc_v2.qto.export_weight_csv --all

5. 코드 구조 (디렉터리 트리, 깊이 2단계)
   config/        yaml 4종
   poc_v2/
   ├── tests/    1단계 회귀
   ├── length/   길이·규격
   ├── baseline2/ 작은 도면 입력 (baseline-2~7)
   └── qto/      중량 산출 (중량-1a/1b) ← PoC 본 deliverable
   reference_materials/ 정답지 xlsx 2종
   sample_data/   gitignored, Notion 별도 채널
   outputs/       라운드 결과물
   docs/          round_history.md, domain_rules_seed.md

6. 새 도면 yaml 채우는 법 (사람 가이드, ~30줄)
   - symbol_rules.yaml: 부호 화이트리스트 추가
   - length_routing.yaml: 시트별 라우팅 추가
   - sheet_name_overrides.yaml: 자동 매칭 실패 케이스만 fallback
   - dedup_routing.yaml: 중복 함정 라우팅 (count_from / spec_from / by_section / skip / count_override)
   - 자세한 도메인 룰은 docs/domain_rules_seed.md 참조

7. 알려진 한계 (표 4종)
   - 도면2 SC1·SC2 카운트 (블록 내부 split-TEXT, count_override 격리)
   - 도면1 1동 기둥 길이 (시트 부재, skip 격리)
   - 도면5 Y1축열 길이 측정 (소스 차이)
   - 단위중량 식 KS 대비 -2~3% (4세그먼트 근사, 멘토 확정 — 현재 식 유지)

8. 라운드 이력
   docs/round_history.md 링크 + "총 라운드 N개, PoC v1 완성까지의 결정 흐름" 한 줄

9. 참고
   - 단위중량 계산식 (단면적 × 7,850 kg/m³)
   - KS D 3502 (참고 표준)
   - 의사결정 원칙 (AI는 결정만, 도구는 측정만 / 회귀 안전망 절대 / 보편 룰 우선 / 솔직한 한계 인정)
```

각 섹션 한 페이지 이하. 전체 README 200~300줄 목표.

---

## 6. 작업 4 — `docs/round_history.md` 작성

라운드별로 한 단락씩 시간 순. 형식:

```
## 1단계 — 부호 카운트
프로젝트 시작. 도면 5장에서 부재 부호별 개수 카운트.
회귀 14/16 PASS. 도면2 SC1·SC2 데이터 한계(블록 내부 split-TEXT) 격리.

## 길이-1 — DIMENSION 기반 길이 추출
세로 DIMENSION 최댓값 룰. 16/16 PASS.

## 규격-1 — 부호↔규격 페어링
일람표 영역 검출 + 좌표 기반 페어링. 25/25 PASS.
중복 함정 발견 (LLM 라우팅 라운드 후보).

## baseline-1 — 단위중량 통일 함수
단면적 × 7,850 kg/m³ 식 (4세그먼트 근사). KS 표 대비 -2~3%.

## baseline-2 ~ baseline-7
작은 도면 입력 모듈 확장. 도면4(19/19)·5(33/33)·3(19/19)·2(16/16)·1(48/48) 추가.
baseline-7: 분리본 routing 일반화.

## 중량-1a (도면4)
dedup yaml + 곱셈·CSV 첫 사이클. 도면4 7,140.4 kg.

## 중량-1b (5장 통합) ← PoC v1 deliverable
by_section / skip / count_override 스키마 확장. **5장 통합 188,726.7 kg / 109개**.

## 핸드오프 작업-1
환경 재현성 검증. 클린 install 234 PASS.
```

라운드별 단락은 **결과와 의미**만. 코드 변경 디테일은 outputs/round_*_보고서.md를 가리킨다.

목표 분량: 라운드당 3~5줄 × 12~14개 라운드 = 50~70줄.

---

## 7. 작업 5 — `docs/domain_rules_seed.md` 작성

목적: 사람1(도메인 규칙 정리 담당자)이 받아서 다듬을 시드. yaml 4종의 주석·결정 사유를 자연어로 풀어 작성.

### 7.1 섹션 구성

```
1. 부호 화이트리스트 정책 (symbol_rules.yaml 근거)
   - 무엇이 부재 부호이고 무엇이 아닌가
   - 자동 제외 카테고리 (기초·철근·상세 참조·두께 표기·통심선)
   - 슬래시 결합 표기 (C1/P1 등) 해석

2. 길이 측정 라우팅 정책 (length_routing.yaml 근거)
   - 세로 DIMENSION 최댓값 룰
   - 시트별 라우팅 필요한 이유 (한 도면에 여러 시트, 측정 소스 다름)

3. 시트명 매칭 fallback 정책 (sheet_name_overrides.yaml 근거)
   - 자동 매칭 실패 케이스만 등록
   - 분리본 sheet (baseline-7 component 매칭)

4. 중복 판별 정책 (dedup_routing.yaml 근거)
   - count_from / spec_from 분리 사유
   - by_section (도면1 동별)
   - skip (도면1 1동 — 측정 소스 부재)
   - count_override (도면2 — 측정 한계 격리)
```

### 7.2 작성 원칙

- yaml에서 본 *결과 룰*을 자연어로 풀어 쓰되, **함수 시그니처·파일 경로·상수 값은 빼고 의미만**
- 라운드 N 같은 시간 서술 없이 *현재 룰*로 작성
- 도면명은 *예시*로만 사용, 룰 자체는 도면 무관 보편 표현
- 도메인 전문가가 읽고 이해 가능한 톤

근거 자료: `outputs/prompts/llm-wiki_prompt.md` (이미 작성된 룰 가이드 형식 참고 가능).

---

## 8. 작업 6 — `reference_materials/` 정리

작업 디렉터리에서 신규 레포로 옮기기 전 정리:

```bash
# 정답지 xlsx 2개만 남기고 나머지 삭제
cd reference_materials/
# 보존: 도면_정답지.xlsx, 도면_길이_정답지.xlsx
# 삭제: 그 외 일체
```

### 8.1 정답지 시트명·셀 점검

openpyxl로 시트 탭명·헤더 행·비고 셀 grep:

```python
import openpyxl, re
wb = openpyxl.load_workbook("도면_정답지.xlsx", data_only=True)
patterns = re.compile(r"고객사|발주처|@|http")
for sn in wb.sheetnames:
    ws = wb[sn]
    for row in ws.iter_rows(values_only=True):
        for v in row:
            if isinstance(v, str) and patterns.search(v):
                print(sn, v)
```

발견 시 사용자 보고. 없으면 통과.

---

## 9. 작업 7 — `.gitignore` 정비

신규 레포 `.gitignore` 최종 형태:

```gitignore
# 환경
.venv/
__pycache__/
*.pyc
*.pyo

# 비밀 정보 (환경변수 파일은 절대 커밋 금지)
.env
.env.*
!.env.example

# IDE
.idea/
.vscode/
.DS_Store

# 기밀 입력 데이터 (Notion 별도 채널)
sample_data/*.dxf

# 빌드·캐시
*.egg-info/
.pytest_cache/

# reference_materials/ 는 git 포함 (정답지 xlsx 2종 — 기밀 아님)
```

기존 `.gitignore`의 `reference_materials/` 라인 **제거**. `sample_data/*.dxf`는 유지.
`.env*` 패턴은 환경변수 파일 자동 차단 (이 프로젝트는 현재 .env 미사용이나 후속 라운드 안전망).

---

## 10. 작업 8 — LICENSE 추가

**MIT 추천**. 사유: 짧고·관대하고·회사명 무관. 상업적 이용 허용 명시.

`LICENSE` 파일:
```
MIT License

Copyright (c) 2026 rangedayo

Permission is hereby granted, free of charge, to any person obtaining a copy
...
```

전문은 GitHub LICENSE 템플릿 또는 https://choosealicense.com/licenses/mit/ 의 MIT 전문 그대로.

대안: Apache 2.0 (특허 조항 명시) — 필요하면 선택.

---

## 11. 작업 9 — 검증 한 사이클 (clean clone)

핸드오프-1 의 검증과 동일한 절차를 **신규 레포**로 반복:

```bash
# 작업 디렉터리와 완전히 분리된 폴더
mkdir C:\temp\verify-new-repo
cd C:\temp\verify-new-repo

# public 레포 clone (인증 불필요)
git clone https://github.com/rangedayo/steel-qto.git
cd steel-qto

# venv + install
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r poc_v2/requirements.txt

# Notion 에서 DXF 5종 받아 sample_data/ 에 배치 (수동)
# 도면1.dxf, 도면2.dxf, 도면3.dxf, 도면4.dxf, 도면5.dxf
# (분리본 dxf 포함 — Notion 채널 안내대로)

# 회귀 실행
pytest -v poc_v2/
```

**기대 결과**: `234 passed / 2 known-fail`.

### 11.1 검증 실패 시 대응

| 증상 | 원인 후보 | 대응 |
|---|---|---|
| ImportError | requirements.txt 누락 | 누락 패키지 핀해서 push, 재검증 |
| FileNotFoundError on yaml | config/ 누락 | 큐레이션 누락, 재커밋 |
| FileNotFoundError on xlsx | reference_materials/ 미포함 (gitignore 잔존) | .gitignore 재확인, 재커밋 |
| FileNotFoundError on dxf | Notion 배치 순서 누락 | README 환경 세팅 §3 보완 |
| 회귀 fail (도면2 SC1·SC2 외) | 본선 코드·yaml 누락 | 큐레이션 점검, 재커밋 |

PASS 확인 후 검증 폴더 삭제.

---

## 12. 작업 10 — 첫 PR 머지 + 보고서

### 12.1 PR diff 점검 (가장 중요한 안전장치)

PR 페이지 (`https://github.com/rangedayo/steel-qto/pull/N`)의 "Files changed" 탭에서:
- 변경 파일 목록 전수 확인 — "두고 갈" 표(§4.3)의 파일이 들어갔는지
- LICENSE Copyright Owner = `rangedayo` 확인
- README 환경 세팅 4단계가 정확한지
- 의도치 않은 파일·외부 URL·사적 정보 잔존 없는지

체크 명령 (feature 브랜치 상태에서):
```bash
git ls-files | grep -iE "제안서|진행보고|sample_data\.png|기타_참고|실제_계획"
# → 결과 없어야 함

git ls-files | wc -l
# → 가져갈 파일 수와 일치해야 함
```

### 12.2 머지

PR 페이지에서:
- "Squash and merge" 또는 "Rebase and merge" 선택 (Require linear history ✅ 이므로 일반 merge commit 불가)
- Merge 버튼 클릭
- 머지 후 feature 브랜치 삭제

### 12.3 보고서

`outputs/handoff_task2_보고서.md` (신규):

```
# 핸드오프 작업-2 보고서 — 문서·레포 정리

## 0. 결론 (TL;DR)
| 항목 | 결과 |
| 새 레포 | steel-qto (https://github.com/rangedayo/steel-qto) |
| 공개 범위 | Public |
| Branch protection | main 보호 활성화 (PR 필수, linear history) |
| 초기 임포트 PR | #N (merged YYYY-MM-DD) |
| clean clone 검증 | 234 passed / 2 known-fail |

## 1. 파일 큐레이션 결과
가져간 / 두고 간 표 (작업 2 산출물 인용)

## 2. 신규 파일
- README.md (9섹션, N줄)
- docs/round_history.md (라운드 14개)
- docs/domain_rules_seed.md (4섹션)
- LICENSE (MIT, Copyright rangedayo)

## 3. 검증 결과
clean clone → pytest 234 PASS 로그 첨부

## 4. 알려진 후속 작업
- 보 부재 통합 라운드
- 단면적 식 KS 표 룩업 (-2~3% 해소)
- LLM 라우팅 자동화

## 5. 팀 공유 안내 템플릿
(슬랙·이메일에 붙여넣을 5줄)
```

---

## 13. 제약사항

### 13.1 절대 금지
- 본선 코드(`poc_v2/`)·yaml(`config/`)·정답지(`reference_materials/*.xlsx`)·테스트 수정
- 회귀 234/2 깨뜨리기 (한 건이라도 깨지면 즉시 중단·보고)
- main에 직접 push (반드시 feature 브랜치 → PR → 머지)
- PR diff 점검 없이 셀프 머지
- 회사명·외부 URL·이메일·사적 정보 발견 시 무시하고 푸시
- "두고 갈" 표(§4.3)의 파일 신규 레포 포함

### 13.2 허용
- 신규 파일: README.md, LICENSE, docs/round_history.md, docs/domain_rules_seed.md
- 정제: `reference_materials/` 정답지 2개 외 삭제, `.gitignore` 정비
- 파일 이동·복사: 작업 디렉터리 → 신규 레포 (큐레이션 표 기준)
- 보고서: `outputs/handoff_task2_*` 신규

### 13.3 결정론
- LLM·랜덤·외부 호출 0건
- 동일 입력 → 동일 출력 보장

---

## 14. 작업 순서

```
0. 선결 점검 (회사명·외부 URL grep, 결과 0건 확인)
1. 새 레포 생성 + Branch protection 셋업 (사용자 직접, 완료됨)
2. 파일 큐레이션 표 작성 (가져갈 / 두고 갈 / 선택)
3. README.md 9섹션 재작성
4. docs/round_history.md
5. docs/domain_rules_seed.md
6. reference_materials/ 정리 + 시트명 점검
7. .gitignore 정비
8. LICENSE 추가 (MIT, Copyright rangedayo)
9. 신규 레포 clone → feature/initial-import 브랜치 → 산출물 stage → push → PR 생성
10. PR diff 점검 → 셀프 머지 (Squash or Rebase)
11. 검증 한 사이클 (clean clone → install → DXF 배치 → pytest 234 PASS)
12. 보고서 + 팀 공유
```

**중간 보고 지점**:
- 작업 2 후 — 큐레이션 표 사용자 검토
- 작업 6 후 — 정답지 점검 결과
- 작업 10 후 — 검증 결과 (전환 직전)

---

## 15. 산출물 체크리스트

- [x] GitHub 신규 레포 `steel-qto` (public, https://github.com/rangedayo/steel-qto)
- [ ] Branch protection 셋업 (main, PR 필수, linear history)
- [ ] 초기 임포트 PR #N merged
- [ ] README.md (9섹션)
- [ ] LICENSE (MIT, Copyright rangedayo)
- [ ] docs/round_history.md
- [ ] docs/domain_rules_seed.md
- [ ] `.gitignore` 정비
- [ ] `reference_materials/` 정답지 xlsx 2개만 잔존
- [ ] `outputs/handoff_task2_파일큐레이션.md`
- [ ] `outputs/handoff_task2_보고서.md`
- [ ] clean clone 검증 234 PASS 로그

---

**문서 끝.**
