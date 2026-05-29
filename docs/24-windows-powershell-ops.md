# Ops Phase 5 - Windows/PowerShell Operator Scripts

## 1. 해결하려는 운영 문제

서버는 Linux/Docker 기반이어도 운영자 단말은 Windows일 수 있다.

운영자가 매번 SSH로 서버에 들어가지 않고도 API health, readiness, metrics, incident snapshot을 확인할 수 있어야 한다.

Ops Phase 5는 Windows 운영자 워크스테이션에서 실행 가능한 PowerShell 점검 스크립트를 설계한다.

## 2. 구현 범위

- `/health` 점검
- `/ready` 점검
- 주요 metric key 존재 여부 확인
- Redis degraded 상태 감지
- incident snapshot JSON 저장
- trace_id/request_id 출력

## 3. 제외 범위

- Windows Server에 서비스를 직접 배포하는 작업은 제외한다.
- RDP/VDI 운영 환경 구성은 제외한다.
- PowerShell로 DB 복구나 rollback을 직접 수행하지 않는다.
- 운영 secret 다운로드 기능은 제외한다.

## 4. 파일/디렉터리 변경 계획

```text
scripts/
  powershell/
    Invoke-HealthCheck.ps1
    Invoke-ReadinessCheck.ps1
    Invoke-MetricsCheck.ps1
    Invoke-BackupDownload.ps1
    Invoke-IncidentSnapshot.ps1

reports/
  incidents/
    incident-snapshot-YYYYMMDD-HHMMSS.json
```

## 5. 검증 명령어

```powershell
pwsh scripts/powershell/Invoke-HealthCheck.ps1 -BaseUrl http://localhost:8080
pwsh scripts/powershell/Invoke-ReadinessCheck.ps1 -BaseUrl http://localhost:8080
pwsh scripts/powershell/Invoke-IncidentSnapshot.ps1 -BaseUrl http://localhost:8080 -Json
```

성공 기준:

- 정상 상태에서 exit code 0
- Redis down 상태에서 readiness degraded 감지
- incident snapshot JSON 파일 생성
- trace_id/request_id 출력
- 민감정보 출력 없음

## 6. 완료 기준과 README에 남길 결과

### 공통 파라미터

```powershell
param(
  [string]$BaseUrl = "http://localhost:8080",
  [string]$OutputDir = "./reports/incidents",
  [int]$TimeoutSec = 5,
  [switch]$Json
)
```

### Exit Code

| Exit Code | 의미 |
|---:|---|
| 0 | 정상 |
| 1 | API 응답 실패 |
| 2 | readiness degraded |
| 3 | metric 누락 |
| 4 | timeout |
| 5 | 인증/접근 거부 |

### Incident Snapshot 예시

```json
{
  "checked_at": "2026-05-29T02:30:00+09:00",
  "base_url": "http://localhost:8080",
  "health": {
    "status_code": 200,
    "latency_ms": 12
  },
  "ready": {
    "status_code": 200,
    "postgres": "up",
    "redis": "degraded"
  },
  "metrics": {
    "redis_fallback_total": 15,
    "db_retry_total": 3
  },
  "trace_id": "01JXXXXX"
}
```
