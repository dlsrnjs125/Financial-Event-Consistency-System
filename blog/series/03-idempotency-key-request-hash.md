# Idempotency Key만 같다고 같은 거래라고 볼 수 있을까?

Idempotency Key는 재시도 요청을 같은 요청으로 묶는 계약이다. 하지만 key만 같다고 항상 같은 거래라고 보면 안 된다. 같은 key로 다른 body가 들어오는 순간, 그것은 재시도가 아니라 충돌일 수 있다.

## 같은 key, 다른 금액

가장 위험한 예시는 금액이 바뀐 요청이다.

```text
Idempotency-Key: idem-001
첫 요청: amount=10,000 -> 처리 완료
두 번째 요청: amount=50,000 -> 같은 key지만 다른 body
```

이때 기존 응답을 그대로 replay하면 client는 50,000원 요청도 성공했다고 오해할 수 있다. 반대로 새 거래로 처리하면 중복 반영이 된다.

## request hash를 저장한 이유

그래서 idempotency record에는 key뿐 아니라 canonical request hash를 저장한다. JSON key 순서가 달라도 의미가 같으면 같은 hash가 나오도록 canonical JSON을 사용한다.

판단은 단순하다.

- 같은 key + 같은 body: 기존 응답 replay
- 같은 key + 다른 body: `409 Conflict`
- 새 key: 처리 시작

## API 응답 정책까지 같이 고정했다

처리 중인 같은 요청은 `ALREADY_PROCESSING`, 완료된 요청은 `REPLAY_COMPLETED`, 실패한 요청은 `REPLAY_FAILED`로 응답한다. 중요한 것은 "중복 요청을 편하게 처리한다"가 아니라 "같은 요청과 다른 요청을 명확히 구분한다"는 점이다.
