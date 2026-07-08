# Production Hardening 기능을 하나의 Drill Plan으로 묶은 이유

PH1~PH8에서는 write suspend, incident artifact, incident analyzer, recovery case, stale reconciliation, AI-safe context, HMAC rotation, HA/Queue ADR을 각각 만들었다. 하지만 기능이 많아질수록 운영자는 다른 질문을 하게 된다.

```text
장애가 났을 때 무엇부터 검증하고, 무엇은 자동 실행하면 안 되는가?
```

## 기능이 많아질수록 검증 순서가 더 중요해진다

각 기능이 따로 존재하는 것만으로는 부족하다. 운영자는 어떤 evidence를 먼저 보고, 어떤 command를 실행할 수 있고, 어디서 사람 승인이 필요한지 알아야 한다.

PH9는 새 복구 기능을 추가하지 않았다. 이미 만든 hardening 산출물을 drill catalog로 묶고, 자동화 가능한 검증과 manual boundary를 정리했다.

## 모든 drill을 자동 실행하면 생기는 위험

처음에는 hardening drill을 `make` target으로 한 번에 묶으면 충분해 보였다. 하지만 곧 문제가 보였다.

- DB down drill은 로컬 PostgreSQL을 멈출 수 있다.
- write resume은 자동 승인하면 안 된다.
- recovery case 실행과 quarantine release는 수동 검토가 필요하다.
- partner key retirement도 사람이 승인해야 한다.
- latency attribution은 PH10/PH11 단계와 경계가 있다.

그래서 PH9의 기본 demo는 JSON/Markdown report 생성과 validation에 머문다.

## safe auto-run과 manual approval boundary를 나눈 이유

PH9 drill row에는 `safe_to_auto_run`, `manual_run_required`, `manual_approval_required_for`, `commands`, `candidate_commands`가 분리되어 있다.

default `commands`는 실제 Makefile target이어야 하고, destructive/manual action은 들어갈 수 없다. 후보 command는 operator가 문서를 읽고 승인한 뒤 실행해야 하는 것으로 남긴다.

## Safety Notes를 report에 남긴 이유

generated Markdown report에는 네 가지 오해 방지 문장을 넣었다.

- PH9는 destructive drill을 기본 실행하지 않는다.
- PH10/PH11 latency work는 follow-up candidate다.
- AI-safe context는 복구 실행 권한이 아니다.
- queue-first architecture는 `ACCEPTED`와 `COMPLETED`를 분리해야 한다.

README에는 이 전체 catalog를 넣지 않았다. README는 포트폴리오 첫 화면이고, full catalog는 docs와 reports가 담당한다.

## 구현 중 실제로 고친 부분

candidate command와 default command가 섞이면 report가 실행 가능한 evidence처럼 보일 수 있었다. 그래서 default `commands`는 Makefile target 존재 여부를 검증하고, 아직 없는 target은 candidate로 분리했다.

또 PH10/PH11 latency work가 PH9 완료 항목처럼 보이지 않게 follow-up candidate로만 남겼다. PH9는 latency analyzer 구현 단계가 아니라 hardening drill catalog 단계다.

## 검증한 것

PH9는 deterministic catalog generator, JSON/Markdown sample report, validator, unit test, Makefile target으로 검증한다.

```bash
make ph9-hardening-drill-demo
make ph9-hardening-drill-validate
make ph9-hardening-drill-list
make ph9-hardening-check
```

validator는 destructive command, missing Makefile target, PH10/PH11 completed claim, AI recovery executor claim, queue completion guarantee claim을 막는다.

## 이 글에서 말할 수 있는 것과 말하면 안 되는 것

말할 수 있는 것은 PH9가 PH1~PH8 산출물을 운영 drill catalog로 묶고, safe auto-run과 manual approval boundary를 분리했다는 점이다.

말하면 안 되는 것은 PH9가 DB down, failover promote, write resume, recovery execution, latency fault injection을 모두 자동 실행한다는 주장이다.
