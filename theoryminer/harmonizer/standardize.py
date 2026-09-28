"""standardize — map constructs, or groups of constructs, to taxonomy concepts.

    from theoryminer.harmonizer import standardize_constructs, standardize_groups

    matches = standardize_constructs(relations, taxonomy="elsst", strategy="enriched", top=5)
    named   = standardize_groups(groups, name_by="mean_sim", top=5)

Scores are cosine similarities. With threshold=None (the default), every span
and every group gets its `top` concepts, however weak. With a threshold, a
concept below it is left out, so a span or a group can get an empty list:
it has no concept. causal_map() then keeps it as its own node, under its
own text. Results are keyed by the original span strings, so every match
traces back to its relation.
"""

import numpy as np

from .embeddings import embed
from .spans import collect_spans, tidy_span
from .taxonomy import taxonomy_embeddings

NAME_RULES = ["mean_sim", "centroid", "medoid"]


def _queries(spans):
    """The text embedded for each span: the tidied span, lowercased. No word is removed."""
    return [tidy_span(s).lower() for s in spans]


def _top_matches(scores, entries, top, threshold=None):
    """The `top` best entries for one score row, one per concept, best first.

    With a threshold, an entry that scores below it is left out. The list can then be empty.

    Example:
        >>> entries = [{"id": "c1", "leaf": "STRESS", "path": "STRESS"},
        ...            {"id": "c2", "leaf": "HEALTH", "path": "HEALTH"}]
        >>> [m["leaf"] for m in _top_matches(np.array([0.62, 0.41]), entries, 5)]
        ['STRESS', 'HEALTH']
        >>> [m["leaf"] for m in _top_matches(np.array([0.62, 0.41]), entries, 5, threshold=0.5)]
        ['STRESS']
        >>> _top_matches(np.array([0.62, 0.41]), entries, 5, threshold=0.7)
        []
    """
    matches = []
    seen = set()
    for j in np.argsort(-scores):
        if threshold is not None and scores[j] < threshold:
            break                                   # the scores are sorted, so all the rest are lower
        e = entries[j]
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        matches.append({"id": e["id"], "leaf": e["leaf"], "path": e["path"],
                        "score": round(float(scores[j]), 4)})
        if len(matches) == top:
            break
    return matches


def _score_summary(best, n_items, threshold):
    """Return the summary text of the best scores, and the count without a concept.

    Example:
        >>> _score_summary([0.4, 0.6, 0.8], 4, 0.4)
        'best score: median 0.60, min 0.40, max 0.80 | no concept >= 0.4: 1 of 4'
        >>> _score_summary([], 2, 0.9)
        'no concept >= 0.9: 2 of 2'
    """
    text = ""
    if best:
        text = f"best score: median {np.median(best):.2f}, min {min(best):.2f}, max {max(best):.2f}"
    if threshold is None:
        return text
    unmatched = f"no concept >= {threshold}: {n_items - len(best)} of {n_items}"
    if not text:
        return unmatched
    return f"{text} | {unmatched}"


def standardize_constructs(items: list, taxonomy: str = "elsst", strategy: str = "enriched", top: int = 5,
                           embeddings: str = "allmpnet", leaves_only: bool = False, cache: bool = True,
                           threshold: float | None = None) -> dict:
    """Map each span to its closest taxonomy concepts.

    Args:
        items: relations from causenet(), or a plain list of span strings.
        taxonomy: "elsst", or a path to a SKOS .rdf file.
        strategy: what text stands for a concept:
            leaf | path | anchor | context | bracket | enriched.
        top: how many concepts to return per span.
        embeddings: model shorthand ("allmpnet", "bge_base", "minilm") or a HF id.
        leaves_only: False (the default since 0.2.0) matches against all concepts, broad ones
            too ("TRUST", "MOTIVATION"). True matches against the leaf concepts only (the
            most specific ones), as before 0.2.0.
        cache: keep the taxonomy embeddings on disk.
        threshold: None keeps every match. A cosine (for example 0.5) leaves out the
            concepts that score lower. A span with no concept left gets an empty list.

    Returns:
        {span: [{"id", "leaf", "path", "score"}, ...]}, best first. The list is empty
        when no concept reaches the threshold.
    """
    spans = collect_spans(items)
    entries, tax_vectors = taxonomy_embeddings(taxonomy, strategy, embeddings, leaves_only, cache)
    span_vectors = embed(_queries(spans), embeddings)

    result = {}
    for i in range(0, len(spans), 2000):          # blocks keep the score matrix small
        scores = span_vectors[i:i + 2000] @ tax_vectors.T
        for k, span in enumerate(spans[i:i + 2000]):
            result[span] = _top_matches(scores[k], entries, top, threshold)

    best = [m[0]["score"] for m in result.values() if m]
    print(f"standardize: {len(spans):,} spans -> top {top} of {len(entries):,} entries | "
          f"{_score_summary(best, len(result), threshold)}")
    return result


def standardize_groups(groups: dict, name_by: str = "mean_sim", taxonomy: str = "elsst",
                       strategy: str = "enriched", top: int = 5, embeddings: str = "allmpnet",
                       leaves_only: bool = False, cache: bool = True, threshold: float | None = None) -> dict:
    """Give each group of spans its closest taxonomy concepts.

    Args:
        groups: output of pairwise_grouping() or clusterer():
            {span: {"group": id, "central": span}}.
        name_by: how a group is scored against the taxonomy:
            "mean_sim"  average the members' similarity vectors (conservative:
                        a mixed group scores low),
            "centroid"  average the member vectors, then score,
            "medoid"    score the central member only.
        The other arguments are the same as in standardize_constructs(), threshold too.

    Returns:
        {group_id: {"central", "size", "members", "matches"}}.
        Noise spans (group -1) each form a group of one, keyed by the span.
        "matches" is empty when no concept reaches the threshold.
    """
    if name_by not in NAME_RULES:
        raise ValueError(f"unknown name_by {name_by!r}; choose one of {NAME_RULES}")

    spans = list(groups)
    entries, tax_vectors = taxonomy_embeddings(taxonomy, strategy, embeddings, leaves_only, cache)
    span_vectors = embed(_queries(spans), embeddings)
    row = {span: i for i, span in enumerate(spans)}

    members = {}
    for span, g in groups.items():
        key = span if g["group"] == -1 else g["group"]
        members.setdefault(key, []).append(span)

    result = {}
    for key, member_list in members.items():
        idx = [row[s] for s in member_list]
        if name_by == "mean_sim":
            scores = (span_vectors[idx] @ tax_vectors.T).mean(axis=0)
        elif name_by == "centroid":
            v = span_vectors[idx].mean(axis=0)
            scores = (v / np.linalg.norm(v)) @ tax_vectors.T
        else:
            central = groups[member_list[0]]["central"]
            scores = span_vectors[row[central]] @ tax_vectors.T
        result[key] = {"central": groups[member_list[0]]["central"],
                       "size": len(member_list), "members": member_list,
                       "matches": _top_matches(scores, entries, top, threshold)}

    best = [r["matches"][0]["score"] for r in result.values() if r["matches"]]
    print(f"standardize: {len(result):,} groups named by {name_by} | "
          f"{_score_summary(best, len(result), threshold)}")
    return result
