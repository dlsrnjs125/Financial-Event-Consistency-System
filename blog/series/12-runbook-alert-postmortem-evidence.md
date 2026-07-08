# 장애를 복구했다는 말만으로는 부족했다

장애 대응은 "복구했다"는 말로 끝나지 않는다. 언제 감지했고, 어떤 기준으로 severity를 정했고, 어떤 조치를 했고, 어떤 evidence로 종료했는지가 남아야 한다.

## Runbook은 명령 목록이 아니라 판단 순서다

Runbook에는 어떤 metric을 먼저 보고, 어떤 상태면 escalate하고, 어떤 작업은 사람이 승인해야 하는지 들어가야 한다.

Redis degraded와 PostgreSQL down은 대응이 다르다. consistency violation은 latency warning보다 먼저 다뤄야 한다. 이런 판단 순서가 없으면 장애 중 명령만 많아진다.

## Alert와 Postmortem을 연결했다

Alert rule은 runbook으로 연결되고, incident timeline은 postmortem으로 이어진다. 장애 대응의 핵심은 "어떤 증거를 보고 어떤 결정을 했는가"를 나중에 재현할 수 있게 하는 것이다.

## CI와 로컬 drill을 분리한 이유

처음에는 CI에서도 Redis stop/start 기반 incident drill을 실행하고 싶었다. 하지만 GitHub Actions 환경에서 Docker Compose stop/start는 flaky할 수 있다.

그래서 CI는 script 실행 가능성, report 형식, 필수 문구를 검증하고, 실제 Redis stop/start drill은 로컬 Docker Compose evidence로 남겼다.

```text
CI: deterministic validation
Local Docker Compose: failure drill evidence
```

장애 대응도 테스트처럼 재현 가능해야 하지만, 모든 재현을 CI에서 무리하게 실행할 필요는 없었다.
