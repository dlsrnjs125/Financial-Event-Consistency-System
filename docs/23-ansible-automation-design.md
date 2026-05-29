# Ops Phase 4 - Ansible Operation Automation

## 1. 해결하려는 운영 문제

운영자가 수동으로 서버에 접속해 명령을 실행하는 방식은 재현성과 감사 가능성이 낮다.

배포, 백업, 로그 수집, rollback은 반복되는 작업이고, 반복되는 작업은 표준화되어야 한다.

Ops Phase 4는 Docker Compose 운영 작업을 Ansible playbook으로 자동화한다.
같은 playbook을 반복 실행해도 불필요한 변경이 없는 idempotent 구조를 목표로 한다.

## 2. 구현 범위

- Docker/Compose 설치 확인
- `.env.example` 기준 필수 환경변수 검증
- docker compose pull/up
- Nginx 설정 검증
- DB 백업 스크립트 호출
- 최근 10분 로그 수집
- API/Redis/Nginx 순서 재시작
- Blue-Green traffic rollback

## 3. 제외 범위

- production inventory 실제 배포는 제외한다.
- Ansible Vault 기반 secret 관리 구성은 초기 범위에서 제외한다.
- Kubernetes module 기반 운영은 제외한다.
- DB rollback 자동화는 제외한다.

## 4. 파일/디렉터리 변경 계획

```text
infra/
  ansible/
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

reports/
  ansible/
    idempotency.log
    collect-logs-result.md
```

## 5. 검증 명령어

```bash
make ansible-lint
make ansible-check
make ansible-dry-run
make ansible-deploy
make ansible-idempotency-test
```

`ansible-idempotency-test` 기준:

```bash
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/playbooks/setup-server.yml
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/playbooks/setup-server.yml \
  | tee reports/ansible/idempotency.log
grep -q "changed=0" reports/ansible/idempotency.log
```

## 6. 완료 기준과 README에 남길 결과

### inventory 구조

```ini
[local]
localhost ansible_connection=local

[app]
financial-app ansible_host=127.0.0.1 ansible_user=ubuntu

[monitoring]
financial-monitoring ansible_host=127.0.0.1 ansible_user=ubuntu
```

### Playbook별 책임

| Playbook | 책임 | destructive 여부 |
|---|---|---|
| `setup-server.yml` | Docker/Nginx/디렉터리 준비 | No |
| `deploy-compose.yml` | compose pull/up | 조건부 |
| `backup-db.yml` | 백업 스크립트 실행 | No |
| `collect-logs.yml` | 로그 압축 수집 | No |
| `restart-service.yml` | 특정 서비스 재시작 | Yes, 명시 옵션 필요 |
| `rollback.yml` | Nginx upstream Blue/Green 전환 | Yes, 명시 옵션 필요 |

### 안전장치

- destructive task는 `--extra-vars confirm=true` 없으면 실패한다.
- production inventory는 기본값으로 실행할 수 없다.
- rollback은 DB rollback을 수행하지 않고 traffic rollback만 수행한다.
- secret 값은 playbook에 직접 작성하지 않는다.
- `.env`는 `.env.example` 기준 필수 키만 검증한다.

README에는 다음 결과를 남긴다.

- ansible-lint 통과
- check mode 통과
- 동일 playbook 2회 실행 시 두 번째 실행 `changed=0`
- rollback playbook은 traffic rollback만 수행
- collect-logs 실행 시 API/Nginx/DB 로그 압축 파일 생성
