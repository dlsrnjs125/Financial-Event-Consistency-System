# 오래 남은 PROCESSING을 자동 완료하지 않은 이유

장애 이후 가장 애매한 상태는 성공도 실패도 확정하기 어려운 거래다. 요청은 시작됐고, 외부 시스템은 timeout을 봤고, 내부에는 `PROCESSING`이 오래 남아 있을 수 있다.

PH5의 질문은 이것이었다.

```text
PROCESSING 상태가 오래 남았을 때 자동 완료나 자동 실패로 처리해도 되는가?
```

## PROCESSING이 오래 남는다는 것의 의미

`PROCESSING`은 단순히 "실패"가 아니다. 서버가 응답 전에 죽었을 수도 있고, DB 연결이 끊겼을 수도 있고, ledger는 이미 생성됐지만 idempotency response를 저장하지 못했을 수도 있다.

이 상태를 성급하게 완료로 바꾸면 중복 완료가 될 수 있고, 실패로 바꾸면 이미 반영된 거래를 실패로 replay할 수 있다.

## 자동 완료와 자동 실패가 둘 다 위험한 이유

금융 이벤트에서는 ledger, transaction event, account balance, idempotency record가 함께 설명되어야 한다. 하나의 row 상태만 보고 결론을 내리면 정합성 근거가 부족하다.

그래서 PH5에서는 stale detector가 직접 상태를 바꾸지 않게 했다. 먼저 count-only reconciliation으로 어디가 어긋났는지 확인한다.

## Count-only reconciliation으로 먼저 확인한 것

PH5는 다음 후보를 count-only로 집계한다.

- stale processing idempotency record
- transaction event without ledger
- duplicate ledger candidate
- balance mismatch candidate
- reconciliation failure candidate

중요한 점은 "찾았다"와 "고쳤다"를 분리한 것이다. report는 증거이고, 보정은 아니다.

## Recovery Case로 넘긴 이유

위험 후보는 PH4 recovery case로 연결된다. 같은 stale record나 mismatch 후보를 여러 번 탐지해도 `source_key` 기준으로 중복 case가 생기지 않는다.

이 구조는 운영자가 볼 수 있는 질문을 만든다.

- 이 case는 자동 완료 가능한가?
- 원장 보정이 필요한가?
- 고객 영향 확인이 필요한가?
- 어떤 quarantine이 유지되어야 하는가?

## 개발 중 실제로 조심한 점

`transaction_event_without_ledger_count`가 정상 처리 중인 이벤트를 오탐하지 않도록 stale 기준을 분리했다. 막 생성된 processing event는 아직 ledger가 없을 수 있으므로 바로 mismatch로 세면 안 된다.

또 PH5는 DB가 내려간 상태에서 실행하는 drill이 아니다. DB down 중에는 PH1~PH3 flow로 incident evidence를 남기고, DB가 복구된 뒤 reconciliation을 실행하는 것이 맞다.

## 검증한 것

테스트는 stale detector가 fresh/terminal record를 제외하는지, stale 후보가 recovery case로 idempotent하게 연결되는지, stale processing event without ledger만 count하는지, report artifact가 민감 값을 포함하지 않는지 확인한다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH5가 stale PROCESSING과 reconciliation mismatch 후보를 count-only evidence로 만들고 recovery case로 연결했다는 점이다.

말하면 안 되는 것은 PH5가 오래 남은 PROCESSING을 자동 완료/실패 처리하거나, compensation ledger와 balance correction을 자동 실행한다는 주장이다.
