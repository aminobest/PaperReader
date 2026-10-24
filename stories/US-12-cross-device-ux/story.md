# US-12 — Great UX on Mac, iPad, iPhone

As a reader, I want the workspace to adapt to my device, so that reading and mapping is comfortable everywhere.

## Acceptance tests
- **AT-12.1** Given a wide screen (≥1100px), map, paper and side panel are visible together with resizable splitters — Levels: system
- **AT-12.2** Given a tablet width (700–1099px), map and paper are split and the side panel is a drawer — Levels: system
- **AT-12.3** Given a phone width (<700px), one pane is shown at a time with a bottom tab bar — Levels: system
- **AT-12.4** Given the app, it serves a web manifest and Apple meta tags for home-screen install — Levels: integration
- **AT-12.5** Given a viewport width, the layout mode function returns desktop/tablet/phone — Levels: unit

## Main files
- `frontend/css/app.css`
- `frontend/js/layout.mjs`
- `frontend/manifest.webmanifest`
