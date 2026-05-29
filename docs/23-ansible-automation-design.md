# Ansible Operation Automation Design

## 1. 목적

운영자가 수동으로 서버에 접속해 명령을 실행하는 방식은 재현성과 감사 가능성이 낮다. 반복되는 서버 설정, 배포, 백업, 로그 수집, rollback 작업을 Ansible playbook으로 표준화한다.

## 2. 구조

```text
infra/ansible/
  inventory.ini
  playbooks/
    setup-server.yml
    deploy-compose.yml
    backup-db.yml
    restart-service.yml
    collect-logs.yml
    rollback.yml
  roles/
    docker/
    nginx/
    monitoring/
    app/
```

## 3. 자동화 대상

| 자동화 항목 | 설명 |
|---|---|
| Docker 설치 확인 | Docker/Compose 설치 여부 확인 |
| 환경 변수 배포 | `.env.example` 기준 필수 환경변수 검증 |
| Compose 배포 | `docker compose pull/up` 표준화 |
| Nginx 설정 검증 | `nginx -t` 실행 |
| DB 백업 실행 | `pg_backup.sh` 호출 |
| 로그 수집 | 최근 10분 API/Nginx/DB 로그 압축 |
| 장애 후 재시작 | API/Redis/Nginx 순서 재시작 |
| Rollback | Blue-Green upstream 전환 |

## 4. 명령 목표

```bash
make ansible-check
make ansible-deploy
make ansible-backup
make ansible-rollback
make ansible-collect-logs
```

## 5. 완료 기준

로컬 inventory 기준으로 playbook이 idempotent하게 동작해야 한다. 같은 playbook을 두 번 실행했을 때 두 번째 실행에서 불필요한 변경이 없어야 한다.

## 6. README 요약 문장

운영자가 수동으로 서버 접속 후 명령을 실행하는 방식은 재현성과 감사 가능성이 낮다고 판단했다. Docker Compose 배포, 백업, 로그 수집, rollback을 Ansible playbook으로 자동화해 반복 작업을 표준화한다.
