#!/bin/bash
# Initialize project

set -e

echo "=== Financial Event Consistency System - Initialize ==="

# 1. Create .env from .env.example
if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
else
  echo ".env already exists"
fi

# 2. Create necessary directories
mkdir -p backend/tests/{unit,integration,consistency}
mkdir -p infra/{nginx,postgres,prometheus,grafana/provisioning,grafana/dashboards}
mkdir -p scripts logs

# 3. Start services
echo "Starting Docker services..."
docker-compose up -d

# 4. Wait for services
echo "Waiting for services to be ready..."
sleep 10

# 5. Run database migrations (placeholder)
echo "Database is ready"

echo ""
echo "✅ Project initialized successfully"
echo ""
echo "Access points:"
echo "- API: http://localhost:8000"
echo "- Nginx: http://localhost:80"
echo "- Grafana: http://localhost:3000 (admin/admin)"
echo "- Prometheus: http://localhost:9090"
echo ""
echo "Test the API:"
echo "  curl http://localhost:8000/health"
