# US-11 — Admin: model, prompts, log

As the admin, I want to set the model, edit all prompt templates and inspect AI calls, so that I can tune the AI without code changes.

## Acceptance tests
- **AT-11.1** Given a non-admin user, admin APIs return 403 — Levels: integration
- **AT-11.2** Given settings (model, temperature, retries, trace colors), when saved then the next LLM call uses them — Levels: integration, system
- **AT-11.3** Given prompt templates, I can list, edit and reset them; a template missing a required placeholder is rejected — Levels: unit, integration, system
- **AT-11.4** Given any LLM call, it is logged (kind, model, messages, response, duration, error) and the log is viewable/clearable — Levels: integration

## Main files
- `backend/app/api/admin.py`
- `frontend/js/admin.js`
