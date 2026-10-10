"""Public functions of the theoryminer pipeline.

Import everything from this package root:

    from theoryminer import harvest
"""

import sys
from importlib.metadata import PackageNotFoundError, version

# The version comes from pyproject.toml through the installed package metadata.
try:
    __version__ = version("theoryminer")
except PackageNotFoundError:        # the code runs from a folder, not installed
    __version__ = "unknown"

from .prepare.harvest import DEFAULT_STEPS, STEPS, harvest
from .causenet import causenet
from .prepare.dois import extract_dois, extract_references
from .harmonizer import (standardize_constructs, standardize_groups, pairwise_grouping,
                         clusterer, label_groups)
from .causal_map import causal_map, draw_map, save_map
from .download import download_papers

# The module paths before 0.3.0: theoryminer.harvest and theoryminer.dois. Old code and notebooks
# that import them get the modules from their new place, prepare/. The paths go away in 0.4.0.
# An alias in sys.modules, not a file: a file theoryminer/harvest.py would replace the function
# theoryminer.harvest with the module when old code imports it.
sys.modules[__name__ + ".harvest"] = sys.modules[__name__ + ".prepare.harvest"]
sys.modules[__name__ + ".dois"] = sys.modules[__name__ + ".prepare.dois"]

# The public names. An editor suggests these after "theoryminer.".
__all__ = ["harvest", "extract_dois", "extract_references", "download_papers", "causenet",
           "standardize_constructs", "standardize_groups", "pairwise_grouping", "clusterer", "label_groups",
           "causal_map", "draw_map", "save_map", "DEFAULT_STEPS", "STEPS", "__version__"]
