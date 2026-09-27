"""causal_map — turn the relations and the group names into a causal map.

The chain: relations -> groups -> names -> map.

    from theoryminer import causal_map, draw_map, save_map, extract_dois
    from theoryminer.harmonizer import pairwise_grouping, label_groups

    groups = pairwise_grouping(relations)
    names = label_groups(groups)
    cmap = causal_map(relations, names)
    draw_map(cmap, papers=extract_dois("sample_files"))    # the interactive page
    save_map(cmap, "outputs/my_map")                        # the tables and a GraphML file

A node is a construct: a group from label_groups(), or a thesaurus concept from
standardize_groups() or standardize_constructs(). An edge goes from the node of
the cause to the node of the effect. The direction comes from the relations.
An edge has two weights: the number of papers and the number of relations.
Every edge keeps its rel_ids, so each edge leads back to its sentences.

Special edges get a flag. Nothing is deleted:
    self_loop   the cause and the effect are in the same node. It usually means that
                the grouping merged two constructs that a paper keeps apart.
    reciprocal  the opposite edge also exists (A -> B and B -> A). The pair gets a
                direction: "dominant" and "minority" when one side has at least
                min_share of the papers, else "contested" for both.

A filter moves an edge from "edges" to "hidden" with a drop_reason. The page of
draw_map() gets all the edges, so its sliders can show the hidden edges again.
"""

import collections
import csv
import html
import json
import os

MIN_SHARE = 0.67      # a two-way pair gets one direction when one side has 2/3 of the papers (2 to 1)
DIRECTIONS = ["one-way", "dominant", "minority", "contested"]

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAGE_TEMPLATE = os.path.join(DATA_DIR, "causal_map.html")     # the page, with three placeholders
CYTOSCAPE_JS = os.path.join(DATA_DIR, "cytoscape.min.js")      # Cytoscape.js 3.30.2, MIT licence
# The fcose layout (MIT licence) in the order that it needs: its base libraries first.
LAYOUT_JS = [os.path.join(DATA_DIR, name) for name in ["layout-base.js", "cose-base.js", "cytoscape-fcose.js"]]
DEFAULT_PAGE = "causal_map.html"   # the file that draw_map() writes outside a notebook, when save=None
FRAME_HEIGHT = 720                 # the height of the map in a notebook cell, in pixels

NODE_COLUMNS = ["node_id", "label", "role", "n_relations", "as_cause", "as_effect", "n_papers",
                "shown", "n_members", "members"]
EDGE_COLUMNS = ["edge_id", "source", "source_label", "target", "target_label", "n_papers", "n_relations",
                "direction", "reciprocal", "self_loop", "drop_reason", "doc_ids", "rel_ids"]


# ---------------------------------------------------------------------------
# 1. The names: one node per group or per concept.
# ---------------------------------------------------------------------------

def _names_shape(names):
    """Tell which function made the names. Return "labels", "groups" or "concepts".

    Raises:
        ValueError: names is empty, or it has another shape.

    Example:
        >>> _names_shape({0: {"central": "stress", "members": ["stress"], "name": "stress"}})
        'labels'
        >>> _names_shape({"stress": [{"id": "c1", "leaf": "STRESS", "path": "", "score": 0.7}]})
        'concepts'
    """
    if not names:
        raise ValueError("names is empty; give the output of label_groups(), standardize_groups() "
                         "or standardize_constructs()")
    first = next(iter(names.values()))
    if isinstance(first, list):
        return "concepts"
    if isinstance(first, dict) and "matches" in first:
        return "groups"
    if isinstance(first, dict) and "name" in first:
        return "labels"
    if isinstance(first, dict) and "group" in first:
        raise ValueError("names holds groups without names; run label_groups(groups) or "
                         "standardize_groups(groups) first, then give its output to causal_map()")
    raise ValueError("unknown shape of names; give the output of label_groups(), standardize_groups() "
                     "or standardize_constructs()")


def _new_node(node_id, label):
    """Return an empty node dict."""
    return {"node_id": node_id, "label": label, "members": [], "as_cause": 0, "as_effect": 0,
            "n_relations": 0, "n_papers": 0, "role": "", "shown": False}


def _add_member(nodes, span_node, node_id, label, span):
    """Put the span into the node. Make the node when it does not exist."""
    if node_id not in nodes:
        nodes[node_id] = _new_node(node_id, label)
    nodes[node_id]["members"].append(span)
    span_node[span] = node_id


def _node_map(names):
    """Return the nodes and the map {span: node_id} for the names.

    The node of a span:
        label_groups()            its group. The label is the group name.
        standardize_groups()      the best concept of its group. Groups with the same best concept
                                  share one node. A group without a concept keeps its own node,
                                  under its central span.
        standardize_constructs()  its best concept. A span without a concept is its own node.
    """
    shape = _names_shape(names)
    nodes = {}
    span_node = {}
    for key, value in names.items():
        if shape == "concepts":
            node_id, label = _concept_or_self(value, f"s:{key}", key)
            _add_member(nodes, span_node, node_id, label, key)
            continue
        if shape == "groups":
            node_id, label = _concept_or_self(value["matches"], f"g:{key}", value["central"])
        else:
            node_id, label = f"g:{key}", value["name"]
        for span in value["members"]:
            _add_member(nodes, span_node, node_id, label, span)
    return nodes, span_node


def _concept_or_self(matches, own_id, own_label):
    """Return (node_id, label): the best concept, or the own id and label when there is no concept.

    Example:
        >>> _concept_or_self([{"id": "c7", "leaf": "STRESS", "path": "", "score": 0.7}], "s:strain", "strain")
        ('c:c7', 'STRESS')
        >>> _concept_or_self([], "s:strain", "strain")
        ('s:strain', 'strain')
    """
    if not matches:
        return own_id, own_label
    return f"c:{matches[0]['id']}", matches[0]["leaf"]


# ---------------------------------------------------------------------------
# 2. The edges: one per (cause node, effect node).
# ---------------------------------------------------------------------------

def _node_of(span, span_node):
    """Return the node id of a span. The span is stripped, as the harmonizer strips it.

    Raises:
        ValueError: the span is not in the names.
    """
    key = span.strip()
    if key not in span_node:
        raise ValueError(f"the span {key!r} is not in names; make the names from the same relations "
                         f"that you give to causal_map()")
    return span_node[key]


def _build_edges(relations, span_node):
    """Merge the relations into edges. Return {(source, target): edge dict}, in first-seen order."""
    edges = collections.OrderedDict()
    for relation in relations:
        source = _node_of(relation["cause"], span_node)
        target = _node_of(relation["effect"], span_node)
        key = (source, target)
        if key not in edges:
            edges[key] = {"edge_id": f"e{len(edges) + 1:05d}", "source": source, "target": target,
                          "n_papers": 0, "n_relations": 0, "rel_ids": [], "doc_ids": [],
                          "direction": "one-way", "reciprocal": False, "self_loop": source == target,
                          "drop_reason": ""}
        edge = edges[key]
        edge["rel_ids"].append(relation["rel_id"])
        if relation["doc_id"] not in edge["doc_ids"]:
            edge["doc_ids"].append(relation["doc_id"])
    for edge in edges.values():
        edge["n_relations"] = len(edge["rel_ids"])
        edge["n_papers"] = len(edge["doc_ids"])
    return edges


def _pair_direction(n_papers, other_papers, min_share):
    """Return the direction of one edge of a two-way pair, from the paper counts of both sides.

    Example:
        >>> _pair_direction(3, 1, 0.67)
        'dominant'
        >>> _pair_direction(1, 3, 0.67)
        'minority'
        >>> _pair_direction(2, 2, 0.67)
        'contested'
    """
    share = max(n_papers, other_papers) / (n_papers + other_papers)
    if share < min_share:
        return "contested"
    if n_papers > other_papers:
        return "dominant"
    return "minority"


def _mark_pairs(edges, min_share):
    """Flag the two-way pairs and give each edge of a pair its direction. Change the edges in place."""
    for (source, target), edge in edges.items():
        other = edges.get((target, source))
        if other is None or edge["self_loop"]:
            continue
        edge["reciprocal"] = True
        edge["direction"] = _pair_direction(edge["n_papers"], other["n_papers"], min_share)


def _apply_filters(edges, min_papers, min_relations):
    """Split the edges into shown and hidden. A hidden edge gets its drop_reason. Return (shown, hidden)."""
    shown = []
    hidden = []
    for edge in edges.values():
        if edge["n_papers"] < min_papers:
            edge["drop_reason"] = "below_min_papers"
            hidden.append(edge)
        elif edge["n_relations"] < min_relations:
            edge["drop_reason"] = "below_min_relations"
            hidden.append(edge)
        else:
            shown.append(edge)
    return shown, hidden


# ---------------------------------------------------------------------------
# 3. The nodes: counts and role.
# ---------------------------------------------------------------------------

def _role(as_cause, as_effect):
    """Return the role of a node from its counts in the shown edges.

    Example:
        >>> _role(3, 0), _role(0, 2), _role(1, 4)
        ('cause only', 'effect only', 'cause and effect')
    """
    if as_effect == 0:
        return "cause only"
    if as_cause == 0:
        return "effect only"
    return "cause and effect"


def _count_nodes(nodes, shown):
    """Count each node in the shown edges, and set its role and flags. Change the nodes in place."""
    papers = collections.defaultdict(set)
    for edge in shown:
        nodes[edge["source"]]["as_cause"] += edge["n_relations"]
        nodes[edge["target"]]["as_effect"] += edge["n_relations"]
        papers[edge["source"]].update(edge["doc_ids"])
        papers[edge["target"]].update(edge["doc_ids"])
    for node_id, node in nodes.items():
        node["n_relations"] = node["as_cause"] + node["as_effect"]
        node["n_papers"] = len(papers[node_id])
        node["shown"] = node["n_relations"] > 0
        if node["shown"]:
            node["role"] = _role(node["as_cause"], node["as_effect"])


# ---------------------------------------------------------------------------
# 4. The public functions.
# ---------------------------------------------------------------------------

def _check_settings(min_papers, min_relations, min_share):
    """Raise a ValueError for a wrong filter setting."""
    if min_papers < 1 or min_relations < 1:
        raise ValueError(f"min_papers and min_relations must be 1 or more; "
                         f"got min_papers={min_papers}, min_relations={min_relations}")
    if not 0.5 < min_share <= 1:
        raise ValueError(f"min_share must be above 0.5 and at most 1; got {min_share}")


def causal_map(relations, names, min_papers=1, min_relations=2, min_share=MIN_SHARE):
    """Build the causal map from the relations and the names of their groups.

    Each node is a construct. Each edge is "cause node -> effect node", with the number
    of papers and relations that claim it. Self-loops and two-way pairs get flags. The
    filters hide the weak edges. Nothing is deleted: a hidden edge is in "hidden" with
    its drop_reason. The function reads no file and loads no model.

    Args:
        relations: the relation dicts from causenet().
        names: the output of label_groups(), standardize_groups() or standardize_constructs(),
            made from the same relations.
        min_papers: show an edge only when at least this many papers claim it. The default 1
            also works for one long book, where every edge has 1 paper.
        min_relations: show an edge only when at least this many relations claim it. The
            default 2 hides the claims that only one sentence makes. Use 1 to show every edge.
        min_share: a two-way pair gets one direction when one side has at least this share of
            the papers of the pair. Else both edges are "contested".

    Returns:
        {"nodes":     {node_id: node dict},
         "edges":     [edge dicts that are shown],
         "hidden":    [edge dicts that a filter hides, with drop_reason],
         "relations": {rel_id: relation dict},
         "settings":  {"min_papers", "min_relations", "min_share"}}

    Raises:
        ValueError: names has an unknown shape, a span of a relation is not in names,
            or a setting is out of range.

    Example:
        >>> relations = [
        ...     {"rel_id": "r1", "doc_id": "p1", "cause": "job insecurity", "effect": "stress"},
        ...     {"rel_id": "r2", "doc_id": "p2", "cause": "fear of job loss", "effect": "anxiety"}]
        >>> names = {0: {"central": "job insecurity", "members": ["job insecurity", "fear of job loss"],
        ...              "name": "job insecurity"},
        ...          1: {"central": "stress", "members": ["stress", "anxiety"], "name": "stress"}}
        >>> cmap = causal_map(relations, names)
        causal map: 2 nodes | 1 edges shown, 0 hidden | self-loops: 0 edges, 0 of 2 relations (0.0%) | two-way pairs: 0 (0 contested)
        >>> edge = cmap["edges"][0]
        >>> edge["source"], edge["target"], edge["n_papers"], edge["rel_ids"]
        ('g:0', 'g:1', 2, ['r1', 'r2'])
    """
    _check_settings(min_papers, min_relations, min_share)
    if not relations:
        raise ValueError("relations is empty; give the output of causenet()")

    # 1. The nodes, and the node of each span.
    nodes, span_node = _node_map(names)

    # 2. The edges, the two-way pairs and the filters.
    edges = _build_edges(relations, span_node)
    _mark_pairs(edges, min_share)
    shown, hidden = _apply_filters(edges, min_papers, min_relations)

    # 3. The counts and roles of the nodes, from the shown edges.
    _count_nodes(nodes, shown)

    relation_by_id = {}
    for relation in relations:
        relation_by_id[relation["rel_id"]] = relation
    cmap = {"nodes": nodes, "edges": shown, "hidden": hidden, "relations": relation_by_id,
            "settings": {"min_papers": min_papers, "min_relations": min_relations, "min_share": min_share}}
    _print_summary(cmap, len(relations))
    return cmap


def _print_summary(cmap, n_relations):
    """Print one short summary of a causal_map() run."""
    shown_nodes = [n for n in cmap["nodes"].values() if n["shown"]]
    all_edges = cmap["edges"] + cmap["hidden"]
    loops = [e for e in all_edges if e["self_loop"]]
    loop_relations = sum(e["n_relations"] for e in loops)
    pairs = sum(e["reciprocal"] for e in all_edges) // 2
    contested = sum(e["direction"] == "contested" for e in all_edges) // 2
    print(f"causal map: {len(shown_nodes):,} nodes | {len(cmap['edges']):,} edges shown, "
          f"{len(cmap['hidden']):,} hidden | self-loops: {len(loops)} edges, {loop_relations} of "
          f"{n_relations} relations ({100 * loop_relations / n_relations:.1f}%) | "
          f"two-way pairs: {pairs} ({contested} contested)")


def _edge_row(edge, nodes):
    """Return one CSV row for an edge. The lists become text joined by " | "."""
    row = dict(edge)
    row["source_label"] = nodes[edge["source"]]["label"]
    row["target_label"] = nodes[edge["target"]]["label"]
    row["doc_ids"] = " | ".join(edge["doc_ids"])
    row["rel_ids"] = " | ".join(edge["rel_ids"])
    return row


def _node_row(node):
    """Return one CSV row for a node. The members become text joined by " | "."""
    row = dict(node)
    row["n_members"] = len(node["members"])
    row["members"] = " | ".join(node["members"])
    return row


def _write_csv(path, columns, rows):
    """Write the rows to a CSV file with the given columns."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_graphml(path, cmap):
    """Write every node and edge to a GraphML file for Gephi or Cytoscape. A hidden edge keeps its drop_reason."""
    import networkx as nx

    graph = nx.MultiDiGraph()
    for node in cmap["nodes"].values():
        row = _node_row(node)
        attributes = {column: row[column] for column in NODE_COLUMNS if column != "node_id"}
        graph.add_node(node["node_id"], **attributes)
    for edge in cmap["edges"] + cmap["hidden"]:
        row = _edge_row(edge, cmap["nodes"])
        attributes = {column: row[column] for column in EDGE_COLUMNS if column not in ("source", "target")}
        graph.add_edge(edge["source"], edge["target"], key=edge["edge_id"], **attributes)
    nx.write_graphml(graph, path)


def save_map(cmap, folder):
    """Write the causal map to a folder: three CSV tables and one GraphML file.

    The files:
        nodes.csv     one row per node
        edges.csv     one row per shown edge
        hidden.csv    one row per hidden edge, with its drop_reason
        map.graphml   every node and edge, for Gephi or Cytoscape desktop

    Args:
        cmap: the output of causal_map().
        folder: the folder for the files. A missing folder is made. Old files are overwritten.

    Returns:
        A list of the paths of the four files.

    Example:
        >>> save_map(cmap, "outputs/my_map")                       # doctest: +SKIP
        saved map: outputs/my_map (nodes.csv, edges.csv, hidden.csv, map.graphml)
    """
    os.makedirs(folder, exist_ok=True)
    nodes = cmap["nodes"]
    paths = [os.path.join(folder, name) for name in ["nodes.csv", "edges.csv", "hidden.csv", "map.graphml"]]

    node_rows = [_node_row(node) for node in nodes.values()]
    edge_rows = [_edge_row(edge, nodes) for edge in cmap["edges"]]
    hidden_rows = [_edge_row(edge, nodes) for edge in cmap["hidden"]]
    _write_csv(paths[0], NODE_COLUMNS, node_rows)
    _write_csv(paths[1], EDGE_COLUMNS, edge_rows)
    _write_csv(paths[2], EDGE_COLUMNS, hidden_rows)
    _write_graphml(paths[3], cmap)

    print(f"saved map: {folder} (nodes.csv, edges.csv, hidden.csv, map.graphml)")
    return paths


# ---------------------------------------------------------------------------
# 5. The interactive page.
# ---------------------------------------------------------------------------

def _paper_sources(papers):
    """Return {doc_id: {"doi", "title", "file"}} from the rows of extract_dois(). None gives {}."""
    sources = {}
    for row in papers or []:
        sources[row["doc_id"]] = {"doi": row.get("doi", ""), "title": row.get("title", ""),
                                  "file": row.get("file", row["doc_id"])}
    return sources


def _page_data(cmap, papers):
    """Return the data of the page: every node and edge, the sentences, the paper sources, the settings."""
    relations = {}
    for rel_id, relation in cmap["relations"].items():
        relations[rel_id] = {"rel_id": rel_id, "doc_id": relation["doc_id"],
                             "page": relation.get("page", ""), "sentence": relation.get("sentence", "")}
    return {"nodes": list(cmap["nodes"].values()), "edges": cmap["edges"] + cmap["hidden"],
            "relations": relations, "papers": _paper_sources(papers), "settings": cmap["settings"]}


def _page_html(cmap, papers, title):
    """Fill the page template. Return the full HTML text of one offline page."""
    with open(PAGE_TEMPLATE, encoding="utf-8") as fh:
        page = fh.read()
    with open(CYTOSCAPE_JS, encoding="utf-8") as fh:
        cytoscape_js = fh.read()
    layout_parts = []
    for path in LAYOUT_JS:
        with open(path, encoding="utf-8") as fh:
            layout_parts.append(fh.read())
    # "</" inside the data would end the <script> block early, so it is written as "<\/".
    data = json.dumps(_page_data(cmap, papers)).replace("</", "<\\/")
    page = page.replace("__TITLE__", html.escape(title))
    page = page.replace("__CYTOSCAPE__", cytoscape_js)
    page = page.replace("__LAYOUT__", "\n".join(layout_parts))
    return page.replace("__DATA__", data)


def _in_notebook():
    """Return True when the code runs in a notebook kernel (Jupyter, VS Code, Colab)."""
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    shell = get_ipython()
    return shell is not None and hasattr(shell, "kernel")


def _show_in_notebook(page, height):
    """Show the page in the output of the notebook cell, in a frame."""
    from IPython.display import HTML, display

    # A bare <iframe> makes IPython print a warning, so the frame sits inside a <div>.
    frame = (f'<div><iframe srcdoc="{html.escape(page, quote=True)}" '
             f'style="width:100%;height:{height}px;border:1px solid #d9dee7"></iframe></div>')
    display(HTML(frame))


def _write_page(path, page):
    """Write the page to a file. A missing folder is made."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)


def draw_map(cmap, papers=None, save=None, title="Causal map", height=FRAME_HEIGHT):
    """Draw the causal map as an interactive page.

    In a notebook, the page shows in the cell output. In a plain Python script, the
    function writes the page to causal_map.html. The page is one HTML file that works
    offline. On the page you can hover over a node or an edge, click an edge to read
    all its sentences, search, drag, zoom, change the filters, and save a picture
    (PNG, JPG or SVG). The page gets every edge, also the hidden edges, and its
    sliders start at the filter values of causal_map().

    Args:
        cmap: the output of causal_map().
        papers: the rows of extract_dois(), for the source of each sentence: its DOI,
            else the paper title, else the file name. None shows the doc_id.
        save: a path for the HTML file, for example "outputs/map.html". The file is
            written in addition to the notebook output. None writes no file in a
            notebook, and causal_map.html in a script.
        title: the title at the top of the page.
        height: the height of the map in a notebook cell, in pixels.

    Returns:
        None. The function shows the page or writes the file.

    Example:
        >>> draw_map(cmap, papers=extract_dois("sample_files"))              # doctest: +SKIP
        >>> draw_map(cmap, save="outputs/map.html")                         # doctest: +SKIP
        saved page: outputs/map.html
    """
    page = _page_html(cmap, papers, title)
    if save is not None:
        _write_page(save, page)
        print(f"saved page: {save}")
    if _in_notebook():
        _show_in_notebook(page, height)
        return
    if save is None:
        _write_page(DEFAULT_PAGE, page)
        print(f"saved page: {DEFAULT_PAGE} (open it in a browser)")
