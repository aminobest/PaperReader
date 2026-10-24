# US-03 — Papers: upload, read, manage

As a reader, I want to upload one or more PDFs into a session and read them in the app, so that the paper is next to its map and notes.

## Acceptance tests
- **AT-03.1** Given one or more PDFs, when I upload them then each becomes a paper with page count and extracted word positions — Levels: integration, system
- **AT-03.2** Given a non-PDF file, when I upload it then it is rejected with 400 — Levels: integration
- **AT-03.3** Given a paper, when I open it then pages render with a selectable text layer — Levels: system
- **AT-03.4** Given a paper, when I rename or delete it then the change persists; delete removes file, annotations and quotes — Levels: integration
- **AT-03.5** Given PDF metadata/filename, then the default title is the metadata title, else the filename without extension — Levels: unit

## Main files
- `backend/app/api/papers.py`
- `backend/app/infrastructure/pdf.py`
- `frontend/js/pdfview.js`
