"""pairwise — group spans whose embeddings are close.

    from theoryminer.harmonizer import pairwise_grouping
    groups = pairwise_grouping(relations, threshold=0.69)

Two spans join when their cosine similarity reaches the threshold. Groups
are the connected components of that graph, as in Paper 3's tool. The
default threshold is Paper 3's calibrated value for all-mpnet (0.69).
"""

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .embeddings import embed
from .spans import collect_spans


def central_member(member_idx, vectors):
    """Index of the member closest to all the others (the medoid)."""
    if len(member_idx) == 1:
        return member_idx[0]
    sub = vectors[member_idx] @ vectors[member_idx].T
    return member_idx[int(np.argmax(sub.mean(axis=1)))]


def pairwise_grouping(items, embeddings="allmpnet", threshold=0.69):
    """Group the spans by pairwise similarity.

    Args:
        items: relations from causenet(), or a plain list of span strings.
        embeddings: model shorthand or a Hugging Face id.
        threshold: two spans join when cosine similarity >= threshold.

    Returns:
        {span: {"group": id, "central": span}}. `central` is the group's medoid.
    """
    spans = collect_spans(items)
    vectors = embed(spans, embeddings)
    n = len(spans)

    # Collect the pairs above the threshold, one block of rows at a time.
    rows, cols = [], []
    for i in range(0, n, 2000):
        block = vectors[i:i + 2000] @ vectors.T
        r, c = np.where(block >= threshold)
        rows.extend(r + i)
        cols.extend(c)
    adjacency = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    n_groups, labels = connected_components(adjacency, directed=False)

    groups = {}
    for g in range(n_groups):
        member_idx = list(np.where(labels == g)[0])
        central = spans[central_member(member_idx, vectors)]
        for i in member_idx:
            groups[spans[i]] = {"group": g, "central": central}

    sizes = np.bincount(labels)
    print(f"pairwise: {n:,} spans -> {n_groups:,} groups at cos >= {threshold} | "
          f"{int((sizes > 1).sum()):,} groups with 2+ members, largest {sizes.max():,}")
    return groups
