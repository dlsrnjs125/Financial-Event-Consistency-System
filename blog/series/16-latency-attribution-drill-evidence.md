# k6 p99가 튀었을 때 바로 DB 탓을 하면 안 되는 이유

k6 p95/p99는 사용자가 느낀 증상을 보여준다. 하지만 증상은 원인 확정이 아니다. 같은 p99 상승도 Nginx edge, FastAPI handler, Redis, PostgreSQL, outbound dependency, client network path 중 어디서든 생길 수 있다.

## p99 상승을 계층별 evidence로 나눴다

예를 들어 이런 경우는 application 내부보다 edge/client path를 먼저 의심한다.

```text
k6 p99 high
nginx request_time high
nginx upstream_time normal
fastapi handler normal
=> edge/client network latency candidate
```

반대로 DB 후보는 이런 형태에 가깝다.

```text
k6 p99 high
nginx upstream_time high
fastapi handler high
postgres phase dominant
=> PostgreSQL pool/lock/latency candidate
```

## latency drill은 숫자가 아니라 evidence를 만든다

PH11에서는 LAT-001~LAT-006 drill을 safe evidence runner로 묶었다. 기본 demo는 DB lock holder, Redis down, network delay 같은 destructive action을 실행하지 않는다.

대신 PH10 analyzer가 읽을 수 있는 input evidence를 만들고 expected classification과 actual classification을 비교한다.

처음에는 report에 저장된 expected/actual 값만 비교하면 충분해 보였다. 하지만 누군가 둘 다 같은 잘못된 값으로 바꾸면 validator가 속을 수 있다.

그래서 PH11 validator는 `ph10_input_scenario`로 evidence를 다시 만들고 PH10 analyzer를 재실행해 stored actual classification과 비교한다.

## consistency counter를 같이 본 이유

latency drill 중 duplicate ledger나 reconciliation failure가 나오면 performance warning이 아니라 consistency incident candidate다. 그래서 PH11 evidence에는 latency 숫자와 consistency counter를 함께 둔다.

결론은 간단하다. k6 p99는 출발점이고, root cause는 계층별 evidence와 consistency boundary를 함께 봐야 좁힐 수 있다.
