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

is_vague_span() finds a span that only points to text in another sentence:
"this", "it", "such things". causenet(avoid_ambiguous=True) skips a relation
with such a span.
"""

import re

# A span that starts with one of these words, and is short, only points to text in another sentence.
VAGUE_STARTS = set("this that these those it its they them their he she we you such which what "
                   "both either neither former latter".split())
MAX_VAGUE_WORDS = 3   # a longer span ("these three social support measures") carries its own meaning

# The article at the start of a span, for the vague test: "the latter" -> "latter".
# No match: "theory of mind" (the pattern needs a space after the word)
RE_ARTICLE = re.compile(r"^(?:the|a|an)\s+", re.I)

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


def is_vague_span(span):
    """Return True when the span only points to text in another sentence.

    The rule: after an article ("the", "a", "an"), the span starts with a pointer
    word (VAGUE_STARTS) and has at most MAX_VAGUE_WORDS words.

    Example:
        >>> is_vague_span("this"), is_vague_span("such things"), is_vague_span("the latter")
        (True, True, True)
        >>> is_vague_span("these three social support measures"), is_vague_span("social support")
        (False, False)
    """
    words = RE_ARTICLE.sub("", span.strip()).lower().split()
    if not words or len(words) > MAX_VAGUE_WORDS:
        return False
    return words[0] in VAGUE_STARTS
