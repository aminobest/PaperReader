"""Integration: US-13 per-user layout preferences."""

from tests.integration.conftest import login

LAYOUT = {"side": "bottom", "swap": True, "share": 0.4, "sideW": 360, "sideH": 260}


def test_prefs_roundtrip_validation_and_privacy(env):
    """AT-13.6 — stored per user; unknown key / non-object / too large → 422; private to the user."""
    client, _, _ = env
    login(client)
    assert client.get("/api/prefs").json() == {}
    assert client.put("/api/prefs/layout.desktop", json=LAYOUT).json() == {"layout.desktop": LAYOUT}
    assert client.put("/api/prefs/layout.phone", json=LAYOUT).status_code == 422
    assert client.put("/api/prefs/layout.tablet", json=[1, 2]).status_code == 422
    assert client.put("/api/prefs/layout.tablet", json={"x": "a" * 3000}).status_code == 422
    client.post("/api/auth/logout")
    assert client.get("/api/prefs").status_code == 401
    login(client, "reader", "reader123456")
    assert client.get("/api/prefs").json() == {}


def test_reset_layout_deletes_pref(env):
    """AT-13.4 — reset removes the stored layout so the device default applies again."""
    client, _, _ = env
    login(client)
    client.put("/api/prefs/layout.tablet", json=LAYOUT)
    assert client.delete("/api/prefs/layout.tablet").status_code == 204
    assert client.get("/api/prefs").json() == {}
