# Windows/PowerShell Operator Scripts

## 1. 목적

서버는 Linux/Docker 기반이어도 운영자 단말은 Windows일 수 있다. Windows 운영자 워크스테이션에서 API 상태, readiness, metrics, incident snapshot을 확인할 수 있도록 PowerShell 점검 스크립트를 설계한다.

## 2. 스크립트 구조

```text
scripts/powershell/
  Invoke-HealthCheck.ps1
  Invoke-ReadinessCheck.ps1
  Invoke-MetricsCheck.ps1
  Invoke-BackupDownload.ps1
  Invoke-IncidentSnapshot.ps1
```

## 3. 역할

| 스크립트 | 역할 |
|---|---|
| `Invoke-HealthCheck.ps1` | `/health`, `/ready` 호출 |
| `Invoke-ReadinessCheck.ps1` | PostgreSQL/Redis degraded 상태 확인 |
| `Invoke-MetricsCheck.ps1` | 주요 metric key 존재 여부 확인 |
| `Invoke-IncidentSnapshot.ps1` | 장애 시 응답, 시간, trace_id 저장 |
| `Invoke-BackupDownload.ps1` | 백업 파일 목록 확인과 다운로드 시뮬레이션 |

## 4. 예시 출력

```text
[OK] API health: 200
[OK] Ready status: postgres=up, redis=degraded
[WARN] Redis fallback count increased: 15
[OK] Trace ID returned: 01JXXXXX
```

## 5. README 요약 문장

실제 사내 운영 환경에서는 서버가 Linux 기반이더라도 운영자 단말은 Windows인 경우가 많다고 보고, PowerShell 기반 점검 스크립트를 추가한다. 이를 통해 Windows 운영자 워크스테이션에서도 API 상태, readiness, metrics, incident snapshot을 확인할 수 있도록 한다.
