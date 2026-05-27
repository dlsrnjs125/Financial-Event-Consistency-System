# 14. Test Case Matrix

## 1. 목적

이 문서는 개발 단계에서 작성할 테스트 케이스의 기준과 우선순위를 고정한다.

테스트는 단순 API 성공 여부가 아니라 금융 이벤트 정합성, 멱등성, 상태 전이, 장애 상황, 보안 검증을 확인해야 한다.

---

## 2. 테스트 케이스 목록

| ID | category | scenario | expected |
|----|----------|----------|----------|
| TC-001 | Idempotency | 같은 Key + 같은 Body 2회 요청 | 기존 응답 반환 |
| TC-002 | Idempotency | 같은 Key + 다른 Body 요청 | 409 Conflict |
| TC-003 | Duplicate | 같은 `external_event_id` 100회 동시 요청 | ledger 1건 |
| TC-004 | State | `COMPLETED -> PROCESSING` 시도 | 예외 발생 |
| TC-005 | State | `FAILED -> COMPLETED` 시도 | 예외 발생 |
| TC-006 | Cancel | DEPOSIT 취소 | 반대 방향 Ledger 생성 |
| TC-007 | Cancel | SETTLED 거래 CANCEL 시도 | 실패 |
| TC-008 | Redis | Redis Down 상태에서 중복 요청 | ledger 1건 |
| TC-009 | DB | DB Pool 고갈 | 일부 503, 정합성 유지 |
| TC-010 | Migration | 잘못된 Migration | CI 실패 |
| TC-011 | Security | 잘못된 HMAC Signature | 401 |
| TC-012 | Security | Timestamp 5분 초과 | 401 |
| TC-013 | Reconciliation | balance와 ledger 불일치 | 메트릭 증가 |

---

## 3. 테스트 작성 순서

1. 상태 머신 Unit Test
2. Idempotency request_hash Unit Test
3. ORM 제약조건 테스트
4. 거래 이벤트 처리 Service Test
5. API Contract Test
6. 중복 이벤트 동시 요청 Consistency Test
7. Redis Down 장애 시나리오 Test
8. DB Pool 고갈 부하 Test
9. Migration 검증 Test
10. 배포 Smoke Test

---

## 4. 테스트 계층

| layer | purpose | examples |
|-------|---------|----------|
| Unit | 도메인 규칙 단위 검증 | 상태 전이, request_hash, 금액 부호 |
| Integration | DB/Redis 포함 검증 | Transaction, Unique Constraint, Redis fallback |
| Consistency | 정합성 회귀 방지 | 동일 이벤트 100회, Ledger 1건 |
| Load | 부하 상황 검증 | k6 peak-load, duplicate-storm |
| Deployment | 배포 전 검증 | Health, Ready, Smoke, Migration |

---

## 5. 설계 결론

이 테스트 매트릭스는 개발자가 어떤 테스트를 어떤 순서로 작성해야 하는지 보여주는 기준표다.

Phase 2에서는 데이터 모델 테스트를 먼저 작성하고, Phase 3에서는 상태 머신 테스트를 작성한다. Phase 4 이후 API와 정합성 테스트를 확장한다.
