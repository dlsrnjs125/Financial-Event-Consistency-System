# Infra Operations Extension Plan

## 1. 해결하려는 운영 문제

Phase 1~12는 금융 이벤트 처리의 정합성, Redis fallback, 성능 측정, CI/CD Gate, Blue-Green/Rollback을 검증했다.

Ops Extension Track은 같은 시스템을 실제 사내 인프라에서 운영한다고 가정하고, 다음 질문에 답하기 위한 운영 확장 설계다.
Ops Phase는 1~8까지만 진행하며, Phase 8 Incident Runbook에서 필수 운영 확장 범위를 종료한다.

- API p95가 증가했을 때 원인이 API 코드인지, DB connection인지, Redis latency인지, 서버 리소스인지 구분할 수 있는가?
- 장애 발생 후 운영자는 어떤 지표와 명령을 먼저 확인해야 하는가?
- PostgreSQL 백업 파일은 실제로 복구 가능한가?
- 배포, 백업, 로그 수집, rollback 같은 반복 작업을 표준화할 수 있는가?
- metrics/admin endpoint는 외부와 내부 중 어디에 열려야 하는가?

## 2. 구현 범위

| Ops Phase | 이름 | Status | 핵심 결과물 |
|---|---|---|---|
| 1 | Infra Metrics Extension | Done | exporter, dashboard, monitoring evidence |
| 2 | Blue-Green Deployment & Rollback Simulation | Done | `ops2-*` 전환/rollback, routed smoke 재현 명령 |
| 3 | Nginx Access Control | Done | public/internal endpoint 분리 |
| 4 | PostgreSQL Backup/Restore DR Drill | Done | backup, checksum, restore, consistency SQL, DR report |
| 5 | Failure Recovery Runbook Drill | Done | Redis/API/PostgreSQL stop/start recovery evidence |
| 6 | Alerting & Incident Response Runbook | Done | Prometheus alert rule, runbook, CI gate evidence |
| 7 | Incident Timeline & Postmortem Drill | Done | Redis degraded incident timeline, postmortem, action item |
| 8 | Incident Runbook Finalization | Completed | incident runbook index, SLO/SLI, observability evidence, measurement template |

Ops Extension Track은 Phase 8 Incident Runbook에서 종료한다.
이후 문서는 새로운 필수 Phase가 아니라, 운영 보안과 장애 대응을 설명하기 위한 보조 문서로 관리한다.
`docs/27-*` ~ `docs/34-*` 문서는 새로운 Ops Phase가 아니라, Ops Phase 7~8의 운영 보안·장애 대응·측정 증거를 보완하기 위한 supporting documents다.

Ops Phase 8의 목표는 다음이다.

- 장애 상황별 탐지 기준을 정의한다.
- 운영자가 어떤 순서로 대응해야 하는지 정리한다.
- 복구 성공 여부를 검증할 수 있는 체크리스트를 둔다.
- 장애 후 재발 방지 항목을 정리한다.
- 실제 실행 가능한 명령과 수동 확인 항목을 구분한다.
- Redis, PostgreSQL, Nginx, 배포 실패, 정합성 위반, 보안 사고를 포함한다.

## 3. 제외 범위

- Kubernetes 기반 운영 환경 구성은 제외한다.
- 실제 NAC/VPN/DLP 솔루션 구축은 제외한다.
- VMware Horizon/VDI 같은 운영자 단말 인프라는 제외한다.
- Cloud managed DB 백업 정책과 PITR 구성은 별도 운영 환경 과제로 남긴다.
- OpenTelemetry 기반 분산 추적은 별도 향후 고도화 후보로 분리한다.

## 4. Supporting Documents

아래 문서들은 추가 Ops Phase가 아니라, Ops Phase 7~8의 운영 판단과 증거 정리를 보완하기 위한 supporting documents다.

| Document | Role | Related Ops Phase | Required |
| --- | --- | --- | --- |
| `27-threat-model.md` | 운영 보안 위협 모델 | Ops 7 | Supporting |
| `28-secret-management-policy.md` | Secret 관리 정책 | Ops 7 | Supporting |
| `29-slo-sli-error-budget.md` | 장애 판단 기준 | Ops 8 | Supporting |
| `30-change-management.md` | 변경 관리 기준 | Ops 2 / Ops 8 | Optional |
| `31-capacity-planning.md` | 용량 산정 기준 | Appendix | Optional |
| `32-security-checklist.md` | 운영 보안 점검표 | Ops 7 | Supporting |
| `33-observability-evidence-plan.md` | 관측 증거 수집 계획 | Ops 8 | Supporting |
| `34-measurement-result-template.md` | 측정 결과 템플릿 | Appendix | Optional |

## 5. 파일/디렉터리 기준

Note:
일부 문서 번호는 Development/Ops 확장 과정에서 생성된 historical numbering을 유지한다.
Ops Phase 번호와 docs 파일 번호는 1:1로 대응하지 않는다.
실제 Ops Phase 기준은 본 문서의 구현 범위 표를 따른다.

```text
docs/
  20-infra-metrics-design.md
  21-nginx-access-control.md
  22-postgres-backup-restore-drill.md
  23-failure-recovery-runbook-drill.md
  24-alerting-incident-response-runbook.md
  25-incident-timeline-postmortem-drill.md
  26-incident-runbook-index.md
  27-threat-model.md
  ...
  34-measurement-result-template.md
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

## 6. 검증 명령어

각 Ops Phase는 최소 1개 이상의 명령이나 report로 검증 가능해야 한다.

```bash
make metrics-check
make ops2-demo
make ops3-demo
make ops4-demo
make ops5-demo
make ops6-demo
make ops7-demo
```

Ops Phase 8은 새로운 장애 주입 기능을 늘리는 단계가 아니라, `docs/26-incident-runbook-index.md`와 supporting documents를 정리해 운영자가 장애 상황별 대응 기준을 찾을 수 있게 만드는 최종 문서화 단계다.
Ops Phase 8 완료를 기준으로 운영 확장 트랙은 종료한다.
이후 항목은 새로운 필수 Phase가 아니라 향후 고도화 후보로 관리한다.

## 7. 완료 기준과 README에 남길 결과

완료 기준은 코드나 설정 파일뿐 아니라 운영자가 읽을 수 있는 결과물을 포함한다.

- dashboard
- alert rule
- runbook
- incident report
- backup verify report
- PostgreSQL restore DR Drill report
- incident runbook index
- SLO/SLI 기준
- observability evidence plan
- measurement result template

운영 확장 작업은 기존 정합성 원칙을 깨면 안 된다.

- PostgreSQL은 최종 Source of Truth다.
- Redis 장애는 degraded dependency로 처리한다.
- rollback은 DB rollback이 아니라 traffic rollback을 기본으로 한다.
- 장애 복구 후 ledger/account 정합성 검증을 수행한다.

## 8. Ops Phase 4 PostgreSQL DR Drill 기준

PostgreSQL 백업은 파일 생성만으로 완료하지 않는다. `pg_dump -Fc`로 생성한 dump를 별도 `postgres-restore/financial_events_restore`에 복원하고, 다음 count-only 검증이 모두 0일 때만 PASS로 기록한다.

- duplicated external event
- duplicated ledger event reference
- orphan ledger
- ledger/account mismatch
- duplicated idempotency key
- account balance mismatch

운영 DB volume은 삭제하지 않으며, `ops4-cleanup`도 restore DB 컨테이너만 대상으로 한다. dump와 checksum은 민감 데이터 또는 운영 메타데이터를 포함할 수 있으므로 git에 커밋하지 않는다.

## 9. Optional Enhancements

다음 항목은 현재 필수 Ops Phase에 포함하지 않고 향후 운영 고도화 후보로 분리한다.

- Ansible 기반 서버 상태 자동화
- Windows/PowerShell 운영자 점검 스크립트
- 고급 capacity planning과 장기 트래픽 예측
- 확장된 change management 승인 workflow
- OpenTelemetry, Loki, Grafana Explore 링크 기반 trace evidence
