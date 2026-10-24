# US-02 — Sessions CRUD

As a reader, I want to create, rename, list and delete named sessions, so that I can group the papers I study together.

## Acceptance tests
- **AT-02.1** Given a name, when I create a session then it appears in my list; a blank name is rejected — Levels: unit, integration, system
- **AT-02.2** Given a session, when I rename or delete it then the list updates; delete cascades papers (files), maps, notes, chats — Levels: integration, system
- **AT-02.3** Given two users, when one lists sessions then only their own sessions are visible/accessible (404 otherwise) — Levels: integration

## Main files
- `backend/app/api/sessions.py`
- `backend/app/infrastructure/repo.py`
- `frontend/js/views/sessions.js`
