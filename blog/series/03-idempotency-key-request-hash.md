# Idempotency Key만 같다고 같은 거래라고 볼 수 있을까?

Idempotency Key는 재시도 요청을 같은 요청으로 묶는 계약이다. 하지만 key만 같다고 항상 같은 거래라고 보면 안 된다.

같은 key로 다른 body가 들어오는 순간, 그것은 재시도가 아니라 충돌일 수 있다.

## 문제 상황

가장 위험한 예시는 금액이 바뀐 요청이다.

```text
Idempotency-Key: idem-001
첫 요청: amount=10,000 -> 처리 완료
두 번째 요청: amount=50,000 -> 같은 key지만 다른 body
```

이때 기존 응답을 그대로 replay하면 client는 50,000원 요청도 성공했다고 오해할 수 있다.

반대로 새 거래로 처리하면 중복 반영이 된다.

## 처음 가정

처음에는 `Idempotency-Key`가 같으면 같은 요청이라고 단순히 볼 수 있을 것 같았다.

하지만 idempotency key는 client가 보내는 값이다. 실수나 버그로 같은 key에 다른 body가 붙을 수 있다.

그래서 key만 저장하지 않고 canonical request hash를 함께 저장했다.

## request hash를 저장한 이유

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

## 판단 규칙

판단은 단순하게 고정했다.

| 조건 | 결과 |
| --- | --- |
| 새 key | `STARTED` |
| 같은 key + 같은 body + 처리 중 | `ALREADY_PROCESSING` |
| 같은 key + 같은 body + 완료 | `REPLAY_COMPLETED` |
| 같은 key + 같은 body + 실패 | `REPLAY_FAILED` |
| 같은 key + 다른 body | `409 Conflict` |

중요한 것은 중복 요청을 편하게 처리하는 것이 아니라, 같은 요청과 다른 요청을 명확히 구분하는 것이다.

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

Idempotency-Key는 무한히 보관할 수 없다. TTL, storage size, replay window, partner별 key policy는 운영 정책으로 추가 정의해야 한다.

현재 단계에서는 같은 key와 body를 기준으로 중복 처리 의미를 명확히 고정하는 데 집중했다.
