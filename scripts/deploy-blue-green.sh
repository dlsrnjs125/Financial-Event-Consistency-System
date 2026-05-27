#!/bin/bash
# Deploy Blue-Green

set -e

BLUE_VERSION=$(docker ps --filter "name=api-blue" --format '{{.Image}}')
GREEN_VERSION="financial-events:$(git rev-parse --short HEAD)"

echo "=== Blue-Green Deployment ==="
echo "Blue: $BLUE_VERSION"
echo "Green: $GREEN_VERSION"

# 1. Build Green image
docker build -t $GREEN_VERSION ./backend

# 2. Start Green container
docker-compose -f docker-compose.yml up -d api-green

# 3. Health check Green
echo "Waiting for Green health check..."
for i in {1..30}; do
  if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Green health check passed"
    break
  fi
  sleep 1
done

# 4. Run smoke test on Green
echo "Running smoke test on Green..."
k6 run tests/k6/smoke-test.js --vus 10 --duration 10s --out console || {
  echo "❌ Green smoke test failed, rolling back"
  docker-compose -f docker-compose.yml down api-green
  exit 1
}

# 5. Switch traffic (requires manual confirmation)
read -p "Switch traffic to Green? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  # Update nginx config to point to api-green
  docker-compose exec nginx bash -c \
    "sed -i 's/api-blue:8000/api-green:8000/g' /etc/nginx/nginx.conf && \
     nginx -s reload"
  
  echo "✅ Traffic switched to Green"
  
  # Monitor for 5 minutes
  echo "Monitoring for 5 minutes..."
  sleep 300
  
  # Remove Blue
  docker-compose -f docker-compose.yml down api-blue
  echo "✅ Deployment completed"
else
  echo "Deployment cancelled"
  docker-compose -f docker-compose.yml down api-green
fi
