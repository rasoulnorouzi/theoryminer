"""Harmonization of construct spans: three routes, one shape of result.

    from theoryminer.harmonizer import (
        standardize_constructs, standardize_groups, pairwise_grouping, clusterer, label_groups)
"""

from .cluster import clusterer
from .labels import label_groups
from .pairwise import pairwise_grouping
from .standardize import standardize_constructs, standardize_groups
