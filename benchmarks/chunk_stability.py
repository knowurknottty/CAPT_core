#!/usr/bin/env python3
"""Content-defined chunk stability benchmark (CAPT-UPG-023).

Measures chunk identity reuse/edit locality. This module makes no claim about
LLM/provider prefix-cache hit rates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

Chunker = Callable[[bytes], Sequence[bytes]]


def _digest(chunk: bytes) -> str:
    return "sha256:" + hashlib.sha256(chunk).hexdigest()


def fixed_size_chunks(data: bytes, size: int = 4096) -> List[bytes]:
    if size <= 0:
        raise ValueError("fixed chunk size must be > 0")
    return [data[i:i + size] for i in range(0, len(data), size)] or [b""]


def optional_fastcdc_chunks(data: bytes, min_size: int = 2048, avg_size: int = 4096, max_size: int = 8192) -> Dict[str, Any]:
    """Run an optional installed FastCDC adapter without making it a dependency."""
    try:
        from fastcdc import fastcdc  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "dependency_unavailable",
            "dependency": "fastcdc",
            "detail": type(exc).__name__,
            "chunks": [],
            "llmPrefixCacheClaim": False,
        }
    try:
        raw = list(fastcdc(data, min_size=min_size, avg_size=avg_size, max_size=max_size))
        chunks = []
        for item in raw:
            offset = int(getattr(item, "offset"))
            length = int(getattr(item, "length"))
            chunks.append(data[offset:offset + length])
        return {"status": "ok", "chunks": chunks, "llmPrefixCacheClaim": False}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "adapter_failed",
            "dependency": "fastcdc",
            "detail": type(exc).__name__,
            "chunks": [],
            "llmPrefixCacheClaim": False,
        }


def chunk_summary(chunks: Sequence[bytes]) -> Dict[str, Any]:
    lengths = [len(chunk) for chunk in chunks]
    digests = [_digest(chunk) for chunk in chunks]
    counts = Counter(digests)
    return {
        "chunkCount": len(chunks),
        "totalBytes": sum(lengths),
        "minChunkBytes": min(lengths) if lengths else 0,
        "maxChunkBytes": max(lengths) if lengths else 0,
        "meanChunkBytes": 0.0 if not lengths else float(sum(lengths)) / float(len(lengths)),
        "uniqueChunkCount": len(counts),
        "duplicateChunkCount": sum(max(0, count - 1) for count in counts.values()),
        "digests": digests,
        "lengths": lengths,
    }


def compare_chunk_identity(before_chunks: Sequence[bytes], after_chunks: Sequence[bytes]) -> Dict[str, Any]:
    before_pairs = Counter((_digest(chunk), len(chunk)) for chunk in before_chunks)
    after_pairs = Counter((_digest(chunk), len(chunk)) for chunk in after_chunks)
    reused_count = 0
    reused_bytes = 0
    for pair, before_count in before_pairs.items():
        count = min(before_count, after_pairs.get(pair, 0))
        reused_count += count
        reused_bytes += count * pair[1]
    before_total = sum(len(chunk) for chunk in before_chunks)
    after_total = sum(len(chunk) for chunk in after_chunks)
    denominator = max(before_total, after_total)
    reuse_ratio = 0.0 if denominator == 0 else float(reused_bytes) / float(denominator)
    after_count = len(after_chunks)
    churn = 0.0 if after_count == 0 else 1.0 - (float(reused_count) / float(after_count))
    return {
        "reusedChunkCount": reused_count,
        "reusedChunkBytes": reused_bytes,
        "byteReuseRatio": reuse_ratio,
        "afterChunkChurnRatio": churn,
        "llmPrefixCacheClaim": False,
    }


def compare_chunkers(
    before: bytes,
    after: bytes,
    *,
    fixed_size: int = 4096,
    content_defined_chunker: Chunker,
    content_defined_name: str = "content_defined",
) -> Dict[str, Any]:
    fixed_before = fixed_size_chunks(before, fixed_size)
    fixed_after = fixed_size_chunks(after, fixed_size)
    cdc_before = list(content_defined_chunker(before))
    cdc_after = list(content_defined_chunker(after))
    return {
        "schemaVersion": "1.0.0",
        "kind": "ChunkStabilityComparison",
        "fixed": {
            "name": "fixed_%d" % fixed_size,
            "before": chunk_summary(fixed_before),
            "after": chunk_summary(fixed_after),
            "stability": compare_chunk_identity(fixed_before, fixed_after),
        },
        "contentDefined": {
            "name": content_defined_name,
            "before": chunk_summary(cdc_before),
            "after": chunk_summary(cdc_after),
            "stability": compare_chunk_identity(cdc_before, cdc_after),
        },
        "llmPrefixCacheClaim": False,
        "providerCacheEvidence": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CAPT content-defined chunk stability probe")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--fixed-size", type=int, default=4096)
    parser.add_argument("--min-size", type=int, default=2048)
    parser.add_argument("--avg-size", type=int, default=4096)
    parser.add_argument("--max-size", type=int, default=8192)
    args = parser.parse_args()

    before = args.before.read_bytes()
    after = args.after.read_bytes()
    before_fast = optional_fastcdc_chunks(before, args.min_size, args.avg_size, args.max_size)
    after_fast = optional_fastcdc_chunks(after, args.min_size, args.avg_size, args.max_size)
    if before_fast["status"] != "ok" or after_fast["status"] != "ok":
        print(json.dumps({
            "status": "fastcdc_unavailable",
            "before": {k: v for k, v in before_fast.items() if k != "chunks"},
            "after": {k: v for k, v in after_fast.items() if k != "chunks"},
            "llmPrefixCacheClaim": False,
        }, indent=2, sort_keys=True))
        return 2

    result = {
        "schemaVersion": "1.0.0",
        "kind": "FastCDCStabilityComparison",
        "fixed": {
            "before": chunk_summary(fixed_size_chunks(before, args.fixed_size)),
            "after": chunk_summary(fixed_size_chunks(after, args.fixed_size)),
            "stability": compare_chunk_identity(
                fixed_size_chunks(before, args.fixed_size),
                fixed_size_chunks(after, args.fixed_size),
            ),
        },
        "fastcdc": {
            "before": chunk_summary(before_fast["chunks"]),
            "after": chunk_summary(after_fast["chunks"]),
            "stability": compare_chunk_identity(before_fast["chunks"], after_fast["chunks"]),
        },
        "llmPrefixCacheClaim": False,
        "providerCacheEvidence": None,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
