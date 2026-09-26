"""taxonomy — load a thesaurus and embed its concepts once.

    from theoryminer.harmonizer.taxonomy import taxonomy_embeddings
    entries, vectors = taxonomy_embeddings("elsst", strategy="enriched", model="allmpnet")

One thesaurus is built in: "elsst" (ELSST R5, SKOS/RDF). The package holds it
as theoryminer/data/ELSST_R5.rdf.gz (CC BY-SA 4.0, see ELSST_LICENSE.md there).
A path to another SKOS .rdf or .rdf.gz file with the same layout also works.

One entry is one root-to-leaf path. A concept with two parents gives two
entries. Every entry has the same shape, whatever the taxonomy:

    {"id": uri, "leaf": "Autonomy", "path": "Psychology > Motivation > Autonomy",
     "parents": ["Motivation", "Psychology"],    # nearest parent first
     "alt": ["self-determination", ...], "note": "<scope note or definition>"}

The embeddings of one (taxonomy, strategy, model, leaves) combination are
computed on first use and saved to `theoryminer/taxonomy_cache/`. Later
calls load the file. Delete the cache folder after a new taxonomy release.

Cache files are plain: `<tax>_<strategy>_<model>_<scope>.npy` holds the vectors
(one row per entry, float32) and `<tax>_<scope>.json` holds the entries in the
same row order. Both open in R (RcppCNPy::npyLoad, jsonlite::fromJSON).
"""

import gzip
import html
import json
import os
import re

import numpy as np

from .embeddings import SHORTHAND, embed

# The package folder. The thesaurus file and the vector cache live inside it,
# so they work the same after "pip install" as in a clone of the repository.
_PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_PACKAGE, "data")
CACHE_DIR = os.path.join(_PACKAGE, "taxonomy_cache")

STRATEGIES = ["leaf", "path", "anchor", "context", "bracket", "enriched"]

# Parsed taxonomies stay in memory for the session.
_LOADED = {}


# ---------------------------------------------------------------------------
# Loaders. Each parser fills one dict of concepts with the same keys:
#   label, alt, note, broader (ids), is_leaf, is_top
# and _entries() turns that dict into the list of entries.
# ---------------------------------------------------------------------------

def _entries(concepts, leaves_only):
    """Return one entry per root-to-concept path. Print the counts."""

    def paths_to_root(uri, seen):
        """Return every path from a root down to `uri`, as lists of ids."""
        c = concepts[uri]
        parents = [p for p in c["broader"] if p in concepts and p not in seen]
        if c["is_top"] or not parents:
            return [[uri]]
        paths = []
        for p in parents:
            for above in paths_to_root(p, seen | {uri}):
                paths.append(above + [uri])
        return paths

    entries = []
    seen_paths = set()
    for uri, c in concepts.items():
        if leaves_only and not c["is_leaf"]:
            continue
        for path in paths_to_root(uri, set()):
            labels = [concepts[u]["label"] for u in path]
            path_text = " > ".join(labels)
            if path_text in seen_paths:
                continue
            seen_paths.add(path_text)
            entries.append({"id": uri, "leaf": c["label"], "path": path_text,
                            "parents": labels[:-1][::-1],
                            "alt": c["alt"], "note": c["note"]})
    n_leaves = sum(1 for c in concepts.values() if c["is_leaf"])
    print(f"taxonomy: {len(concepts):,} concepts | {n_leaves:,} leaves | "
          f"{len(entries):,} entries ({'leaves only' if leaves_only else 'all concepts'})")
    return entries


def _read_text(path):
    """Return the text of a file. A file whose name ends with ".gz" is unpacked first.

    Example:
        >>> _read_text(DEFAULT_FILES["elsst"])[:38]
        '<?xml version="1.0" encoding="UTF-8"?>'
    """
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _load_elsst(path, leaves_only):
    """Parse the ELSST SKOS/RDF file and return the list of entries."""
    text = _read_text(path)
    blocks = re.findall(r'<rdf:Description[^>]*rdf:about="([^"]+)"(.*?)</rdf:Description>',
                        text, re.S)
    re_pref = re.compile(r'<skos:prefLabel xml:lang="en">(.*?)</skos:prefLabel>', re.S)
    re_alt = re.compile(r'<skos:altLabel xml:lang="en">(.*?)</skos:altLabel>', re.S)
    re_note = re.compile(r'<skos:scopeNote xml:lang="en">(.*?)</skos:scopeNote>', re.S)
    re_def = re.compile(r'<skos:definition xml:lang="en">(.*?)</skos:definition>', re.S)
    re_broader = re.compile(r'<skos:broader rdf:resource="([^"]+)"')
    re_narrower = re.compile(r'<skos:narrower rdf:resource="([^"]+)"')

    concepts = {}
    for uri, body in blocks:
        if "skos/core#Concept" not in body:
            continue
        pref = re_pref.search(body)
        if not pref:
            continue
        note = re_note.search(body) or re_def.search(body)
        concepts[uri] = {
            "label": html.unescape(pref.group(1)).strip(),
            "alt": [html.unescape(a).strip() for a in re_alt.findall(body)],
            "note": html.unescape(note.group(1)).strip() if note else "",
            "broader": re_broader.findall(body),
            "is_leaf": not re_narrower.findall(body),
            "is_top": "skos:topConceptOf" in body,
        }
    return _entries(concepts, leaves_only)


LOADERS = {"elsst": _load_elsst}
DEFAULT_FILES = {"elsst": os.path.join(DATA_DIR, "ELSST_R5.rdf.gz")}


def load_taxonomy(name, leaves_only=True):
    """Return the entries of a taxonomy.

    `name` is "elsst", or a path to a SKOS .rdf or .rdf.gz file with the ELSST layout.
    """
    key = (name, leaves_only)
    if key in _LOADED:
        return _LOADED[key]
    if name in LOADERS:
        _LOADED[key] = LOADERS[name](DEFAULT_FILES[name], leaves_only)
    elif os.path.isfile(name):
        _LOADED[key] = _load_elsst(name, leaves_only)
    else:
        raise ValueError(f"unknown taxonomy {name!r}; choose one of {list(LOADERS)} "
                         f"or give the path of a SKOS .rdf or .rdf.gz file")
    return _LOADED[key]


# ---------------------------------------------------------------------------
# What text represents one entry. Six strategies.
# ---------------------------------------------------------------------------

def strategy_text(entry, strategy):
    """Return the text that stands for the entry under the strategy."""
    leaf = entry["leaf"].lower()
    path = entry["path"].lower()
    parents = ", ".join(p.lower() for p in entry["parents"])
    if strategy == "leaf":
        return leaf
    if strategy == "path":
        return path
    if strategy == "anchor":
        return f"{leaf}: {path}"
    if strategy == "context":
        return f"{leaf} is related to {parents}" if parents else leaf
    if strategy == "bracket":
        return f"{leaf} ({parents})" if parents else leaf
    if strategy == "enriched":
        parts = [leaf]
        if entry["alt"]:
            parts.append("; ".join(a.lower() for a in entry["alt"]))
        if entry["note"]:
            parts.append(entry["note"].lower().rstrip("."))
        parts.append(path)
        return ". ".join(parts)
    raise ValueError(f"unknown strategy {strategy!r}; choose one of {STRATEGIES}")


# ---------------------------------------------------------------------------
# Embeddings of the whole taxonomy, cached on disk.
# ---------------------------------------------------------------------------

def taxonomy_embeddings(name="elsst", strategy="enriched", model="allmpnet",
                        leaves_only=True, cache=True):
    """Return (entries, vectors). Vectors come from the cache file when it exists."""
    entries = load_taxonomy(name, leaves_only)
    tax_tag = os.path.splitext(os.path.basename(name))[0].lower()
    model_tag = model if model in SHORTHAND else model.replace("/", "_")
    scope = "leaves" if leaves_only else "all"
    path = os.path.join(CACHE_DIR, f"{tax_tag}_{strategy}_{model_tag}_{scope}.npy")

    if cache and os.path.exists(path):
        vectors = np.load(path)
        if vectors.shape[0] == len(entries):
            print(f"taxonomy: embeddings from cache ({os.path.basename(path)})")
            return entries, vectors

    minutes = max(1, round(len(entries) / 1300))
    print(f"taxonomy: no cache yet for ({tax_tag}, {strategy}, {model_tag}, {scope}). "
          f"Embedding {len(entries):,} entries now; about {minutes} min on CPU. "
          f"This runs once; later calls load {os.path.basename(path)}.")
    vectors = embed([strategy_text(e, strategy) for e in entries], model)
    if cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        np.save(path, vectors.astype(np.float32))
        entries_path = os.path.join(CACHE_DIR, f"{tax_tag}_{scope}.json")
        if not os.path.exists(entries_path):
            with open(entries_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False)
    return entries, vectors
