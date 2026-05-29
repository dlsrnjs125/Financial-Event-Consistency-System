# Infra Operations Extension Plan

## 1. 목적

Phase 1~12는 금융 이벤트 처리의 정합성, Redis fallback, 성능 측정, CI/CD Gate, Blue-Green/Rollback을 검증했다. 추가 운영 확장 단계는 같은 시스템을 실제 사내 인프라에서 운영한다고 가정하고, 관측 범위와 운영 절차를 애플리케이션 바깥으로 넓히는 기획이다.

핵심 질문은 다음과 같다.

- API p95가 증가했을 때 원인이 API 코드인지, DB connection인지, Redis latency인지, 서버 리소스인지 구분할 수 있는가?
- 장애 발생 후 운영자는 어떤 지표와 명령을 먼저 확인해야 하는가?
- PostgreSQL 백업 파일은 실제로 복구 가능한가?
- 배포, 백업, 로그 수집, rollback 같은 반복 작업을 표준화할 수 있는가?
- metrics/admin endpoint는 외부와 내부 중 어디에 열려야 하는가?

## 2. 추가 운영 Phase

| Phase | 이름 | 핵심 결과물 |
|---|---|---|
| 12 | Infra Metrics Extension | exporter, dashboard, alert rule |
| 13 | Nginx Access Control | public/internal endpoint 분리 |
| 14 | Backup/Restore DR Drill | backup, restore, checksum, consistency SQL |
| 15 | Ansible Automation | idempotent playbook |
| 16 | PowerShell Operator Scripts | Windows 점검 스크립트 |
| 17 | Internal Network Security | endpoint 접근 정책, masking/DLP 기준 |
| 18 | Incident Runbook | 장애별 탐지/대응/복구 절차 |

## 3. 설계 원칙

- PostgreSQL은 정합성 Source of Truth로 유지한다.
- Redis는 성능 최적화 계층이며, 장애 시 degraded dependency로 다룬다.
- metric label에는 고유 식별자를 넣지 않는다.
- 운영 명령은 destructive action을 기본값으로 포함하지 않는다.
- 백업은 생성보다 복구 가능성 검증을 우선한다.
- 자동화는 같은 명령을 반복 실행해도 결과가 안정적인 idempotent 구조를 목표로 한다.

## 4. 완료 기준

- README와 roadmap에 추가 운영 Phase가 연결되어 있다.
- docs 20~26과 runbook 문서가 각 Phase의 설계 기준을 설명한다.
- blog 13~19가 운영 확장 주제로 이어진다.
