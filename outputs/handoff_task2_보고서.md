# 핸드오프 작업-2 보고서 — 문서·레포 정리

> **작성일**: 2026-05-31
> **목표**: PoC v1 을 팀원이 클론해 바로 회귀 PASS 되는 깨끗한 public 레포(steel-qto)로 정제·이전.
> **원칙 준수**: 본선 코드(`poc_v2/`)·yaml(`config/`)·정답지(`*.xlsx`)·테스트 **무수정**. main 직접 push 0건, 모든 변경 PR.

---

## 0. 결론 (TL;DR)

| 항목 | 결과 |
|---|---|
| 새 레포 | **steel-qto** (https://github.com/rangedayo/steel-qto) |
| 공개 범위 | **Public** |
| Branch protection | main 보호 활성 (PR 필수, linear history) — 사용자 셋업 완료 |
| 초기 임포트 PR | **#1** (squash merged, 2026-05-31) — 128 파일 |
| clean clone 검증 | **263 passed / 2 known-fail** (도면2 SC1·SC2) 재현 ✅ |
| 본선 코드 수정 | ❌ 없음 (원칙 준수) |
| main 직접 push | ❌ 0건 (feature 브랜치 → PR → squash 머지) |

---

## 1. 파일 큐레이션 결과

큐레이션 표 전문은 [handoff_task2_파일큐레이션.md](handoff_task2_파일큐레이션.md) 참조.

**실제 가져간 것 (128 파일, `git ls-files` 기준)**
- 루트 5: `README.md` · `LICENSE` · `.gitignore` · `.python-version` · `pyproject.toml`
- `config/` 5 yaml (symbol_rules · length_routing · sheet_name_overrides · dedup_routing · **unit_weight_table**)
- `poc_v2/` 58 (tests · length · baseline2 · qto + requirements.txt)
- `docs/` 2 (round_history.md · domain_rules_seed.md)
- `reference_materials/` 정답지 xlsx 2종
- `outputs/` 56 (handoff 보고서·큐레이션, 라운드 프롬프트·보고서, 결과 CSV — PoC v1 deliverable 포함)

**실제 두고 간 것**
- `sample_data/*.dxf` (기밀 — Notion 비공개 채널, gitignore)
- `outputs/visualize/*.html` (~45, 재생성 가능) · `outputs/notes/` · `outputs/diagnose/` · `outputs/archive/`
- `reference_materials/dxf_anal7.py` · `outputs/prompts/claude_code_prompt.md`
- `.venv/` · `__pycache__/` · `*.pyc` · `.pytest_cache/`

**PR diff 점검 (머지 직전) — 전항 통과**
- 금지 파일 패턴(제안서·진행보고·기타_참고 등) 0건
- dxf·캐시·제외 디렉터리 0건 · 외부 URL·이메일 누설 0건
- LICENSE Copyright = `rangedayo` · reference_materials = xlsx 2종만 · 추적 128 파일

---

## 2. 신규 파일

| 파일 | 내용 |
|---|---|
| `README.md` | 9섹션 (개요·파이프라인·환경세팅 4단계·빠른시작·코드구조·yaml 가이드·알려진한계·라운드이력·참고) |
| `docs/round_history.md` | 라운드 14개(1단계→길이→규격→baseline-1~7→중량-1a/1b→핸드오프) 시간순 |
| `docs/domain_rules_seed.md` | 4섹션 (부호 화이트리스트·길이 라우팅·시트명 fallback·중복 판별) — 도메인 담당자 시드 |
| `LICENSE` | MIT, Copyright (c) 2026 rangedayo |
| `.gitignore` | sample_data/*.dxf 유지, reference_materials 포함, .env* 차단 |
| `pyproject.toml` | `name` 을 `steel-qto` 로 변경 |

---

## 3. 검증 결과 (clean clone)

작업 디렉터리와 완전 분리된 `C:\temp\verify-new-repo` 에서:

```
git clone https://github.com/rangedayo/steel-qto.git
py(3.11.9) -m venv .venv ; pip install -r poc_v2/requirements.txt   # exit 0
sample_data/ 에 DXF 5종(+분리본) 배치
pytest -q poc_v2/
→ 2 failed, 263 passed, 7 warnings in 167.73s
   FAILED test_regression.py::test_symbol_total[도면2-SC1]
   FAILED test_regression.py::test_symbol_total[도면2-SC2]
```

**263 passed / 2 known-fail** — 원본 baseline과 동일하게 재현. 검증 후 폴더 삭제.

### 3.1 발견된 환경 카베앗 (deliverable 결함 아님)
- 한국어 Windows(cp949 로캘) + 구버전 pip 조합에서 `pip install -r poc_v2/requirements.txt` 가
  requirements.txt 의 UTF-8 한글 주석(em-dash 등)을 cp949 로 잘못 디코딩해 `UnicodeDecodeError` 발생.
- **`PYTHONUTF8=1`**(Python UTF-8 모드) 설정 시 정상 install (검증은 이 모드로 통과).
- 파일 자체는 정상 UTF-8 이며 본선 무수정 원칙상 손대지 않음. **후속 권장**: README 환경세팅에
  `set PYTHONUTF8=1` 안내 추가, 또는 별도 라운드에서 requirements.txt 주석을 ASCII 로 정리.

### 3.2 baseline 수치 정정 (234 → 263)
- 명세·핸드오프-1 보고서의 "234 passed" 는 `qto/tests/test_unit_weight_calc.py`(29건, baseline-1부터 커밋)를
  누락 집계한 값. 실측 전체는 **263 passed / 2 known-fail** 이며 깨진 테스트 0건.
- 사용자 승인 하에 263 을 진짜 baseline 으로 채택, 신규 문서 전부 263 으로 표기.

---

## 4. 알려진 후속 작업

- 보(beam) 부재 통합 라운드 (현재 기둥만 산출).
- 단면적 식 KS 표 룩업 (현재 4세그먼트 근사, KS 대비 -2~3%).
- 측정 라우팅(dedup/length/sheet yaml) LLM 자동화 — 현재 사람이 임시로 채우는 결정 슬롯.
- requirements.txt 주석 ASCII 정리 또는 README 에 PYTHONUTF8 안내 (§3.1).

---

## 5. 팀 공유 안내 템플릿

> 📦 **steel-qto** 레포가 열렸습니다 — 철골 물량 산출 PoC v1.
> 클론 후 `pip install -r poc_v2/requirements.txt` → Notion 채널에서 DXF 5종을 `sample_data/` 에 배치 → `pytest -v poc_v2/` 로 263 passed / 2 known-fail 확인하면 환경 OK.
> (한국어 Windows에서 install 인코딩 에러 나면 `set PYTHONUTF8=1` 후 재시도)
> 현재 done: 5장 통합 기둥 총중량 188,726.7 kg / 109개. 도메인 규칙은 `docs/domain_rules_seed.md`, 라운드 이력은 `docs/round_history.md` 참고.
> https://github.com/rangedayo/steel-qto

---

**문서 끝.**
