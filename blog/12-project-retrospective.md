# 12편. 프로젝트 회고: 금융권 백엔드에서 정합성과 운영 안정성을 어떻게 설계했는가?

## 들어가며

11편의 기술 글을 통해 금융 이벤트 처리 시스템의 정합성을 보장하는 방법을 다루었습니다.

이 마지막 편에서는 **전체 여정을 회고**하고, 설계 과정에서 배운 교훈을 정리합니다.

---

## 프로젝트 요약

### 문제
외부 금융 시스템에서 중복·재시도·타임아웃으로 인한 중복 이벤트가 시스템을 통해 중복 처리되는 문제

### 해결 방식
1. **Idempotency Key**: 같은 요청의 중복 처리 방지
2. **PostgreSQL Transaction + Unique Constraint**: 최종 정합성 보장
3. **Redis Lock/Cache**: 성능 최적화 (선택사항)
4. **상태 머신**: 불가능한 상태 전이 차단
5. **자동화 테스트**: CI에서 배포 차단
6. **모니터링 + 장애 재현**: 운영 안정성 확보

### 결과
- 중복 이벤트 100번 동시 요청 → 1회만 처리 ✅
- Redis 장애에도 정합성 유지 ✅
- 잘못된 상태 전이 테스트로 자동 차단 ✅
- Blue-Green 배포로 무중단 배포 ✅

---

## 설계 시 중요한 판단들

### 1. Redis를 정합성 기준으로 두지 않은 이유
```
❌ 나쁜 설계
"Redis Lock을 획득했으니 정합성이 보장된다"
→ Redis 장애 시 정합성 깨짐

✅ 좋은 설계
"Redis는 성능 도구일 뿐, 최종 정합성은 PostgreSQL"
→ Redis 장애에도 Unique Constraint로 보호
```

### 2. Row Lock (FOR UPDATE) 사용
```
Race condition을 막기 위해 트랜잭션 중에
Account 행에 Lock을 걸어 동시성 문제 방지
```

### 3. 멱등성 기록에 Request Hash 저장
```
같은 Idempotency Key로 다른 금액이 들어오는
위험을 409 Conflict로 방어
```

### 4. Expand → Backfill → Contract Migration
```
운영 DB에서 Lock으로 인한 장애를 피하고
기존 코드와 신규 코드가 공존할 수 있도록 설계
```

---

## 테스트에서 배운 점

### 단위 테스트의 한계
```
상태 머신 단위 테스트는 통과했지만
동시 요청 100개는 테스트하지 않으면 발견 못 함
```

### 정합성 테스트의 중요성
```
- 100개 동시 요청 테스트
- Redis 없이도 중복 방지 테스트
- DB Connection Pool 고갈 테스트
→ 이들이 모두 통과해야 배포 가능
```

### 부하 테스트의 영향
```
k6로 실제 시나리오를 재현했을 때
처음 설계의 문제점들이 드러남
```

---

## 운영에서 배운 점

### 모니터링의 중요성
```
- financial_events_duplicate_total = 0 확인
- financial_invalid_state_transition_total = 0 확인
- idempotency_cache_hit_ratio 모니터링
→ 이 지표들로 시스템 건강도 판단
```

### 알람 설정
```
중복 이벤트 발생 → 즉시 알람
잘못된 상태 전이 → 즉시 알람
Redis 장애 → 모니터링하되 정합성은 유지됨
```

### 롤백 전략
```
Blue-Green 배포로 문제 발생 시 즉시 원상복구
배포 후 5분 모니터링으로 문제 조기 발견
```

---

## 설계 과정에서 남은 기준

### 1. 문제를 먼저 좁힌다

처음부터 모든 금융 시스템을 만들려고 하지 않았다. 외부 시스템 retry, timeout, 중복 이벤트, 잘못된 상태 전이처럼 정합성이 깨지는 입력을 먼저 정의했다.

### 2. 최종 기준을 하나로 둔다

Redis, metric, log는 모두 보조 수단이다. 중복 반영 여부는 PostgreSQL transaction, unique constraint, LedgerEntry 기준으로 판단했다.

### 3. 검증 명령을 남긴다

설계 문서만으로는 부족했다. `make phase10-redis-down-check`, `make final-check`, `make phase12-check`처럼 같은 장애와 검증을 반복할 수 있는 명령을 남겼다.

### 4. 배포와 rollback도 정합성 검증의 일부다

배포는 새 컨테이너가 뜨는 것으로 끝나지 않는다. Green smoke, Nginx internal upstream 확인, rollback 후 `deploy-verify`까지 통과해야 배포 절차가 닫힌다.

---

## 다른 도메인으로의 확장 가능성

### 결제 시스템
```
결제 승인 → 취소 상태 전이의 정합성 필요
```

### 증권 거래 시스템
```
주문 → 체결 → 결제의 원자성 보장 필요
```

### 재고 관리
```
재고 감소 → 보충 주문의 최종 정합성 필요
```

---

## 마지막 한 마디

> **이 프로젝트의 핵심은 "요청을 받는 것"이 아니라, 중복·재시도·장애·배포 상황에서도 거래 결과가 한 번만 정확하게 반영되도록 설계하고, 테스트로 고정하고, 모니터링으로 관측하는 것입니다.**
>
> **이것이 진정한 "운영 가능한 시스템"입니다.**

---

## 참고 자료

- PostgreSQL Documentation: Transaction Isolation
- Redis Documentation: Persistence & Failover
- k6 Documentation: Load Testing
- Prometheus & Grafana: Monitoring
- Blue-Green Deployment: Best Practices

---

## AI 활용 및 검증 과정

AI는 설계 초안, 테스트 시나리오 발굴, 코드 리뷰 체크리스트 작성에 보조 도구로 사용했다. 최종 반영 여부는 현재 코드 구조, 테스트 결과, 실제 재현 가능성 기준으로 판단했다.

특히 다음 항목은 제안 내용을 그대로 받아들이지 않고, 코드와 명령으로 다시 확인한 뒤 반영했다.

- Redis readiness policy를 PostgreSQL hard dependency와 Redis degraded dependency로 분리
- `idempotency_key`, `account_no` raw logging 제거와 masking helper 적용
- `security-log-check`와 secret scan 역할 분리
- `final-check`를 non-mutating 검증 명령으로 정리
- Nginx reload 실패 시 upstream backup restore 추가
- Green host port와 container port를 구분하고 Nginx 내부 upstream을 `api-green:8000`으로 검증

이 과정에서 AI는 누락된 장애 시나리오를 찾는 데 유용했지만, 실제 완료 기준은 `make final-check`, `make phase12-check`, k6/SQL 검증, 로그/메트릭 확인 결과였다.

## 가장 크게 바뀐 설계 기준

처음에는 Redis lock을 잘 사용하면 중복 요청 대부분을 앞단에서 막을 수 있다고 생각했다. 하지만 Redis Down duplicate storm을 재현하자 기준이 달라졌다. Redis는 성능 최적화 계층일 뿐이고, 정합성의 최종 기준은 PostgreSQL transaction과 unique constraint여야 했다.

또 하나의 변화는 "성공한 배포"의 정의였다. 컨테이너가 뜨고 Nginx가 reload되면 배포가 끝났다고 볼 수 없다. Green 검증, Nginx 내부 upstream 확인, 전환 후 smoke, rollback 후 verify까지 통과해야 배포 절차가 안전하다고 볼 수 있다.

이 프로젝트를 정리하면서 남은 기준은 다음과 같다.

- 장애는 문서로만 정의하지 않고 명령으로 재현한다.
- Redis 장애와 DB 장애는 readiness 정책에서 다르게 다룬다.
- metric은 집계 관측용, 로그는 개별 요청 추적용으로 나눈다.
- CI Gate는 빠른 회귀 차단에 집중하고, heavy performance test는 별도 Gate로 분리한다.
- rollback은 DB를 되돌리는 것이 아니라 traffic을 안전한 버전으로 되돌리는 절차다.

## 범위를 어디서 멈췄는가

프로젝트를 진행하다 보면 Kubernetes, Slack/PagerDuty, Loki/OpenTelemetry, 실제 클라우드 운영까지 확장할 수 있는 지점이 계속 생긴다.  
하지만 이번 프로젝트의 핵심은 모든 운영 도구를 붙이는 것이 아니라, 금융 이벤트 처리에서 중복 반영을 막고, 장애 상황에서도 PostgreSQL 기준 정합성을 검증하며, 복구 판단 기준을 Runbook과 evidence로 남기는 것이었다.

따라서 Ops Extension Track은 Phase 8 Incident Runbook에서 종료했다.  
이후 항목은 구현 부족이 아니라 운영 환경이 커질 때 필요한 확장 후보로 분리했다.

## 저작권 및 라이선스

이 프로젝트는 학습과 기술 검증을 목적으로 작성했다.
