# Security Checklist

> 이 문서는 Ops Phase 7 Internal Network Security를 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 목적

운영 확장 단계에서 보안은 별도 기능이 아니라 배포 전 검증 Gate로 다뤄야 한다.

이 문서는 secret, dependency, container, script, Nginx, logging 관점의 보안 체크리스트를 정의한다.

## 2. CI 보안 Gate 후보

| Gate | 도구 후보 | 목적 |
|---|---|---|
| Secret Scan | gitleaks, detect-secrets, TruffleHog | credential leak 탐지 |
| Dependency Scan | pip-audit, safety | Python dependency 취약점 탐지 |
| Container Scan | Trivy | image vulnerability 탐지 |
| Python SAST | bandit | 위험한 Python 패턴 탐지 |
| Nginx Config Test | nginx -t | proxy 설정 오류 탐지 |
| Ansible Lint | ansible-lint | playbook 품질 검증 |
| Shell Lint | shellcheck | shell script 품질 검증 |
| PowerShell Lint | PSScriptAnalyzer | PowerShell script 품질 검증 |

## 3. Logging Checklist

- raw account number를 로그에 남기지 않는다.
- raw idempotency key를 로그에 남기지 않는다.
- HMAC signature를 로그에 남기지 않는다.
- client secret을 로그에 남기지 않는다.
- raw request body를 운영 로그에 남기지 않는다.
- trace_id/request_id는 로그 correlation 목적으로 허용한다.

## 4. Metrics Checklist

- Prometheus label에 account number를 넣지 않는다.
- Prometheus label에 idempotency key를 넣지 않는다.
- Prometheus label에 event_id/request_id를 넣지 않는다.
- route label에는 동적 path parameter를 raw로 넣지 않는다.
- partner_id가 고카디널리티라면 raw label로 사용하지 않는다.

## 5. Backup Security Checklist

- 백업 파일은 암호화한다.
- 백업 파일명에 개인정보나 계좌번호를 넣지 않는다.
- metadata에 secret을 넣지 않는다.
- restore DB는 외부 포트를 열지 않는다.
- checksum과 restore 검증 결과를 기록한다.
- 삭제는 dry-run 후 수행한다.

## 6. Docker Compose Hardening Checklist

- 가능한 서비스는 `no-new-privileges`를 적용한다.
- 가능한 서비스는 `cap_drop: ALL`을 적용한다.
- read-only filesystem 적용 가능 여부를 서비스별로 검토한다.
- container user를 root가 아닌 UID로 실행 가능한지 확인한다.
- tmpfs가 필요한 경로를 명시한다.

## 7. 완료 기준

배포 전 정합성 테스트뿐 아니라 secret leak, dependency vulnerability, container image vulnerability,
shell/ansible/powershell script 품질 검사를 별도 Gate로 분리한다.
