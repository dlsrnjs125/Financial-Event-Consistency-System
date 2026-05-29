# Failed Deployment Runbook

## 1. 장애 정의

Green 검증, Nginx config test, upstream switch, 전환 후 smoke 중 하나가 실패한 배포 장애다.

Phase 12 기준 rollback은 DB rollback이 아니라 API traffic rollback이다.

## 2. 사용자 영향

- Green 전환 전 실패라면 사용자 영향이 없어야 한다.
- 전환 후 실패라면 5xx 증가 또는 거래 이벤트 수신 실패가 발생할 수 있다.
- rollback 후 정합성 검증이 필요하다.

## 3. 즉시 확인할 Dashboard

- Deployment dashboard: active color, switch status
- Nginx dashboard: 5xx, upstream response time
- API dashboard: health, readiness, error rate

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/failed-deployment.md"
```

확인할 alert:

- `FailedDeploymentSmoke`
- `Nginx5xxSpike`
- `GreenReadinessFailed`

## 5. 1차 확인 명령

```bash
make deploy-status
make deploy-smoke
make deploy-rollback
make deploy-verify
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| Green `/ready` 실패 | 전환 전 차단 | switch 금지 |
| `nginx -t` 실패 | config 오류 | reload 금지 |
| reload 실패 | state drift 위험 | backup restore |
| 전환 후 smoke 실패 | Green regression | Blue rollback |
| rollback 후 검증 실패 | shared data/dependency 문제 | DB/Redis runbook 연결 |

## 7. 대응 절차

1. Green 검증 실패면 전환하지 않는다.
2. 전환 후 smoke 실패면 rollback 실행
3. rollback 후 Blue `/ready`와 smoke 확인
4. DB rollback은 자동 수행하지 않는다.
5. ledger/account 정합성 검증 실행

## 8. 복구 확인 기준

- active upstream이 Blue로 복구
- `/health`, `/ready` 200
- deploy-smoke 통과
- duplicate ledger/event count 0

## 9. 재발 방지

- Green 검증 항목 강화
- Nginx reload 실패 시 backup restore 유지
- host port와 container port 혼동 방지
- migration은 backward-compatible 원칙 유지

## 10. 사후 기록 템플릿

- 발생 시간:
- 실패 단계:
- active color:
- rollback 여부:
- 정합성 검증 결과:
