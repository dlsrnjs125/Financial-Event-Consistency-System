# Threat Model

## 1. 목적

보안 설계는 어떤 기술을 사용했는지보다 어떤 위협을 막으려는지부터 정의해야 한다.

이 문서는 금융 이벤트 처리 시스템에서 예상하는 공격/사고 시나리오와 대응 설계를 정리한다.

## 2. 위협 모델

| 위협 | 공격/사고 시나리오 | 대응 설계 |
|---|---|---|
| Replay Attack | 과거 정상 요청을 재전송 | HMAC + timestamp + idempotency key |
| Forged Event | 외부인이 거래 이벤트 위조 | HMAC secret, partner/client id 검증 |
| Duplicate Event | timeout 후 같은 이벤트 반복 수신 | idempotency key + DB unique constraint |
| Unauthorized Admin Access | 외부에서 `/admin/*` 접근 | IP allowlist + admin token + audit log |
| Metrics Exposure | `/metrics`로 내부 구조 노출 | 내부망/Prometheus network만 허용 |
| Log Leakage | 계좌번호/서명/토큰 로그 유출 | masking, raw body 저장 금지 |
| Backup Leakage | 백업 파일 외부 유출 | 암호화, checksum, 접근 권한 제한 |
| Secret Leakage | `.env`, HMAC secret 노출 | secret scan, Git ignore, rotation 정책 |

## 3. 로그에 남기는 값과 남기지 않는 값

운영 로그는 장애 추적 도구지만 민감정보 저장소가 되어서는 안 된다.

남길 수 있는 값:

- trace_id
- request_id
- event_id
- masked account number
- masked 또는 hashed idempotency key
- status
- dependency
- result

남기지 않는 값:

- raw account number
- raw idempotency key
- HMAC signature
- client secret
- authorization header
- raw request body

## 4. Metrics 노출 통제

`/metrics`는 단순 상태 페이지가 아니다.
내부 endpoint, job 이름, dependency 상태, 버전 정보가 노출될 수 있다.

Metric label 금지:

- account_no
- user_id
- raw idempotency_key
- raw external_event_id
- 고카디널리티 partner_id
- 동적 ID가 포함된 request path

Prometheus/Grafana 설계에서는 고카디널리티 label을 금지한다.
이는 운영 비용과 모니터링 장애 가능성에 직접 연결된다.

## 5. Docker Compose 보안 하드닝 후보

| 서비스 | 하드닝 적용 | 이유 |
|---|---|---|
| API | 가능 | 파일 쓰기 최소화 |
| Nginx | 부분 가능 | cache/temp path 확인 필요 |
| PostgreSQL | 제한적 | 데이터 디렉터리 write 필요 |
| Redis | 제한적 | appendonly 설정 여부 확인 필요 |
| Exporter | 가능 | read-only 성격 |

하드닝 옵션 후보:

```yaml
security_opt:
  - no-new-privileges:true
read_only: true
cap_drop:
  - ALL
user: "1000:1000"
tmpfs:
  - /tmp
```

## 6. CI 보안 Gate 후보

- Secret Scan: gitleaks 또는 detect-secrets
- Dependency Scan: pip-audit 또는 safety
- Container Scan: Trivy
- Python SAST: bandit
- Nginx config test: `nginx -t`
- Ansible lint: ansible-lint
- Shell script lint: shellcheck
- PowerShell lint: PSScriptAnalyzer

Secret scan은 구조화 로그 검사와 역할이 다르다.
secret scan은 repository credential 유출을 찾고, security-log-check는 운영 코드의 raw sensitive logging을 막는다.
