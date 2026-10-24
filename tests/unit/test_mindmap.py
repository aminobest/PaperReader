"""US-05/US-06 — mind-map parsing and tree invariants."""

import pytest

from app.domain.mindmap import MapFormatError, fold_flags, parse_children, parse_map, would_create_cycle

REPLY = """Here you go:
```json
{"title": "GMN", "nodes": [
  {"id": "n1", "parent": null, "title": "GMN", "kind": "topic", "explanation": "core"},
  {"id": "n2", "parent": "n1", "title": "Problem", "kind": "question",
   "quotes": [{"paper": "P1", "page": 1, "text": "Short texts carry little context"}]},
  {"id": "n3", "parent": "n2", "title": "Detail", "kind": "weird-kind"},
  {"id": "n4", "parent": "missing", "title": "Orphan"}
 ],
 "links": [{"from": "n3", "to": "n1", "label": "supports"}, {"from": "n3", "to": "zzz"}]}
```"""


def test_reply_becomes_tree_with_kinds_quotes_links():
    """AT-05.2 — JSON (even fenced, with prose) → root/branches/details, kinds normalised, links resolved."""
    m = parse_map(REPLY)
    assert m.title == "GMN"
    by = {n.ref: n for n in m.nodes}
    assert by["n1"].parent is None and by["n2"].parent == "n1" and by["n3"].parent == "n2"
    assert by["n4"].parent == "n1"  # orphan re-attached to the root
    assert by["n3"].kind == "detail"  # unknown kind → detail
    assert by["n2"].quotes[0].page == 1
    assert [(lk.source, lk.target) for lk in m.links] == [("n3", "n1")]  # dangling link dropped
    order = [n.ref for n in m.nodes]
    assert order.index("n2") < order.index("n3")  # parents first


@pytest.mark.parametrize("bad", ["no json here", "{not json}", '{"nodes": []}', "[1,2]"])
def test_malformed_reply_raises(bad):
    """AT-05.2 — unusable output raises MapFormatError (which triggers the corrective retry)."""
    with pytest.raises(MapFormatError):
        parse_map(bad)


def test_parent_cycle_in_reply_is_broken():
    """AT-05.2 — a cycle in the LLM's parent links never produces an unreachable subtree."""
    m = parse_map('{"nodes": [{"id":"a","parent":null,"title":"A"},{"id":"b","parent":"c","title":"B"},'
                  '{"id":"c","parent":"b","title":"C"}]}')
    assert {n.ref for n in m.nodes} == {"a", "b", "c"}


def test_expansion_children_hang_under_the_parent():
    """AT-06.3 — expansion nodes with parent null become direct children of the expanded node."""
    nodes = parse_children('{"nodes": [{"id":"c1","parent":null,"title":"X"},{"id":"c2","parent":"c1","title":"Y"}]}', "__parent__")
    assert [(n.ref, n.parent) for n in nodes] == [("c1", "__parent__"), ("c2", "c1")]


def test_move_cycle_detection():
    """AT-06.1 — a node cannot move under itself or a descendant."""
    parents = {"root": None, "a": "root", "b": "a", "c": "b"}
    assert would_create_cycle("a", "c", parents)
    assert would_create_cycle("a", "a", parents)
    assert not would_create_cycle("c", "root", parents)


def test_fold_flags_show_exactly_n_levels():
    """AT-06.5 — depth N collapses nodes at depth ≥ N that have children (so unfolding one branch reveals
    one more level at a time); None unfolds all."""
    nodes = [{"id": "r", "parent_id": None}, {"id": "a", "parent_id": "r"}, {"id": "b", "parent_id": "a"},
             {"id": "c", "parent_id": "b"}]
    assert fold_flags(nodes, 1) == {"r": False, "a": True, "b": True, "c": False}
    assert fold_flags(nodes, 2) == {"r": False, "a": False, "b": True, "c": False}
    assert not any(fold_flags(nodes, None).values())


def test_depth_and_merge_of_deeper_nodes():
    """AT-05.5 — depth counts levels below the root; deeper nodes merge under existing or new parents."""
    from app.domain.mindmap import depth_of, merge_deeper
    m = parse_map('{"nodes": [{"id":"n1","parent":null,"title":"Root"},{"id":"n2","parent":"n1","title":"Branch"}]}')
    assert depth_of(m.nodes) == 1
    added = merge_deeper(m, '{"nodes": [{"id":"x2","parent":"x1","title":"Leaf"},{"id":"x1","parent":"n2","title":"Mid"},'
                            '{"id":"n2","parent":"n1","title":"Clash"},{"id":"zz","parent":"nowhere","title":"Orphan"}]}')
    assert [(n.title, n.parent) for n in added] == [("Mid", "n2"), ("Clash", "n1"), ("Leaf", "x1")]
    assert depth_of(m.nodes + added) == 3
