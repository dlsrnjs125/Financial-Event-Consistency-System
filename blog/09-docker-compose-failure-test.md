# 9편. Docker Compose 기반 장애 재현 환경 만들기

## 들어가며

지금까지 설계하고 구현하고 테스트했습니다.

이제 **실제 장애를 재현**해야 합니다.

이 편에서는 Docker Compose로 Redis, PostgreSQL, API, Nginx, Prometheus, Grafana를 한 번에 띄우고 장애를 시뮬레이션합니다.

---

## Docker Compose 구성

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: financial_events
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
  
  redis:
    image: redis:7
    ports:
      - "6379:6379"
  
  api:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://postgres:password@postgres:5432/financial_events
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
  
  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
  
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

---

## 장애 재현 시나리오

### 시나리오 1: Redis 다운
```bash
# Redis 컨테이너 중지
docker-compose pause redis

# k6 실행
k6 run tests/k6/duplicate-storm.js

# 검증: PostgreSQL 정합성 유지 확인
psql -c "SELECT COUNT(*) FROM ledger_entries WHERE account_id = 'ACC-001'"

# Redis 재시작
docker-compose unpause redis
```

### 시나리오 2: PostgreSQL 연결 풀 고갈
```bash
# Connection Pool 제한 설정
export DB_POOL_SIZE=5

docker-compose down
docker-compose up -d

# k6로 동시 요청 증가
k6 run tests/k6/peak-load.js

# 모니터링: Grafana에서 Connection 사용률 확인
```

### 시나리오 3: API 서버 재시작
```bash
# 부하 테스트 실행 중
k6 run tests/k6/sustained-load.js &

# API 컨테이너 강제 종료
docker-compose restart api

# 검증: 중복 거래 발생 여부 확인
```

---

## 다음 편에서

10편에서는 CI/CD에서 정합성 테스트를 배포 Gate로 사용하는 방법을 다룹니다.
