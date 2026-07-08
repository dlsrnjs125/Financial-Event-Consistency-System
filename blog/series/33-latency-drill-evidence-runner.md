# k6 Latency Drill을 PH10 Analyzer와 연결한 이유

k6로 p95/p99를 올리는 테스트는 만들 수 있다. 하지만 latency 숫자를 만드는 것과 원인 후보를 좁히는 evidence를 만드는 것은 다르다.

PH11의 질문은 이것이었다.

```text
Latency drill은 숫자를 만드는 것인가, 원인 후보를 좁히는 evidence를 만드는 것인가?
```

## latency 숫자를 만드는 것만으로는 부족하다

p99가 올랐다는 사실만으로 DB, Redis, Nginx, external dependency를 확정할 수 없다. PH10 analyzer가 읽을 수 있는 형태로 server evidence와 consistency counter가 함께 있어야 한다.

그래서 PH11은 k6 drill 자체를 많이 늘리는 대신, LAT-001~LAT-006 drill catalog와 PH10 input evidence generator를 만들었다.

## DB lock, Redis down, network delay를 default demo에 넣지 않은 이유

DB lock holder, Redis down, network delay는 의미 있는 drill이지만 기본 demo에 넣으면 로컬 환경을 깨뜨릴 수 있다.

PH11 default demo는 synthetic sanitized evidence만 생성한다. 실제 fault injection은 manual 또는 follow-up candidate로 남긴다.

## LAT-001~LAT-006을 drill catalog로 묶은 이유

PH11 catalog는 다음 흐름을 고정한다.

| Drill | 의미 |
| --- | --- |
| LAT-001 | baseline latency evidence |
| LAT-002 | PostgreSQL pool pressure evidence |
| LAT-003 | PostgreSQL lock contention evidence |
| LAT-004 | Redis delay/down evidence |
| LAT-005 | external dependency slow response evidence |
| LAT-006 | Nginx edge/client network latency evidence |

각 drill은 expected PH10 classification, PH10 input scenario, manual boundary, success criteria, failure signals를 가진다.

## PH10 expected와 actual classification을 비교한 이유

PH11은 자체 root cause 판단을 만들지 않는다. PH10 analyzer를 classification source로 사용한다.

처음에는 report에 저장된 expected/actual 값만 비교하면 충분해 보였다. 하지만 누군가 둘 다 같은 잘못된 값으로 바꾸면 validator가 놓칠 수 있다.

그래서 validator는 `ph10_input_scenario`로 PH10 input evidence를 다시 만들고, PH10 analyzer를 재실행해 stored actual classification과 비교한다. PH11의 설득력은 stored value가 아니라 analyzer output과의 연결에서 나온다.

## consistency check를 latency drill에 포함한 이유

latency drill 중에도 duplicate ledger나 reconciliation failure가 나오면 그건 performance warning이 아니라 consistency incident candidate다.

PH11 report는 consistency counter를 포함하고, non-zero counter를 clean latency로 낮추는 표현을 validator가 거부한다.

## 구현 중 실제로 막은 오해

PH11 validator는 k6 단독 root-cause claim, destructive default command, missing Makefile target, expected/actual mismatch, analyzer recomputation mismatch, forbidden metric label, sensitive text pattern을 막는다.

또 LAT-004의 redis unavailable scenario와 LAT-005의 app HTTP client path scenario는 대표 row 외 추가 PH10 input scenario로 검증한다. table만 보고 하나의 classification만 고려했다고 오해하지 않게 문서에 경계를 남겼다.

## 검증한 것

대표 명령은 다음과 같다.

```bash
make ph11-latency-drill-demo
make ph11-latency-drill-validate
make ph11-latency-drill-list
make ph11-latency-check
```

unit test는 deterministic catalog, PH10 scenario classification, recomputed analyzer output validation, command boundary, consistency boundary, sensitive data policy를 확인한다.

## 숫자보다 evidence 흐름이 중요했다

PH11은 LAT-001~LAT-006 latency drill을 safe evidence runner로 묶고, PH10 analyzer expected/actual classification과 consistency check를 함께 검증한다.

production fault injection, DB lock holder, Redis down, network delay, mock partner, Toxiproxy/netem, OpenTelemetry full tracing을 모두 구현한 것은 아니다. 이 단계의 핵심은 latency 숫자를 만드는 것이 아니라 PH10 analyzer가 다시 읽을 수 있는 evidence 흐름을 고정하는 것이다.
