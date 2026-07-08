# 장애를 복구했다는 말만으로는 부족했다

장애 대응에서 "복구했습니다"라는 말만으로는 충분하지 않다. 언제 감지했고, 어떤 영향이 있었고, 어떤 조치를 했고, 복구 후 정합성이 유지됐는지를 evidence로 남겨야 한다.

이 글은 runbook, alert rule, incident timeline, postmortem을 하나의 운영 흐름으로 묶은 과정이다.

## 복구했다는 말만으로는 나중에 아무것도 설명할 수 없었다

Redis degraded, PostgreSQL down, Nginx route issue, latency spike는 모두 다른 장애다. 그런데 대응 기록이 사람마다 다르면 나중에 같은 장애를 재현하거나 개선하기 어렵다.

그래서 장애 대응을 다음 흐름으로 고정했다.

```text
Detect
  -> Triage
  -> Mitigate
  -> Recover
  -> Verify consistency
  -> Postmortem action item
```

## Incident Timeline을 어떻게 나눴나

Redis degraded incident drill에서는 timeline을 단계별로 나눴다.

| 단계 | 의미 |
| --- | --- |
| STARTED | controlled drill 시작 |
| DETECTED | `/ready`에서 Redis degraded 확인 |
| IMPACT_CHECK | Redis down 상태에서 duplicate smoke 요청 |
| MITIGATED | Redis restart 요청 |
| RECOVERED | readiness PASS |
| VERIFIED | duplicate ledger count 0, consistency check PASS |

이렇게 나누면 "언제 알았는가"와 "언제 복구됐는가"를 분리해서 볼 수 있다.

## Alert severity는 정합성 기준으로 나눴다

Redis down은 성능과 가용성 저하를 만들 수 있다. 하지만 PostgreSQL 기준 정합성이 유지된다면 warning으로 시작한다.

반대로 PostgreSQL down, reconciliation failure, duplicate ledger는 Source of Truth 또는 금융 정합성 문제이므로 critical로 본다.

Alert는 단순 threshold가 아니라 운영자가 어떤 순서로 움직일지 알려주는 action signal이어야 한다.

## latency를 네 가지로 나눈 이유

postmortem에는 시간을 하나만 남기지 않았다.

| 항목 | 의미 |
| --- | --- |
| Detection latency | 장애 시작부터 감지까지 걸린 시간 |
| Mitigation latency | 감지 후 완화 조치까지 걸린 시간 |
| Recovery duration | 완화 조치 후 readiness PASS까지 걸린 시간 |
| Total incident duration | 시작부터 검증 완료까지 전체 시간 |

전체 시간이 길어도 감지가 느린 것인지, 조치가 느린 것인지, 복구 검증이 오래 걸린 것인지에 따라 개선 방향이 다르다.

## count-only evidence를 남긴 이유

incident report에 실제 row data나 account number 원문을 남기지 않았다. 대신 다음처럼 count-only evidence를 남긴다.

- duplicate external event count
- duplicate ledger count
- idempotency conflict count
- readiness dependency status
- synthetic external event id prefix
- idempotency key prefix

장애 기록은 분석에 충분해야 하지만, 민감정보 저장소가 되면 안 된다.

## CI와 local drill을 분리한 이유

CI에서 Redis stop/start 같은 destructive drill을 직접 실행하면 test runner 환경에 따라 flaky해질 수 있다.

그래서 CI에서는 다음을 검증했다.

- script가 실행 가능한지
- report schema가 맞는지
- postmortem 필수 필드가 있는지
- consistency check command가 wiring되어 있는지

실제 Redis degraded incident drill은 local Docker Compose evidence로 남긴다.

```bash
make ops7-incident-timeline-drill
make ops7-incident-timeline-check
```

## 모든 운영 명령을 자동 실행 대상으로 보지 않았다

운영 drill을 한 곳에 모을 때도 모든 명령을 자동 실행 대상으로 넣지는 않았다.

DB down, write resume, recovery approval, failover, queue replay, partner key retirement는 위험도가 다르다. 그래서 safe report generation과 validation은 자동화하고, write resume, recovery execution, partner key retirement, failover promotion, queue replay는 manual approval boundary로 남겼다.

운영 자동화의 목표는 사람을 완전히 빼는 것이 아니라, 자동으로 실행해도 되는 검증과 사람이 승인해야 하는 조치를 분리하는 것이다.

## 정합성 위반에는 error budget을 두지 않았다

latency와 5xx에는 error budget을 둘 수 있다. 하지만 duplicate ledger, account balance mismatch, invalid terminal transition은 1건이라도 consistency incident candidate다.

금융 이벤트 시스템에서 "조금의 중복 반영은 허용"이라는 기준은 두지 않았다.

## 트러블슈팅: 복구와 검증은 다르다

Redis를 다시 올리고 `/ready`가 PASS가 됐다고 해서 장애 대응이 끝난 것은 아니다.

duplicate smoke 요청 이후 ledger가 중복 생성되지 않았는지, idempotency replay가 같은 결과를 반환하는지, consistency SQL이 PASS인지 확인해야 한다.

그래서 timeline의 마지막 단계를 `RECOVERED`가 아니라 `VERIFIED`로 뒀다.

## 남은 한계

이 runbook은 local Docker Compose와 sample evidence 기준이다. 실제 운영 on-call에서는 Slack/PagerDuty 연동, alert threshold tuning, dashboard snapshot 보존, 권한 승인 절차가 추가되어야 한다.

그래도 장애 대응을 감지, 영향 확인, 완화, 복구, 정합성 검증, 사후 액션으로 분리한 점이 핵심이다.
