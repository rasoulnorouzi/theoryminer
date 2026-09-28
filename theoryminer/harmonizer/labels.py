"""labels — give a group of spans a label, without a taxonomy.

    from theoryminer.harmonizer import label_groups
    labelled = label_groups(clusters)                 # by="keywords", top=3: the default since 0.2.0

Use this module when your field has no thesaurus, or when the thesaurus
does not hold your constructs. The module loads no model and reads no
file. It uses the group dict alone.

Input, from pairwise_grouping() or clusterer():

    {span: {"group": int, "central": span}}

    span      the original construct text, as causenet returned it
    group     the id of the group; -1 marks a noise span from clusterer
    central   the medoid of the group: the member with the highest mean
              cosine to the other members

Output, one row per group:

    {group_id: {"central":  span,              the medoid, as it came in
                "size":     int,               number of members
                "members":  [span, ...],       every span of the group
                "keywords": [(word, score)],   best first, `top` of them
                "name":     str}}              the label, made by `by`

    The key is the group id. A noise span keeps its own text as the key,
    the same rule that standardize_groups uses.
"""

import collections
import math
import re

# Function words. They never enter a label. No span is changed.
STOPWORDS = set("""
a an the and or but nor so yet of in to for with on at from by about as into
through during before after above below between under over toward towards upon
is am are was were be been being has have had having do does did will shall
would should could might may can it its this that these those there here they
them their which what who whom whose when where how also more most less very
each every any some other such own same than then just only not no
""".split())

# The three ways to make a label.
RULES = ["medoid", "keywords", "both"]


def _content_words(text):
    """Return the content words of one span, lowercased."""
    words = re.findall(r"[a-z][a-z'-]+", text.lower())
    return [word for word in words if word not in STOPWORDS]


def _label(spans, central, keywords, by):
    """Make the label of one group. A group of one takes its member."""
    if len(spans) == 1:
        return spans[0]
    words = " ".join(word for word, _ in keywords)
    if by == "medoid":
        return central
    if by == "keywords":
        return words
    return f"{central} | {words}"


def label_groups(groups: dict, by: str = "keywords", top: int = 3) -> dict:
    """Label each group of spans. No taxonomy. No model.

    Args:
        groups: the dict from pairwise_grouping() or clusterer():
            {span: {"group": int, "central": span}}.
        by: how the label is made.
            "medoid"   the central member, one span.
            "keywords" the `top` keywords, joined by a space (the default since 0.2.0;
                       "both" before).
            "both"     the medoid, a pipe, then the keywords.
        top: how many keywords to keep for each group.

    Returns:
        {group_id: {"central", "size", "members", "keywords", "name"}}.
        See the module docstring for the shape of each field.

    How the keywords are ranked:
        One group is one document. The score of a word is

            (count in the group / words in the group)
            * log(1 + groups / groups that hold the word)

        The first factor rewards a word that the members repeat. The
        second factor punishes a word that every group holds. So
        "well-being" wins in its group, and "increased" sinks, although
        the members repeat both. This is class-based TF-IDF.

    Rules:
        A group with one member takes the member as its label. Nothing
        can be ranked there, so no size knob is needed.
        Function words never enter a label. One short list in the module
        holds them. The list serves the label only.
        The label is for the graph node and for the reader. The spans
        stay as they are; no function removes a word from a span.
        The scores come back with the keywords, so a reader can see why
        the function chose a label.

    Example:
        >>> clusters = clusterer(relations)
        >>> labelled = label_groups(clusters, by="keywords", top=3)
        >>> labelled[179]
        {"central": "increased well-being and health outcomes", "size": 8,
         "members": ["greater psychological health and well-being", ...],
         "keywords": [("well-being", 1.597), ("health", 0.582),
                      ("increased", 0.47)],
         "name": "well-being health increased"}
    """
    if by not in RULES:
        raise ValueError(f"unknown by {by!r}; choose one of {RULES}")

    # Collect the members of each group. A noise span makes a group of one.
    members = {}
    for span, group in groups.items():
        key = span if group["group"] == -1 else group["group"]
        members.setdefault(key, []).append(span)

    # Count the groups that hold each word. A word in every group is weak.
    groups_with_word = collections.Counter()
    for spans in members.values():
        words = set()
        for span in spans:
            words.update(_content_words(span))
        groups_with_word.update(words)
    n_groups = len(members)

    result = {}
    for key, spans in members.items():
        # How often the members of this group use each word.
        counts = collections.Counter()
        for span in spans:
            counts.update(_content_words(span))
        n_words = sum(counts.values()) or 1

        # Frequency in the group, times rarity across the groups.
        scores = {}
        for word, count in counts.items():
            rarity = math.log(1 + n_groups / groups_with_word[word])
            scores[word] = count / n_words * rarity
        best = sorted(scores.items(), key=lambda item: -item[1])[:top]
        keywords = [(word, round(score, 3)) for word, score in best]

        central = groups[spans[0]]["central"]
        result[key] = {"central": central,
                       "size": len(spans),
                       "members": spans,
                       "keywords": keywords,
                       "name": _label(spans, central, keywords, by)}

    n_multi = sum(1 for row in result.values() if row["size"] > 1)
    print(f"labels: {len(result):,} groups labelled by {by} | "
          f"{n_multi:,} with 2 or more members")
    return result
