# US-01 — Sign in

As a reader, I want to sign in with my existing account (same as plansTracker), so that only I can reach my papers and notes on the tailnet.

## Acceptance tests
- **AT-01.1** Given a plansTracker `pbkdf2_sha256` hash, when the correct password is verified then it passes and a wrong one fails — Levels: unit, integration
- **AT-01.2** Given no session cookie, when any `/api` route (except login/health) is called then 401 is returned and the UI shows the login screen — Levels: integration, system
- **AT-01.3** Given `data/users.json`, when the app starts on an empty DB then those users are imported once (idempotent on restart) — Levels: integration
- **AT-01.4** Given valid credentials, when I log in then I land on my sessions list; when I log out I am back on the login screen — Levels: system

## Main files
- `backend/app/api/auth.py`
- `backend/app/infrastructure/security.py`
- `frontend/js/app.js`
