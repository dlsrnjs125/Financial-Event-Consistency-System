# 17편. Windows 운영자 단말에서 Linux/Docker 서비스를 점검하는 방법

## 1. 문제를 어떻게 정의했는가

서버는 Linux/Docker 기반이어도 운영자 단말은 Windows일 수 있다.
운영자가 매번 SSH로 서버에 들어가지 않고도 API health, readiness, metrics, incident snapshot을 확인할 수 있어야 한다.

그래서 PowerShell 기반 점검 스크립트를 Ops Phase 5로 설계했다.

## 2. 스크립트 구조

```text
scripts/powershell/
  Invoke-HealthCheck.ps1
  Invoke-ReadinessCheck.ps1
  Invoke-MetricsCheck.ps1
  Invoke-BackupDownload.ps1
  Invoke-IncidentSnapshot.ps1
```

## 3. Health와 readiness를 나누는 이유

`/health`는 API process가 살아 있는지 확인한다.
`/ready`는 PostgreSQL과 Redis dependency 상태를 확인한다.
두 endpoint를 섞으면 운영자가 잘못 판단할 수 있다.

예를 들어 Redis가 내려간 경우 API는 degraded mode로 계속 처리할 수 있다.

```text
[OK] API health: 200
[OK] Ready status: postgres=up, redis=degraded
[WARN] Redis fallback count increased: 15
```

반대로 PostgreSQL이 내려간 경우에는 정합성을 보장할 수 없으므로 readiness 실패로 봐야 한다.

## 4. incident snapshot

장애 순간에는 "나중에 보자"가 어렵다.
시간이 지나면 metric과 log context가 사라지거나 다른 이벤트와 섞인다.

`Invoke-IncidentSnapshot.ps1`은 장애 시점의 응답, timestamp, trace_id, readiness body, 주요 metric key를 파일로 저장하는 역할을 맡는다.

저장 대상은 다음처럼 제한한다.

- HTTP status
- response time
- trace_id/request_id
- readiness dependency 상태
- 주요 metric 값

raw request body, HMAC signature, client secret은 저장하지 않는다.

## 5. 완료 기준

Windows PowerShell에서 다음 스크립트를 실행할 수 있어야 한다.

```powershell
./Invoke-HealthCheck.ps1
./Invoke-ReadinessCheck.ps1
./Invoke-MetricsCheck.ps1
./Invoke-IncidentSnapshot.ps1
```

## 6. 남은 한계

PowerShell 스크립트는 운영자 점검 편의를 위한 보조 도구다.
서버 내부 조치, DB 복구, Blue-Green rollback은 여전히 서버 운영 명령과 자동화 도구에서 수행해야 한다.

## 7. 실제 구현 후 보강할 내용

이 글은 Ops Phase 5 구현 전 설계 초안이다. 구현 후에는 다음 내용을 추가한다.

- PowerShell 정상 실행 결과
- Redis down 상태에서 degraded exit code 확인
- incident snapshot JSON 예시
- trace_id/request_id 출력 결과
- 민감정보가 출력되지 않는지 확인한 결과
