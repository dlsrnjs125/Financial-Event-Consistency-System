# Infra Operations Extension Plan

## 1. 해결하려는 운영 문제

Phase 1~12는 금융 이벤트 처리의 정합성, Redis fallback, 성능 측정, CI/CD Gate, Blue-Green/Rollback을 검증했다.

Ops Phase 1~8은 같은 시스템을 실제 사내 인프라에서 운영한다고 가정하고, 다음 질문에 답하기 위한 운영 확장 설계다.

- API p95가 증가했을 때 원인이 API 코드인지, DB connection인지, Redis latency인지, 서버 리소스인지 구분할 수 있는가?
- 장애 발생 후 운영자는 어떤 지표와 명령을 먼저 확인해야 하는가?
- PostgreSQL 백업 파일은 실제로 복구 가능한가?
- 배포, 백업, 로그 수집, rollback 같은 반복 작업을 표준화할 수 있는가?
- metrics/admin endpoint는 외부와 내부 중 어디에 열려야 하는가?

## 2. 구현 범위

| Ops Phase | 이름 | 핵심 결과물 |
|---|---|---|
| 1 | Infra Metrics Extension | exporter, dashboard, alert rule |
| 2 | Blue-Green Deployment & Rollback Simulation | `ops2-*` 전환/rollback, routed smoke 재현 명령 |
| 3 | Nginx Access Control | public/internal endpoint 분리 |
| 4 | Backup/Restore DR Drill | backup, restore, checksum, consistency SQL |
| 5 | Ansible Automation | idempotent playbook |
| 6 | PowerShell Operator Scripts | Windows 점검 스크립트 |
| 7 | Internal Network Security | endpoint 접근 정책, masking/DLP 기준 |
| 8 | Incident Runbook | 장애별 탐지/대응/복구 절차 |

## 3. 제외 범위

- Kubernetes 기반 운영 환경 구성은 제외한다.
- 실제 NAC/VPN/DLP 솔루션 구축은 제외한다.
- VMware Horizon/VDI 같은 운영자 단말 인프라는 제외한다.
- Cloud managed DB 백업 정책과 PITR 구성은 별도 운영 환경 과제로 남긴다.
- OpenTelemetry 기반 분산 추적은 별도 향후 고도화 후보로 분리한다.

## 4. 파일/디렉터리 변경 계획

```text
docs/
  20-infra-metrics-design.md
  21-nginx-access-control.md
  22-backup-restore-drill.md
  23-ansible-automation-design.md
  24-windows-powershell-ops.md
  25-internal-network-security.md
  26-incident-runbook-index.md
  runbooks/
    redis-down.md
    postgres-connection-exhausted.md
    nginx-5xx-spike.md
    high-latency-p99.md
    disk-full.md
    failed-deployment.md

blog/
  13-why-infra-metrics-matter.md
  ...
  19-incident-runbook-oncall-simulation.md
```

## 5. 검증 명령어

각 Ops Phase는 최소 1개 이상의 명령으로 검증 가능해야 한다.

```bash
make metrics-check
make ops2-demo
make nginx-test
make dr-drill
make ansible-idempotency-test
make incident-drill-redis-down
```

## 6. 완료 기준과 README에 남길 결과

완료 기준은 코드나 설정 파일뿐 아니라 운영자가 읽을 수 있는 결과물을 포함한다.

- dashboard
- alert rule
- runbook
- incident report
- backup verify report
- ansible execution log

운영 확장 작업은 기존 정합성 원칙을 깨면 안 된다.

- PostgreSQL은 최종 Source of Truth다.
- Redis 장애는 degraded dependency로 처리한다.
- rollback은 DB rollback이 아니라 traffic rollback을 기본으로 한다.
- 장애 복구 후 ledger/account 정합성 검증을 수행한다.
