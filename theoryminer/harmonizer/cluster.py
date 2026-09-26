"""cluster — group spans by density with HDBSCAN.

    from theoryminer.harmonizer import clusterer
    clusters = clusterer(relations)

Defaults are Paper 3's calibrated configuration for all-mpnet on ELSST:
HDBSCAN with min_cluster_size=2, min_samples=2, on the raw embeddings
(no UMAP). Pass a umap dict to reduce the vectors first.
"""

import numpy as np
from sklearn.cluster import HDBSCAN

from .embeddings import embed
from .pairwise import central_member
from .spans import collect_spans


def clusterer(items, embeddings="allmpnet", min_cluster_size=2, min_samples=2, umap=None):
    """Cluster the spans with HDBSCAN.

    Args:
        items: relations from causenet(), or a plain list of span strings.
        embeddings: model shorthand or a Hugging Face id.
        min_cluster_size: HDBSCAN's smallest cluster.
        min_samples: HDBSCAN's density requirement.
        umap: None for the raw embeddings, or a dict of UMAP settings, for example
            dict(n_components=5, n_neighbors=15, min_dist=0.0).

    Returns:
        {span: {"group": id, "central": span}}. group -1 is noise; a noise
        span is its own central member.
    """
    spans = collect_spans(items)
    vectors = embed(spans, embeddings)

    points = vectors
    if umap is not None:
        from umap import UMAP
        settings = {"metric": "cosine", "random_state": 42, **umap}
        points = UMAP(**settings).fit_transform(vectors)

    # The vectors are normalized, so euclidean distance orders pairs exactly as
    # cosine does, and it lets HDBSCAN use its fast tree search.
    labels = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples,
                     metric="euclidean").fit_predict(points.astype(np.float64))

    groups = {}
    for g in sorted(set(labels)):
        member_idx = list(np.where(labels == g)[0])
        if g == -1:
            for i in member_idx:
                groups[spans[i]] = {"group": -1, "central": spans[i]}
            continue
        central = spans[central_member(member_idx, vectors)]
        for i in member_idx:
            groups[spans[i]] = {"group": int(g), "central": central}

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    print(f"cluster: {len(spans):,} spans -> {n_clusters:,} clusters | "
          f"{n_noise:,} noise ({n_noise / max(len(spans), 1):.0%})"
          + (f" | umap {umap}" if umap else " | raw embeddings"))
    return groups
