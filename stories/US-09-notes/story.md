# US-09 — Notes

As a reader, I want to keep persistent notes per session, optionally linked to a node, so that my own understanding is stored next to the map.

## Acceptance tests
- **AT-09.1** Given a session, I can create, edit (autosaved) and delete notes and they persist after reload — Levels: integration, system
- **AT-09.2** Given a selected node, a new note links to it and the list can be filtered to it; deleting the node keeps the note but unlinks it — Levels: integration
- **AT-09.3** Given a note without title, then its title is derived from the first line of the body — Levels: unit

## Main files
- `backend/app/api/notes.py`
- `frontend/js/notes.js`
