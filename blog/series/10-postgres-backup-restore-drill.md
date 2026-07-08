# PostgreSQL 백업은 만들어지는 것보다 복구되는 것이 중요하다

백업 파일이 있다는 사실은 복구 가능성을 보장하지 않는다. 실제로 restore DB에 복원하고 정합성 SQL을 통과해야 백업이라고 말할 수 있다.

## backup과 restore를 분리했다

`pg_dump`는 백업을 만든다. 하지만 `pg_dump` 성공만으로는 충분하지 않다. 파일이 깨졌거나, restore 권한이 없거나, schema가 맞지 않으면 장애 시 사용할 수 없다.

그래서 별도 restore DB를 만들었다.

```text
postgres-restore container
financial_events_restore database
pg_restore
consistency SQL
```

운영 DB에 직접 restore하지 않는 것도 중요한 원칙이었다.

## 정합성 SQL로 확인한 것

복구된 DB에서 확인할 기준은 단순 row count가 아니다.

- duplicate external event count
- duplicate ledger count
- transaction event without ledger
- balance mismatch
- idempotency consistency

이 값들이 모두 깨끗해야 "백업이 복구된다"고 말할 수 있다.

## DR Drill의 의미

DR Drill은 백업 명령이 아니라 복구 가능성을 증명하는 evidence다. 이 프로젝트에서는 backup artifact, checksum, restore result, consistency SQL 결과를 함께 남기는 쪽을 선택했다.
