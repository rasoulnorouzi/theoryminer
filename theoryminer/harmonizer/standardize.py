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
    """Find the closest thesaurus concepts for each span.

    The function turns each span (tidied and lowercased, no word removed) and each thesaurus
    concept into a vector, and scores each pair with the cosine. It returns the `top` best
    concepts of each span, one per concept, best first. The first call makes the thesaurus
    vectors and saves them (see `cache`). The function loads the embedding model.

    Args:
        items: The spans to work on.
            Values: the relations from causenet() (the function reads "cause" and "effect"), or a
            plain list of span strings. Each unique span is used once.
            Default: none. Give the relations or the spans.
        taxonomy: The thesaurus.
            Values: "elsst", or the path of a SKOS .rdf or .rdf.gz file with the ELSST layout:
            rdf:Description blocks of type skos:Concept, with an English skos:prefLabel.
            Default "elsst": ELSST release 5 (3,436 concepts), which ships with the package.
        strategy: The text that stands for each thesaurus concept.
            Values: "leaf" (the concept name), "path" (the path from the top of the thesaurus),
            "anchor" (the name, then the path), "context" ("<name> is related to <parents>"),
            "bracket" (the name, with the parents in brackets), "enriched" (the name, the other
            names, the definition and the path).
            Default "enriched".
        top: The number of concepts to return, best first.
            Values: a whole number, 1 or more.
            Default 5.
        embeddings: The model that turns a text into a vector.
            Values: "allmpnet", "bge_base", "minilm", or the name of another sentence-transformers
            model on Hugging Face. A new model makes new thesaurus vectors the first time.
            Default "allmpnet".
        leaves_only: Which thesaurus concepts can be a match.
            Values: True: only the most specific concepts (the leaves). False: all concepts, the
            broad ones too, for example TRUST and MOTIVATION.
            Default False: all concepts (the default since 0.2.0).
        cache: Whether to keep the thesaurus vectors on disk.
            Values: True or False.
            Default True: read the vectors from ~/.cache/theoryminer/taxonomy (or from the folder in
            THEORYMINER_CACHE_DIR), and make and save them on the first call (about 3 minutes on a
            CPU). False makes them again in each session.
        threshold: The lowest score that a concept needs to be a match. The score is a cosine.
            Values: None, or a number from -1 to 1 (in practice 0.4 to 0.7).
            Default None: keep the `top` concepts, however low their score.

    Returns:
        {span: [match, ...]}: for each span, a list of up to `top` dicts, best first, with the keys
            id     the web address of the concept
            leaf   the name of the concept
            path   the path from the top of the thesaurus to the concept
            score  the cosine, rounded to 4 decimals
        The list is empty when no concept reaches `threshold`.

    Raises:
        ValueError: An unknown taxonomy (not "elsst" and not a file), or an unknown strategy.

    Example:
        >>> matches = standardize_constructs(["loneliness", "social trust"], top=2)   # doctest: +SKIP
        >>> [(m["leaf"], m["score"]) for m in matches["social trust"]]              # doctest: +SKIP
        [('TRUST', 0.7604), ('INTERPERSONAL TRUST', 0.6876)]
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
    """Find the closest thesaurus concepts for each group of spans.

    The function scores each group against each thesaurus concept, with the rule in `name_by`,
    and returns the `top` best concepts of each group. A noise span (group -1) is a group of
    its own. The first call makes the thesaurus vectors and saves them (see `cache`). The
    function loads the embedding model.

    Args:
        groups: The groups to name.
            Values: the result of pairwise_grouping() or clusterer(): {span: {"group": id,
            "central": span}}.
            Default: none. Give the groups.
        name_by: How a group gets one score for each concept.
            Values: "mean_sim": score each member, then take the mean. A mixed group scores low.
            "centroid": take the mean vector of the members, then score it. It always ranks the
            concepts as "mean_sim" does, with higher scores. "medoid": score the central span only.
            Default "mean_sim".
        taxonomy: The thesaurus.
            Values: "elsst", or the path of a SKOS .rdf or .rdf.gz file with the ELSST layout:
            rdf:Description blocks of type skos:Concept, with an English skos:prefLabel.
            Default "elsst": ELSST release 5 (3,436 concepts), which ships with the package.
        strategy: The text that stands for each thesaurus concept.
            Values: "leaf" (the concept name), "path" (the path from the top of the thesaurus),
            "anchor" (the name, then the path), "context" ("<name> is related to <parents>"),
            "bracket" (the name, with the parents in brackets), "enriched" (the name, the other
            names, the definition and the path).
            Default "enriched".
        top: The number of concepts to return, best first.
            Values: a whole number, 1 or more.
            Default 5.
        embeddings: The model that turns a text into a vector.
            Values: "allmpnet", "bge_base", "minilm", or the name of another sentence-transformers
            model on Hugging Face. A new model makes new thesaurus vectors the first time.
            Default "allmpnet".
        leaves_only: Which thesaurus concepts can be a match.
            Values: True: only the most specific concepts (the leaves). False: all concepts, the
            broad ones too, for example TRUST and MOTIVATION.
            Default False: all concepts (the default since 0.2.0).
        cache: Whether to keep the thesaurus vectors on disk.
            Values: True or False.
            Default True: read the vectors from ~/.cache/theoryminer/taxonomy (or from the folder in
            THEORYMINER_CACHE_DIR), and make and save them on the first call (about 3 minutes on a
            CPU). False makes them again in each session.
        threshold: The lowest score that a concept needs to be a match. The score is a cosine.
            Values: None, or a number from -1 to 1 (in practice 0.4 to 0.7).
            Default None: keep the `top` concepts, however low their score.

    Returns:
        {key: group}: one dict per group. The key is the group id, or the span text for a noise
        span. Each group has the keys
            central  the central span of the group
            size     the number of members
            members  the spans of the group
            matches  up to `top` concepts, best first, with the keys id, leaf, path and score;
                     empty when no concept reaches `threshold`

    Raises:
        ValueError: An unknown name_by, an unknown taxonomy, or an unknown strategy.

    Example:
        >>> named = standardize_groups(clusterer(cards), top=1)               # doctest: +SKIP
        >>> named[1]["size"], named[1]["matches"][0]["leaf"]                    # doctest: +SKIP
        (5, 'LONELINESS')
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
