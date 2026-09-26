"""Tests for the device setting of causenet(). No test loads the model."""

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
