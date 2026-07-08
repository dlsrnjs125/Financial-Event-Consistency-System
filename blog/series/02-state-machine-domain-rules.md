# 거래 상태를 코드가 아니라 규칙으로 막은 이유

거래 상태는 단순한 문자열 컬럼처럼 보이지만, 금융 이벤트 시스템에서는 상태 전이가 곧 운영 의미가 된다. `COMPLETED`가 다시 `PROCESSING`으로 바뀌거나, `FAILED`가 갑자기 `COMPLETED`가 되면 외부 시스템과 내부 원장이 서로 다른 이야기를 하게 된다.

## COMPLETED가 다시 PROCESSING이 되면 안 된다

처음에는 status 컬럼만 있으면 충분해 보였다. 하지만 retry 처리 중 이미 완료된 이벤트가 다시 processing으로 바뀌면 문제가 생긴다.

```text
첫 요청: ledger 반영 완료, status=COMPLETED
재시도 처리 중 status=PROCESSING으로 되돌림
외부 시스템: 아직 처리 중이라고 이해
내부 원장: 이미 반영됨
```

이 모순을 막기 위해 상태 변경을 단순 update가 아니라 도메인 규칙으로 다뤘다.

## TransactionEvent, LedgerEntry, Account를 분리한 이유

`TransactionEvent`는 외부에서 들어온 금융 이벤트다. `LedgerEntry`는 잔액이 왜 바뀌었는지 설명하는 원장 근거다. `Account.balance`는 현재 잔액의 캐시된 결과다.

이 셋을 분리해야 "이벤트는 들어왔지만 원장은 아직 없다", "원장은 있는데 잔액 검증이 필요하다" 같은 장애 상태를 설명할 수 있다.

## 테스트로 막은 잘못된 전이

상태 머신 테스트는 허용 전이와 금지 전이를 모두 고정한다.

- `RECEIVED -> VALIDATED -> PROCESSING -> COMPLETED`
- `COMPLETED -> PROCESSING` 금지
- `FAILED -> COMPLETED` 금지
- `SETTLED -> CANCELLED` 금지

이 규칙 덕분에 중복 이벤트 방어도 단순 DB constraint에만 의존하지 않는다. 이미 완료된 이벤트가 다시 처리 중으로 되돌아가지 않기 때문에, 외부 retry와 내부 원장 상태가 같은 방향으로 설명된다.
