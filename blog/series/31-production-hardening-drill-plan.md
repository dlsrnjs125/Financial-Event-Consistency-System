# Production Hardening 기능을 하나의 Drill Plan으로 묶은 이유

## 1. 문제

PH1~PH8에서는 PostgreSQL write suspend, incident artifact, incident analyzer, recovery case, stale reconciliation, AI-safe context, HMAC rotation, HA/Queue ADR을 각각 만들었다.

하지만 실제 운영에서는 기능이 개별적으로 존재하는 것만으로는 부족하다. 장애가 났을 때 중요한 것은 어떤 순서로 검증하고, 어떤 증거를 남기고, 어디부터 사람이 승인해야 하는지를 명확히 아는 것이다.

특히 이 프로젝트의 기준은 PostgreSQL이 최종 Source of Truth라는 점이다. Redis는 보조 계층이고, PostgreSQL write path가 불가능하면 신규 금융 write는 성공 처리하지 않는다.

## 2. 처음에 의심한 방식

처음에는 모든 hardening drill을 `make` target으로 한 번에 실행하면 충분하지 않을까 생각했다.

하지만 곧 문제가 보였다.

- DB down drill은 로컬 PostgreSQL을 멈출 수 있다.
- write resume은 자동 승인하면 안 된다.
- recovery case와 quarantine은 금전 상태 변경 전 수동 검토가 필요하다.
- partner key retirement도 사람이 승인해야 한다.
- latency attribution은 아직 PH10/PH11 후보이지 PH9 완료 기능이 아니다.

즉 PH9에서 해야 할 일은 모든 것을 자동 실행하는 것이 아니라, 안전하게 실행 가능한 것과 수동 승인 경계를 분리하는 것이었다.

## 3. 선택한 방식

PH9에서는 production hardening drill catalog를 만들었다.

각 drill은 다음 정보를 가진다.

- phase와 drill id
- 목적
- 연결 문서
- safe auto-run 여부
- manual run 필요 여부
- Docker, k6, database 필요 여부
- 실제 존재하는 Makefile command
- expected evidence
- safety boundary
- manual approval boundary
- success criteria
- failure signals
- sensitive data policy

기본 demo는 JSON/Markdown report만 생성한다. DB down, write resume, failover, recovery approval 같은 작업은 default command가 아니라 manual boundary나 candidate command로 남긴다.

## 4. 구현 중 트러블슈팅

### 자동화 범위가 과도해지는 문제

모든 drill을 catalog에 넣으면 전부 자동 실행 가능한 것처럼 보일 수 있다.

그래서 `safe_to_auto_run`, `manual_run_required`, `manual_approval_required_for`를 분리했다. validator는 safe auto-run drill에 write resume, failover promote, ledger correction 같은 승인 작업이 들어가면 실패한다.

### 존재하지 않는 target을 실행 가능한 명령처럼 쓰는 문제

report의 `commands`에 아직 없는 Makefile target을 넣으면, 구현된 evidence처럼 보일 수 있다.

그래서 validator가 Makefile target 존재 여부를 확인한다. 아직 후보인 latency 명령은 completed command가 아니라 follow-up candidate로만 둔다.

### PH10/PH11 후보를 PH9 완료처럼 보이게 하는 문제

PH9는 latency attribution 구현이 아니다.

docs/41과 docs/42는 PH10/PH11 후보로 연결하지만, PH9 report의 completed drill에는 넣지 않는다. validator도 PH10/PH11이 drill 목록에 들어오면 실패한다.

### AI-safe context와 AI 복구 실행을 혼동하는 문제

PH6의 AI-safe context는 분석용 context 생성이지 복구 실행 권한이 아니다.

PH9 validator는 AI가 자동 복구 실행자처럼 표현되는 문장을 금지한다. 금전 상태 변경, write resume, recovery adoption은 사람이 승인한다.

### README에 drill catalog를 길게 넣는 문제

PH9는 PH1~PH8을 모두 묶기 때문에 README에 전체 catalog를 넣으면 너무 길어진다.

README에는 한 문장 요약, 대표 명령, docs 링크만 넣고, 자세한 내용은 `docs/51-ph9-production-hardening-drill-plan.md`와 generated report에 둔다.

## 5. 검증

PH9 검증은 다음 흐름으로 구성했다.

- deterministic catalog generator
- JSON/Markdown sample report
- report validator
- unit test
- Makefile target
- `security-log-check`
- docs/blog 정리

대표 명령:

```bash
make ph9-hardening-drill-demo
make ph9-hardening-drill-validate
make ph9-hardening-drill-list
make ph9-hardening-check
```

## 6. 결론

PH9의 핵심은 새로운 장애 복구 기능을 추가하는 것이 아니다.

이미 만든 production hardening 산출물을 운영 drill 관점에서 재현 가능하게 묶고, 자동화 가능한 검증과 사람이 승인해야 하는 작업의 경계를 명확히 하는 것이다.

이렇게 해두면 포트폴리오 관점에서도 “장애 대응 기능을 만들었다”에서 한 단계 더 나아가, “장애 대응 기능을 어떤 기준으로 검증하고 운영할지까지 설계했다”는 evidence가 남는다.
