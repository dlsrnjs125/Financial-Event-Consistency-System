# 10편. CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법

## 들어가며

개발자들은 코드를 작성할 때 의도하지 않게 정합성을 깨는 코드를 만들 수 있습니다.

이 편에서는 **CI/CD에서 정합성 테스트를 배포 Gate**로 설정하여 이를 방지합니다.

---

## CI 파이프라인

```yaml
name: CI

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Lint
        run: flake8 backend/app

  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Unit Test
        run: pytest tests/unit -v

  integration-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v3
      - name: Integration Test
        run: pytest tests/integration -v

  consistency-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v3
      - name: Consistency Test
        run: pytest tests/consistency -v
      - name: Check Duplicate Prevention
        run: pytest tests/consistency/test_duplicate_storm.py -v

  migration-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
    steps:
      - uses: actions/checkout@v3
      - name: Migration Test
        run: alembic upgrade head

  docker-build-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Docker Build
        run: docker build -t financial-events:latest ./backend

  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Secret Scan
        uses: trufflesecurity/trufflehog@main
```

---

## 배포 Gate 체크리스트

### 필수 (FAIL 시 배포 차단)
- [ ] Lint 통과 (스타일 오류 0건)
- [ ] Unit Test 통과 (100%)
- [ ] State Machine Test 통과
- [ ] Idempotency Test 통과 (중복 반영 0건)
- [ ] Concurrency Test 통과
- [ ] Migration Test 통과
- [ ] Docker Build 성공
- [ ] Secret Scan 통과 (하드코딩된 Secret 0건)

### 권장 (경고만 표시)
- [ ] Coverage > 80%
- [ ] OpenAPI Schema 검증 통과

---

## 배포 전 확인

```bash
#!/bin/bash
# deploy-gate.sh

echo "=== Deployment Gate Check ==="

# 1. 정합성 테스트
pytest tests/consistency -v || exit 1

# 2. 100 동시 요청 테스트
pytest tests/consistency/test_100_concurrent_requests.py -v || exit 1

# 3. Redis 없이도 중복 방지
pytest tests/consistency/test_redis_down.py -v || exit 1

# 4. DB 정합성 검증
psql -f scripts/validate-consistency.sql || exit 1

echo "✅ All deployment gates passed!"
```

---

## 다음 편에서

11편에서는 Blue-Green 배포와 Rollback을 다룹니다.
