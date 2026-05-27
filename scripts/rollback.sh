#!/bin/bash
# Rollback to previous version

set -e

echo "=== Rollback to Blue ==="

# 1. Switch traffic back to Blue
docker-compose exec nginx bash -c \
  "sed -i 's/api-green:8000/api-blue:8000/g' /etc/nginx/nginx.conf && \
   nginx -s reload"

echo "✅ Traffic switched to Blue"

# 2. Stop Green
docker-compose down api-green

echo "✅ Rollback completed"
