# Sensitive Data, AI Governance, and Encryption Trade-off

> 실제 금융 데이터가 포함된 운영 evidence는 AI 분석에 그대로 전달하면 안 된다.
> 마스킹, Hash, HMAC, 암호화, Tokenization은 서로 다른 목적을 가진다.

## 1. 현재 마스킹/Hash 수준의 한계

현재 프로젝트는 로그에 raw account number, raw idempotency key, HMAC signature, raw request body를 남기지 않는 원칙을 가진다.
이 원칙은 운영 로그 유출 위험을 줄이지만, 저장 데이터 자체의 보호와 AI 분석 context 보호까지 자동으로 해결하지는 않는다.

한계:

- masking은 표시값을 줄이는 것이지 DB 저장값을 보호하는 암호화가 아니다.
- SHA-256 hash는 salt/key 없이 쓰면 사전 공격에 취약할 수 있다.
- HMAC은 인증/무결성 검증 또는 keyed lookup digest에 적합하지만 복호화할 수 없다.
- 암호화는 원문 보호에 필요하지만 lookup, rotation, key 관리 비용이 생긴다.
- AI 분석에는 raw incident data가 아니라 sanitized context가 필요하다.

## 2. Hash는 암호화가 아니다

Hash는 단방향 digest다.
복호화할 수 없으며, 작은 후보군을 가진 값에는 brute force 또는 dictionary attack 위험이 있다.

계좌번호처럼 형식과 범위가 예측 가능한 값은 plain SHA-256보다 key가 있는 HMAC lookup hash가 안전하다.

## 3. 데이터 분류 등급

| Level | 데이터 | AI 전달 기준 |
| --- | --- | --- |
| Level 0. 원본 민감 데이터 | 원문 계좌번호, 고객명, 전화번호, raw request body, HMAC signature, Authorization header, client secret | 금지 |
| Level 1. 마스킹 데이터 | masked account number, masked idempotency key | 제한적 사용 |
| Level 2. 가명/토큰 데이터 | account_token, event_token, idempotency_key_hash | AI 분석 기본 포맷 |
| Level 3. 집계 데이터 | p95/p99, error rate, duplicate count, Redis fallback count | 허용 |

AI 분석 기본 입력은 Level 2~3으로 제한한다.
Level 1은 장애 추적에 꼭 필요한 경우에만 포함한다.

## 4. AI에게 전달 가능한 데이터와 금지 데이터

전달 가능:

- sanitized incident report
- count-only consistency result
- masked structured logs
- Prometheus metric summary
- k6 summary
- runbook 초안
- postmortem 초안

전달 금지:

- 원문 계좌번호
- 원문 idempotency key
- HMAC signature
- Authorization header
- raw request body
- DB dump
- client secret
- 고객 식별정보
- 보정 SQL 최종 실행 권한

## 5. 마스킹, Hash, HMAC, 암호화, Tokenization 용도 분리

| 기술 | 목적 | 복호화 가능 | 주요 사용처 |
| --- | --- | --- | --- |
| Masking | 화면/로그/evidence 표시 최소화 | 아니오 | `ACC-****-1234`, masked idempotency key |
| SHA-256 Hash | 비밀이 아닌 단방향 무결성/동일성 확인 | 아니오 | request_hash, snapshot hash |
| HMAC Hash | secret key 기반 lookup digest | 아니오 | account lookup hash, idempotency key hash |
| Randomized AEAD Encryption | 원문 보호와 복호화 | 예 | account_no ciphertext |
| Deterministic Encryption | 암호문 equality lookup | 예 | 제한적, leakage trade-off 큼 |
| Tokenization | 운영/AI context에서 원문 대체 | mapping 보유 시 가능 | account_token, event_token |

## 6. 컬럼 암호화 설계 초안

```text
account_no_ciphertext      = randomized AEAD 암호화 값
account_no_lookup_hash     = HMAC-SHA256(account_no)
account_no_masked          = 로그/응답/evidence 표시용
encryption_key_version     = 복호화 key version
```

조회 흐름:

1. 입력 account number를 HMAC lookup hash로 변환한다.
2. `account_no_lookup_hash`로 account row를 찾는다.
3. 복호화가 필요한 내부 업무에서만 `account_no_ciphertext`를 복호화한다.
4. 로그와 report에는 `account_no_masked` 또는 token만 사용한다.

## 7. Key version / rotation 기준

| 항목 | 기준 |
| --- | --- |
| encryption_key_version | row마다 저장해 복호화 key 선택 가능 |
| active key | 신규 암호화에 사용 |
| legacy key | 기존 row 복호화에만 사용 |
| rotation trigger | secret leak, 정기 rotation, key age 초과 |
| rotation 방식 | read-reencrypt-write 또는 batch re-encryption |
| 승인 | 운영자/보안 담당자 승인 필요 |

Secret rotation은 HMAC authentication hardening과 연결된다.
Partner secret은 key id 또는 version을 포함해 rolling rotation을 지원하는 방향으로 설계한다.

## 8. 로그/백업/리포트/evidence 보호 기준

| 산출물 | 보호 기준 |
| --- | --- |
| structured log | raw body, raw key, signature, secret 금지 |
| Prometheus metric | 고카디널리티 ID와 민감 label 금지 |
| backup dump | git commit 금지, 접근 제한, checksum 기록 |
| incident report | sanitized context만 포함 |
| AI context | Level 2~3 중심, Level 0 금지 |
| screenshot evidence | 내부 IP/secret/account 노출 여부 검토 |

## 9. 자동화 가능한 검사와 수동 승인 영역

자동화 가능:

- raw key/account/signature 로그 패턴 검사
- metric label 고카디널리티/민감 label 검사
- AI context sanitizer 테스트
- secret scan
- report artifact 경로 gitignore 확인

수동 승인 필요:

- secret rotation 최종 실행
- key retirement
- DB dump 외부 반출
- AI 분석 예외 허용
- 고객/제휴사 영향도 공개 판단

## 10. README에 들어갈 요약 문장

```text
Production Hardening에서는 장애 분석 자동화와 AI 활용을 도입하더라도,
AI에는 원문 계좌번호, raw idempotency key, HMAC signature, raw request body, secret을 전달하지 않는다.
Incident Analyzer는 sanitized report를 생성하고, 금전 상태 변경과 write resume은 사람이 승인한다.
```

## 11. Trade-off

### 11.1 마스킹 vs 컬럼 암호화

- 선택한 정책: 로그/응답은 마스킹, 저장 원문 보호는 컬럼 암호화를 별도 검토한다.
- 대안: 마스킹만 적용한다.
- 선택 이유: 마스킹은 표시 보호이고 DB 유출 보호가 아니다.
- 포기한 것: 단순한 저장/조회 구조.
- 보완 전략: lookup hash와 ciphertext를 분리한다.
- 면접 답변용 한 문장: 마스킹은 로그 보호이고 암호화는 저장 데이터 보호라서, 두 기술을 대체 관계가 아니라 보완 관계로 나눴습니다.

### 11.2 SHA-256 Hash vs HMAC Hash

- 선택한 정책: request_hash는 canonical body hash, 민감 식별자 lookup은 HMAC hash를 사용한다.
- 대안: 모든 digest에 SHA-256만 사용한다.
- 선택 이유: 계좌번호처럼 후보군이 작은 값은 key 없는 hash가 취약하다.
- 포기한 것: key 관리가 없는 단순성.
- 보완 전략: HMAC key version과 rotation 정책을 둔다.
- 면접 답변용 한 문장: 민감 식별자 동일성 조회에는 plain hash보다 keyed HMAC digest가 적합합니다.

### 11.3 randomized encryption vs deterministic encryption

- 선택한 정책: 원문 보호는 randomized AEAD를 우선하고, 조회는 별도 HMAC lookup hash를 사용한다.
- 대안: deterministic encryption으로 equality lookup을 해결한다.
- 선택 이유: deterministic encryption은 같은 원문이 같은 암호문으로 드러나는 leakage가 있다.
- 포기한 것: 암호문 단독 equality lookup의 편의성.
- 보완 전략: `ciphertext`와 `lookup_hash` 컬럼을 분리한다.
- 면접 답변용 한 문장: 암호화는 randomized로 안전성을 높이고, 조회는 HMAC hash로 분리했습니다.

### 11.4 Tokenization vs 암호화

- 선택한 정책: AI/운영 context에는 token을 사용하고, 원문 보호는 암호화로 다룬다.
- 대안: 암호화 값만 모든 곳에 사용한다.
- 선택 이유: AI 분석에는 복호화 가능한 값 자체가 필요 없다.
- 포기한 것: 하나의 식별자만 쓰는 단순성.
- 보완 전략: token mapping 접근 권한을 별도로 제한한다.
- 면접 답변용 한 문장: AI 분석에는 복호화 가능한 암호문보다 원문과 분리된 token이 더 안전합니다.

### 11.5 pgcrypto vs KMS/Vault Transit

- 선택한 정책: 운영 환경에서는 KMS/Vault Transit 같은 외부 key 관리 후보를 우선 ADR로 검토한다.
- 대안: PostgreSQL `pgcrypto`로 DB 내부 암호화.
- 선택 이유: DB와 key를 같은 경계에 두면 DB 침해 시 방어 효과가 제한된다.
- 포기한 것: 로컬 구현의 단순성.
- 보완 전략: 로컬 PoC는 pgcrypto 가능, production 설계는 KMS/Vault 기준으로 분리한다.
- 면접 답변용 한 문장: pgcrypto는 PoC에는 편하지만 production에서는 key 관리 경계를 DB 밖으로 빼는 편이 안전합니다.

### 11.6 AI 자동 분석 vs 사람이 최종 검토

- 선택한 정책: AI는 sanitized report 요약과 초안 작성만 담당한다.
- 대안: AI가 복구 action을 직접 결정한다.
- 선택 이유: 금전 상태 변경과 고객 영향 판단은 책임 있는 승인 절차가 필요하다.
- 포기한 것: 완전 자동 복구.
- 보완 전략: rule-based analyzer 결과와 AI 초안을 운영자가 검토한다.
- 면접 답변용 한 문장: AI는 운영자를 돕는 report assistant로 두고, 원장 보정과 write resume은 사람이 승인하게 했습니다.
