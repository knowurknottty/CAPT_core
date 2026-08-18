"""CAPT-UPG-023 chunk-stability benchmark tests."""

from benchmarks.chunk_stability import (
    chunk_summary,
    compare_chunk_identity,
    compare_chunkers,
    fixed_size_chunks,
)


def delimiter_chunker(data: bytes):
    return [part for part in data.split(b"|") if part]


def test_content_defined_identity_can_survive_prefix_insertion_in_probe_fixture():
    before = b"AAAA|BBBB|CCCC|DDDD"
    after = b"ZZZZ|AAAA|BBBB|CCCC|DDDD"
    result = compare_chunkers(
        before,
        after,
        fixed_size=4,
        content_defined_chunker=delimiter_chunker,
        content_defined_name="delimiter_fixture",
    )
    fixed_reuse = result["fixed"]["stability"]["byteReuseRatio"]
    cdc_reuse = result["contentDefined"]["stability"]["byteReuseRatio"]
    assert cdc_reuse > fixed_reuse
    assert result["llmPrefixCacheClaim"] is False
    assert result["providerCacheEvidence"] is None


def test_chunk_identity_metrics_handle_duplicates_by_multiplicity():
    before = [b"same", b"same", b"other"]
    after = [b"same", b"different", b"same"]
    metrics = compare_chunk_identity(before, after)
    assert metrics["reusedChunkCount"] == 2
    assert metrics["reusedChunkBytes"] == 8
    assert metrics["llmPrefixCacheClaim"] is False


def test_fixed_size_chunking_and_summary_are_deterministic():
    data = b"abcdefghij"
    chunks = fixed_size_chunks(data, 4)
    assert chunks == [b"abcd", b"efgh", b"ij"]
    first = chunk_summary(chunks)
    second = chunk_summary(chunks)
    assert first == second
    assert first["chunkCount"] == 3
    assert first["totalBytes"] == len(data)
