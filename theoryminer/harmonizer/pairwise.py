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
    """Group the spans by pairwise similarity.

    Args:
        items: relations from causenet(), or a plain list of span strings.
        embeddings: model shorthand or a Hugging Face id.
        threshold: the cosine similarity that a span needs to join a group.
        linkage: how a span is compared with a group: "average" (the mean cosine to the
            members), "complete" (every member), or "single" (one member; Paper 3's method).

    Returns:
        {span: {"group": id, "central": span}}. `central` is the group's medoid.

    Raises:
        ValueError: linkage is not one of LINKAGES.
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
