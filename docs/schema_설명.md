# routing.schema.json / validator.py 사용방법

작성일: 2026-06-02

---

## 1. 목적

이 문서는 LLM이 작성한 YAML을 `routing.schema.json` 으로 검증하는 방법을 설명한다.

구성 요소의 역할은 다음과 같다.

- `YAML`: LLM이 실제로 작성한 결과물
- `routing.schema.json`: YAML 형식이 맞는지 검사하는 기준
- `validator.py`: YAML을 읽어 스키마 검증을 수행하는 코드

즉, `YAML`은 작성 대상이고 `JSON Schema`는 검사 기준이다.

---

## 2. 파일 위치

- 스키마 파일: [routing.schema.json](../poc_v2/qto/routing.schema.json)
- 검증 코드: [validator.py](../poc_v2/qto/validator.py)

---

## 3. 전체 사용 흐름

1. LLM이 적산용 YAML을 작성한다.
2. 검증 코드가 YAML을 읽는다.
3. `routing.schema.json` 기준으로 형식을 검사한다.
4. 검증에 통과하면 다음 적산 단계로 넘긴다.
5. 검증에 실패하면 YAML을 수정하거나 사람 검토 단계로 돌린다.

---

## 4. 검증 대상 YAML 예시

예를 들어 LLM이 아래와 같은 YAML을 만들었다고 가정한다.

```yaml
도면1:
  by_section:
    1동:
      skip: true
      skip_reason: "1동에 기둥 길이를 산출할 수 있는 시트가 없어 산출 대상에서 제외"
    2동:
      기둥:
        MC1:
          count_from: "(2동)기둥주심도"
          spec_from: "(2동)기둥주심도"
```

이 YAML을 스키마에 넣어 형식이 맞는지 검사한다.

---

## 5. 파이썬 코드에서 사용하는 방법

`validator.py` 안에는 사람4가 사용할 `validate_yaml_file(...)` 함수가 들어 있다.
기존 `validator_yaml(...)` 함수는 보조 검증 또는 CLI 용도로 유지할 수 있다.

기본 사용 예시는 다음과 같다.

```python
from validator import validate_yaml_file

ok, errors = validate_yaml_file("llm_output.yaml")
if not ok:
    for message in errors:
        print(message)
```

이 경우:

- `llm_output.yaml` 을 읽고
- 같은 폴더의 `routing.schema.json` 을 자동으로 찾아
- 형식 검증을 수행한다
- 검증 결과를 `(통과여부, 에러메시지 목록)` 형태로 돌려준다

반환값 규칙은 다음과 같다.

- 통과 시: `(True, [])`
- 실패 시: `(False, [에러메시지들])`

---

## 6. validator.py 내부 동작

검증 코드는 아래 순서로 동작한다.

1. YAML 파일을 읽는다
2. 스키마 파일을 읽는다
3. `Draft202012Validator(...).iter_errors(...)` 로 오류를 수집한다
4. 형식이 맞으면 `(True, [])` 를 반환한다
5. 형식이 틀리면 `(False, [에러메시지들])` 를 반환한다

즉 이 코드는 `LLM 출력이 형식상 적산 파이프라인에 들어갈 수 있는지`를 확인하는 입구 역할을 한다.

---

## 7. 어떤 오류를 잡는가

현재 스키마는 아래 같은 오류를 잡도록 설계되어 있다.

- `spec_from` 이 없는 경우
- `count_from` 과 `count_override` 가 동시에 있는 경우
- `count_from` 과 `count_override` 가 둘 다 없는 경우
- `skip: true` 인데 `skip_reason` 이 없는 경우
- 부호 아래 값이 객체가 아니라 문자열 하나로 들어간 경우
- `by_section` 구조가 맞지 않는 경우

여러 오류가 있을 경우 한 번에 모아 반환하므로, 사용자는 YAML의 여러 문제를 한 번에 확인할 수 있다.
또한 에러 메시지에는 YAML 내부 위치 경로가 포함된다.

예:

- `[도면2/기둥/SC1] 'spec_from' is a required property`
- `[루트] ...`

---

## 8. 사람4 통합 방식

사람4는 보통 아래 순서로 통합하면 된다.

1. 사람3 또는 LLM이 생성한 YAML 파일을 받는다
2. `validate_yaml_file(...)` 로 형식을 검사한다
3. `(True, [])` 이면 적산 파이프라인으로 넘긴다
4. `(False, [에러메시지들])` 이면 에러를 보여 주고 검토 단계로 돌린다

즉 검증 코드는 `형식이 틀린 YAML이 적산 코드로 들어가는 것을 막는 안전장치`다.

---

## 9. 주의사항

- 이 검증은 `형식`을 검사하는 것이다
- 도면 해석이 맞았는지까지 보장하지는 않는다
- 즉 `스키마 통과 = 적산 판단까지 완전 정답`은 아니다
- 형식 검증 통과 후에도 사람 검토 또는 후속 검증이 필요할 수 있다

---

## 10. 한 줄 요약

LLM은 YAML을 작성하고, 사람2가 만든 `routing.schema.json` 과 `validate_yaml_file(...)` 는 그 YAML이 적산 파이프라인에 들어갈 수 있는 형식인지 먼저 검사한다.

