# PostgreSQL Failure and Write Suspend Policy

> PostgreSQL은 최종 정합성 기준이지만, 항상 처리 가능한 저장소는 아니다.
> PostgreSQL write path가 불가능한 순간에는 신규 금융 거래를 확정 처리하지 않는다.

## 1. 핵심 원칙

PostgreSQL은 `idempotency_records`, `transaction_events`, `ledger_entries`, `accounts.balance`의 최종 Source of Truth다.
따라서 PostgreSQL write가 불가능한 상태에서 200 OK 또는 처리 완료 응답을 반환하면 처리 여부를 증명할 수 없는 거래가 생긴다.

기본 정책:

```text
PostgreSQL unavailable
-> 신규 write 요청은 503 Service Unavailable
-> Retry-After 반환
-> 동일 Idempotency-Key 기반 재시도 유도
-> 시스템 내부에는 처리 성공으로 기록하지 않음
-> DB 복구 후 동일 Idempotency-Key / external_event_id로 재시도 처리
```

Redis 장애는 degraded dependency로 처리할 수 있지만 PostgreSQL 장애는 hard dependency 장애다.
실패를 성공으로 위장하지 않는 것이 금융 정합성의 우선순위다.

## 2. DB down과 DB pressure의 차이

| 구분 | 의미 | 기본 정책 |
| --- | --- | --- |
| DB down | connection refused, primary unavailable, failover 중 write 불가 | 신규 금융 write fail-closed |
| DB pressure | connection pool 고갈, lock wait 증가, deadlock 증가, slow query | traffic 감속, batch 중지, 필요 시 부분 write suspend |
| DB uncertainty | failover 직후 stale connection, commit 여부 불명확 | in-doubt window 기록, recovery mode 진입 |

DB down은 거래 처리 불가 상태다.
DB pressure는 일부 traffic을 줄이면 회복될 수 있는 상태다.
DB uncertainty는 처리 여부를 자동으로 단정하면 안 되는 상태다.

## 3. 장애 유형별 정책

| 장애 유형 | 판단 기준 | 사용자 응답 | 자동 대응 | 사람이 판단해야 하는 부분 | 복구 후 검증 SQL 또는 metric |
| --- | --- | --- | --- | --- | --- |
| DB 완전 down | connection refused, `/ready` postgres fail | `503` + `Retry-After` | write suspend, incident 생성, consistency check 예약 | DB 복구 또는 failover 승인 | readiness 200, duplicate ledger 0, orphan idempotency 0 |
| DB connection pool 고갈 | pool timeout, active conn 90% 이상 | `503` 또는 timeout | rate limit 강화, batch 중지, pool metric 수집 | pool size 조정, slow query 분석 | active conn 정상화, 5xx 감소, rollback count 확인 |
| lock wait/deadlock 증가 | lock wait, deadlock count, p99 증가 | 지연 또는 `500/503` | slow transaction report, affected event 격리 후보 | transaction/query 수정 승인 | lock wait 감소, deadlock 증가 중단 |
| replication lag | standby lag 증가 | write는 primary만, read 제한 | read replica 사용 중지 후보, lag evidence 수집 | failover 가능 여부 판단 | lag 정상화, primary identity 확인 |
| failover 중 stale connection | primary 전환, stale connection error | `503` + `Retry-After` | pool recycle, readiness fail, recovery mode | promote/rollback 결정, write resume 승인 | active primary 확인, in-doubt case 0 또는 recovery case 생성 |
| disk full/WAL 폭증 | disk 90% 이상, WAL 증가, replication slot 적체 | `503` 가능 | write suspend 후보, backup/batch 중단 | WAL/slot 정리 승인, storage 증설 | disk usage 정상화, WAL 증가율 감소 |
| backup restore 실패 | DR drill restore 또는 consistency SQL fail | 운영 요청 영향은 간접적 | alert, incident 생성 | 복구 전략 재검토 | restore success, count-only consistency PASS |

### DB_UNAVAILABLE 중 incident/recovery 기록 위치

DB down 상태에서는 `incident_events`와 `recovery_cases`를 PostgreSQL에 즉시 저장할 수 없다.
따라서 `DB_UNAVAILABLE` 상태의 1차 증거는 out-of-band incident artifact로 남기고, PostgreSQL 복구 후 DB table에 backfill한다.

권장 artifact 구조:

```text
reports/incidents/{incident_id}/
- metrics-snapshot.json
- sanitized-app-logs.json
- docker-status.txt
- readiness-result.json
- write-suspend-state.json
- pending-recovery-cases.json
```

복구 후 처리 흐름:

```text
out-of-band incident artifact
-> incident_events insert
-> recovery_cases insert
-> reconciliation 실행
-> write resume 승인
```

이 정책은 "DB가 죽었을 때 DB에 장애 정보를 저장한다"는 모순을 피하기 위한 것이다.
artifact에는 raw account number, raw idempotency key, HMAC signature, raw request body, secret을 포함하지 않는다.

## 4. PostgreSQL write 불가 시 fail-closed 정책

신규 금융 write는 다음 조건에서 fail-closed 한다.

- PostgreSQL primary에 write transaction을 시작할 수 없다.
- `idempotency_records`에 처리 상태를 기록할 수 없다.
- `transaction_events`와 `ledger_entries`의 atomic write를 보장할 수 없다.
- failover 중 commit 여부가 불명확한 window가 감지되었다.

Fail-closed는 장애 중 성공률을 포기하는 대신, 처리 여부가 불명확한 성공 응답을 만들지 않는 선택이다.

## 5. 503 Service Unavailable + Retry-After 응답 정책

장애 중 신규 write 응답 예시:

```text
HTTP/1.1 503 Service Unavailable
Retry-After: 30
```

응답 의미:

- 요청이 확정 처리되지 않았다.
- 같은 `Idempotency-Key`와 같은 body로 재시도해야 한다.
- 외부 시스템은 `external_event_id`를 유지해야 한다.
- 서버는 장애 중 처리 성공으로 기록했다고 주장하지 않는다.

## 6. Write suspend mode

`WRITE_SUSPENDED`는 신규 금융 write path를 의도적으로 닫는 운영 상태다.

| 항목 | 정책 |
| --- | --- |
| 대상 | `POST /transaction-events` 같은 원장성 write |
| 허용 | `/health`, 제한적 `/ready`, admin recovery 조회 |
| 차단 | 신규 ledger/account balance 변경 |
| 응답 | `503` + `Retry-After` 또는 정책 충돌 시 `409` |
| 종료 | consistency gate와 운영자 write resume 승인 후 |

자동화는 write suspend 활성화 후보를 만들 수 있다.
실제 운영 환경에서 write resume은 사람이 승인한다.

### Write suspend 상태 저장소

PostgreSQL down 상황에서도 write suspend 판단은 동작해야 하므로, write suspend 상태는 PostgreSQL 단독 저장소에 의존하지 않는다.

우선순위:

| 우선순위 | 저장소 | 역할 | 한계 |
| --- | --- | --- | --- |
| 1 | application runtime memory flag | 가장 빠른 write 차단 | process restart 시 사라질 수 있음 |
| 2 | local file/config mounted volume | process 재시작 후에도 상태 유지 | multi-node 동기화 설계 필요 |
| 3 | Nginx maintenance/write-blocking route | API 앞단에서 write 차단 | 세밀한 account/client quarantine에는 부적합 |
| 4 | DB-backed admin_config flag | 정상 상태의 운영 기록과 감사 추적 | PostgreSQL down 중 읽을 수 없음 |

운영 원칙:

- DB down 감지 직후 API runtime flag로 신규 write를 차단한다.
- 동시에 `write-suspend-state.json` artifact를 남긴다.
- Nginx에서 write route 차단이 가능하면 2차 방어로 적용한다.
- PostgreSQL 복구 후 DB-backed flag와 `incident_events`에 상태를 backfill한다.
- Redis는 보조 계층이므로 write suspend의 유일한 저장소로 사용하지 않는다.

현재 PH1 구현:

- 상태 파일 기본값은 `reports/runtime/write-suspend-state.json`이다.
- API runtime memory와 local artifact를 함께 사용한다.
- `POST /api/v1/transaction-events`만 신규 write 차단 대상이다.
- active 상태에서는 `503 Service Unavailable`과 `Retry-After`를 반환한다.
- `/health`, `/ready`, `/metrics`는 write suspend로 차단하지 않는다.
- PostgreSQL probe 또는 SQLAlchemy DB 예외가 발생하면 `postgres_unavailable` 사유로 write suspend를 활성화한다.
- DB가 회복되어도 자동 resume하지 않으며, 운영자가 `make ph1-write-suspend-resume`으로 재개한다.
- PH1 구현 기록과 drill 절차는 [43-ph1-write-suspend-db-down-drill.md](43-ph1-write-suspend-db-down-drill.md)를 기준으로 관리한다.

### Multi-node 한계와 production 보완

이번 프로젝트의 1차 구현은 Docker Compose 단일 API 인스턴스 기준으로 runtime flag와 local artifact를 검증한다.
다중 인스턴스 production 환경에서는 runtime flag 단독으로 write suspend를 보장할 수 없다.

Production 보완 후보:

- Nginx/LB route blocking으로 write path를 전역 차단한다.
- shared config store 또는 deployment-level maintenance mode를 둔다.
- 각 API instance가 suspend state를 주기적으로 확인하고 drift를 report한다.
- instance restart 시 local file artifact 또는 global control plane에서 suspend 상태를 복구한다.

따라서 runtime flag는 빠른 로컬 차단 수단이고, production 전역 차단은 Nginx/LB 또는 shared control plane과 함께 설계해야 한다.

## 7. Read-only mode

`READ_ONLY`는 조회성 endpoint와 운영자 확인 endpoint만 제한적으로 유지하는 상태다.

주의:

- read replica lag가 있으면 금융 상태 조회도 stale할 수 있다.
- read-only mode에서 조회 결과는 "최종 확정 최신 상태"로 과장하지 않는다.
- write endpoint는 성공 응답을 반환하지 않는다.

## 8. Recovery mode

`RECOVERY_MODE`는 DB가 다시 연결되었지만, 장애 window의 처리 여부 검증이 끝나지 않은 상태다.

Recovery mode에서 수행할 일:

- 장애 window의 idempotency/event/ledger/account consistency SQL 실행
- stale `PROCESSING` record 탐지
- in-doubt event를 recovery case로 생성
- affected account/client quarantine 유지 또는 해제 판단
- write resume 승인 전 최종 evidence 수집

## 9. 복구 후 write resume 승인 기준

| 기준 | 완료 조건 |
| --- | --- |
| DB readiness | primary write 가능, stale connection 해소 |
| 정합성 | duplicate ledger 0, duplicate event 0, account balance mismatch 0 |
| Idempotency | orphan/stale PROCESSING 자동 분석 완료 |
| Recovery case | 자동 판단 불가 case는 OPEN 상태로 격리 |
| 관측성 | 5xx, pool timeout, lock wait 증가 중단 |
| 승인 | 운영자가 write resume 승인 기록 |

## 10. 외부 시스템 재시도 계약

외부 시스템은 다음 계약을 지켜야 한다.

- 동일 이벤트 재시도 시 같은 `Idempotency-Key`를 유지한다.
- 같은 `Idempotency-Key`에는 같은 body를 사용한다.
- 같은 금융 이벤트에는 같은 `external_event_id`를 유지한다.
- `503`과 `Retry-After`는 미처리 또는 처리 불명확이 아니라 "성공 아님"으로 해석한다.
- `409 Conflict`는 같은 key 다른 body 또는 정책 충돌로 해석한다.

### External Retry Contract v1

| 응답/상황 | 외부 시스템 행동 | 동일 Idempotency-Key 유지 | 동일 body 유지 | 서버 의미 |
| --- | --- | --- | --- | --- |
| `200/201 COMPLETED` | 재시도 불필요 | N/A | N/A | 확정 처리 |
| `202 PROCESSING` | 일정 시간 후 조회 또는 재시도 | 예 | 예 | 처리 중 |
| `401/403` | 재시도 금지, 인증 정보 확인 | N/A | N/A | 인증/권한 실패 |
| `409 Conflict` | 같은 key로 재시도 금지 | 아니오 | N/A | key/body 충돌 또는 정책 충돌 |
| `422 Unprocessable Entity` | 재시도 금지, payload 수정 필요 | N/A | N/A | 유효성 실패 |
| `429 Too Many Requests` | backoff 후 재시도 | 예 | 예 | rate limit |
| `500 Internal Server Error` | 동일 key/body로 재시도 가능 | 예 | 예 | 서버 오류, 처리 여부 확인 필요 |
| `503 Service Unavailable` + `Retry-After` | `Retry-After` 이후 재시도 | 예 | 예 | 확정 처리 안 됨 |
| Client timeout | 동일 key/body로 재시도 | 예 | 예 | 처리 여부 불명확 |

재시도 정책:

- 외부 시스템은 exponential backoff와 jitter를 적용한다.
- `Retry-After`를 무시한 폭주 재시도는 `429` 또는 client quarantine 후보가 된다.
- Idempotency record 보관 기간은 API contract와 data retention 정책에 맞춰 별도 명시한다.
- 서버가 commit 후 응답 전에 죽은 경우, 동일 key/body 재시도는 기존 `COMPLETED` 결과 replay를 목표로 한다.
- Nginx/client timeout은 곧바로 거래 실패를 의미하지 않는다.
- 서버 내부 transaction이 commit되었을 수 있으므로 동일 `Idempotency-Key` 재시도 시 `request_hash`를 확인하고, `transaction_event`, `ledger_entry`, `account.balance`를 대조해 `COMPLETED` replay 또는 recovery case로 분기한다.
- Nginx proxy timeout, app handler timeout, DB statement timeout의 순서는 후속 구현에서 명시적으로 테스트한다.

## 11. k6/장애 drill로 검증할 항목

PH1에서 구현/검증할 항목:

- PostgreSQL stop 중 POST 요청이 `503` + `Retry-After`를 반환한다.
- DB down 중 처리 성공 idempotency record가 생성되지 않는다.
- PostgreSQL start 후 동일 `Idempotency-Key` 재시도 시 ledger 1건만 생성된다.
- 복구 후 consistency SQL 결과가 모두 0이다.
- incident report에 원문 계좌번호, raw idempotency key, signature가 포함되지 않는다.

후속 구현 후보:

- failover-like stale connection 상황에서 write suspend가 유지된다.
- multi-node 전역 write blocking을 Nginx/LB 또는 shared control plane과 연결한다.
- out-of-band incident artifact를 DB-backed `incident_events`와 `recovery_cases`로 backfill한다.

## 12. Trade-off

### 12.1 DB down 시 fail-closed vs 임시 저장 후 나중에 반영

- 선택한 정책: DB write 불가 시 신규 금융 write는 `503`으로 fail-closed 한다.
- 대안: Redis, memory, file, local queue에 임시 저장 후 나중에 PostgreSQL에 반영한다.
- 선택 이유: 금융 거래에서 처리 여부를 증명할 수 없는 성공 응답이 가장 위험하다.
- 포기한 것: DB 장애 중 요청 성공률.
- 보완 전략: 외부 retry contract, 같은 idempotency key 유지, 장애 window 기록, 복구 후 재시도 검증.
- 면접 답변용 한 문장: PostgreSQL이 Source of Truth인 구조에서는 DB 장애 중 성공 응답을 주는 순간 정합성을 증명할 수 없기 때문에, 신규 write는 fail-closed로 막고 재시도 가능한 실패로 반환했습니다.

### 12.2 503 Retry-After vs 202 Accepted

- 선택한 정책: 현재 API 계약에서는 확정 처리 실패를 `503` + `Retry-After`로 반환한다.
- 대안: `202 Accepted`로 수신만 보장하고 비동기 처리한다.
- 선택 이유: 현재 설계는 API 응답 시점에 PostgreSQL transaction 결과를 기준으로 처리 완료 의미를 제공한다.
- 포기한 것: DB 장애 중 수신 가용성.
- 보완 전략: durable queue 도입 시 API 계약을 `ACCEPTED`와 `POSTED/COMPLETED`로 분리하는 ADR을 둔다.
- 면접 답변용 한 문장: 202를 쓰려면 응답 의미가 처리 완료가 아니라 수신 완료로 바뀌므로, 현재 transaction 중심 계약에서는 503 재시도를 선택했습니다.

### 12.3 write suspend 자동화 vs 운영자 수동 차단

- 선택한 정책: 자동화는 write suspend 후보 판단과 활성화 트리거를 제공하고, write resume은 사람이 승인한다.
- 대안: 모든 차단과 재개를 운영자가 수동으로 수행한다.
- 선택 이유: 탐지와 차단은 빠를수록 좋지만, 재개는 정합성 evidence 확인이 필요하다.
- 포기한 것: 완전 자동 복구 속도.
- 보완 전략: incident analyzer report, consistency SQL, recovery case 목록을 승인 근거로 제공한다.
- 면접 답변용 한 문장: 차단은 자동화할 수 있지만, 금전 상태가 다시 안전하다는 판단은 evidence 기반으로 사람이 승인하도록 경계를 나눴습니다.

### 12.4 read-only mode 유지 vs 전체 서비스 중단

- 선택한 정책: 조회와 admin recovery는 제한적으로 유지하되, 금융 write는 닫는다.
- 대안: API 전체를 중단한다.
- 선택 이유: 운영자는 장애 중에도 상태 확인과 복구 판단을 해야 한다.
- 포기한 것: read 결과가 항상 최신이라는 단순한 보장.
- 보완 전략: read replica lag와 recovery mode 상태를 표시하고, stale 가능성이 있는 조회는 운영자용으로 제한한다.
- 면접 답변용 한 문장: 전체 중단보다 read-only와 recovery endpoint를 제한적으로 유지하면 복구 판단은 가능하지만, write 성공 의미는 절대 제공하지 않습니다.

### 12.5 DB-backed write suspend flag vs out-of-band state

- 선택한 정책: PostgreSQL down 상황에서도 동작해야 하므로 write suspend 판단은 DB 단독 저장소에 의존하지 않는다.
- 대안: write suspend 상태를 PostgreSQL `admin_config` 테이블에만 저장한다.
- 선택 이유: DB down 상황에서 DB-backed flag는 읽을 수 없으므로 hard dependency 장애 대응에 부적합하다.
- 포기한 것: 모든 운영 상태를 DB에서 일관되게 관리하는 단순성.
- 보완 전략: runtime flag, file artifact, Nginx route blocking, 복구 후 DB backfill을 조합한다.
- 면접 답변용 한 문장: DB 장애 대응 상태는 DB에만 둘 수 없기 때문에, 장애 중에는 out-of-band artifact와 runtime flag로 차단하고 복구 후 DB에 backfill하도록 설계했습니다.
