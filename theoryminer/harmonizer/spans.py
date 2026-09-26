"""spans — small helpers for the construct spans.

tidy_span() repairs what the model tokenizer breaks when it decodes a
span: special tokens, wordpiece markers, spaces around apostrophes and
brackets, punctuation at the ends. It removes no word and changes no
word. causenet() applies it to every cause and effect span, so the span
is a substring of its sentence again.

collect_spans() accepts what the user has at hand: the relations from
causenet(), or a plain list of strings. It keeps the original span string
as the key of every result, so a span can always be traced back to its
relation.
"""

import re

_SPECIAL = re.compile(r"\[(CLS|SEP|PAD|UNK|MASK)\]")
_EDGE_LEFT = " \t\"'“”‘’`,.;:!?)]}"
_EDGE_RIGHT = " \t\"'“”‘’`,.;:!?([{"


def tidy_span(text):
    """Repair the decoding of one span. Keep every word.

    Examples:
        "society ' s desired values"      -> "society's desired values"
        "don ' t conflict with needs"     -> "don't conflict with needs"
        "[CLS] autonomy support is critical" -> "autonomy support is critical"
        "inte ##grative processes"        -> "integrative processes"
        "internalization ) is a goal"     -> "internalization) is a goal"
        "), and intrapersonal events"     -> "and intrapersonal events"
        "intrinsic motivation,"           -> "intrinsic motivation"
    """
    t = _SPECIAL.sub(" ", text)
    t = re.sub(r"\s+##", "", t)                    # join a wordpiece to its word
    t = t.replace("##", "")                        # a fragment at the start keeps its letters
    t = re.sub(r"\s+'\s*", "'", t)                 # society ' s -> society's ; don ' t -> don't
    t = re.sub(r"\s+([,.;:!?%)\]}])", r"\1", t)    # no space before closing punctuation
    t = re.sub(r"([(\[{])\s+", r"\1", t)           # no space after an opening bracket
    t = re.sub(r"\s+", " ", t)
    t = t.lstrip(_EDGE_LEFT).rstrip(_EDGE_RIGHT)
    if t.count("(") != t.count(")"):               # an unbalanced bracket is decoder debris
        t = t.replace("(", " ").replace(")", " ")
        t = re.sub(r"\s+", " ", t).strip(_EDGE_LEFT + _EDGE_RIGHT)
    return t


def collect_spans(items):
    """Return the unique spans in `items`, in first-seen order.

    `items` is a list of strings, or a list of relation dicts with
    "cause" and "effect" keys (the output of causenet).
    """
    seen = []
    for item in items:
        if isinstance(item, str):
            texts = [item]
        else:
            texts = [item["cause"], item["effect"]]
        for t in texts:
            t = t.strip()
            if t and t not in seen:
                seen.append(t)
    return seen
