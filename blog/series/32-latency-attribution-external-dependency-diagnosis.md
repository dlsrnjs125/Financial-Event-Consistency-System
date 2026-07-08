# k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유

운영에서 latency가 튀면 가장 먼저 보이는 숫자는 보통 k6 p95, p99, error rate다. 이 숫자는 사용자가 느낀 증상이다. 하지만 증상은 원인 확정이 아니다.

PH10의 질문은 이것이었다.

```text
p95/p99가 높아졌을 때 왜 바로 DB 문제라고 말하면 안 되는가?
```

## p95/p99는 증상이지 원인 확정이 아니다

같은 p99 증가라도 원인은 PostgreSQL lock, DB pool wait, Redis timeout, FastAPI 내부 처리, Nginx edge 구간, 외부 endpoint, client network path일 수 있다.

그래서 PH10에서는 latency drill을 실행하지 않고, 이미 수집된 sanitized evidence를 분류하는 deterministic analyzer를 만들었다.

## Nginx request time과 upstream time을 나눠 본 이유

Nginx request time은 높은데 upstream time과 FastAPI handler timing이 정상이라면, 내부 application보다 edge/client network path를 먼저 의심해야 한다.

반대로 upstream과 handler가 같이 높다면 application 내부 phase timing을 봐야 한다. 이 분리가 없으면 모든 latency가 "서버가 느림"으로 뭉개진다.

## FastAPI phase, Redis, PostgreSQL, outbound evidence를 함께 본 이유

PostgreSQL이 원인 후보가 되려면 FastAPI handler timing이 증가하고, 그 안에서 PostgreSQL phase가 지배적인 비율을 차지해야 한다.

Redis는 degraded latency와 unavailable fallback을 나눠 본다. Redis가 느린 경우와 Redis가 없어져 DB fallback이 동작하는 경우는 운영 판단이 다르다.

outbound HTTP도 별도 phase로 본다. 내부 business logic이 느린 것인지, 외부 호출이 느린 것인지 분리해야 다음 runbook이 달라진다.

## blackbox probe로 외부 endpoint와 app client path를 나눈 이유

outbound HTTP가 느릴 때 provider endpoint가 느린지, 우리 앱의 HTTP client path가 느린지 구분해야 한다.

PH10은 app outbound timing과 blackbox probe timing을 비교한다. 둘 다 높으면 external endpoint slow 후보가 되고, blackbox는 정상인데 app outbound만 높으면 DNS, TLS, connection pool, timeout, retry 설정을 의심한다.

## 정합성 위반을 latency warning으로 낮추지 않은 이유

retry storm이나 timeout 상황에서는 latency와 consistency 문제가 같이 보일 수 있다.

그래서 PH10 report에는 duplicate ledger, duplicate external event, reconciliation failure, invalid state transition counter를 따로 둔다. 이 값이 0이 아니면 latency보다 consistency incident flow를 먼저 본다.

## 안전한 evidence만 남긴다

PH10 report는 raw 금융 식별자, retry 식별자, 인증/서명 자료, 요청 본문, plain endpoint 값을 담지 않는다.

대신 bounded route/endpoint/partner label, method, status family, phase, latency percentile, consistency count만 남긴다.

## 구현 중 실제로 막은 오해

validator는 k6 단독 root-cause claim, PH11 drill completed claim, forbidden metric label, sensitive raw content, unexpected sensitive top-level key를 실패 처리한다.

특히 PH10은 "root cause 확정"이 아니라 candidate classification이다. 운영자는 이 결과를 보고 다음 dashboard, log, runbook 확인 범위를 좁힌다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH10이 k6 증상을 Nginx/FastAPI/Redis/PostgreSQL/outbound/blackbox/consistency evidence와 함께 비교해 원인 후보를 좁힌다는 점이다.

말하면 안 되는 것은 PH10이 실제 latency drill, fault injection, OpenTelemetry full tracing, AI root-cause confirmation을 완료했다는 주장이다.
