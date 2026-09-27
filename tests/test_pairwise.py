"""Tests for the linkage rules of pairwise_grouping(). No test loads a model.

The vectors are made from a chosen similarity matrix, so each test knows every cosine.
"""

import numpy as np
import pytest

from theoryminer.harmonizer.pairwise import _single_labels, _tree_labels, pairwise_grouping

# The example from the design talk: a is close to b and to c, but b and c are far apart.
#            a     b     c
COSINES = [[1.00, 0.80, 0.85],
           [0.80, 1.00, 0.40],
           [0.85, 0.40, 1.00]]


def vectors_with_cosines(cosines):
    """Return unit vectors whose pairwise cosines are the given matrix."""
    return np.linalg.cholesky(np.array(cosines))


def same_group(labels, i, j):
    return labels[i] == labels[j]


def test_the_vectors_have_the_chosen_cosines():
    vectors = vectors_with_cosines(COSINES)
    assert np.allclose(vectors @ vectors.T, COSINES)


def test_single_linkage_chains_b_and_c_through_a():
    labels = _single_labels(vectors_with_cosines(COSINES), 0.69)
    assert same_group(labels, 0, 1)
    assert same_group(labels, 0, 2)
    assert same_group(labels, 1, 2)         # b-c is 0.40, but a links them


def test_average_linkage_keeps_b_out():
    # a + c join first (0.85). b to {a, c}: mean (0.80 + 0.40) / 2 = 0.60 < 0.69.
    labels = _tree_labels(vectors_with_cosines(COSINES), 0.69, "average")
    assert same_group(labels, 0, 2)
    assert not same_group(labels, 0, 1)


def test_complete_linkage_keeps_b_out():
    labels = _tree_labels(vectors_with_cosines(COSINES), 0.69, "complete")
    assert same_group(labels, 0, 2)
    assert not same_group(labels, 0, 1)


def test_average_linkage_joins_b_when_the_mean_is_high_enough():
    # The mean cosine of b to {a, c} is 0.60, so a threshold of 0.55 lets b in.
    labels = _tree_labels(vectors_with_cosines(COSINES), 0.55, "average")
    assert len(set(labels)) == 1


def test_one_span_gives_one_group():
    assert _tree_labels(np.array([[1.0, 0.0]]), 0.69, "average").tolist() == [0]


def test_unknown_linkage_raises():
    with pytest.raises(ValueError, match="unknown linkage 'mean'"):
        pairwise_grouping(["a", "b"], linkage="mean")


def test_default_linkage_is_average():
    import inspect
    assert inspect.signature(pairwise_grouping).parameters["linkage"].default == "average"
