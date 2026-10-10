"""Time causal_map() and the map page on synthetic networks of growing size."""

import os
import random
import sys
import time

from theoryminer import causal_map
from theoryminer.causal_map import _page_html

OUT = sys.argv[1]
SIZES = [(300, 1500), (1000, 6000), (3000, 20000), (10000, 80000)]   # (nodes, relations)
SENTENCE = "Higher loneliness predicts lower wellbeing among adolescents in the sample studied. " * 2


def synthetic(n_nodes, n_relations, seed=1):
    """Return (relations, names) with n_nodes groups of 3 spans and n_relations relations."""
    rng = random.Random(seed)
    names = {}
    spans = []
    for g in range(n_nodes):
        members = [f"construct {g} variant {k}" for k in range(3)]
        names[g] = {"central": members[0], "members": members, "name": f"construct {g}"}
        spans.extend(members)
    relations = []
    for i in range(n_relations):
        # a skewed choice: a few hub constructs, many rare ones, as in real corpora
        cause = spans[int(len(spans) * rng.random() ** 2)]
        effect = spans[int(len(spans) * rng.random() ** 2)]
        relations.append({"rel_id": f"r{i}", "sent_id": f"s{i}", "doc_id": f"p{i % 500}", "page": 1,
                          "cause": cause, "effect": effect, "sentence": SENTENCE, "doi": "", "title": ""})
    return relations, names


def time_layout(path, quality):
    """Load the page in headless Chromium. Return (load seconds, layout seconds, shown nodes, shown edges)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        start = time.time()
        page.goto("file://" + path, timeout=600_000)
        page.wait_for_function("typeof cy !== 'undefined'", timeout=600_000)
        load = time.time() - start
        result = page.evaluate("""(quality) => {
            const shown = cy.elements().filter(x => !x.hasClass('hidden'));
            const t = performance.now();
            shown.layout({...LAYOUT, quality: quality}).run();
            return [performance.now() - t, shown.nodes().length, shown.edges().length];
        }""", quality)
        browser.close()
    return load, result[0] / 1000, result[1], result[2]


for n_nodes, n_relations in SIZES:
    relations, names = synthetic(n_nodes, n_relations)
    start = time.time()
    cmap = causal_map(relations, names, min_sentences=1)
    build = time.time() - start
    start = time.time()
    page = _page_html(cmap, None, "bench")
    render = time.time() - start
    path = os.path.join(OUT, f"map_{n_nodes}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"\n== {n_nodes} nodes, {n_relations} relations: causal_map {build:.2f}s, page build {render:.2f}s, "
          f"page {len(page) / 1e6:.1f} MB, shown edges {len(cmap['edges'])}, hidden {len(cmap['hidden'])}", flush=True)
    for quality in ["draft", "default", "proof"]:
        if n_nodes >= 10000 and quality == "proof":
            print("   proof: skipped at this size (too slow)", flush=True)
            continue
        load, layout, shown_nodes, shown_edges = time_layout(path, quality)
        print(f"   {quality:7s}: page load (incl. first layout) {load:6.1f}s | layout {layout:6.1f}s | "
              f"{shown_nodes} nodes, {shown_edges} edges", flush=True)
