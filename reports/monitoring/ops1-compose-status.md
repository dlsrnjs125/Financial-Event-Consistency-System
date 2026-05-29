# Ops Phase 1 Docker Compose Status

- Date: 2026-05-29T19:22:24Z
- Git Commit: e2b36fe
- Branch: feature/ops1-infra-metrics-extension

```text
NAME                          IMAGE                                           COMMAND                  SERVICE             CREATED         STATUS                   PORTS
financial-api-blue            financial-event-consistency-system-api-blue     "sh -c 'uvicorn app.…"   api-blue            6 minutes ago   Up 6 minutes (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
financial-cadvisor            gcr.io/cadvisor/cadvisor:v0.49.1                "/usr/bin/cadvisor -…"   cadvisor            6 minutes ago   Up 6 minutes (healthy)   127.0.0.1:8081->8080/tcp
financial-grafana             grafana/grafana:latest                          "/run.sh"                grafana             2 minutes ago   Up 2 minutes             127.0.0.1:3000->3000/tcp
financial-nginx               nginx:alpine                                    "/docker-entrypoint.…"   nginx               6 minutes ago   Up 6 minutes             0.0.0.0:443->443/tcp, [::]:443->443/tcp, 0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
financial-node-exporter       prom/node-exporter:v1.8.2                       "/bin/node_exporter …"   node-exporter       6 minutes ago   Up 6 minutes             127.0.0.1:9100->9100/tcp
financial-postgres            postgres:15-alpine                              "docker-entrypoint.s…"   postgres            6 minutes ago   Up 6 minutes (healthy)   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
financial-postgres-exporter   prometheuscommunity/postgres-exporter:v0.15.0   "/bin/postgres_expor…"   postgres-exporter   6 minutes ago   Up 6 minutes             9187/tcp
financial-prometheus          prom/prometheus:latest                          "/bin/prometheus --c…"   prometheus          2 minutes ago   Up 2 minutes             127.0.0.1:9090->9090/tcp
financial-redis               redis:7-alpine                                  "docker-entrypoint.s…"   redis               6 minutes ago   Up 6 minutes (healthy)   0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
financial-redis-exporter      oliver006/redis_exporter:v1.62.0                "/redis_exporter --r…"   redis-exporter      6 minutes ago   Up 6 minutes             9121/tcp
```
