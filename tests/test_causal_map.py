"""Tests for causal_map(), save_map() and draw_map(). No test loads a model.

The toy map covers each special case: a dominant/minority pair, a contested pair,
a self-loop, and one paper that repeats a claim.
"""

import csv

import networkx as nx
import pytest

from theoryminer import causal_map, draw_map, save_map


def relation(rel_id, doc_id, cause, effect, sentence="A sentence."):
    return {"rel_id": rel_id, "sent_id": rel_id, "doc_id": doc_id, "page": 1,
            "cause": cause, "effect": effect, "sentence": sentence}


RELATIONS = [
    relation("r1", "p1", "job insecurity", "stress"),
    relation("r2", "p2", "fear of job loss", "anxiety"),
    relation("r3", "p3", "job insecurity", "stress"),
    relation("r4", "p4", "stress", "job insecurity"),        # 1 paper against 3: the minority side
    relation("r5", "p1", "loneliness", "health"),
    relation("r6", "p2", "health", "loneliness"),            # 1 paper against 1: contested
    relation("r7", "p1", "stress", "anxiety"),               # both spans in one group: a self-loop
    relation("r8", "p5", "this", "health"),
    relation("r9", "p1", "job insecurity", "stress"),        # p1 repeats its claim
]

# The shape of label_groups(). A noise span is keyed by its own text.
NAMES = {
    0: {"central": "job insecurity", "members": ["job insecurity", "fear of job loss"], "name": "job insecurity"},
    1: {"central": "stress", "members": ["stress", "anxiety"], "name": "stress"},
    2: {"central": "loneliness", "members": ["loneliness"], "name": "loneliness"},
    3: {"central": "health", "members": ["health"], "name": "health"},
    "this": {"central": "this", "members": ["this"], "name": "this"},
}


def edge_between(cmap, source_label, target_label):
    """Return the edge from one label to another, shown or hidden."""
    for edge in cmap["edges"] + cmap["hidden"]:
        source = cmap["nodes"][edge["source"]]["label"]
        target = cmap["nodes"][edge["target"]]["label"]
        if source == source_label and target == target_label:
            return edge
    raise AssertionError(f"no edge {source_label} -> {target_label}")


def node_called(cmap, label):
    for node in cmap["nodes"].values():
        if node["label"] == label:
            return node
    raise AssertionError(f"no node {label}")


# --- the edges --------------------------------------------------------------

def test_papers_and_relations_are_counted_separately():
    edge = edge_between(causal_map(RELATIONS, NAMES, min_relations=1), "job insecurity", "stress")
    assert edge["n_relations"] == 4
    assert edge["n_papers"] == 3                       # p1 counts once
    assert edge["rel_ids"] == ["r1", "r2", "r3", "r9"]


def test_a_pair_with_3_papers_against_1_has_one_direction():
    cmap = causal_map(RELATIONS, NAMES, min_relations=1)
    assert edge_between(cmap, "job insecurity", "stress")["direction"] == "dominant"
    assert edge_between(cmap, "stress", "job insecurity")["direction"] == "minority"
    assert edge_between(cmap, "stress", "job insecurity")["reciprocal"]


def test_a_pair_with_1_paper_against_1_is_contested():
    cmap = causal_map(RELATIONS, NAMES, min_relations=1)
    assert edge_between(cmap, "loneliness", "health")["direction"] == "contested"
    assert edge_between(cmap, "health", "loneliness")["direction"] == "contested"


def test_a_lower_min_share_decides_the_pair():
    # With min_share 0.51, a 3-to-1 pair stays decided; 1 to 1 stays contested.
    cmap = causal_map(RELATIONS, NAMES, min_relations=1, min_share=0.51)
    assert edge_between(cmap, "loneliness", "health")["direction"] == "contested"


def test_a_self_loop_is_flagged_and_kept():
    edge = edge_between(causal_map(RELATIONS, NAMES, min_relations=1), "stress", "stress")
    assert edge["self_loop"]
    assert not edge["reciprocal"]
    assert edge["drop_reason"] == ""


# --- the filters -------------------------------------------------------------

def test_min_papers_hides_edges_with_their_reason():
    cmap = causal_map(RELATIONS, NAMES, min_papers=2, min_relations=1)
    assert len(cmap["edges"]) == 1
    assert len(cmap["edges"]) + len(cmap["hidden"]) == 6       # nothing is deleted
    for edge in cmap["hidden"]:
        assert edge["drop_reason"] == "below_min_papers"


def test_min_relations_hides_edges_with_their_reason():
    cmap = causal_map(RELATIONS, NAMES, min_relations=2)
    assert [edge["n_relations"] for edge in cmap["edges"]] == [4]
    assert cmap["hidden"][0]["drop_reason"] == "below_min_relations"


def test_roles_and_counts_follow_the_shown_edges():
    cmap = causal_map(RELATIONS, NAMES, min_papers=2, min_relations=1)
    assert node_called(cmap, "job insecurity")["role"] == "cause only"
    assert node_called(cmap, "stress")["role"] == "effect only"
    assert not node_called(cmap, "health")["shown"]


def test_a_node_with_edges_in_and_out_is_cause_and_effect():
    health = node_called(causal_map(RELATIONS, NAMES, min_relations=1), "health")
    assert health["as_cause"] == 1
    assert health["as_effect"] == 2
    assert health["role"] == "cause and effect"


# --- the three shapes of names -------------------------------------------------

def match(concept_id, leaf, score=0.7):
    return {"id": concept_id, "leaf": leaf, "path": leaf, "score": score}


def test_names_from_standardize_constructs_merge_spans_with_one_concept():
    relations = [relation("r1", "p1", "job insecurity", "stress"),
                 relation("r2", "p2", "fear of job loss", "odd span")]
    names = {"job insecurity": [match("c1", "JOB INSECURITY")],
             "fear of job loss": [match("c1", "JOB INSECURITY")],
             "stress": [match("c2", "STRESS")],
             "odd span": []}                                   # no concept above the threshold
    cmap = causal_map(relations, names, min_relations=1)
    assert node_called(cmap, "JOB INSECURITY")["members"] == ["job insecurity", "fear of job loss"]
    assert node_called(cmap, "odd span")["node_id"] == "s:odd span"


def test_names_from_standardize_groups_use_the_concept_or_the_central_span():
    relations = [relation("r1", "p1", "job insecurity", "stress")]
    names = {0: {"central": "job insecurity", "size": 1, "members": ["job insecurity"],
                 "matches": [match("c1", "JOB INSECURITY")]},
             1: {"central": "stress", "size": 1, "members": ["stress"], "matches": []}}
    cmap = causal_map(relations, names, min_relations=1)
    edge = cmap["edges"][0]
    assert cmap["nodes"][edge["source"]]["label"] == "JOB INSECURITY"
    assert cmap["nodes"][edge["target"]]["label"] == "stress"


def test_groups_without_names_raise_with_a_hint():
    groups = {"stress": {"group": 0, "central": "stress"}}
    with pytest.raises(ValueError, match="run label_groups"):
        causal_map(RELATIONS, groups)


def test_a_span_that_is_not_in_names_raises():
    with pytest.raises(ValueError, match="'unknown' is not in names"):
        causal_map([relation("r1", "p1", "unknown", "stress")], NAMES)


def test_wrong_settings_raise():
    with pytest.raises(ValueError, match="min_papers"):
        causal_map(RELATIONS, NAMES, min_papers=0)
    with pytest.raises(ValueError, match="min_share"):
        causal_map(RELATIONS, NAMES, min_share=0.4)


# --- save_map() and draw_map() --------------------------------------------------

def test_save_map_writes_the_tables_and_the_graph(tmp_path):
    cmap = causal_map(RELATIONS, NAMES, min_papers=2, min_relations=1)
    save_map(cmap, str(tmp_path / "map"))
    with open(tmp_path / "map" / "hidden.csv", encoding="utf-8") as fh:
        hidden = list(csv.DictReader(fh))
    assert len(hidden) == 5
    assert hidden[0]["drop_reason"] == "below_min_papers"
    graph = nx.read_graphml(tmp_path / "map" / "map.graphml")
    assert graph.number_of_edges() == 6


def test_draw_map_in_a_script_writes_one_offline_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    relations = RELATIONS + [relation("r10", "p6", "stress", "health", "Stress </script> harms health.")]
    papers = [{"doc_id": "p1", "file": "p1.pdf", "doi": "10.1000/xyz", "title": "A title"}]
    draw_map(causal_map(relations, NAMES, min_relations=1), papers=papers)
    page = (tmp_path / "causal_map.html").read_text(encoding="utf-8")
    assert "cytoscape" in page
    assert "10.1000/xyz" in page
    assert "Stress <\\/script> harms health." in page         # the sentence cannot end the script block
    assert "<script src" not in page                           # no outside file: the page works offline
    assert "<link" not in page


def test_draw_map_with_save_writes_that_file(tmp_path):
    draw_map(causal_map(RELATIONS, NAMES, min_relations=1), save=str(tmp_path / "out" / "map.html"))
    assert (tmp_path / "out" / "map.html").is_file()


def test_each_placeholder_is_filled_once(tmp_path):
    # A placeholder name in a comment of the template would copy the whole library or the data twice.
    draw_map(causal_map(RELATIONS, NAMES, min_relations=1), save=str(tmp_path / "map.html"))
    page = (tmp_path / "map.html").read_text(encoding="utf-8")
    assert page.count("The Cytoscape Consortium") == 1
    assert page.count("iVis-at-Bilkent") == 1
    assert "cytoscapeFcose" in page


def test_the_default_hides_edges_with_one_relation():
    cmap = causal_map(RELATIONS, NAMES)
    assert cmap["settings"] == {"min_papers": 1, "min_relations": 2, "min_share": 0.67}
    assert [edge["n_relations"] for edge in cmap["edges"]] == [4]
    assert len(cmap["hidden"]) == 5
