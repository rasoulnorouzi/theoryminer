"""Public functions of the theoryminer pipeline.

Import everything from this package root:

    from theoryminer import harvest
"""

from importlib.metadata import PackageNotFoundError, version

# The version comes from pyproject.toml through the installed package metadata.
try:
    __version__ = version("theoryminer")
except PackageNotFoundError:        # the code runs from a folder, not installed
    __version__ = "unknown"

from .harvest import DEFAULT_STEPS, STEPS, harvest
from .causenet import causenet
from .dois import extract_dois
from .harmonizer import (standardize_constructs, standardize_groups, pairwise_grouping,
                         clusterer, label_groups)
from .causal_map import causal_map, draw_map, save_map
