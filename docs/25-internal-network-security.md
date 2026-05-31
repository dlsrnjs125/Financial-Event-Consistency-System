# Ops Phase 7 Supporting - Internal Network & Secure Admin Access

> 이 문서는 Ops Phase 7 Internal Network Security를 보완하기 위한 supporting document입니다.
> 별도의 추가 Ops Phase가 아닙니다.

## 1. 해결하려는 운영 문제

모든 endpoint를 같은 방식으로 열어두면 운영은 편해 보일 수 있다.
하지만 `/metrics`, `/ready`, `/admin/reconciliation` 같은 endpoint는 내부 상태와 장애 정보를 노출할 수 있다.

이 문서는 NAC/VPN/DLP 솔루션 자체를 구현하기보다, 금융 사내망 운영 관점에서 어떤 endpoint를 어떤 주체에게 열어야 하는지 정의한다.

## 2. 구현 범위

- public/internal endpoint 접근 정책 정의
- metrics endpoint private access 설계
- admin endpoint IP allowlist + admin token 설계
- 감사 로그 필드 정의
- 로그 마스킹/DLP 기준 정리

## 3. 제외 범위

- 실제 NAC/VPN/DLP 솔루션 구축은 하지 않는다.
- VMware Horizon/VDI 인프라는 직접 구축하지 않는다.
- Kubernetes NetworkPolicy 구성은 제외한다.
- 관리자 권한 모델의 상세 RBAC 구현은 별도 Phase로 분리한다.

## 4. 파일/디렉터리 변경 계획

```text
infra/
  nginx/
    conf.d/
      internal-admin.conf
      metrics-access.conf

docs/
  25-internal-network-security.md

scripts/
  security/
    check-access-matrix.sh
    check-admin-audit-log.sh
```

## 5. 검증 명령어

```bash
make access-matrix-test
make metrics-private-test
make admin-audit-log-test
make log-masking-test
```

성공 기준:

- public zone에서 `/metrics` 접근 차단
- monitoring zone에서 `/metrics` 접근 허용
- internal ops zone에서 `/admin/*` 접근 허용
- admin audit log에 필수 필드 기록
- raw token, HMAC secret, raw account number 미기록

## 6. 완료 기준과 README에 남길 결과

### Network Zone

| Zone | 주체 | 접근 가능 대상 |
|---|---|---|
| Public Zone | 외부 금융사 | `POST /api/v1/transaction-events` |
| Internal Ops Zone | 운영자/VPN | `/ready`, `/admin/*` |
| Monitoring Zone | Prometheus/Grafana | `/metrics`, exporter |
| App Private Zone | API 서버 | DB, Redis |
| Data Zone | PostgreSQL | API에서만 접근 |

### Endpoint 접근 매트릭스

| Endpoint | Public | Internal Ops | Monitoring | App |
|---|---|---|---|---|
| `/api/v1/transaction-events` | 허용 | 허용 | 차단 | 허용 |
| `/health` | 허용 | 허용 | 허용 | 허용 |
| `/ready` | 차단 | 허용 | 허용 | 허용 |
| `/metrics` | 차단 | 제한 | 허용 | 허용 |
| `/admin/reconciliation` | 차단 | 허용 | 차단 | 허용 |
| PostgreSQL | 차단 | 차단 | 제한 | 허용 |
| Redis | 차단 | 차단 | 제한 | 허용 |

### 감사 로그 필드

admin endpoint 호출 시 다음 값을 기록한다.

- timestamp
- operator_id 또는 admin_token_id
- source_ip
- request_id
- action
- result
- affected_resource

기록 금지:

- raw token
- HMAC secret
- account_no 원문
- request body 전체
