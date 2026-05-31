# SLO, SLI, Error Budget

> 이 문서는 Ops Phase 8 Incident Runbook을 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 목적

성능 metric은 수집만으로 충분하지 않다.
어느 수준부터 장애인지 판단할 기준이 필요하다.

이 문서는 금융 이벤트 처리 시스템의 SLI, SLO, error budget 정책을 정의한다.

## 2. SLI/SLO

| SLI | 목표 SLO | 장애 판단 |
|---|---|---|
| API 성공률 | 99.5% 이상 | 5분간 5xx > 1% |
| 이벤트 처리 p95 | 300ms 이하 | 5분간 p95 > 500ms |
| 이벤트 처리 p99 | 1s 이하 | 5분간 p99 > 2s |
| 정합성 위반 | 0건 | 1건이라도 Critical |
| Redis fallback | 허용 | 급증 시 Warning |
| DB connection 사용률 | 80% 미만 | 90% 이상 Critical |
| Backup restore 검증 | 100% 성공 | 실패 시 Critical |

## 3. 정합성 SLO

금융 정합성 위반은 error budget을 허용하지 않는다.

- ledger 중복 반영: 0건
- account balance 불일치: 0건
- 잘못된 terminal status 전이: 0건
- orphan idempotency record: 0건

정합성 위반은 성능 저하와 달리 error budget을 두지 않는다.
1건 발생 시 Critical incident로 분류한다.

## 4. Severity Level

| 장애 | Severity | 이유 |
|---|---|---|
| Ledger 중복 반영 | SEV1 | 금융 정합성 위반 |
| PostgreSQL down | SEV1 | 거래 처리 불가 |
| Secret leak | SEV1 | 이벤트 위조 가능성 |
| Redis down | SEV2 | degraded 가능, 최종 정합성 유지 |
| Nginx 5xx spike | SEV2 | 사용자 요청 실패 |
| p99 latency spike | SEV2 | timeout/retry 증가 가능 |
| Disk 85% | SEV3 | 예방 대응 가능 |
| Dashboard 일부 누락 | SEV3 | 장애 탐지 능력 저하 |

## 5. Error Budget 정책

- API latency와 5xx는 error budget을 둘 수 있다.
- Redis fallback은 정합성이 유지되는 한 Warning으로 시작한다.
- 정합성 위반, secret leak, PostgreSQL write 불가는 error budget을 두지 않는다.
- SEV1은 즉시 incident report와 재발 방지 action item을 요구한다.
