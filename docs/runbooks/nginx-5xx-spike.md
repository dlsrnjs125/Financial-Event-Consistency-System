# Nginx 5xx Spike Runbook

## 1. 장애 정의

Nginx에서 5xx 응답이 급증하거나 upstream 연결 실패가 발생한 상태다.

원인은 upstream API 장애, Nginx 설정 오류, Blue-Green 전환 실패, readiness 실패일 수 있다.

## 2. 사용자 영향

외부 금융사 이벤트 수신 실패가 증가할 수 있다.

client retry가 발생하면 duplicate storm으로 이어질 수 있으므로 idempotency와 DB 정합성 검증이 함께 필요하다.

## 3. 즉시 확인할 Dashboard

- Nginx dashboard: 5xx rate, upstream response time
- API dashboard: 5xx, readiness status
- Deployment dashboard: active upstream color

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/nginx-5xx-spike.md"
```

확인할 alert:

- `Nginx5xxSpike`
- `NginxUpstreamLatencyHigh`
- `FailedDeploymentSmoke`

## 5. 1차 확인 명령

```bash
make deploy-status
make deploy-smoke
docker compose exec -T nginx nginx -t
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| `nginx -t` 실패 | config 오류 | reload 금지, backup restore |
| Green health 실패 | target 준비 안 됨 | switch 중단 |
| 전환 후 5xx 증가 | deployment regression | Blue rollback |
| Blue/Green 모두 실패 | shared dependency 장애 | DB/Redis readiness 확인 |

## 7. 대응 절차

1. active upstream 확인
2. Nginx config test 실행
3. Blue/Green API health 확인
4. 전환 직후 장애라면 rollback 실행
5. rollback 후 smoke와 정합성 검증 실행

## 8. 복구 확인 기준

- Nginx 5xx 증가 중단
- `/health`, `/ready` 200
- deploy-smoke 통과
- duplicated ledger/event count 0

## 9. 재발 방지

- upstream snippet 변경 전후 `nginx -t` 유지
- reload 실패 시 backup restore 유지
- Nginx 내부에서 target API health 확인

## 10. 사후 기록 템플릿

- 발생 시간:
- active color:
- upstream target:
- rollback 여부:
- smoke 결과:
- 정합성 검증 결과:
