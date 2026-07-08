# PostgreSQL HA와 Queue를 바로 붙이지 않은 이유

PostgreSQL이 Source of Truth인 금융 이벤트 시스템에서 가장 먼저 떠오르는 개선은 HA와 durable queue다. 둘 다 좋은 선택지가 될 수 있다. 하지만 바로 붙이지 않은 이유는 구현 난이도 때문이 아니라, API 응답 의미와 정합성 책임이 같이 바뀌기 때문이다.

PH8의 질문은 이것이었다.

```text
HA나 Queue를 붙이면 정말 문제가 해결되는가?
```

## 장애 대응 기술을 붙이면 끝나는가?

현재 API는 PostgreSQL commit 이후에 `COMPLETED`를 설명할 수 있다. PostgreSQL write path가 죽으면 신규 금융 write는 `503 + Retry-After`로 fail-closed 한다.

이 선택은 장애 중 성공률을 낮추지만, 처리 여부가 불명확한 성공 응답을 만들지 않는다.

## Direct PostgreSQL transaction을 유지한 이유

PH8에서는 다섯 가지 option을 비교했다.

| 선택지 | 핵심 |
| --- | --- |
| Direct PostgreSQL transaction + fail-closed | 현재 구조. `COMPLETED` 의미가 가장 명확하다. |
| PostgreSQL primary/standby HA | DB 단일 장애점을 줄이지만 failover 검증이 필요하다. |
| Synchronous replication | RPO를 낮출 수 있지만 commit latency가 증가한다. |
| Managed DB HA | DB 운영 부담은 줄지만 app retry/readiness 책임은 남는다. |
| Durable queue-first architecture | 수신 가용성은 높지만 `ACCEPTED`와 `COMPLETED`를 분리해야 한다. |

현재 프로젝트에서는 direct PostgreSQL transaction + fail-closed를 유지했다. API contract를 바꾸지 않고 가장 잘 설명할 수 있는 선택이기 때문이다.

## HA가 해결하는 것과 해결하지 못하는 것

HA는 장애 window를 줄일 수 있다. 하지만 HA가 있으면 consistency gate가 필요 없어진다는 뜻은 아니다.

Failover 후 stale connection, primary identity 확인, replication lag, write resume approval은 여전히 남는다. 그래서 PH8 decision evidence에는 HA option에도 consistency gate와 resume approval을 필수 control로 넣었다.

## Queue-first 구조에서 ACCEPTED와 COMPLETED를 분리해야 하는 이유

Queue-first는 DB down 중에도 요청을 받을 수 있게 해준다. 하지만 queue에 들어갔다는 사실은 ledger가 PostgreSQL에 반영됐다는 뜻이 아니다.

따라서 queue-first를 도입한다면 응답 의미를 분리해야 한다.

- `ACCEPTED`: queue가 이벤트를 받았다.
- `COMPLETED`: consumer가 PostgreSQL에 원장 반영을 끝냈다.

이 둘을 섞으면 금융 이벤트 처리 의미가 깨진다.

## ADR로 먼저 남긴 판단

PH8은 실제 HA cluster나 queue middleware를 구현하지 않았다. 대신 decision matrix와 validator를 만들었다.

```bash
make ph8-ha-queue-decision-demo
make ph8-ha-queue-decision-validate
make ph8-architecture-check
```

decision score는 benchmark가 아니라 project-fit signal이다. 숫자가 절대 성능 지표처럼 읽히지 않도록 report에 note를 남겼다.

## 구현 중 실제로 막은 오해

validator는 queue-first가 ledger completion을 보장한다고 쓰는 문장, HA가 consistency gate를 대체한다고 쓰는 문장, decision matrix total이 option score와 맞지 않는 경우를 실패 처리한다.

이 검증은 문서형 산출물에도 무결성이 필요하다는 판단에서 넣었다. PH8의 output은 코드 실행 결과보다 decision evidence에 가깝기 때문이다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH8이 PostgreSQL HA와 durable queue 도입 전 API contract, 정합성 책임, 운영 승인 경계를 ADR과 decision evidence로 정리했다는 점이다.

말하면 안 되는 것은 PH8에서 HA cluster, queue middleware, queue-first V2 API를 구현했다는 주장이다. PH8은 도입이 아니라 판단 근거를 남긴 단계다.
