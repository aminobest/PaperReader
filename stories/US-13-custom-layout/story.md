# US-13 — Resizable, rearrangeable workspace

As a reader, I want to resize the map, paper and side-panel areas and rearrange them (e.g. notes
as a footer, map and paper swapped), so that the workspace fits how I read on each device.

## Acceptance tests
- **AT-13.1** Given desktop or tablet, when I drag a divider then the map/paper split or the side-panel size changes, and the sizes are restored after a reload — Levels: unit, system
- **AT-13.2** Given the layout menu, I can put the side panel (Node · Notes · Chat) on the right, left, bottom (footer) or — on tablet — in a drawer — Levels: unit, system
- **AT-13.3** Given the layout menu, I can swap map and paper — Levels: unit, system
- **AT-13.4** Given a customised layout, "Reset layout" restores the device default and double-clicking a divider resets only that size — Levels: unit, integration, system
- **AT-13.5** Given stored preferences, the layout is kept per device class (desktop vs tablet), invalid values fall back to defaults, and the phone keeps its tab layout — Levels: unit, system
- **AT-13.6** Given a signed-in user, preferences are stored per user on the server; only known keys and small JSON objects are accepted; other users cannot see them — Levels: unit, integration

## Main files
- `frontend/js/layout.mjs` (pure layout model), `frontend/js/workspace.js` (menu, dividers)
- `backend/app/api/prefs.py`, `backend/app/domain/rules.py` (`validate_pref`), `user_prefs` table
