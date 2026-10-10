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


def clusterer(items: list, embeddings: str = "allmpnet", min_cluster_size: int = 2, min_samples: int = 2,
              umap: dict | None = None) -> dict:
    """Group the spans by density, with HDBSCAN.

    The function turns each span into a vector and finds the dense regions: spans with many
    close neighbours. Each dense region is a group. A span in no dense region is noise
    (group -1); it stays in the result as its own central span. The function loads the
    embedding model.

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
        min_cluster_size: The smallest group.
            Values: a whole number, 2 or more.
            Default 2: a pair of spans can be a group (the value of Paper 3).
        min_samples: How many close neighbours a span needs to be in a dense region.
            Values: a whole number, 1 or more. A higher value gives fewer groups and more noise.
            Default 2 (the value of Paper 3).
        umap: Whether to make the vectors shorter with UMAP before the clustering.
            Values: None, or a dict of UMAP settings, for example dict(n_components=5,
            n_neighbors=15, min_dist=0.0). The metric is cosine and random_state is 42, unless
            the dict sets them.
            Default None: cluster the full vectors.

    Returns:
        {span: {"group": id, "central": span}}: for each span, the number of its group (0, 1, 2, ...)
        or -1 for noise, and the central span of that group. A noise span is its own central span.

    Raises:
        ValueError: min_cluster_size below 2 or min_samples below 1 (HDBSCAN checks them).

    Example:
        >>> clusters = clusterer(cards)                                  # doctest: +SKIP
        >>> clusters["loneliness"], clusters["teacher support"]            # doctest: +SKIP
        ({'group': 1, 'central': 'reducing loneliness'}, {'group': -1, 'central': 'teacher support'})
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
    # copy=False: astype() already gives HDBSCAN its own array, so no second copy is needed.
    # Setting it also stops the FutureWarning of scikit-learn 1.9 (the default becomes True in 1.10).
    labels = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean",
                     copy=False).fit_predict(points.astype(np.float64))

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
