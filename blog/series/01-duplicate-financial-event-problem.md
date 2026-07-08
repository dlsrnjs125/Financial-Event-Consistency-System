# 금융 이벤트 시스템에서 가장 무서운 장애는 500이 아니라 중복 반영이었다

금융 이벤트 처리에서 가장 무서운 장애는 API가 느려지는 것이 아니라, 같은 거래가 두 번 반영되는 것이다.

외부 은행이나 결제 시스템은 응답을 받지 못하면 같은 이벤트를 다시 보낼 수 있다. 이때 두 번째 요청을 신규 거래로 처리하면 장애는 단순 timeout이 아니라 잔액 오류가 된다.

## 응답을 못 받은 요청은 실패일까, 성공일까?

가장 단순한 장애 시나리오는 다음과 같다.

```text
은행이 DEPOSIT 이벤트를 전송한다.
API는 DB commit을 끝냈다.
응답 전송 중 네트워크가 끊긴다.
은행은 timeout으로 보고 같은 이벤트를 재전송한다.
두 번째 요청을 신규 거래로 처리하면 10,000원이 20,000원으로 보인다.
```

API 관점에서는 첫 요청도 성공이고 두 번째 요청도 성공일 수 있다. 하지만 금융 원장 관점에서는 실패다.

그래서 이 프로젝트의 성공 기준은 "HTTP 200을 잘 반환한다"가 아니라 "중복 원장 0건을 유지한다"가 됐다.

## "중복 요청을 막는다"는 말이 부족했던 이유

처음에는 "중복 요청을 막는다"는 표현이면 충분하다고 생각했다. 하지만 구현하면서 중복에도 종류가 있다는 것을 분리해야 했다.

첫 번째는 같은 `external_event_id`가 여러 번 들어오는 경우다. 외부 금융 시스템이 같은 이벤트를 재전송한 것이므로 원장 반영은 한 번이어야 한다.

두 번째는 같은 `Idempotency-Key`가 여러 번 들어오는 경우다. 같은 body라면 기존 응답을 replay해야 하지만, 같은 key로 다른 body가 들어오면 충돌로 봐야 한다.

세 번째는 Redis 장애 중 duplicate storm이다. Redis lock이 없어도 PostgreSQL 기준으로 중복 반영이 없어야 한다.

## 성공 기준을 HTTP 응답이 아니라 PostgreSQL 결과로 옮겼다

최종 정합성 기준은 PostgreSQL에 둔다.

```text
TransactionEvent.external_event_id unique
LedgerEntry.transaction_event_id unique
IdempotencyRecord.idempotency_key unique
```

Redis lock은 요청 폭주를 줄일 수 있지만, 최종 방어선은 아니다. Redis가 죽어도 DB unique constraint와 transaction boundary가 중복 반영을 막아야 한다.

## API 성공률보다 ledger count를 먼저 본 이유

검증은 API 응답만 보지 않았다.

```bash
make k6-duplicate
make k6-verify
```

`make k6-duplicate`는 같은 이벤트를 반복 전송하고, `make k6-verify`는 PostgreSQL에서 중복 row와 ledger 중복을 확인한다.

중요한 것은 "요청이 몇 개 성공했는가"가 아니라 "DB에 같은 금융 효과가 몇 번 남았는가"다.

## 이 프로젝트가 계속 붙잡은 기준

이후 단계의 Redis fallback, k6 duplicate storm, PostgreSQL down write suspend, incident artifact, recovery case도 모두 같은 질문으로 돌아온다.

```text
장애가 났을 때 같은 금융 효과가 두 번 남지 않는가?
성공이라고 말한 요청은 PostgreSQL commit evidence를 갖는가?
복구 후에도 ledger와 account balance가 서로 설명되는가?
```

이 기준을 먼저 세워두면 기능이 늘어도 판단이 흔들리지 않는다.

## 트러블슈팅: timeout은 실패와 성공 사이에 있다

client timeout은 서버 실패와 같지 않다. 서버는 commit을 끝냈지만 client가 응답을 못 받았을 수 있다.

그래서 retry 요청을 무조건 실패로 돌리면 안 되고, 무조건 새로 처리해도 안 된다.

Idempotency record와 request hash를 통해 다음처럼 판단해야 한다.

- 이미 완료된 같은 요청이면 같은 결과를 replay한다.
- 처리 중인 같은 요청이면 `ALREADY_PROCESSING`으로 판단한다.
- 같은 key지만 다른 body면 `409 Conflict`로 분리한다.

## 실제 금융망에서는 retry policy까지 계약해야 한다

이 프로젝트는 local Docker Compose와 sample evidence 기준으로 정합성 boundary를 검증한다. 실제 운영에서는 payment network timeout, partner retry policy, SLA, long-running reconciliation까지 더해져야 한다.

하지만 출발점은 분명하다. 금융 이벤트 시스템에서 가장 먼저 증명해야 하는 것은 "빠르다"가 아니라 "장애와 재시도 속에서도 한 번만 반영된다"다.
