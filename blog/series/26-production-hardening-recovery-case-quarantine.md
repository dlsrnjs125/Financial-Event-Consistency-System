# 26. Recovery Case와 Quarantine: 자동 복구보다 먼저 필요한 수동 승인 경계

PH3까지는 장애 artifact를 수집하고 deterministic rule로 첫 분류를 만들었다.

PH4의 질문은 조금 다르다.

```text
정합성 위험 후보를 찾았을 때, 시스템이 바로 금전 상태를 고쳐도 되는가?
```

답은 아니다. 자동화는 evidence를 묶고 recovery case를 만들고 영향을 받은 대상을 격리하는 데까지가 적절하다. 원장 보정, write resume, 고객 영향 판단은 운영자 승인 경계를 넘어야 한다.

이번 단계에서는 `recovery_cases`와 `quarantine_records`를 추가했다. PH3 analyzer result는 `source_key` 기준으로 recovery case에 idempotent하게 등록된다. 같은 incident를 여러 번 ingestion해도 중복 case가 생기지 않는다.

Quarantine은 전체 write suspend보다 좁은 containment다. PH1의 전역 write suspend가 PostgreSQL write path 장애를 막는 큰 차단기라면, PH4의 account quarantine은 특정 대상에 대한 신규 금융 write를 멈추는 작은 차단기다.

중요한 제한도 남겼다. PH4는 compensation ledger를 생성하지 않고 account balance를 직접 수정하지 않는다. API도 조회 전용으로 열고, 승인/반려/해제는 CLI로 남겼다. 이는 운영자 승인 흐름과 감사 trail을 먼저 고정하기 위한 선택이다.

구현하면서 가장 조심한 지점은 민감 데이터였다. Recovery case에는 raw account number, raw Idempotency-Key, request body, HMAC signature, authorization header, secret을 저장하지 않는다. PH3 analyzer result가 `sensitive_data_included=false`가 아니면 case 생성 자체를 거부한다.

이제 시스템은 장애를 “분류했다”에서 끝나지 않고, “운영자가 승인해야 하는 복구 후보”로 보관할 수 있게 됐다.
