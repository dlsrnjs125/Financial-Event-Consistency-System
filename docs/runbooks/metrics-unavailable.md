# Metrics Unavailable Runbook

## 1. 장애 정의

Prometheus target down, exporter 장애, Grafana dashboard provision 실패 등으로 운영자가 장애를 관측하기 어려운 상태다.

거래 처리 자체가 즉시 실패하지 않더라도 장애 탐지 능력이 저하되므로 SEV3으로 분류한다.

## 2. 사용자 영향

- 장애 탐지 지연
- p95/p99, 5xx, Redis fallback, DB pressure 확인 어려움
- incident 분석 품질 저하

## 3. 즉시 확인할 Dashboard

- Prometheus target page
- Grafana provisioning status
- Infra dashboard

## 4. Alert Rule

```yaml
annotations:
  runbook: "docs/runbooks/metrics-unavailable.md"
```

확인할 alert:

- `PrometheusTargetDown`
- `GrafanaDashboardMissing`
- `ExporterDown`

## 5. 1차 확인 명령

```bash
make metrics-check
make dashboard-check
make local-status
```

## 6. 원인 분기표

| 관측 결과 | 판단 | 대응 |
|---|---|---|
| api target down | API metrics scrape 실패 | API `/metrics` 확인 |
| exporter target down | exporter 장애 | exporter container 확인 |
| dashboard 누락 | provisioning 실패 | Grafana provisioning log 확인 |
| Prometheus API 실패 | Prometheus 장애 | Prometheus container 확인 |

## 7. 대응 절차

1. target down 목록 확인
2. 해당 container 상태 확인
3. Prometheus config reload 또는 restart
4. Grafana provisioning log 확인
5. 핵심 metric key 조회 재시도

## 8. 복구 확인 기준

- 필수 Prometheus target 모두 UP
- API/Infra/DB/Redis/Nginx dashboard 확인 가능
- alert rule syntax 검증 통과

## 9. 재발 방지

- exporter health alert 추가
- dashboard provisioning check 자동화
- config 변경 시 `promtool` 검증 추가

## 10. 사후 기록 템플릿

- 발생 시간:
- down target:
- 누락 dashboard:
- 복구 조치:
- 재발 방지:
