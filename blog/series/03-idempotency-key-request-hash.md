# Idempotency Key만 같다고 같은 거래라고 볼 수 있을까?

Idempotency Key는 재시도 요청을 같은 요청으로 묶는 계약이다. 하지만 key만 같다고 항상 같은 거래라고 보면 안 된다.

같은 key로 다른 body가 들어오는 순간, 그것은 재시도가 아니라 충돌일 수 있다.

## 같은 Key로 금액이 바뀌면 replay하면 안 된다

가장 위험한 예시는 금액이 바뀐 요청이다.

```text
Idempotency-Key: idem-001
첫 요청: amount=10,000 -> 처리 완료
두 번째 요청: amount=50,000 -> 같은 key지만 다른 body
```

이때 기존 응답을 그대로 replay하면 client는 50,000원 요청도 성공했다고 오해할 수 있다.

반대로 새 거래로 처리하면 중복 반영이 된다.

## Idempotency-Key만 저장하면 충분할 줄 알았다

처음에는 `Idempotency-Key`가 같으면 같은 요청이라고 단순히 볼 수 있을 것 같았다.

하지만 idempotency key는 client가 보내는 값이다. 실수나 버그로 같은 key에 다른 body가 붙을 수 있다.

그래서 key만 저장하지 않고 canonical request hash를 함께 저장했다.

## JSON 문자열이 아니라 요청 의미를 비교해야 했다

request hash는 body의 의미가 같은지 비교하기 위한 값이다.

JSON key 순서가 달라도 의미가 같으면 같은 hash가 나와야 한다. 그래서 canonical JSON을 사용한다.

```json
{"amount":10000,"event_type":"DEPOSIT"}
```

와

```json
{"event_type":"DEPOSIT","amount":10000}
```

은 같은 요청으로 봐야 한다.

## Replay, Processing, Conflict를 나눈 기준

판단은 단순하게 고정했다.

| 조건 | 결과 |
| --- | --- |
| 새 key | `STARTED` |
| 같은 key + 같은 body + 처리 중 | `ALREADY_PROCESSING` |
| 같은 key + 같은 body + 완료 | `REPLAY_COMPLETED` |
| 같은 key + 같은 body + 실패 | `REPLAY_FAILED` |
| 같은 key + 다른 body | `409 Conflict` |

중요한 것은 중복 요청을 편하게 처리하는 것이 아니라, 같은 요청과 다른 요청을 명확히 구분하는 것이다.

## Idempotency record를 무한히 보관하지 않은 이유

실제 운영에서는 Idempotency-Key를 영원히 보관할 수 없다. 저장 공간도 문제지만, 더 중요한 것은 "같은 key를 언제까지 같은 요청으로 볼 것인가"라는 계약이다.

예를 들어 어떤 partner는 24시간 안의 retry만 같은 요청으로 볼 수 있고, 어떤 partner는 정산 지연 때문에 며칠 뒤 재전송이 발생할 수 있다. 이 replay window는 시스템 내부 구현만으로 정할 수 없고, 외부 시스템의 retry policy와 함께 계약되어야 한다.

이번 프로젝트에서는 TTL 삭제 배치나 partner별 replay window까지 구현하지 않았다. 대신 같은 key와 같은 request hash가 들어왔을 때 어떤 결과를 반환해야 하는지, 같은 key와 다른 body가 들어왔을 때 왜 `409 Conflict`로 거부해야 하는지를 먼저 고정했다.

즉 운영 보관 정책보다 먼저, 같은 요청과 다른 요청을 구분하는 기준을 검증한 것이다.

## 실패 응답을 replay할 것인가도 정책이다

실패한 요청을 같은 key로 다시 보냈을 때 무조건 재처리하면 같은 요청이 여러 번 실행될 수 있다. 반대로 실패 응답을 계속 replay하면 일시 장애가 복구된 뒤에도 client가 성공할 기회를 얻지 못할 수 있다.

이번 프로젝트에서는 저장된 실패 응답을 재사용하는 방향으로 기준을 고정했다. 실패 재처리 허용 여부는 partner retry contract, 실패 유형, 보상 거래 정책과 함께 별도 ADR로 분리해야 한다.

## 트러블슈팅: body 비교를 문자열로 하면 흔들린다

raw JSON 문자열을 그대로 비교하면 key 순서, 공백, formatting 차이 때문에 같은 의미의 요청도 다르게 보일 수 있다.

그래서 canonical JSON 기반 hash로 비교한다. 이 방식은 client formatting 차이를 줄이고, 서버가 판단한 "같은 요청" 기준을 안정적으로 만든다.

## evidence

idempotency 테스트는 다음을 확인한다.

- 같은 key와 같은 body는 replay된다.
- 같은 key와 다른 body는 conflict가 된다.
- 처리 중인 요청은 새로 처리되지 않는다.
- 실패한 요청 replay 정책이 API 응답 정책과 일치한다.

```bash
make test-unit
make test-consistency
```

## 남은 한계

TTL, storage size, replay window, partner별 key policy는 운영 정책으로 추가 정의해야 한다.

현재 단계에서는 같은 key와 body를 기준으로 중복 처리 의미를 명확히 고정하는 데 집중했다.
