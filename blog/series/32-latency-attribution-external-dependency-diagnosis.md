# k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유

## 1. 문제

운영 환경에서 latency가 튀면 가장 먼저 보이는 숫자는 보통 k6 p95, p99, error rate다. 이 숫자는 사용자가 느낀 증상을 보여주지만 원인을 증명하지는 않는다.

같은 p99 증가라도 원인은 PostgreSQL lock, DB pool wait, Redis timeout, FastAPI 내부 처리, Nginx edge 구간, 외부 partner endpoint, 또는 client network path일 수 있다.

## 2. PH10의 목표

PH10에서는 latency drill을 실행하지 않고, 이미 수집된 증거를 분류하는 deterministic analyzer를 만들었다.

분석 대상은 k6 지표만이 아니다. Nginx request/upstream timing, FastAPI handler timing, Redis/PostgreSQL phase timing, outbound HTTP timing, blackbox probe, consistency counter를 함께 비교한다.

결과는 최종 root cause가 아니라 candidate classification이다. 운영자는 이 결과를 보고 다음에 확인할 dashboard, log, runbook을 좁힌다.

## 3. k6는 증상이고 phase timing은 근거다

k6 p99가 높다는 사실만으로 “DB가 느리다”고 말하면 위험하다. PostgreSQL이 원인 후보가 되려면 FastAPI handler도 같이 증가하고, 그 안에서 PostgreSQL phase가 지배적인 비율을 차지해야 한다.

반대로 Nginx request time은 높은데 upstream과 FastAPI handler가 정상이라면 내부 application보다는 edge/client network path를 먼저 의심해야 한다.

## 4. 외부 dependency도 두 갈래로 나눈다

outbound HTTP가 느릴 때도 provider endpoint가 느린지, 우리 앱의 HTTP client path가 느린지 구분해야 한다.

PH10은 app outbound timing과 blackbox probe timing을 비교한다. 둘 다 높으면 external endpoint slow 후보가 되고, blackbox는 정상인데 app outbound만 높으면 DNS, TLS, connection pool, timeout, retry 설정을 의심한다.

## 5. consistency incident는 latency warning으로 낮추지 않는다

retry storm이나 timeout 상황에서는 latency와 consistency 문제가 같이 보일 수 있다.

그래서 PH10 report에는 duplicate ledger, duplicate external event, reconciliation failure, invalid state transition counter를 따로 둔다. 이 값이 0이 아니면 `VIOLATION_DETECTED`로 유지하고, latency 분류 결과보다 consistency incident flow를 먼저 본다.

## 6. 안전한 evidence만 남긴다

PH10 report는 raw account number, raw retry key, authorization material, signing material, raw request body, raw endpoint URL을 담지 않는다.

대신 `route_group`, `endpoint_group`, `partner_alias`, `method`, `status_code_family`, `phase` 같은 bounded label과 latency percentile, consistency count만 남긴다.

## 7. PH11과의 경계

PH10은 analyzer와 report 단계다. k6 latency drill, mock partner, Toxiproxy/netem fault injection, OpenTelemetry full tracing은 PH11 이후의 후속 후보로 남겼다.

이 경계를 분리한 이유는 간단하다. 먼저 evidence를 어떻게 읽을지 정하지 않으면, drill을 많이 만들어도 “p99가 올랐다”는 말만 반복하게 된다.
