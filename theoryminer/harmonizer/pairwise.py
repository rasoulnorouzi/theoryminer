"""pairwise — group spans whose embeddings are close.

    from theoryminer.harmonizer import pairwise_grouping
    groups = pairwise_grouping(relations, threshold=0.69)

The `linkage` setting decides when a new span joins a group:

    "average"   the mean cosine to all the members reaches the threshold (the default since 0.2.0)
    "complete"  the cosine to every member reaches the threshold
    "single"    the cosine to one member reaches the threshold. The groups are the connected
                components of the similarity graph, as in Paper 3's tool (the default before 0.2.0)

Single linkage chains: a ~ b and b ~ c put a and c in one group, even when a and c are
not similar. In the sample files this made one group of 153 spans. Average linkage stops
the chain, because one close member is not enough.

The default threshold is Paper 3's calibrated value for all-mpnet (0.69). Paper 3
calibrated it for single linkage. Measure it again before you rely on it with "average".
"""

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage as cluster_tree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial.distance import pdist

from .embeddings import embed
from .spans import collect_spans

LINKAGES = ["average", "complete", "single"]
BLOCK = 2000       # rows of the similarity matrix per step; keeps the memory small for single linkage


def central_member(member_idx, vectors):
    """Index of the member closest to all the others (the medoid)."""
    if len(member_idx) == 1:
        return member_idx[0]
    sub = vectors[member_idx] @ vectors[member_idx].T
    return member_idx[int(np.argmax(sub.mean(axis=1)))]


def _single_labels(vectors, threshold):
    """Return one group label per vector: the connected components of the pairs with cosine >= threshold.

    This is Paper 3's method. It stays unchanged, so old results can be made again.

    Example:
        >>> vectors = np.array([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]])
        >>> _single_labels(vectors, 0.7).tolist()
        [0, 0, 1]
    """
    n = len(vectors)
    rows = []
    cols = []
    for i in range(0, n, BLOCK):
        block = vectors[i:i + BLOCK] @ vectors.T
        r, c = np.where(block >= threshold)
        rows.extend(r + i)
        cols.extend(c)
    adjacency = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    n_groups, labels = connected_components(adjacency, directed=False)
    return labels


def _tree_labels(vectors, threshold, linkage):
    """Return one group label per vector, from average or complete linkage.

    The tree joins the two closest groups, step by step. The cut stops each join where the
    group distance is larger than 1 - threshold. With "average", the group distance is the
    mean cosine distance between the members of the two groups.

    Memory: the function keeps one distance per pair of spans (n * (n - 1) / 2 numbers).
    10,000 spans need about 400 MB.

    Example:
        >>> vectors = np.array([[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]])
        >>> _tree_labels(vectors, 0.7, "average").tolist()
        [0, 0, 1]
    """
    if len(vectors) == 1:
        return np.zeros(1, dtype=int)
    distances = pdist(vectors, metric="cosine")
    distances = np.clip(distances, 0.0, 2.0)        # rounding can give -0.0000001
    tree = cluster_tree(distances, method=linkage)
    labels = fcluster(tree, t=1.0 - threshold, criterion="distance")
    return labels - 1                               # fcluster counts from 1


def pairwise_grouping(items: list, embeddings: str = "allmpnet", threshold: float = 0.69,
                      linkage: str = "average") -> dict:
    """Group the spans that are similar, pair by pair.

    The function turns each span into a vector and joins spans whose cosine reaches
    `threshold`. `linkage` decides when a span joins a group that has more members. Each
    group gets a central span: the member closest to all the others. Every span is in a
    group, so there is no noise. The function loads the embedding model.

    Args:
        items: The spans to work on.
            Values: the relations from causenet() (the function reads "cause" and "effect"), or a
            plain list of span strings. Each unique span is used once.
            Default: none. Give the relations or the spans.
        embeddings: The model that turns a text into a vector.
            Values: "allmpnet" (sentence-transformers/all-mpnet-base-v2), "bge_base"
            (BAAI/bge-base-en-v1.5), "minilm" (sentence-transformers/all-MiniLM-L6-v2, small and
            fast), or the name of another sentence-transformers model on Hugging Face.
            Default "allmpnet": the model of Paper 3. The default thresholds were calibrated for it.
        threshold: The cosine that a span needs to join a group.
            Values: a number from -1 to 1 (in practice 0.5 to 0.9). A higher value gives smaller,
            stricter groups.
            Default 0.69: the value of Paper 3, calibrated for "allmpnet" with "single" linkage.
        linkage: How a span is compared with a group.
            Values: "average": the mean cosine to all the members reaches `threshold`.
            "complete": the cosine to every member reaches `threshold`.
            "single": the cosine to one member reaches `threshold`. This can chain unrelated
            spans into one large group (Paper 3's method).
            Default "average" (since 0.2.0).

    Returns:
        {span: {"group": id, "central": span}}: for each span, the number of its group (0, 1, 2, ...)
        and the central span of that group.

    Raises:
        ValueError: An unknown linkage.

    Example:
        >>> pairwise_grouping(["social support", "strong social support", "teacher support"])   # doctest: +SKIP
        {'social support': {'group': 0, 'central': 'social support'}, 'strong social support': {'group': 0, 'central': 'social support'}, 'teacher support': {'group': 1, 'central': 'teacher support'}}
    """
    if linkage not in LINKAGES:
        raise ValueError(f"unknown linkage {linkage!r}; choose one of {LINKAGES}")

    spans = collect_spans(items)
    vectors = embed(spans, embeddings)
    if linkage == "single":
        labels = _single_labels(vectors, threshold)
    else:
        labels = _tree_labels(vectors, threshold, linkage)

    groups = {}
    for g in range(int(labels.max()) + 1):
        member_idx = list(np.where(labels == g)[0])
        central = spans[central_member(member_idx, vectors)]
        for i in member_idx:
            groups[spans[i]] = {"group": g, "central": central}

    sizes = np.bincount(labels)
    print(f"pairwise: {len(spans):,} spans -> {len(sizes):,} groups at cos >= {threshold}, "
          f"{linkage} linkage | {int((sizes > 1).sum()):,} groups with 2+ members, largest {sizes.max():,}")
    return groups
