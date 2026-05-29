# 16편. Ansible로 금융 시스템 운영 작업 자동화하기

## 1. 문제를 어떻게 정의했는가

운영자가 서버에 접속해 매번 직접 명령을 실행하면 결과가 사람마다 달라질 수 있다.
배포, 백업, 로그 수집, rollback은 반복되는 작업이고, 반복되는 작업은 표준화되어야 한다.

Makefile은 로컬 명령을 묶는 데 유용하다.
하지만 여러 서버에 같은 상태를 적용하거나 idempotent하게 운영 작업을 실행하기에는 Ansible이 더 적합하다.

## 2. 자동화 대상

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

자동화 대상은 다음과 같다.

- Docker/Compose 설치 확인
- `.env` 필수 값 검증
- docker compose pull/up
- Nginx 설정 검증
- DB 백업 실행
- 최근 10분 로그 수집
- API/Redis/Nginx 순서 재시작
- Blue-Green rollback

## 3. idempotent playbook이 중요한 이유

운영 자동화의 핵심은 명령을 줄이는 것이 아니라, 같은 작업을 누가 실행해도 같은 결과가 나오게 하는 것이다.
같은 playbook을 두 번 실행했을 때 두 번째 실행에서 불필요한 변경이 없어야 한다.

이 기준이 없으면 자동화가 오히려 위험해진다.
배포 playbook을 다시 실행했을 뿐인데 서비스가 재시작되거나 config가 불필요하게 바뀌면, 운영자는 자동화를 신뢰하기 어렵다.

## 4. Makefile과 Ansible의 역할 차이

Makefile은 개발자 로컬 명령의 진입점이다.

```bash
make deploy-status
make deploy-smoke
make deploy-rollback
```

Ansible은 서버 상태를 맞추는 도구다.

```bash
make ansible-check
make ansible-deploy
make ansible-backup
make ansible-rollback
make ansible-collect-logs
```

둘을 경쟁 관계로 보지 않고, Makefile이 Ansible playbook 호출의 entrypoint가 되도록 설계한다.

## 5. 완료 기준

로컬 inventory 기준으로 다음 조건을 만족해야 한다.

- 첫 실행에서 필요한 변경만 수행
- 두 번째 실행에서 unnecessary change 없음
- 실패 시 어느 task에서 실패했는지 로그로 확인 가능
- rollback playbook은 DB rollback이 아니라 API traffic rollback만 수행

## 6. 남은 한계

단일 로컬 inventory는 실제 운영의 multi-host, 권한 분리, secret vault, bastion host 구조를 대체하지 못한다.
하지만 운영 명령을 사람이 암기하는 방식에서 playbook으로 표준화하는 첫 단계로 충분히 의미가 있다.

## 7. 실제 구현 후 보강할 내용

이 글은 Ops Phase 4 구현 전 설계 초안이다. 구현 후에는 다음 내용을 추가한다.

- `ansible-lint` 결과
- check mode 실행 결과
- 동일 playbook 2회 실행 시 두 번째 `changed=0` 확인
- collect-logs 산출물
- rollback playbook이 DB rollback이 아니라 traffic rollback만 수행하는지 확인한 결과
