"""CAPT-UPG-022 structural hashing tests using Tree-sitter-like fake nodes."""

from benchmarks.tree_sitter_hashing import compare_hashes, hash_tree


class Node:
    def __init__(self, kind, start, end, children=None, named=True):
        self.type = kind
        self.start_byte = start
        self.end_byte = end
        self.children = list(children or [])
        self.is_named = named


def test_coordinates_do_not_enter_normalized_hash_when_tree_and_leaf_text_match():
    source = b"alpha"
    one = Node("identifier", 0, 5)
    # A second parser could report different coordinates only if source mapping
    # changed; hash_tree intentionally uses coordinates only to obtain leaf text.
    two = Node("identifier", 0, 5)
    first = hash_tree(one, source)
    second = hash_tree(two, source)
    assert first["rootDigest"] == second["rootDigest"]
    assert first["coordinateSensitive"] is False
    assert first["behavioralEquivalenceClaim"] is False
    assert first["semanticEquivalenceClaim"] is False


def test_leaf_identifier_change_changes_structural_content_hash():
    before_source = b"alpha"
    after_source = b"bravo"
    before = hash_tree(Node("identifier", 0, 5), before_source)
    after = hash_tree(Node("identifier", 0, 5), after_source)
    delta = compare_hashes(before, after)
    assert delta["rootChanged"] is True
    assert [] in delta["changedSubtreePaths"]
    assert delta["semanticEquivalenceClaim"] is False


def test_comment_nodes_are_excluded_from_structural_hash():
    source_a = b"value#old"
    source_b = b"value#new"
    root_a = Node("module", 0, len(source_a), [
        Node("identifier", 0, 5),
        Node("comment", 5, len(source_a)),
    ])
    root_b = Node("module", 0, len(source_b), [
        Node("identifier", 0, 5),
        Node("comment", 5, len(source_b)),
    ])
    before = hash_tree(root_a, source_a)
    after = hash_tree(root_b, source_b)
    assert before["rootDigest"] == after["rootDigest"]
    assert before["commentsIncluded"] is False


def test_changed_named_subtree_is_visible():
    source_a = b"foobar"
    source_b = b"foobaz"
    root_a = Node("module", 0, 6, [Node("identifier", 0, 3), Node("identifier", 3, 6)])
    root_b = Node("module", 0, 6, [Node("identifier", 0, 3), Node("identifier", 3, 6)])
    before = hash_tree(root_a, source_a)
    after = hash_tree(root_b, source_b)
    delta = compare_hashes(before, after)
    assert [1] in delta["changedSubtreePaths"]
    assert [0] in delta["unchangedSubtreePaths"]
