"""causenet — find cause-effect pairs in sentences.

One call does the full job:

    from theoryminer import harvest, causenet
    data = harvest("codes/raw_data/my_book.pdf")
    relations = causenet(data["sentences"])

The function wraps the SocioCausaNet model (rasoultilburg/SocioCausaNet).
It loads the model and the tokenizer once per session, picks the device,
and batches the input. It writes no files. Keep the returned list in a
variable; a full book takes long on CPU, so do not throw the result away.
"""

import time

from .harmonizer.spans import tidy_span

# The model loads once and stays in memory for the next calls.
_MODEL = None
_TOKENIZER = None
_DEVICE = None


def _load_model():
    """Load SocioCausaNet and its tokenizer. Keep them for later calls."""
    global _MODEL, _TOKENIZER, _DEVICE
    if _MODEL is None:
        import torch
        from transformers import AutoModel, AutoTokenizer
        print("causenet: loading rasoultilburg/SocioCausaNet ...")
        _MODEL = AutoModel.from_pretrained("rasoultilburg/SocioCausaNet",
                                           trust_remote_code=True)
        _TOKENIZER = AutoTokenizer.from_pretrained("rasoultilburg/SocioCausaNet",
                                                   trust_remote_code=True)
        _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        _MODEL.to(_DEVICE).eval()
        print("causenet: device =", _DEVICE)
    return _MODEL, _TOKENIZER


def causenet(sentences, threshold=0.8, mode="neural", decision="cls+span",
             batch_size=64):
    """Find cause-effect pairs in the sentences.

    Args:
        sentences: The sentence rows, as in harvest()["sentences"].
            A plain list of strings also works.
        threshold: Confidence needed to accept a relation (rel_threshold).
        mode: How the model links cause and effect: "neural", "auto",
            or "heuristic".
        decision: What makes a sentence causal: "cls+span", "cls_only",
            or "span_only".
        batch_size: Sentences per model call.

    Returns:
        A list of dicts, one per relation, with the keys:
        rel_id, sent_id, doc_id, page, cause, effect, sentence.
    """
    # Accept plain strings, so a quick test needs no harvest() call.
    rows = []
    for i, s in enumerate(sentences):
        if isinstance(s, str):
            rows.append({"doc_id": "input", "page": 0,
                         "sent_id": f"s{i:04d}", "clean": s})
        else:
            rows.append(s)

    model, tokenizer = _load_model()

    # Run the model in batches.
    preds = []
    t0 = time.time()
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        preds.extend(model.predict([r["clean"] for r in batch],
                                   tokenizer=tokenizer,
                                   rel_mode=mode,
                                   rel_threshold=threshold,
                                   cause_decision=decision))
        done = min(i + batch_size, len(rows))
        print(f"\r  {done:,}/{len(rows):,} sentences ({time.time() - t0:.0f}s)", end="")
    print()

    # Turn the predictions into flat relation rows with full provenance.
    # The model decodes a span from token ids, and the tokenizer breaks the
    # text: "society ' s", "[CLS] ...", "##egrative". tidy_span() repairs
    # that. It removes no word, so the span stays a substring of its sentence.
    relations = []
    n_causal = 0
    n_tidied = 0
    n_verbatim = 0
    for r, p in zip(rows, preds):
        if not p["causal"]:
            continue
        n_causal = n_causal + 1
        for k, rel in enumerate(p["relations"]):
            cause = tidy_span(rel["cause"])
            effect = tidy_span(rel["effect"])
            if cause != rel["cause"] or effect != rel["effect"]:
                n_tidied = n_tidied + 1
            sentence = r["clean"].lower()          # the model returns lowercase spans
            if cause.lower() in sentence and effect.lower() in sentence:
                n_verbatim = n_verbatim + 1
            relations.append({
                "rel_id": f"{r['sent_id']}r{k:02d}",
                "sent_id": r["sent_id"],
                "doc_id": r["doc_id"],
                "page": r.get("page", 0),
                "cause": cause,
                "effect": effect,
                "sentence": r["clean"],
            })

    print(f"causenet: {n_causal:,} causal sentences of {len(rows):,} | {len(relations):,} relations")
    if relations:
        print(f"  spans repaired after decoding: {n_tidied:,} | "
              f"both spans found verbatim in their sentence: {n_verbatim / len(relations):.0%}")
    return relations
