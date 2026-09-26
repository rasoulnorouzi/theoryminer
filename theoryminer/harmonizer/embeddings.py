"""embeddings — one place that turns texts into vectors.

    from theoryminer.harmonizer.embeddings import embed
    vectors = embed(["autonomy", "self-determination"], model="allmpnet")

Vectors are L2-normalized, so cosine similarity is the dot product:
    similarity = vectors_a @ vectors_b.T
Each model loads once per session and stays in memory.
"""

# Short names for the models used in this project. A full Hugging Face id also works.
SHORTHAND = {
    "allmpnet": "sentence-transformers/all-mpnet-base-v2",   # Paper 3's choice
    "bge_base": "BAAI/bge-base-en-v1.5",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",       # cheap comparison
}

_LOADED = {}


def embed(texts, model="allmpnet"):
    """Return one normalized vector per text, as a numpy array (n, dim)."""
    name = SHORTHAND.get(model, model)
    if name not in _LOADED:
        from sentence_transformers import SentenceTransformer
        print(f"embeddings: loading {name} ...")
        _LOADED[name] = SentenceTransformer(name)
    return _LOADED[name].encode(list(texts), normalize_embeddings=True,
                                batch_size=256, show_progress_bar=False)
