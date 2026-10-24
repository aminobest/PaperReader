# Deployment (CR-02)

- One container, published on **127.0.0.1:7400 only** (`docker-compose.yml`).
- **Tailscale Serve** exposes it to the tailnet over HTTPS (not Funnel, not public):

```bash
cd /root/personal/PaperReader
docker compose up --build -d
tailscale serve --bg --https=443 http://127.0.0.1:7400
tailscale serve status
```

URL: **https://ubuntu-32gb-hel1-1.tail32bbbc.ts.net/** (Mac, iPad, iPhone on the tailnet).
iPhone/iPad: Safari → Share → *Add to Home Screen*.

## Secrets & data
- `.env` (git-ignored, chmod 600): `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `DEFAULT_MODEL`.
- `data/` (git-ignored, bind-mounted): `paperreader.db`, `papers/`, `users.json` (copied from the
  plansTracker users; imported on first start, existing usernames untouched).
- Backup = copy `data/`.

## Operations
- Logs: `docker compose logs -f`. AI calls: Admin → AI call log.
- Model: Admin → Model (`/admin`), no redeploy needed.
