# US-10 — Chat about nodes or passages

As a reader, I want to chat with the AI about selected node(s) or a selected passage, so that I can ask until I understand.

## Acceptance tests
- **AT-10.1** Given selected node(s) or a passage, I can start a chat thread; threads can be listed, renamed and deleted — Levels: integration, system
- **AT-10.2** Given an assistant answer, its quotes are grounded (retry/drop) and stored as `chat` quotes; `[n]` citations map to them — Levels: unit, integration
- **AT-10.3** Given an answer, its quotes are highlighted in the AI-trace color and clicking a citation jumps to it — Levels: system
- **AT-10.4** Given a chat, the prompt contains the node path/explanation (or passage), the papers and the history — Levels: unit

## Main files
- `backend/app/application/chat_service.py`
- `frontend/js/chat.js`
