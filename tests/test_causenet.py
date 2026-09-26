"""Tests for the device setting of causenet(). No test loads the model."""

import importlib

import pytest
import torch

from theoryminer.causenet import _pick_device


def test_cpu_gives_cpu():
    assert _pick_device("cpu") == "cpu"


def test_auto_follows_the_gpu():
    if torch.cuda.is_available():
        assert _pick_device("auto") == "cuda"
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
