# 배포 실패 시 DB를 되돌리지 않고 트래픽만 Blue로 되돌린 이유

Blue-Green 배포에서 rollback을 DB rollback으로 생각하면 위험하다. 금융 이벤트 시스템에서는 이미 commit된 거래를 배포 실패 때문에 되돌릴 수 없다.

## rollback의 범위를 traffic으로 제한했다

이 프로젝트의 rollback은 API traffic rollback이다. Green 배포가 실패하면 Nginx upstream을 Blue로 되돌린다. DB는 그대로 둔다.

이 판단은 정합성 원칙과 연결된다. LedgerEntry는 삭제하지 않고, account balance는 ledger로 설명되어야 한다.

## 전환 순서를 고정한 이유

처음에는 Nginx upstream만 Green으로 바꾸면 된다고 생각했다. 하지만 Green이 준비되지 않았거나 Nginx reload가 실패하면 전환은 성공한 것처럼 보여도 실제 요청은 실패할 수 있다.

그래서 순서를 고정했다.

```text
Green health/ready/smoke
-> nginx config test
-> traffic switch
-> post-switch smoke
-> consistency gate
```

## rollback 후에도 정합성을 확인한다

Blue로 traffic을 되돌린 뒤에도 duplicate ledger/event count를 확인한다. 배포 rollback은 availability 조치이고, consistency gate는 금융 데이터 안전 확인이다. 둘을 같이 봐야 배포 실패를 안전하게 닫을 수 있다.
