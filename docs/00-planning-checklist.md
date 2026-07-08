# 기획 단계 체크리스트

이 문서는 기획 단계 종료 여부를 판단하기 위한 질문과 현재 프로젝트의 답변 위치를 정리한다.

## 문제 정의

| 질문 | 현재 답변 |
|------|-----------|
| 이 프로젝트는 어떤 금융 도메인 문제를 해결하는가? | 외부 금융 시스템의 재시도, 타임아웃, 네트워크 지연으로 동일 거래 이벤트가 중복 수신될 때 잔액과 원장이 한 번만 반영되도록 보장한다. 상세 내용은 [01-problem-definition.md](01-problem-definition.md)에 정리되어 있다. |
| 단순 CRUD와 무엇이 다른가? | 단순 생성/조회가 아니라 멱등성, 동시성, DB 트랜잭션, 상태 전이, 장애 fallback을 함께 검증한다. |
| 중복 이벤트가 왜 위험한가? | 같은 입금/출금/취소가 여러 번 반영되면 잔액 오류, 중복 결제, 정산 불일치, 감사 대응 실패로 이어진다. |

## 도메인 범위

| 질문 | 현재 답변 |
|------|-----------|
| 어떤 이벤트를 처리할 것인가? | `DEPOSIT`, `WITHDRAW`, `CANCEL` 3개 이벤트를 Phase 1 범위로 한다. |
| 이번 버전에서 제외할 것은 무엇인가? | 부분 취소, 복합 이체, 환율, 수수료, 실제 은행/PG/증권사 연동, Kubernetes, MSA, Kafka는 제외한다. |
| 실제 외부 시스템은 어떻게 가정할 것인가? | 은행/결제사/증권사 역할을 하는 Mock 외부 시스템이 Webhook/API 방식으로 이벤트를 재전송한다고 가정한다. |

상세 범위는 [02-domain-scope.md](02-domain-scope.md)에 정리되어 있다.

## 정합성 기준

| 질문 | 현재 답변 |
|------|-----------|
| 동일 이벤트는 어떻게 식별하는가? | 외부 시스템이 전달한 `external_event_id`를 동일 이벤트 식별자로 사용하고 DB UNIQUE 제약으로 최종 방어한다. |
| 동일 요청과 다른 요청은 어떻게 구분하는가? | `Idempotency-Key`와 정규화된 요청 본문의 `request_hash`를 함께 비교한다. 같은 Key와 같은 Hash는 동일 요청, 같은 Key와 다른 Hash는 충돌 요청이다. |
| 거래가 한 번만 반영됐다는 것을 어떻게 증명하는가? | `transaction_events.external_event_id`, `ledger_entries.transaction_event_id`, `idempotency_records.idempotency_key`의 유일성과 Ledger 기반 잔액 재계산으로 증명한다. |

상세 규칙은 [03-consistency-rules.md](03-consistency-rules.md)에 정리되어 있다.

## 운영 기준

| 질문 | 현재 답변 |
|------|-----------|
| Redis가 죽으면 어떻게 되는가? | Redis Lock/Cache는 성능 최적화 계층으로만 사용한다. Redis 장애 시 PostgreSQL Transaction, Row Lock, UNIQUE Constraint로 중복 반영을 막는다. |
| DB Connection Pool이 고갈되면 어떻게 되는가? | API는 DB 연결 실패/대기 시간을 에러율과 응답 지연으로 노출하고, k6 부하 테스트와 Grafana 지표로 재현한다. 신규 요청은 실패하거나 재시도를 유도하지만 이미 커밋된 거래는 중복 반영되지 않아야 한다. |
| 배포 중 문제가 생기면 어떻게 rollback할 것인가? | Blue-Green 구조에서 Nginx upstream을 이전 Blue로 되돌리고 `scripts/rollback.sh`로 Green 컨테이너를 중지한다. |

## 블로그 기준

각 블로그 글은 개발 산출물과 연결되어야 한다. 전체 매핑은 [04-development-roadmap.md](04-development-roadmap.md)의 "블로그 산출물 매핑"에 정리되어 있다.

## 최종 산출물 확인

| 기준 | 상태 | 위치 |
|------|------|------|
| 프로젝트 문제 정의 문서 | 완료 | [01-problem-definition.md](01-problem-definition.md) |
| 도메인 범위 | 완료 | [02-domain-scope.md](02-domain-scope.md) |
| 정합성 규칙 문서 | 완료 | [03-consistency-rules.md](03-consistency-rules.md) |
| ERD 초안 | 완료 | [02-domain-scope.md](02-domain-scope.md), [../blog/series/02-state-machine-domain-rules.md](../blog/series/02-state-machine-domain-rules.md) |
| 상태 머신 초안 | 완료 | [03-consistency-rules.md](03-consistency-rules.md), [../blog/series/02-state-machine-domain-rules.md](../blog/series/02-state-machine-domain-rules.md) |
| 개발 Phase 정리 | 완료 | [04-development-roadmap.md](04-development-roadmap.md) |
| 블로그 12편 목적/산출물 매핑 | 완료 | [04-development-roadmap.md](04-development-roadmap.md) |
| Architecture Decision Record | 완료 | [05-architecture-decision-record.md](05-architecture-decision-record.md) |
| 보안 설계 | 완료 | [06-security-design.md](06-security-design.md) |
| 관측성 설계 | 완료 | [07-observability-design.md](07-observability-design.md) |
| 장애 시나리오 | 완료 | [08-failure-scenarios.md](08-failure-scenarios.md) |
| 배포 전략 | 완료 | [09-deployment-strategy.md](09-deployment-strategy.md) |
| CANCEL 이벤트 정책 | 완료 | [10-cancel-event-policy.md](10-cancel-event-policy.md) |
| API 응답/재시도 정책 | 완료 | [11-api-response-policy.md](11-api-response-policy.md) |
| 데이터 모델 명세 | 완료 | [12-data-model-spec.md](12-data-model-spec.md) |
| 상태 전이표 | 완료 | [13-state-transition-table.md](13-state-transition-table.md) |
| 테스트 케이스 매트릭스 | 완료 | [14-test-case-matrix.md](14-test-case-matrix.md) |
| API Contract | 완료 | [15-api-contract.md](15-api-contract.md) |
| README 초안 목차 | 완료 | [../README.md](../README.md) |
