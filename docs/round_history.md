# 라운드 이력

PoC v1(5장 통합 기둥 총중량 CSV)에 이르기까지의 라운드별 결정 흐름.
각 라운드는 **결과와 의미**만 적는다. 코드 변경 디테일은 `outputs/round_*_보고서.md` 참조.

---

## 1단계 — 부호 카운트
프로젝트 시작. 도면 5장에서 부재 부호별 개수를 합계 기준으로 카운트.
페이지 분할 정책을 폐기하고, "무엇을 셀지(화이트리스트) / 무엇을 거를지(제외 규칙)"만 yaml로 정의.
회귀 14/16 PASS. 도면2 SC1·SC2는 블록 내부 split-TEXT 데이터 한계로 측정 불가 → 격리.

## 길이-1 — DIMENSION 기반 길이 추출
세로 방향 DIMENSION 엔티티의 measurement 최댓값을 기둥 길이로 채택하는 룰.
시트별 측정 소스를 length_routing.yaml로 라우팅. 16/16 PASS.

## 길이-4 — 단위중량 표 초안
H형강 규격 → 단위중량(kg/m) 참조 표(unit_weight_table.yaml) 초안 작성.
KS D 3502 정확값은 멘토 확인 대상으로 남기고, 이후 계산식 방식으로 대체됨.

## 규격-1 — 부호↔규격 페어링
일람표 영역을 검출하고 좌표 기반으로 부호↔규격을 페어링. 25/25 PASS.
같은 부호가 여러 시트에 등장하는 **중복 함정**을 발견 (이후 dedup 라우팅·LLM 라우팅 후보).

## baseline-1 — 단위중량 통일 함수
규격 → 4세그먼트 단면적 × 7,850 kg/m³ 로 단위중량을 계산하는 함수로 통일.
KS 표 대비 -2~3% 근사(멘토 확정, 현재 식 유지). 단위중량 단위테스트 추가.

## baseline-2 ~ baseline-7 — 작은 도면 입력 모듈 확장
작은 도면(단일/분리본) 입력 파이프라인을 도면별로 확장:
도면4 → 5 → 3 → 2 → 1 순으로 회귀 추가. baseline-7에서 분리본 sheet routing을 일반화.
일람표 좌표매칭 차감으로 누적 회귀 확립.

## 중량-1a (도면4) — 곱셈·CSV 첫 사이클
dedup_routing.yaml(도면4 섹션) + weight_pipeline + CSV export 첫 사이클.
도면4 기둥 총중량 **7,140.4 kg** (KS 대비 -2.9%) PASS. 측정 모듈 무수정.

## 중량-1b (5장 통합) ← PoC v1 deliverable
dedup 스키마를 by_section / skip / count_override 로 확장해 5장 통합.
**5장 통합 기둥 총중량 188,726.7 kg / 109개**. PoC v1 본 deliverable 완성.

## 핸드오프 작업-1 — 환경 재현성 검증
별도 폴더·새 venv에서 클린 install → 회귀 재현 검증. requirements 버전 핀·pyproject 신설.
클린 install PASS. (테스트 데이터 gitignore로 인한 온보딩 블로커를 보고서에 기록.)

## 핸드오프 작업-2 — 문서·레포 정리
PoC v1을 팀 공유용 public 레포(steel-qto)로 정제·이전.
clean clone 검증 **263 passed / 2 known-fail** 재현. (이 문서가 그 산출물.)

---

> known-fail 2건(도면2 SC1·SC2)은 1단계부터 수용된 데이터 한계로, 회귀 실패가 아니라
> `count_override`로 격리된 항목이다.
