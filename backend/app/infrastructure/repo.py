"""US-01..US-11 — SQLite persistence (single file in DATA_DIR). Thin, explicit SQL; JSON for lists."""

from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager

from app.domain.ids import new_id, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user', active INTEGER NOT NULL DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS prompts (key TEXT PRIMARY KEY, template TEXT NOT NULL, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS papers (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  title TEXT NOT NULL, filename TEXT, page_count INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS paper_pages (
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE, page INTEGER NOT NULL,
  words TEXT NOT NULL, PRIMARY KEY (paper_id, page));
CREATE TABLE IF NOT EXISTS maps (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  title TEXT NOT NULL, paper_ids TEXT NOT NULL, status TEXT NOT NULL, error TEXT, report TEXT,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS nodes (
  id TEXT PRIMARY KEY, map_id TEXT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
  parent_id TEXT REFERENCES nodes(id) ON DELETE CASCADE, title TEXT NOT NULL,
  explanation TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'detail',
  position INTEGER NOT NULL DEFAULT 0, collapsed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS links (
  id TEXT PRIMARY KEY, map_id TEXT NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
  source_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  target_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE, label TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS chats (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  map_id TEXT REFERENCES maps(id) ON DELETE SET NULL, node_ids TEXT NOT NULL DEFAULT '[]',
  paper_ids TEXT NOT NULL DEFAULT '[]', passage TEXT, title TEXT NOT NULL, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL, content TEXT NOT NULL, report TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY, origin TEXT NOT NULL,
  node_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
  message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  page INTEGER NOT NULL, text TEXT NOT NULL, rects TEXT NOT NULL, created_at TEXT);
CREATE TABLE IF NOT EXISTS annotations (
  id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  page INTEGER NOT NULL, text TEXT NOT NULL DEFAULT '', rects TEXT NOT NULL, color TEXT NOT NULL,
  comment TEXT NOT NULL DEFAULT '', created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  node_id TEXT REFERENCES nodes(id) ON DELETE SET NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT, kind TEXT NOT NULL, target_id TEXT,
  status TEXT NOT NULL, report TEXT, error TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS user_prefs (
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, key TEXT NOT NULL, value TEXT NOT NULL,
  updated_at TEXT, PRIMARY KEY (user_id, key));
CREATE TABLE IF NOT EXISTS ai_logs (
  id TEXT PRIMARY KEY, ts TEXT, kind TEXT, model TEXT, messages TEXT, response TEXT,
  duration_ms INTEGER, error TEXT);
CREATE INDEX IF NOT EXISTS ix_nodes_map ON nodes(map_id);
CREATE INDEX IF NOT EXISTS ix_quotes_node ON quotes(node_id);
CREATE INDEX IF NOT EXISTS ix_quotes_msg ON quotes(message_id);
CREATE INDEX IF NOT EXISTS ix_ann_paper ON annotations(paper_id);
"""

JSON_COLS = {"paper_ids", "node_ids", "rects", "report", "messages", "words"}

# How each owned table reaches its session (US-02 AT-02.3: ownership checks).
OWNER_SQL = {
    "sessions": "SELECT id FROM sessions WHERE id=?",
    "papers": "SELECT session_id FROM papers WHERE id=?",
    "maps": "SELECT session_id FROM maps WHERE id=?",
    "nodes": "SELECT m.session_id FROM nodes n JOIN maps m ON m.id=n.map_id WHERE n.id=?",
    "links": "SELECT m.session_id FROM links l JOIN maps m ON m.id=l.map_id WHERE l.id=?",
    "quotes": "SELECT p.session_id FROM quotes q JOIN papers p ON p.id=q.paper_id WHERE q.id=?",
    "annotations": "SELECT p.session_id FROM annotations a JOIN papers p ON p.id=a.paper_id WHERE a.id=?",
    "notes": "SELECT session_id FROM notes WHERE id=?",
    "chats": "SELECT session_id FROM chats WHERE id=?",
}


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_COLS & d.keys():
        if d[k] is not None:
            d[k] = json.loads(d[k])
    return d


def _enc(v):
    return json.dumps(v) if isinstance(v, (list, dict)) else v


class Repo:
    def __init__(self, path: str) -> None:
        self.path = path
        with self.tx() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---- generic helpers -------------------------------------------------
    def insert(self, table: str, **cols) -> dict:
        cols.setdefault("id", new_id())
        keys = ", ".join(cols)
        with self.tx() as c:
            c.execute(f"INSERT INTO {table} ({keys}) VALUES ({', '.join('?' * len(cols))})",
                      [_enc(v) for v in cols.values()])
        return self.get(table, cols["id"])

    def update(self, table: str, id_: str, **cols) -> dict | None:
        if cols:
            sets = ", ".join(f"{k}=?" for k in cols)
            with self.tx() as c:
                c.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*map(_enc, cols.values()), id_])
        return self.get(table, id_)

    def delete(self, table: str, id_: str) -> None:
        with self.tx() as c:
            c.execute(f"DELETE FROM {table} WHERE id=?", (id_,))

    def get(self, table: str, id_: str) -> dict | None:
        with self.tx() as c:
            return _row(c.execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone())

    def query(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.tx() as c:
            return [_row(r) for r in c.execute(sql, args).fetchall()]

    def session_of(self, table: str, id_: str) -> str | None:
        with self.tx() as c:
            r = c.execute(OWNER_SQL[table], (id_,)).fetchone()
        return r[0] if r else None

    # ---- meta / users / settings / prompts --------------------------------
    def secret(self) -> str:
        with self.tx() as c:
            r = c.execute("SELECT value FROM meta WHERE key='auth_secret'").fetchone()
            if r:
                return r[0]
            s = secrets.token_urlsafe(32)
            c.execute("INSERT INTO meta (key, value) VALUES ('auth_secret', ?)", (s,))
            return s

    def seed_users(self, users: list[dict]) -> int:
        """AT-01.3 — import users once; existing usernames are left untouched."""
        added = 0
        with self.tx() as c:
            for u in users:
                cur = c.execute(
                    "INSERT OR IGNORE INTO users (id, username, password_hash, role, active, created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (u.get("id") or new_id(), u["username"].strip().lower(), u["password_hash"],
                     u.get("role", "user"), 1 if u.get("active", True) else 0, u.get("created_at") or now()))
                added += cur.rowcount
        return added

    def user_by_name(self, username: str) -> dict | None:
        rows = self.query("SELECT * FROM users WHERE username=?", (username.strip().lower(),))
        return rows[0] if rows else None

    def settings(self) -> dict:
        return {r["key"]: json.loads(r["value"]) for r in self.query("SELECT * FROM settings")}

    def set_settings(self, values: dict) -> None:
        with self.tx() as c:
            for k, v in values.items():
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))

    def prompt_overrides(self) -> dict[str, dict]:
        return {r["key"]: r for r in self.query("SELECT * FROM prompts")}

    def set_prompt(self, key: str, template: str | None) -> None:
        with self.tx() as c:
            if template is None:
                c.execute("DELETE FROM prompts WHERE key=?", (key,))
            else:
                c.execute("INSERT OR REPLACE INTO prompts (key, template, updated_at) VALUES (?,?,?)",
                          (key, template, now()))

    # ---- US-13 user preferences ---------------------------------------------
    def prefs(self, user_id: str) -> dict:
        return {r["key"]: json.loads(r["value"]) for r in self.query("SELECT key, value FROM user_prefs WHERE user_id=?",
                                                                     (user_id,))}

    def set_pref(self, user_id: str, key: str, value) -> None:
        with self.tx() as c:
            if value is None:
                c.execute("DELETE FROM user_prefs WHERE user_id=? AND key=?", (user_id, key))
            else:
                c.execute("INSERT OR REPLACE INTO user_prefs (user_id, key, value, updated_at) VALUES (?,?,?,?)",
                          (user_id, key, json.dumps(value), now()))

    # ---- papers ------------------------------------------------------------
    def save_pages(self, paper_id: str, pages: list[dict]) -> None:
        with self.tx() as c:
            c.executemany("INSERT INTO paper_pages (paper_id, page, words) VALUES (?,?,?)",
                          [(paper_id, p["page"], json.dumps(p["words"])) for p in pages])

    def pages(self, paper_id: str) -> list[dict]:
        return self.query("SELECT page, words FROM paper_pages WHERE paper_id=? ORDER BY page", (paper_id,))

    # ---- maps ----------------------------------------------------------------
    def map_full(self, map_id: str) -> dict | None:
        m = self.get("maps", map_id)
        if not m:
            return None
        m["nodes"] = self.query("SELECT * FROM nodes WHERE map_id=? ORDER BY position, created_at", (map_id,))
        m["links"] = self.query("SELECT * FROM links WHERE map_id=?", (map_id,))
        m["quotes"] = self.query(
            "SELECT q.id, q.origin, q.node_id, q.message_id, q.paper_id, q.page, q.text, q.rects, q.created_at "
            "FROM quotes q JOIN nodes n ON n.id=q.node_id WHERE n.map_id=? ORDER BY q.page", (map_id,))
        return m

    def next_position(self, map_id: str, parent_id: str | None) -> int:
        rows = self.query("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM nodes WHERE map_id=? AND parent_id IS ?",
                          (map_id, parent_id))
        return rows[0]["p"]

    def add_quotes(self, located: list, *, origin: str, node_id: str | None = None,
                   message_id: str | None = None) -> list[dict]:
        rows = [self.insert("quotes", origin=origin, node_id=node_id, message_id=message_id,
                            paper_id=loc.paper_id, page=loc.page, text=loc.text, rects=loc.rects,
                            created_at=now()) for loc in located]
        return [{k: row[k] for k in ("id", "origin", "node_id", "message_id", "paper_id", "page", "text", "rects", "created_at")}
                for row in rows]

    def delete_node_quotes(self, node_id: str, origin: str = "map") -> None:
        with self.tx() as c:
            c.execute("DELETE FROM quotes WHERE node_id=? AND origin=?", (node_id, origin))

    # ---- AI log ----------------------------------------------------------------
    def log_ai(self, **entry) -> None:
        self.insert("ai_logs", ts=now(), **entry)

    def clear_ai_logs(self) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM ai_logs")
