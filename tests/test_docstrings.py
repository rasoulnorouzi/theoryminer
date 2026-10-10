"""Tests for the docstrings of the public functions (CLAUDE.md 6.5, rules 3 and 7). No model is loaded.

Each argument of a public function has a block under "Args:" with "Values:" and "Default".
Each value of a choice setting is in the docstring. A function that raises a ValueError
for a wrong argument has a "Raises:" section.
"""

import inspect
import re

import pytest

import theoryminer
from theoryminer import causenet as causenet_function
from theoryminer.download import papers
from theoryminer.harmonizer import cluster, embeddings, labels, pairwise, standardize, taxonomy

causenet_module = inspect.getmodule(causenet_function)

PUBLIC = ["harvest", "extract_dois", "extract_references", "download_papers", "causenet",
          "standardize_constructs", "standardize_groups", "pairwise_grouping", "clusterer", "label_groups",
          "causal_map", "draw_map", "save_map"]

# The choice settings: {function: {argument: the permitted values}}.
CHOICES = {
    "harvest": {"steps": list(theoryminer.STEPS)},
    "download_papers": {"sources": papers.ALL_SOURCES},
    "causenet": {"mode": list(causenet_module.MODES), "decision": causenet_module.DECISIONS,
                 "device": causenet_module.DEVICES},
    "pairwise_grouping": {"linkage": pairwise.LINKAGES, "embeddings": list(embeddings.SHORTHAND)},
    "clusterer": {"embeddings": list(embeddings.SHORTHAND)},
    "label_groups": {"by": labels.RULES},
    "standardize_constructs": {"strategy": taxonomy.STRATEGIES, "embeddings": list(embeddings.SHORTHAND)},
    "standardize_groups": {"name_by": standardize.NAME_RULES, "strategy": taxonomy.STRATEGIES,
                           "embeddings": list(embeddings.SHORTHAND)},
}

# The functions that raise a ValueError for a wrong argument.
RAISES = ["harvest", "extract_dois", "extract_references", "download_papers", "causenet", "standardize_constructs",
          "standardize_groups", "pairwise_grouping", "clusterer", "label_groups", "causal_map"]

# The start of one argument block: four spaces, the name, a colon.
RE_ARGUMENT = re.compile(r"^    (\w+):", re.M)


def argument_blocks(doc):
    """Return {argument: its text} from the "Args:" section of a docstring."""
    section = doc.split("Args:", 1)[1]
    section = re.split(r"\n(?:Returns|Raises|Example|Yields):", section)[0]
    starts = list(RE_ARGUMENT.finditer(section))
    blocks = {}
    for i, match in enumerate(starts):
        end = len(section)
        if i + 1 < len(starts):
            end = starts[i + 1].start()
        blocks[match.group(1)] = section[match.start():end]
    return blocks


@pytest.mark.parametrize("name", PUBLIC)
def test_every_argument_has_values_and_a_default(name):
    function = getattr(theoryminer, name)
    doc = inspect.getdoc(function)
    blocks = argument_blocks(doc)
    for argument in inspect.signature(function).parameters:
        assert argument in blocks, f"{name}(): the argument {argument!r} has no block under Args"
        assert "Values:" in blocks[argument], f"{name}({argument}=...): no 'Values:'"
        assert "Default" in blocks[argument], f"{name}({argument}=...): no 'Default'"


@pytest.mark.parametrize("name", sorted(CHOICES))
def test_every_choice_value_is_in_the_docstring(name):
    blocks = argument_blocks(inspect.getdoc(getattr(theoryminer, name)))
    for argument, values in CHOICES[name].items():
        for value in values:
            assert value in blocks[argument], f"{name}({argument}=...): the value {value!r} is missing"


@pytest.mark.parametrize("name", RAISES)
def test_a_function_that_raises_has_a_raises_section(name):
    doc = inspect.getdoc(getattr(theoryminer, name))
    assert "Raises:" in doc and "ValueError" in doc.split("Raises:", 1)[1]


def test_causenet_refuses_an_unknown_mode_before_it_loads_the_model():
    with pytest.raises(ValueError, match="unknown mode 'heuristic'"):
        theoryminer.causenet(["A causes B."], mode="heuristic")


def test_harvest_refuses_an_unknown_step_before_it_reads_a_pdf():
    with pytest.raises(ValueError, match="unknown step 'split_sentence'"):
        theoryminer.harvest("no_such_folder", steps=["split_sentence"])
