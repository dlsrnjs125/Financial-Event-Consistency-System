# 개발 로드맵과 블로그 산출물 매핑

## 현재 진행 상태

- 현재 위치: **Phase 1 기획/설계 및 초기 세팅 완료**
- GitHub 초기 Push: **완료**
- 다음 단계: **Phase 2 도메인 모델링 구현**

초기 세팅에는 문서 구조, README, Docker Compose, FastAPI 기본 엔트리포인트, 마이그레이션 초안, 테스트/부하 테스트/배포 스크립트 골격 구성이 포함된다.
실제 거래 이벤트 처리 로직, ORM 모델 분리, DB 연동 서비스, Redis Lock/Cache는 다음 Phase에서 순차적으로 구현한다.

## 개발 Phase

| 상태 | Phase | 목표 | 주요 산출물 | 완료 기준 |
|------|-------|------|-------------|-----------|
| 완료 | 1. 기획/설계 | 문제와 범위 확정 | 문제 정의, 도메인 범위, 정합성 규칙, ERD, 상태 머신 초안 | 기획 체크리스트의 모든 질문에 답변 가능 |
| 다음 | 2. 도메인 모델링 | 핵심 엔티티와 상태 전이 구현 | ORM 모델, 상태 머신, 기본 마이그레이션 | 상태 머신 Unit Test 통과 |
| 대기 | 3. 기본 API | 거래 이벤트 수신 API 구현 | FastAPI 라우트, 요청/응답 스키마, Health/Ready API | API smoke test 통과 |
| 대기 | 4. 정합성 핵심 로직 | 중복 이벤트와 멱등성 방어 | IdempotencyRecord, request_hash, DB transaction, unique constraint | 동일 이벤트 100회 동시 요청 시 1회만 반영 |
| 대기 | 5. Redis 적용 | Lock/Cache로 중복 요청 완화 | Redis lock, response cache, DB fallback | Redis Down 상태에서도 최종 정합성 유지 |
| 대기 | 6. 테스트 자동화 | 정합성 회귀 방지 | Unit/Integration/Consistency Test | CI에서 정합성 테스트 실패 시 배포 차단 |
| 대기 | 7. 부하/장애 재현 | 운영 리스크 검증 | k6 시나리오, Redis Down, DB Pool 고갈, API 재시작 실험 | 장애 상황별 결과 기록 |
| 대기 | 8. 모니터링 | 운영 관측 가능성 확보 | Prometheus metrics, Grafana dashboard, alert rule | 중복 이벤트, 에러율, 지연, DB/Redis 상태 관측 |
| 대기 | 9. 배포/롤백 | 안전한 릴리스 흐름 구성 | Docker Compose, Nginx Blue-Green, deploy/rollback script | Green 검증 후 전환, 문제 시 Blue 복귀 |
| 대기 | 10. 문서/회고 | 포트폴리오 완성 | README, 블로그 12편, 회고 | 산출물 링크와 실험 결과 정리 |

## 완료 체크 기록

| 항목 | 상태 | 비고 |
|------|------|------|
| 기획 문서 작성 | 완료 | 문제 정의, 도메인 범위, 정합성 규칙 정리 |
| README 초안 작성 | 완료 | 프로젝트 목표, 실행 방법, 검증 기준 정리 |
| Docker Compose 기반 인프라 골격 | 완료 | PostgreSQL, Redis, API, Nginx, Prometheus, Grafana 구성 |
| FastAPI 기본 엔트리포인트 | 완료 | Health, Ready, Metrics, placeholder API 구성 |
| 테스트/부하 테스트 골격 | 완료 | Unit Test, Consistency Test skeleton, k6 시나리오 초안 |
| 배포/롤백 스크립트 골격 | 완료 | Blue-Green 전환과 rollback 스크립트 초안 |
| GitHub 초기 Push | 완료 | `main` 브랜치가 원격 저장소 `origin/main`을 추적 |

## 블로그 산출물 매핑

| 편 | 글 | 연결 산출물 | 보여줄 코드/테스트/실험 |
|----|----|-------------|--------------------------|
| 1 | 왜 금융 이벤트 처리에서 중복 처리가 중요한가? | 문제 정의 문서, 정합성 규칙 | 중복 입금 시나리오, 동일 이벤트 100회 검증 기준 |
| 2 | 도메인 모델링과 상태 머신 설계 | ERD 초안, 상태 머신 초안 | 엔티티 정의, 허용/금지 상태 전이, 상태 머신 Unit Test |
| 3 | Idempotency Key로 중복 요청을 방어하는 방법 | IdempotencyRecord 설계 | request_hash 비교, 같은 Key/다른 Body 409 테스트 |
| 4 | PostgreSQL Transaction과 Unique Constraint로 정합성 보장하기 | DB schema, transaction 처리 흐름 | `external_event_id` UNIQUE, Ledger 1:1 제약, 동시 요청 테스트 |
| 5 | Redis Lock/Cache를 어디까지 믿어야 할까? | Redis lock/cache 설계 | Redis 장애 fallback 코드, Redis Down 중복 방지 테스트 |
| 6 | 잘못된 상태 전이를 막는 테스트 전략 | 상태 머신 테스트, CI gate | `COMPLETED -> PROCESSING` 차단 테스트, 배포 차단 기준 |
| 7 | k6로 중복 이벤트 폭주 상황 재현하기 | k6 smoke/peak/duplicate 시나리오 | p50/p95/p99, 중복 반영 0건 검증 SQL |
| 8 | Prometheus/Grafana로 거래 이벤트 처리 상태 관측하기 | metrics endpoint, alert rule, dashboard | 중복 이벤트 카운터, 에러율, DB/Redis 지표 |
| 9 | Docker Compose 기반 장애 재현 환경 만들기 | `docker-compose.yml`, 장애 재현 스크립트 | Redis 중지, DB Pool 고갈, API 재시작 실험 |
| 10 | CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법 | GitHub Actions workflow | lint/unit/consistency/migration/docker gate 결과 |
| 11 | Blue-Green 배포와 Rollback 시뮬레이션 | Nginx 설정, deploy/rollback script | Green 헬스체크, 트래픽 전환, rollback 실행 로그 |
| 12 | 프로젝트 회고 | 전체 산출물 요약 | 설계 판단, 테스트에서 발견한 리스크, 운영 안정성 회고 |

## README 초안 목차

1. 프로젝트 목표
2. 시스템 아키텍처
3. 빠른 시작
4. 주요 엔드포인트
5. 기술 블로그 시리즈
6. 검증 기준
7. 테스트 전략
8. CI/CD 파이프라인
9. 모니터링 대시보드
10. 개발 가이드
11. 장애 대응
12. 문서
13. 배운 점

## 남은 구현 메모

- 현재 백엔드는 기획/초기 세팅 완료 상태이므로 거래 이벤트 API의 실제 DB 처리 로직은 Phase 2 이후 구현한다.
- Consistency Test 파일은 테스트 시나리오 골격을 먼저 잡은 상태이며, DB 연동 구현 후 skip을 제거한다.
- Phase 2에서는 `backend/app` 하위에 ORM 모델, 상태 머신, DB 세션, 요청/응답 스키마를 분리한다.
- Phase 2 완료 후 상태 머신 Unit Test를 실제 앱 코드 기준으로 통과시키고, 이 문서의 Phase 2 상태를 `완료`로 변경한다.
