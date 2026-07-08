# 복구 후보를 바로 실행하지 않고 Recovery Case로 둔 이유

PH3까지는 장애 evidence를 모으고 첫 classification 후보를 만들었다. 그 다음에 바로 복구를 실행하면 편해 보인다. 하지만 금융 이벤트 시스템에서 가장 위험한 순간은 장애 탐지가 아니라 복구 실행이다.

이 글의 질문은 이것이었다.

```text
복구 후보가 생겼을 때, 바로 실행하지 않고 어떤 상태로 보관해야 하는가?
```

## 장애 대응에서 가장 위험한 순간

PostgreSQL 장애나 정합성 위험 후보를 발견했다고 해서 account balance를 고치거나 quarantine을 풀어도 되는 것은 아니다. 원장 보정, write resume, 고객 영향 판단은 모두 금융 책임이 생기는 작업이다.

그래서 PH4에서는 자동화 범위를 "recovery case 생성과 격리 후보 관리"로 제한했다.

## Recovery Case가 필요한 이유

PH4는 `recovery_cases`를 추가했다. PH3 analyzer result는 `source_key` 기준으로 recovery case에 idempotent하게 등록된다. 같은 incident를 여러 번 ingestion해도 중복 case가 생기지 않는다.

Recovery case에는 다음 의미가 있다.

- 어떤 evidence에서 나온 복구 후보인지 남긴다.
- 어떤 manual approval이 필요한지 남긴다.
- 실행 전 상태를 추적한다.
- 자동 실행이 아니라 운영자 검토 대상으로 보관한다.

## Quarantine은 차단이 아니라 보류다

Quarantine은 전체 시스템을 멈추는 write suspend와 다르다. 특정 account 또는 target에 대해 신규 write를 보류하고, 운영자가 확인할 시간을 만든다.

이 보류 상태를 차단으로만 보면 과하다. PH4에서는 quarantine을 "복구 판단 전 추가 피해를 막는 containment"로 해석했다.

## Manual approval boundary를 둔 이유

PH4는 compensation ledger를 만들지 않고, account balance를 직접 수정하지 않고, quarantine release를 자동 승인하지 않는다. API도 기본 비활성화된 read-only admin view로 제한했다.

이 결정은 기능이 부족해서가 아니다. 어떤 작업이 자동화 가능하고, 어떤 작업은 사람 승인으로 남아야 하는지 먼저 고정하기 위해서다.

## 구현 중 트러블슈팅

가장 조심한 부분은 민감 데이터였다. Recovery case에는 raw 금융 식별자, retry 식별자, request body, 인증/서명 자료, secret을 저장하지 않는다.

또 PH3 analyzer result가 `sensitive_data_included=false`가 아니면 case 생성을 거부한다. upstream evidence가 안전하지 않은데 recovery case로 복사하면, 안전하지 않은 artifact가 DB에 오래 남는다.

지원하지 않는 analyzer classification을 recovery case로 받아들이지 않는 것도 중요했다. 알 수 없는 classification은 일단 운영자가 분류 규칙을 보강해야 할 신호이지, 자동으로 generic case를 만드는 신호가 아니다.

## 검증한 것

테스트는 recovery case 생성 idempotency, approval/execution guard, reject 후 실행 차단, analyzer result 기반 case 생성, quarantine write guard, sensitive analyzer result 거부, unsupported classification 거부를 확인한다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH4가 incident classification 후보를 recovery case와 quarantine으로 연결하고, 수동 승인 전 실행을 막는 경계를 만들었다는 점이다.

말하면 안 되는 것은 PH4가 자동 원장 보정, 자동 quarantine release, 자동 write resume을 구현했다는 주장이다. PH4의 핵심은 복구 실행이 아니라 복구 후보의 안전한 보관이다.
