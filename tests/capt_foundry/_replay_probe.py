"""Fresh-process replay probe.

Opens an existing Foundry database in a NEW interpreter and re-derives every
digest. Used by test_lifecycle.py so replay is proven across a real process
boundary rather than merely across a new connection in the same process.

Prints one JSON object to stdout. Exit 0 on success.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capt_foundry import (
    AliasRegistry,
    CorpusRegistry,
    EntityRegistry,
    FoundryStore,
)
from capt_foundry.publisher import ArtifactPublisher
from capt_foundry.seal_export import SealAssetExporter

STAMP = "2026-08-03T00:00:00Z"


def main() -> int:
    db = sys.argv[1]
    store = FoundryStore(db)
    entities = EntityRegistry(store, clock=lambda: STAMP)
    aliases = AliasRegistry(store, entities, clock=lambda: STAMP)
    corpora = CorpusRegistry(store, clock=lambda: STAMP)
    publisher = ArtifactPublisher(store, entities, aliases, corpora, clock=lambda: STAMP)
    exporter = SealAssetExporter(entities, aliases, corpora, clock=lambda: STAMP)

    stored = publisher.get("asset.ada")
    verification = publisher.verify("asset.ada")
    out = {
        "schema_version": store.schema_version,
        "manifest_hash": stored["manifest_hash"],
        "manifest": stored["manifest"],
        "corpus_digest": corpora.require("c.notes")["manifest_digest"],
        "export_digest": exporter.export(exported_at=STAMP)["content_digest"],
        "payload_digest_matches": verification["payload_digest_matches"],
        "alias_resolves": aliases.resolve("A. A. Lovelace")["entity_id"],
    }
    store.close()
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
