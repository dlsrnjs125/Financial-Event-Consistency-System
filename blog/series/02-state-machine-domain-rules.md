# 거래 상태를 코드가 아니라 규칙으로 막은 이유

거래 상태는 단순한 문자열 컬럼처럼 보이지만, 금융 이벤트 시스템에서는 상태 전이가 곧 운영 의미가 된다.

`COMPLETED`가 다시 `PROCESSING`으로 바뀌거나, `FAILED`가 갑자기 `COMPLETED`가 되면 외부 시스템과 내부 원장이 서로 다른 이야기를 하게 된다.

## COMPLETED가 다시 PROCESSING이 되면 무슨 일이 생길까?

retry 처리 중 이미 완료된 이벤트가 다시 처리 상태로 바뀌는 상황을 생각해보자.

```text
첫 요청: ledger 반영 완료, status=COMPLETED
재시도 처리 중 status=PROCESSING으로 되돌림
외부 시스템: 아직 처리 중이라고 이해
내부 원장: 이미 반영됨
```

이 모순을 막으려면 status update를 단순 SQL update로 두면 안 된다.

## enum만으로는 상태 전이를 설명할 수 없었다

처음에는 enum 컬럼과 validation만 있으면 충분해 보였다. 하지만 enum은 "어떤 값이 가능한가"만 말해준다. "어떤 값에서 어떤 값으로 갈 수 있는가"는 별도 규칙이다.

그래서 상태 전이를 도메인 규칙으로 분리했다.

## 이벤트, 원장, 잔액을 한 테이블에 넣지 않은 이유

`TransactionEvent`는 외부에서 들어온 금융 이벤트다.

`LedgerEntry`는 잔액이 왜 바뀌었는지 설명하는 원장 근거다.

`Account.balance`는 현재 잔액의 캐시된 결과다.

이 셋을 분리해야 장애 상태를 설명할 수 있다.

| 상태 | 가능한 해석 |
| --- | --- |
| event 있음, ledger 없음 | 처리 전이거나 처리 실패 |
| event COMPLETED, ledger 없음 | 정합성 위반 후보 |
| ledger 있음, balance mismatch | 잔액 재검증 필요 |
| duplicate ledger 있음 | 중복 반영 사고 |

## 상태 전이는 코드 편의가 아니라 운영 언어다

상태 머신 테스트는 허용 전이와 금지 전이를 모두 고정한다.

```text
RECEIVED -> VALIDATED -> PROCESSING -> COMPLETED
RECEIVED -> VALIDATED -> FAILED
PROCESSING -> FAILED
```

반대로 다음 전이는 막는다.

```text
COMPLETED -> PROCESSING
FAILED -> COMPLETED
SETTLED -> CANCELLED
```

금지 전이를 테스트로 고정한 이유는, 나중에 service 코드가 늘어나도 상태 의미가 조용히 바뀌지 않게 하기 위해서다.

## 취소는 row 삭제가 아니라 반대 원장이다

금융 이벤트에서 취소는 row 삭제가 아니다. 이미 반영된 기록을 지우면 감사 추적이 사라진다.

CANCEL은 compensation transaction으로 다뤄야 한다. SETTLED 상태를 직접 CANCELLED로 바꾸는 것이 아니라, 반대 방향의 ledger 근거를 남겨야 한다.

## COMPLETED 취소와 SETTLED 이후 정정은 다르다

취소도 하나로 보면 안 된다.

`COMPLETED` 상태는 내부 원장 반영은 끝났지만, 외부 정산이나 회계 확정 전일 수 있다. 이 경우에는 도메인 정책에 따라 `CANCELLED`로 전이하고 반대 방향의 ledger를 남길 수 있다.

반면 `SETTLED`는 외부 정산까지 완료된 상태다. 이 상태를 단순히 `CANCELLED`로 바꾸면 외부 정산 시스템과 내부 원장이 서로 다른 이야기를 하게 된다. 그래서 `SETTLED -> CANCELLED` 직접 전이는 막고, 필요한 경우 `REVERSAL` 또는 보상 거래를 별도 이벤트로 기록해야 한다.

이번 프로젝트에서는 부분 취소, 수수료, 다중 계좌 이체, 외부 정산 확정 이후 reversal까지 모두 구현하지는 않았다. 대신 완료된 기록을 삭제하지 않고, 반대 원장으로 설명한다는 원칙을 상태 머신과 테스트로 고정하는 데 집중했다.

## evidence

상태 전이 검증은 unit test로 고정한다.

```bash
make test-unit
```

핵심은 "정상 전이가 된다"보다 "위험한 전이가 막힌다"다.

## 남은 한계

상태 머신은 도메인 규칙을 막는 1차 방어선이다. 하지만 concurrent retry, DB unique conflict, idempotency replay까지 포함한 최종 정합성은 service transaction과 PostgreSQL constraint가 함께 보장해야 한다.

상태 전이는 코드 취향 문제가 아니라, 장애 상황에서 거래 의미를 설명하기 위한 운영 언어다.
