"""causenet — find cause-effect pairs in sentences.

One call does the full job:

    from theoryminer import harvest, causenet
    data = harvest("raw_data/my_book.pdf")
    relations = causenet(data["sentences"])

The function wraps the SocioCausaNet model (rasoultilburg/SocioCausaNet).
It loads the model and the tokenizer once per session, puts the model on
the device you ask for ("auto", "cpu", "cuda" or "mps"), and batches the input.
It writes no files. Keep the returned list in a variable: a full book takes
long on a CPU, so do not throw the result away.
"""

import time

from .harmonizer.spans import is_vague_span, tidy_span

# The permitted values of the device setting.
# "auto" tries an NVIDIA GPU ("cuda"), then an Apple GPU ("mps"), then the CPU.
DEVICES = ["auto", "cpu", "cuda", "mps"]

# The model loads once and stays in memory for the next calls.
_MODEL = None
_TOKENIZER = None
_DEVICE = None


def _mps_available():
    """Return True when torch can use the GPU of an Apple Silicon Mac (MPS)."""
    import torch
    mps = getattr(torch.backends, "mps", None)
    if mps is None:
        return False
    return mps.is_available()


def _pick_device(device):
    """Return the torch device for the device setting: "cpu", "cuda" or "mps".

    Args:
        device: "auto", "cpu", "cuda" or "mps". "auto" gives "cuda" when torch
            can see an NVIDIA GPU, else "mps" on an Apple Silicon Mac, else "cpu".

    Returns:
        "cpu", "cuda" or "mps".

    Raises:
        ValueError: The setting is unknown, or torch cannot see the GPU that was asked for.

    Example:
        >>> _pick_device("cpu")
        'cpu'
    """
    import torch
    if device not in DEVICES:
        raise ValueError(f"unknown device {device!r}; choose one of {DEVICES}")
    if device == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if _mps_available():
            return "mps"
        return "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("device 'cuda' was asked for, but torch sees no GPU; "
                         "use device='cpu' or device='auto'")
    if device == "mps" and not _mps_available():
        raise ValueError("device 'mps' was asked for, but torch sees no Apple GPU; "
                         "use device='cpu' or device='auto'")
    return device


def _load_model(device="auto"):
    """Load SocioCausaNet and its tokenizer once, and put the model on the device.

    The first call loads the model. A later call with another device moves
    the model that is already in memory. It does not load it again.

    Args:
        device: "auto", "cpu", "cuda" or "mps", as in causenet().

    Returns:
        (model, tokenizer).
    """
    global _MODEL, _TOKENIZER, _DEVICE
    wanted = _pick_device(device)

    if _MODEL is None:
        from transformers import AutoModel, AutoTokenizer
        print("causenet: loading rasoultilburg/SocioCausaNet ...")
        _MODEL = AutoModel.from_pretrained("rasoultilburg/SocioCausaNet",
                                           trust_remote_code=True)
        _TOKENIZER = AutoTokenizer.from_pretrained("rasoultilburg/SocioCausaNet",
                                                   trust_remote_code=True)
        _MODEL.eval()

    # The model's predict() sends each batch to the device of the model itself.
    if wanted != _DEVICE:
        _MODEL.to(wanted)
        _DEVICE = wanted
        print("causenet: device =", _DEVICE)
    return _MODEL, _TOKENIZER


def _run_model(texts, mode, threshold, decision):
    """Run SocioCausaNet on a list of texts. Return one prediction dict per text."""
    return _MODEL.predict(texts, tokenizer=_TOKENIZER, rel_mode=mode,
                          rel_threshold=threshold, cause_decision=decision)


def _predict_batch(texts, mode, threshold, decision):
    """Run the model on one batch. If it fails on an Apple GPU, move to the CPU and run again.

    Some torch operations do not work on the Apple GPU (MPS) yet. The run must
    not stop for that reason. So the model moves to the CPU once, and it stays
    there for the rest of the session. An error on another device goes up as usual.
    """
    try:
        return _run_model(texts, mode, threshold, decision)
    except (RuntimeError, NotImplementedError):
        if _DEVICE != "mps":
            raise
    print("\ncausenet: the model failed on the Apple GPU (mps); it runs on the cpu from now on")
    _load_model("cpu")
    return _run_model(texts, mode, threshold, decision)


def _is_ambiguous(cause, effect):
    """Return True when the cause or the effect only points to another sentence ("this", "it", "such things").

    Example:
        >>> _is_ambiguous("this", "stress"), _is_ambiguous("job insecurity", "stress")
        (True, False)
    """
    return is_vague_span(cause) or is_vague_span(effect)


def _sentence_relations(row, pred, avoid_ambiguous, counts):
    """Turn the prediction for one causal sentence into relation dicts. Update the counts in place.

    The model decodes a span from token ids, and the tokenizer breaks the text:
    "society ' s", "[CLS] ...", "##egrative". tidy_span() repairs that. It removes
    no word, so the span stays a substring of its sentence. A span that is empty after
    the repair (the model decoded only special tokens) is decoding debris: the relation is
    skipped and counted. A skipped relation keeps its number k, so the rel_ids do not change.
    """
    relations = []
    sentence = row["clean"].lower()          # the model returns lowercase spans
    for k, rel in enumerate(pred["relations"]):
        cause = tidy_span(rel["cause"])
        effect = tidy_span(rel["effect"])
        if cause != rel["cause"] or effect != rel["effect"]:
            counts["tidied"] += 1
        if not cause.strip() or not effect.strip():
            counts["empty"] += 1
            continue
        if avoid_ambiguous and _is_ambiguous(cause, effect):
            counts["ambiguous"].append(f"{cause} -> {effect}")
            continue
        if cause.lower() in sentence and effect.lower() in sentence:
            counts["verbatim"] += 1
        relations.append({"rel_id": f"{row['sent_id']}r{k:02d}", "sent_id": row["sent_id"],
                          "doc_id": row["doc_id"], "page": row.get("page", 0),
                          "cause": cause, "effect": effect, "sentence": row["clean"]})
    return relations


def causenet(sentences: list, threshold: float = 0.8, mode: str = "neural", decision: str = "span_only",
             batch_size: int = 64, device: str = "auto", avoid_ambiguous: bool = True) -> list[dict]:
    """Find cause-effect pairs in the sentences.

    Args:
        sentences: The sentence rows, as in harvest()["sentences"].
            A plain list of strings also works.
        threshold: Confidence needed to accept a relation (rel_threshold).
        mode: How the model links cause and effect: "neural", "auto",
            or "heuristic".
        decision: What makes a sentence causal: "span_only" (the default since
            0.2.0: a cause span and an effect span are enough), "cls+span"
            (also the sentence classifier must say causal; the default before
            0.2.0), or "cls_only".
        batch_size: Sentences per model call. On a GPU a larger value is
            usually faster. Lower it after a CUDA "out of memory" error.
        device: Where the model runs: "auto" (an NVIDIA GPU, else an Apple GPU,
            else the CPU), "cpu", "cuda" or "mps". If the model fails on an
            Apple GPU, it moves to the CPU and the run goes on.
        avoid_ambiguous: True (the default) skips a relation whose cause or effect
            only points to another sentence: "this", "it", "such things" (the rule
            is harmonizer.spans.is_vague_span). The summary prints the count and
            examples. False keeps every relation.

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

    _load_model(device)

    # Run the model in batches.
    preds = []
    t0 = time.time()
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        texts = [r["clean"] for r in batch]
        preds.extend(_predict_batch(texts, mode, threshold, decision))
        done = min(i + batch_size, len(rows))
        print(f"\r  {done:,}/{len(rows):,} sentences ({time.time() - t0:.0f}s)", end="")
    print()

    # Turn the predictions into flat relation rows with full provenance.
    relations = []
    n_causal = 0
    counts = {"tidied": 0, "verbatim": 0, "empty": 0, "ambiguous": []}
    for r, p in zip(rows, preds):
        if not p["causal"]:
            continue
        n_causal = n_causal + 1
        relations.extend(_sentence_relations(r, p, avoid_ambiguous, counts))

    print(f"causenet: {n_causal:,} causal sentences of {len(rows):,} | {len(relations):,} relations")
    if relations:
        print(f"  spans repaired after decoding: {counts['tidied']:,} | "
              f"both spans found verbatim in their sentence: {counts['verbatim'] / len(relations):.0%}")
    if counts["empty"]:
        print(f"  skipped: {counts['empty']:,} relations with an empty span after decoding")
    if counts["ambiguous"]:
        examples = "; ".join(counts["ambiguous"][:3])
        print(f"  skipped (avoid_ambiguous=True): {len(counts['ambiguous']):,} relations with a pointer span, "
              f"for example: {examples}")
    return relations
