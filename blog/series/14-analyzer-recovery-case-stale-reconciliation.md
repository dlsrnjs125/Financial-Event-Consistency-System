# 장애를 찾았다고 바로 고치면 더 위험했다

장애 증거를 모으면 바로 복구하고 싶어진다. 하지만 금융 이벤트 시스템에서 자동 복구는 탐지보다 더 위험할 수 있다. 잘못된 보정은 새로운 정합성 사고가 된다.

## Analyzer는 복구 실행자가 아니다

PH3 analyzer는 sanitized artifact를 읽고 classification 후보를 만든다. 복구를 실행하지 않는다.

중요한 트러블슈팅은 `manifest.json` 누락이었다. 파일이 없다는 것은 민감정보가 포함됐다는 뜻이 아니다. 그래서 `ARTIFACT_SANITIZATION_RISK`가 아니라 `INSUFFICIENT_EVIDENCE`로 분리했다.

## Recovery Case는 자동 보정이 아니라 보류다

PH4는 analyzer result를 recovery case와 quarantine으로 연결한다. 하지만 analyzer result가 `sensitive_data_included=false`가 아니면 case 생성을 거부한다.

안전하지 않은 artifact를 DB에 오래 남기면 recovery case 자체가 유출 경로가 되기 때문이다.

## Stale PROCESSING은 자동 완료하지 않았다

오래 남은 `PROCESSING`은 애매하다. ledger가 이미 생성됐을 수도 있고, 아직 처리 중일 수도 있다.

막 생성된 processing event는 아직 ledger가 없을 수 있으므로 `transaction_event_without_ledger`를 바로 mismatch로 세면 오탐이 된다. 그래서 stale 기준을 분리하고 count-only reconciliation으로 evidence를 만든 뒤 recovery case로 넘겼다.

이 흐름의 핵심은 "찾았다"와 "고쳤다"를 분리하는 것이다.
