# 사람4 작업 사양 — `poc_v2/integration_run.py`

> **AI 사용 안내**: 이 문서를 첫 메시지에 통째로 붙여넣은 뒤 작업을 시작하세요. 사용자(사람4)의 실제 도면 파일은 절대 업로드하지 마세요. 공개 가능한 코드·yaml 형식·정답 수치만 다룹니다.

---

## 1. 프로젝트 컨텍스트

- 레포: `steel-qto` (Public, GitHub 호스팅, https://github.com/rangedayo/steel-qto)
- 목적: 철골 적산(quantity takeoff) 자동화 PoC
- 사용자 역할: **사람4 — 통합 코드 담당**
- Python: 3.11, Windows + PowerShell 환경, `.venv` 활성화 전제

### 팀 구성 (관련 부분)

| 팀원 | 역할 | 산출물 (이미 main에 머지됨) |
|---|---|---|
| 사람1 | 도메인 규칙 정리 | `docs/domain_rules.md`, `docs/example.yaml`, `docs/domain_rules_설명.md` |
| 사람2 | 스키마·검증기 | `poc_v2/qto/validator.py`, `poc_v2/qto/routing.schema.json`, `docs/schema_설명.md` |
| 사람3 | LLM 라우팅 실험 | (예정) 도면별 LLM 출력 yaml |
| **사람4** | **통합 코드** | **이번 작업: `poc_v2/integration_run.py` + 테스트** |
| 사람5 | 레포 관리자 | PR 머지·게이트키핑 |

### 기존 baseline (수정 금지)

`config/dedup_routing.yaml`(사람이 손으로 작성)을 입력으로 받아 `outputs/round_weight_도면X.csv`를 생성하는 파이프라인이 이미 동작 중이며, **263 PASS / 2 known-fail (도면2-SC1, 도면2-SC2)** 회귀 베이스라인을 가지고 있다. 이 베이스라인은 한 줄도 깨지면 안 된다.

---

## 2. 임무

도면 → LLM 출력 yaml → 검증 → baseline 곱셈 → CSV의 전체 흐름을 **하나의 결정론적 스크립트**로 자동화한다. 기존 baseline의 입력을 "손으로 만든 yaml"에서 "LLM 출력 yaml(검증 통과분)"으로 바꾸는 일이며, **baseline 코드 자체는 호출만 하고 절대 수정하지 않는다.**

---

## 3. 만들 파일 (정확히 2개)

### ① `poc_v2/integration_run.py` — 메인 스크립트

#### 흐름

```
1. LLM 출력 yaml 경로 받기  (인자 또는 함수 파라미터)
2. validate_yaml_file(path) 호출
3. ok=False  →  에러 메시지 출력 후 비정상 종료 (sys.exit(1) 또는 raise)
4. ok=True   →  해당 yaml을 outputs/llm_routing/{도면}_approved.yaml 로 복사 저장
                (디렉토리 없으면 mkdir parents=True)
5. approved yaml을 DedupRoute 리스트로 로드
6. build_default_providers()로 provider 4종 획득
7. compute_weight_for_drawing(...) 호출 → list[WeightRow | SkipRow]
8. 결과를 outputs/round_weight_llm_{도면}.csv 로 저장
   (UTF-8 BOM 포함, Excel 호환)
```

#### 함수 시그니처 예시

```python
from pathlib import Path

def run_for_drawing(drawing: str, llm_yaml_path: Path) -> Path:
    """
    LLM yaml 검증 → baseline 곱셈 → CSV 저장.

    Returns:
        생성된 CSV의 절대 경로.

    Raises:
        ValueError: 검증 실패 시. 메시지에 validator 에러 목록 포함.
        FileNotFoundError: yaml 경로가 없을 때.
    """
    ...
```

#### CLI 진입점

```python
if __name__ == "__main__":
    # 사용 예:
    #   python -m poc_v2.integration_run 도면4 inputs/llm_outputs/도면4_routing.yaml
    # 사람3 LLM 출력이 아직 없으면 정답 yaml로 흉내:
    #   python -m poc_v2.integration_run 도면4 config/dedup_routing.yaml
    ...
```

### ② `poc_v2/tests/test_integration_run.py` — 회귀 테스트

#### 명세

- pytest 형식 (`def test_*` 함수)
- 최소 다음 케이스 포함:
  - `test_integration_run_도면4_total_weight`: 도면4를 `config/dedup_routing.yaml`을 가짜 LLM 출력으로 사용해 돌렸을 때, 생성된 CSV의 도면4 총중량 = 7,140 kg (±1 kg 허용)
  - `test_integration_run_validation_failure`: 일부러 깨뜨린 yaml(예: `spec_from` 누락) 입력 시 ValueError 또는 SystemExit 발생, CSV 미생성
  - `test_integration_run_does_not_overwrite_dedup_routing`: 실행 후 `config/dedup_routing.yaml`의 mtime/내용 미변경 확인
- 테스트는 `tmp_path` fixture로 출력 디렉토리 격리할 것 (실제 `outputs/` 오염 방지)
- 기존 263 PASS / 2 known-fail은 절대 깨지면 안 됨

---

## 4. 입력·출력 명세

### 입력 yaml 형식

`config/dedup_routing.yaml` 형식과 동일. 예시:

```yaml
도면4:
  기둥:
    SC1:
      count_from: "1층 구조평면도"
      spec_from: "1층 구조평면도"
    SC2:
      count_from: "1층 구조평면도"
      spec_from: "1층 구조평면도"
```

스키마 정의는 `poc_v2/qto/routing.schema.json` 참고. 검증은 `validate_yaml_file()`이 자동 수행.

### 출력 CSV 형식

경로: `outputs/round_weight_llm_{도면}.csv`
인코딩: UTF-8 with BOM
컬럼:

```
도면, 부재종류, 부호, 개수, 길이_mm, 규격, 단위중량_kg_per_m, 총중량_kg,
count_from, spec_from, length_from
```

마지막 행은 합계: `{도면}, 기둥, 합계, {총개수}, -, -, -, {총중량_kg}, -, -, -`

가작업 정답 예시 (도면4):

```csv
도면,부재종류,부호,개수,길이_mm,규격,단위중량_kg_per_m,총중량_kg,count_from,spec_from,length_from
도면4,기둥,SC1,14,9000,H-350x175x7x11,48.25,6079.0,1층 구조평면도,1층 구조평면도,"종단면도, 횡단면도"
도면4,기둥,SC2,4,9000,H-194x150x6x9,29.48,1061.4,1층 구조평면도,1층 구조평면도,"종단면도, 횡단면도"
도면4,기둥,합계,18,-,-,-,7140.4,-,-,-
```

### 출력 위치 규칙 (절대 준수)

- **원본 `config/dedup_routing.yaml` 절대 덮어쓰지 않음**
- 검증 통과 yaml: `outputs/llm_routing/{도면}_approved.yaml` (신규 생성)
- 최종 CSV: `outputs/round_weight_llm_{도면}.csv`

---

## 5. 사용할 기존 모듈

```python
# 검증 (사람2 산출물)
from poc_v2.qto.validator import validate_yaml_file
# validate_yaml_file(path: str | Path) -> tuple[bool, list[str]]
#   ok=True 이면 errors=[]
#   ok=False 이면 errors=["[도면X/기둥/A1] 'spec_from' is a required property", ...]

# yaml → DedupRoute 로드 (정확한 함수명은 dedup_loader.py 직접 확인 필요)
from poc_v2.qto.dedup_loader import DedupRoute, SkipMarker
# 모듈 안에 load 함수 또는 클래스가 존재함. import 전에 파일 열어 확인할 것.

# 본선 곱셈 (수정 금지, 호출만)
from poc_v2.qto.weight_pipeline import (
    compute_weight_for_drawing,
    build_default_providers,
    WeightRow,
    SkipRow,
    total_weight_kg,
    total_count,
)

# 시그니처:
# compute_weight_for_drawing(
#     drawing: str,
#     dedup_routes: list[DedupRoute],
#     *,
#     skip_markers: Optional[list[SkipMarker]] = None,
#     count_provider, length_provider, spec_provider, unit_weight_fn,
# ) -> list[WeightRow | SkipRow]
#
# build_default_providers() -> (count_provider, length_provider, spec_provider, unit_weight_fn)
```

> ⚠️ **import 경로는 추정값일 수 있음.** 작업 시작 시 먼저 `poc_v2/qto/dedup_loader.py`, `poc_v2/qto/weight_pipeline.py`, `poc_v2/qto/export_weight_csv.py`를 직접 열어보고 실제 시그니처·함수명을 확인할 것. CSV 출력 형식은 `export_weight_csv.py`를 참고해 정렬·헤더·BOM 처리 일관성을 맞춘다.

---

## 6. 절대 원칙

1. **본선 코드·yaml·정답지 무수정**
   - 수정 금지 디렉토리·파일:
     - `poc_v2/qto/weight_pipeline.py`
     - `poc_v2/qto/dedup_loader.py`
     - `poc_v2/qto/export_weight_csv.py`
     - `poc_v2/baseline2/**`
     - `poc_v2/length/**`
     - `config/dedup_routing.yaml`
     - `reference_materials/**` (정답지)
   - 사람2 산출물(`validator.py`, `routing.schema.json`)도 호출만 하고 수정 금지.

2. **결정론**: 동일 입력 → 동일 출력. LLM 호출은 사람4 영역에서 **절대 금지**(사람3 영역).

3. **회귀 유지**: 작업 후 `pytest -v poc_v2/` → 263 passed (+ 새 테스트 N개) / 2 known-fail (도면2-SC1, 도면2-SC2). 다른 결과 나오면 즉시 중단·원인 분석.

4. **main 직접 push 금지**: 새 feature 브랜치 → PR → squash-merge (사람5가 머지).

5. **requirements.txt 수정 금지**: 이번 작업에 새 의존성 불필요. `pyyaml`, `jsonschema`, `pytest`, `ezdxf` 등 필요한 건 다 명시되어 있음.

6. **public 레포**: 회사명·고객사명·이메일·절대 경로·실제 도면 데이터 모두 금지.

---

## 7. 워크플로우

### (1) 최신 main에서 브랜치 시작

```bash
git checkout main
git pull
git checkout -b feature/integration_run
```

### (2) 작업

- 먼저 `poc_v2/qto/dedup_loader.py`, `weight_pipeline.py`, `export_weight_csv.py` 직접 읽어 시그니처 확인
- `integration_run.py` 구현
- 테스트 작성

### (3) 검증

```bash
# 회귀
pytest -v poc_v2/

# 수동 동작 확인
python -m poc_v2.integration_run 도면4 config/dedup_routing.yaml
# → outputs/round_weight_llm_도면4.csv 가 생성되고 총중량이 7,140 kg 인지 확인
```

### (4) 커밋·푸시·PR

```bash
git add poc_v2/integration_run.py poc_v2/tests/test_integration_run.py
git status   # 본선 코드가 staged 되지 않았는지 반드시 확인
git commit -m "feat: add integration_run.py — LLM yaml 검증→baseline→CSV 통합"
git push origin feature/integration_run
```

PR 본문에 다음 포함:

```
## 변경 내용
- poc_v2/integration_run.py: LLM yaml → validator 검증 → baseline → CSV 통합 스크립트
- poc_v2/tests/test_integration_run.py: 회귀 테스트 N개 추가

## 검증
- pytest -v poc_v2/ → 263 + N passed / 2 known-fail (도면2-SC1, 도면2-SC2) 유지
- python -m poc_v2.integration_run 도면4 config/dedup_routing.yaml
  → outputs/round_weight_llm_도면4.csv 생성, 도면4 총중량 = 7,140 kg 확인
- config/dedup_routing.yaml 미수정 확인
- 본선 코드 diff 0줄 확인
```

---

## 8. 완료 체크리스트

작업 끝났다고 판단하기 전 다음을 모두 확인:

- [ ] `poc_v2/integration_run.py` 작성 완료, CLI 진입점 동작
- [ ] `poc_v2/tests/test_integration_run.py` 작성 완료, 최소 3개 테스트 케이스
- [ ] `pytest -v poc_v2/` → 263 + N passed / 2 known-fail 유지 (다른 결과 나오면 멈출 것)
- [ ] 도면4 통합 실행 → CSV 총중량 7,140 kg (±1) 확인
- [ ] `git diff main..HEAD` 출력에 본선 코드·yaml·정답지 변경 없음
- [ ] `config/dedup_routing.yaml` 미변경 확인
- [ ] `outputs/llm_routing/도면4_approved.yaml` 정상 생성
- [ ] requirements.txt 미변경
- [ ] 브랜치 최신 main 기반 (사람1·2 산출물이 삭제로 표시되지 않음)

---

## 9. 이전 가작업의 교훈 (피해야 할 함정)

이전 가작업 브랜치에서 다음 문제가 발견되었음. 새 작업에서는 반드시 피할 것:

1. **옛 main 기반 브랜치** → 사람1·2 산출물이 diff에서 "삭제" 표시됨. 반드시 최신 main에서 새 브랜치 따기.
2. **`weight_pipeline.py` 1줄 수정** → 본선 무수정 원칙 위반. 같은 효과가 필요하면 `integration_run.py` 안에서 처리.
3. **`requirements.txt` 수정** → 이미 별도 PR로 정리됨. 손대지 말 것.
4. **통합 스크립트 본체(.py) 누락** → CSV만 있고 자동화 코드가 없었음. 이번에는 `.py`가 핵심 산출물.

---

## 10. 응답 톤 (AI 어시스턴트 가이드)

- 사용자(사람4)는 한국 건설 도메인 전문가이며, 코드 경험은 제한적일 수 있음.
- 코드 자체는 정확·결정론적·테스트 가능하게 작성하되, 설명은 **평이한 한국어**로.
- 매 단계마다 무엇을 왜 하는지 한 줄씩 설명 첨부.
- 본선 코드를 수정하고 싶은 유혹이 생기면 **반드시 멈추고 사용자에게 보고**. 우회 방법을 본인 코드 안에서 찾을 것.
- 회사·고객사 도면 데이터 업로드 요청 절대 받지 말 것.
