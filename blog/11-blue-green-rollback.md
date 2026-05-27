# 11편. Blue-Green 배포와 Rollback 시뮬레이션

## 들어가며

정합성 테스트를 통과했다면, 이제 **안전하게 배포**해야 합니다.

이 편에서는 Blue-Green 배포로 무중단 배포를 구현합니다.

---

## Blue-Green 구조

```
Nginx (Port 80)
  ├─ /api → api-blue:8000 (현재 운영)
  └─ /api → api-green:8000 (신규 버전, 테스트 중)
```

---

## 배포 흐름

### 1. Green 배포 및 테스트
```bash
# Green 컨테이너 시작
docker-compose up -d api-green

# Green 헬스 체크
curl http://localhost:8001/health

# Green 정합성 테스트 (100 동시 요청)
k6 run tests/k6/consistency-test.js --out console
```

### 2. Nginx 트래픽 전환
```bash
# Nginx upstream 변경 (Blue → Green)
sed -i 's/api-blue:8000/api-green:8000/g' /etc/nginx/nginx.conf
nginx -s reload
```

### 3. 모니터링 (5분)
```
- Error Rate 모니터링
- Response Time 모니터링
- Duplicate Event 수 모니터링
```

### 4. Rollback (문제 발생 시)
```bash
# 트래픽 원복 (Green → Blue)
sed -i 's/api-green:8000/api-blue:8000/g' /etc/nginx/nginx.conf
nginx -s reload

# Green 컨테이너 중지
docker-compose stop api-green
```

---

## 배포 스크립트

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

BLUE_VERSION=$(docker ps --filter "name=api-blue" --format '{{.Image}}')
GREEN_VERSION="financial-events:$CI_COMMIT_SHA"

echo "=== Blue-Green Deployment ==="
echo "Blue: $BLUE_VERSION"
echo "Green: $GREEN_VERSION"

# 1. Green 배포
docker build -t $GREEN_VERSION ./backend
docker-compose -f docker-compose.green.yml up -d

# 2. 헬스 체크
for i in {1..30}; do
  if curl -f http://localhost:8001/health > /dev/null; then
    echo "✅ Green health check passed"
    break
  fi
  sleep 1
done

# 3. 정합성 테스트
pytest tests/consistency/test_100_concurrent_requests.py \
  --api-url=http://localhost:8001 -v || {
  echo "❌ Green consistency test failed, rolling back"
  docker-compose -f docker-compose.green.yml down
  exit 1
}

# 4. 트래픽 전환
docker-compose exec nginx bash -c \
  "sed -i 's/api-blue:8000/api-green:8000/g' /etc/nginx/nginx.conf && \
   nginx -s reload"

echo "✅ Traffic switched to Green"

# 5. 모니터링 (5분)
sleep 300

# 6. 이전 Blue 제거
docker-compose -f docker-compose.blue.yml down

echo "✅ Deployment completed"
```

---

## Rollback 스크립트

```bash
#!/bin/bash
# scripts/rollback.sh

echo "=== Rolling back to Blue ==="

docker-compose exec nginx bash -c \
  "sed -i 's/api-green:8000/api-blue:8000/g' /etc/nginx/nginx.conf && \
   nginx -s reload"

docker-compose -f docker-compose.green.yml down

echo "✅ Rollback completed"
```

---

## 다음 편에서

12편에서는 프로젝트 전체 회고와 배운 점을 정리합니다.
