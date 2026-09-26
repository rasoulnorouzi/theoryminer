"""Tests for tidy_span() and collect_spans(). No model is loaded."""

from theoryminer.harmonizer.spans import collect_spans, tidy_span


def test_tidy_span_repairs_the_decoding_and_keeps_every_word():
    cases = {
        "society ' s desired values": "society's desired values",
        "don ' t conflict with needs": "don't conflict with needs",
        "[CLS] autonomy support is critical": "autonomy support is critical",
        "inte ##grative processes": "integrative processes",
        "intrinsic motivation,": "intrinsic motivation",
        "the lack of autonomy": "the lack of autonomy",
    }
    for raw, expected in cases.items():
        assert tidy_span(raw) == expected


def test_collect_spans_from_relations_keeps_the_first_seen_order():
    relations = [{"cause": "autonomy", "effect": "motivation"},
                 {"cause": "motivation", "effect": "well-being"}]
    assert collect_spans(relations) == ["autonomy", "motivation", "well-being"]


def test_collect_spans_from_strings_removes_blanks_and_repeats():
    assert collect_spans(["  autonomy ", "autonomy", "", "competence"]) == ["autonomy", "competence"]
