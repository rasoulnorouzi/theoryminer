"""Tests for the device setting of causenet(). No test loads the model."""

import importlib

import pytest
import torch

from theoryminer.causenet import _pick_device


def test_cpu_gives_cpu():
    assert _pick_device("cpu") == "cpu"


def test_auto_follows_the_gpu():
    # The same order as the code: an NVIDIA GPU, else an Apple GPU (the macOS runner has one), else the CPU.
    if torch.cuda.is_available():
        assert _pick_device("auto") == "cuda"
    elif torch.backends.mps.is_available():
        assert _pick_device("auto") == "mps"
    else:
        assert _pick_device("auto") == "cpu"


def test_unknown_device_raises():
    with pytest.raises(ValueError, match="unknown device 'gpu'"):
        _pick_device("gpu")


def test_cuda_without_gpu_raises():
    if torch.cuda.is_available():
        pytest.skip("this machine has a GPU")
    with pytest.raises(ValueError, match="torch sees no GPU"):
        _pick_device("cuda")


def test_mps_without_apple_gpu_raises():
    if torch.backends.mps.is_available():
        pytest.skip("this machine has an Apple GPU")
    with pytest.raises(ValueError, match="no Apple GPU"):
        _pick_device("mps")


class FakeModel:
    """A stand-in for SocioCausaNet that fails on the Apple GPU, like a missing torch operation."""

    def __init__(self):
        self.device = "mps"

    def to(self, device):
        self.device = device
        return self

    def predict(self, texts, **settings):
        if self.device == "mps":
            raise NotImplementedError("this operation is not ready on mps")
        return [{"causal": False, "relations": []} for text in texts]


def test_failure_on_apple_gpu_moves_the_model_to_the_cpu(monkeypatch):
    module = importlib.import_module("theoryminer.causenet")
    monkeypatch.setattr(module, "_MODEL", FakeModel())
    monkeypatch.setattr(module, "_TOKENIZER", object())
    monkeypatch.setattr(module, "_DEVICE", "mps")
    preds = module._predict_batch(["one sentence"], "neural", 0.8, "cls+span")
    assert preds == [{"causal": False, "relations": []}]
    assert module._DEVICE == "cpu"


def test_default_decision_is_span_only():
    # Changed in 0.2.0: a cause span and an effect span make a sentence causal.
    import inspect
    from theoryminer import causenet
    assert inspect.signature(causenet).parameters["decision"].default == "span_only"


def test_avoid_ambiguous_is_on_by_default():
    import inspect
    from theoryminer import causenet
    assert inspect.signature(causenet).parameters["avoid_ambiguous"].default is True


def test_avoid_ambiguous_skips_pointer_spans_and_keeps_the_rel_ids():
    from theoryminer.causenet import _sentence_relations
    row = {"sent_id": "d000p0001s000", "doc_id": "paper", "page": 1,
           "clean": "This harms health, and job insecurity increases stress."}
    pred = {"causal": True, "relations": [{"cause": "this", "effect": "health"},
                                          {"cause": "job insecurity", "effect": "stress"}]}
    counts = {"tidied": 0, "verbatim": 0, "ambiguous": []}
    kept = _sentence_relations(row, pred, True, counts)
    assert [r["cause"] for r in kept] == ["job insecurity"]
    assert kept[0]["rel_id"] == "d000p0001s000r01"          # the number of the skipped relation stays free
    assert counts["ambiguous"] == ["this -> health"]
    counts = {"tidied": 0, "verbatim": 0, "ambiguous": []}
    assert len(_sentence_relations(row, pred, False, counts)) == 2


def test_the_pointer_rule():
    from theoryminer.harmonizer.spans import is_vague_span
    for span in ["this", "it", "such things", "these factors", "the latter"]:
        assert is_vague_span(span), span
    for span in ["job insecurity", "these three social support measures", "theory of mind"]:
        assert not is_vague_span(span), span


def test_a_relation_with_an_empty_span_is_skipped_and_counted():
    from theoryminer.causenet import _sentence_relations
    row = {"sent_id": "s1", "doc_id": "paper", "page": 1, "clean": "Stress harms health."}
    pred = {"causal": True, "relations": [{"cause": "[CLS]", "effect": "health"},
                                          {"cause": "stress", "effect": "health"}]}
    counts = {"tidied": 0, "verbatim": 0, "empty": 0, "ambiguous": []}
    kept = _sentence_relations(row, pred, True, counts)
    assert [r["rel_id"] for r in kept] == ["s1r01"]
    assert counts["empty"] == 1
