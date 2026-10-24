# CR-02 — Docker + Tailscale deployment

As the owner, I want the app running in one container reachable only on my tailnet over HTTPS, so that I can use it from all my devices safely.

## Acceptance tests
- **AT-C02.1** Given the container, `GET /api/health` returns ok and the port is bound to 127.0.0.1 only — Levels: integration, system

## Main files
- `Dockerfile`
- `docker-compose.yml`
- `docs/deployment.md`
