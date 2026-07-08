# k6 Latency Drill을 PH10 Analyzer와 연결한 이유

## 1. 문제

p95/p99를 올리는 k6 테스트는 만들 수 있다.
하지만 그 숫자만으로 DB, Redis, Nginx, 외부 dependency 원인을 확정할 수는 없다.

또 DB lock, Redis down, network delay 같은 drill을 기본 자동 실행에 넣으면 로컬 환경과 운영 안전성을 해칠 수 있다.

## 2. 처음에 의심한 방식

- k6-latency target을 전부 만들면 충분한가?
- DB lock holder와 Redis down을 default demo에 넣어도 되는가?
- mock partner가 실제 외부사 장애를 완전히 대체할 수 있는가?
- PH10 expected classification과 actual classification을 비교하지 않아도 되는가?

## 3. 선택한 방식

PH11에서는 LAT-001~LAT-006 drill catalog를 만들고, default demo와 manual/opt-in drill boundary를 분리했다.

기본 demo는 synthetic evidence와 PH10 input evidence만 만든다.
PH10 analyzer가 실제 classification을 계산하고, PH11 report는 expected classification과 actual classification을 비교한다.

## 4. 구현 중 트러블슈팅

k6 단독 root cause claim을 막기 위해 validator에서 금지 문구를 검사했다.

DB lock, Redis down, network delay는 default command에 넣지 않고 manual/candidate command로 분리했다.

존재하지 않는 Makefile target이 실행 가능한 command처럼 보이지 않도록 default `commands`는 실제 target만 허용했다.

PH10 expected/actual classification mismatch는 validation error로 처리했다.

consistency violation은 latency warning으로 낮추지 않고 별도 incident candidate로 우선 처리했다.

metric label에는 `trace_id`, `request_id`, `event_id`, retry key, raw URL, account/customer identifier를 넣지 않도록 했다.

## 5. 검증

PH11 구현은 다음 산출물로 검증한다.

- deterministic drill catalog
- PH10 analyzer integration
- sample PH10 input evidence
- JSON/Markdown drill report
- validator
- unit test
- Makefile target
- docs/blog 정리

## 6. 결론

PH11의 핵심은 latency 숫자를 만드는 것이 아니다.

latency 증상과 서버 evidence, PH10 analyzer classification, consistency check를 함께 묶어 운영자가 원인 후보를 안전하게 좁힐 수 있는 drill evidence 흐름을 만드는 것이다.
