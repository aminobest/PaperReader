# Admin view and in-app issue reporter

Read this when: building or changing the admin view, the issue reporter or the shared
layout. Build or change them ONLY at project setup or when the user explicitly asks.

Contents: 1. Admin view · 2. Issue reporter · 3. issue.md format · 4. How it is built ·
5. Security · 6. No-UI variant · 7. Standard stories

## 1. Admin view

- Path from the profile (`admin.path`, default `/admin`); admins only.
- **Issue reporter on/off** — shows or hides the icon everywhere, immediately, no redeploy.
- **Who can report** — `admins` or `signed_in` (default `signed_in`).
- **Issues list** — every report: title, page, status, reporter, date, link to read it.
  Read-only; reports are closed through the issue-handling workflow in SKILL.md.
- Room for project-specific settings, each added in its own story.
- Settings: the profile's `admin` values are **seed defaults** only. The runtime value lives
  in app storage (DB or settings file in a volume) and the admin view changes it there.
- Needs sign-in with an admin role. No accounts yet → one admin account configured via env
  vars. Test accounts live only in fixtures.

## 2. Issue reporter (what the user sees)

- A small icon in the **bottom-right corner of every view**, rendered by the shared layout
  so new views get it automatically. It doesn't cover content and is keyboard-accessible.
- Clicking it opens a pop-up with:
  - a **title** field;
  - a **rich text editor**: bold, italic, lists, links, code (any maintained editor for the
    project's UI technology);
  - **screenshots**: paste, drag and drop, or file picker — PNG, JPEG or WebP, max 5 images,
    5 MB each;
  - a visible note: "Reports are stored in the project repository — don't include
    passwords or personal data.";
  - **Send** and **Cancel**.
- Context is added automatically: page path, time, reporter, app version, browser, screen size.
- After Send, the user sees a confirmation with the issue ID.

## 3. issue.md format

```
issues/issue-20261031-0007/
  issue.md
  attachments/screenshot-1.png
```

```markdown
---
id: issue-20261031-0007
title: Highlight disappears after zooming
status: open                     # open | closed
page: /papers/42/view
reported_by: reader
reported_at: 2026-10-31T14:03:00Z
app_version: 1.4.2 (abc1234)
browser: Firefox 131, 1440x900
attachments: [attachments/screenshot-1.png]
# added on close: resolved_at, resolution
---

When I zoom to 150 %, the **yellow highlight** on the selected quote vanishes.

![screenshot-1](attachments/screenshot-1.png)
```

## 4. How it is built

- **presentation** — icon + pop-up in the shared layout; `POST /api/issues`.
- **logic** — `IssueService`: validates, sanitises, converts rich text to Markdown, numbers
  the report. — Markdown is readable in editors, git and by agents.
- **data** — `IssueRepository` writes the folder; `SettingsRepository` stores admin settings.
- **Docker** — `compose.yaml` bind-mounts `./issues:/app/issues`, writable by the container's
  non-root user (see `references/setup.md` §2); `compose.test.yaml` mounts a throwaway folder.
- **Git** — `issues/` is committed to the repo.

## 5. Security — report content is untrusted

- Only users allowed by the "who can report" setting can send; only admins open the admin view.
- **No raw HTML at all**: convert to Markdown from an allowlist (bold, italic, lists, code,
  links); drop everything else.
- Links: allow only `http:`, `https:`, `mailto:`; strip `javascript:`, `data:` and others.
- Images: check type by content, enforce count and size limits, **re-encode server-side**
  (drops EXIF and any embedded payload).
- The server picks every file and folder name; user-supplied filenames are never used.
- Create the report atomically: write to `issues/.tmp-<random>/` (same filesystem, git-ignored),
  then rename to the next free ID; rename fails because the ID exists → retry with the next number.
- Disk quota for `issues/` (e.g. 500 MB, configurable); over quota → refuse with a clear message.
- CSRF protection on `POST /api/issues`; rate limit per user (e.g. 5 per minute).

## 6. No-UI variant

CLIs and background services skip the admin view and offer `report-issue`: it opens the
user's `$EDITOR` and writes the same folder and `issue.md` format (same sanitising rules).

## 7. Standard stories

Create both at setup: `US-01`/`US-02` in a new project, next free numbers otherwise.

```markdown
# US-01 — Admin view
As the project owner I want an admin view
so that I can manage the app without editing code or redeploying.

### AT-01.1 — Only admins can open the admin view
Given a signed-in user without the admin role
When they open /admin
Then they are refused and see no admin data
Levels: unit, integration, system

### AT-01.2 — The issue reporter can be switched off
Given an admin on the admin view
When they switch the issue reporter off
Then the icon disappears from every view for every user, without a redeploy
Levels: integration, system

### AT-01.3 — Admins see all reports
Given open and closed reports in the issues folder
When an admin opens the issues list
Then each report shows its title, page, status, reporter and date
Levels: integration, system
```

```markdown
# US-02 — In-app issue reporter
As a user I want to report a problem from the screen where it happened
so that the developers get the exact context without me explaining it.

### AT-02.1 — The icon is on every view
Given the issue reporter is on and the user may report
When they open any view
Then a small issue icon is shown in the bottom-right corner
Levels: system

### AT-02.2 — A report with screenshots is saved to the issues folder
Given the pop-up is open
When the user writes formatted text, pastes two screenshots and presses Send
Then issues/issue-<id>/ contains issue.md (status open, page, reporter, time, app version)
and both images under attachments/, and the user sees the ID
Levels: unit, integration, system

### AT-02.3 — Unsafe content is neutralised
Given a report with a <script> tag, a javascript: link and an image named ../../evil.png
When it is sent
Then the saved Markdown has no HTML and no javascript: link, and the image is re-encoded
under a server-chosen name inside the report's own folder
Levels: unit, integration

### AT-02.4 — Invalid images are refused
Given an attachment that is not an image, or is larger than 5 MB
When the user presses Send
Then the report is refused with a clear message and nothing is written
Levels: unit, integration
```
