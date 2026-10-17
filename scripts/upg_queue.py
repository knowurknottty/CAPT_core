#!/usr/bin/env python3
"""Work-queue scheduler for CAPT upgrade campaigns (stdlib only, Python >= 3.10).

The backlog JSON is the single shared state for every agent. This tool:

* validates the backlog (schema, unique ids, known dependencies, acyclic
  graph, referenced paths exist unless declared under ``creates``);
* computes the *ready* set: open items whose dependencies are merged and whose
  file footprint does not overlap any in-flight item (to avoid merge conflicts);
* performs guarded status transitions with an append-only history, enforcing
  separation of duties (the claimant may never mark its own item merged).

Concurrency model
-----------------
Local agents: every mutation takes an exclusive ``fcntl`` lock on a sidecar
lock file and writes atomically (temp file + fsync + ``os.replace``).

Distributed agents: the backlog lives in git. A mutation is a commit; a
rejected (non-fast-forward) push means another agent won. Fetch, rebase,
re-run ``ready``/``claim``. ``--expect-status`` lets a caller assert the state
it observed, so a stale view fails loudly instead of overwriting.

Exit codes: 0 success, 1 validation/transition refusal, 2 usage or I/O error.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import fcntl
import json
import os
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

DEFAULT_BACKLOG = Path("docs/upgrade-campaign/capt_upg_025_backlog.json")

TIERS = ("P0", "P1", "P2", "P3")
KINDS = frozenset({"hole", "weak_spot", "upgrade", "novel"})
PROVENANCE = frozenset({"V", "V-code", "R", "P"})
ROLES = frozenset({"implementer", "adversary", "verifier", "operator"})
RISKS = frozenset({"low", "medium", "high"})
STATUSES = frozenset({
    "open", "claimed", "red", "green", "in_review", "changes_requested",
    "merged", "blocked", "deferred", "rejected",
})
IN_FLIGHT = frozenset({"claimed", "red", "green", "in_review", "changes_requested"})
TERMINAL = frozenset({"merged", "rejected"})
TRANSITIONS: Mapping[str, frozenset[str]] = {
    "open": frozenset({"claimed", "deferred", "rejected"}),
    "claimed": frozenset({"red", "open", "blocked"}),
    "red": frozenset({"green", "blocked"}),
    "green": frozenset({"in_review", "red"}),
    "in_review": frozenset({"changes_requested", "merged"}),
    "changes_requested": frozenset({"red", "green", "blocked"}),
    "blocked": frozenset({"open", "claimed"}),
    "deferred": frozenset({"open"}),
    "merged": frozenset(),
    "rejected": frozenset(),
}
REQUIRED_ITEM_KEYS = frozenset({
    "id", "title", "tier", "kind", "provenance", "summary", "files", "creates",
    "depends_on", "risk", "needs_adr", "owner_role", "acceptance", "verification",
    "status",
})


class QueueError(Exception):
    """A refusal the caller can act on (exit code 1)."""


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------

@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def load(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise QueueError(f"backlog not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise QueueError(f"backlog is not valid JSON: {path}:{exc.lineno}:{exc.colno}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise QueueError("backlog must be an object with an 'items' array")
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".upg-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def _index(items: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in items}


def validate(data: dict[str, Any], repo_root: Path) -> list[str]:
    """Return human-readable problems; an empty list means valid."""
    problems: list[str] = []
    items: list[dict[str, Any]] = data["items"]
    seen: set[str] = set()
    for pos, item in enumerate(items):
        where = f"items[{pos}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: not an object")
            continue
        missing = REQUIRED_ITEM_KEYS - item.keys()
        if missing:
            problems.append(f"{where}: missing keys {sorted(missing)}")
            continue
        iid = item["id"]
        where = iid
        if not isinstance(iid, str) or not iid.startswith("CAPT-UPG-"):
            problems.append(f"{where}: id must start with CAPT-UPG-")
        if iid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(iid)
        for key, allowed in (("tier", set(TIERS)), ("kind", KINDS), ("provenance", PROVENANCE),
                             ("owner_role", ROLES), ("risk", RISKS), ("status", STATUSES)):
            if item[key] not in allowed:
                problems.append(f"{where}: {key}={item[key]!r} not in {sorted(allowed)}")
        for key in ("files", "creates", "depends_on", "acceptance", "verification"):
            value = item[key]
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                problems.append(f"{where}: {key} must be a list of non-empty strings")
        if not item["acceptance"]:
            problems.append(f"{where}: acceptance must not be empty")
        if item["provenance"] == "P" and item["kind"] in {"hole", "weak_spot"}:
            problems.append(f"{where}: a hole/weak_spot cannot be provenance P (proposal)")
        if iid in item["depends_on"]:
            problems.append(f"{where}: depends on itself")
        for rel in item["files"]:
            if not (repo_root / rel).exists():
                problems.append(f"{where}: referenced path does not exist: {rel} (move it to 'creates' if new)")
        if item["status"] in IN_FLIGHT and not item.get("claimedBy"):
            problems.append(f"{where}: status {item['status']} requires claimedBy")
    index = _index(items)
    for item in items:
        if isinstance(item, dict):
            for dep in item.get("depends_on", []):
                if dep not in index:
                    problems.append(f"{item.get('id')}: unknown dependency {dep}")
    problems.extend(_cycles(items))
    return problems


def _cycles(items: Sequence[dict[str, Any]]) -> list[str]:
    graph = {str(i["id"]): [d for d in i.get("depends_on", [])] for i in items if isinstance(i, dict)}
    state: dict[str, int] = {}
    found: list[str] = []

    def visit(node: str, trail: list[str]) -> None:
        mark = state.get(node, 0)
        if mark == 2:
            return
        if mark == 1:
            cycle = trail[trail.index(node):] + [node]
            found.append("dependency cycle: " + " -> ".join(cycle))
            return
        state[node] = 1
        for dep in graph.get(node, []):
            if dep in graph:
                visit(dep, trail + [node])
        state[node] = 2

    for node in sorted(graph):
        visit(node, [])
    return found


# --------------------------------------------------------------------------
# scheduling
# --------------------------------------------------------------------------

def _footprint(item: dict[str, Any]) -> set[str]:
    return {p.rstrip("/") for p in [*item["files"], *item["creates"]]}


def _overlaps(a: set[str], b: set[str]) -> bool:
    for x in a:
        for y in b:
            if x == y or x.startswith(y + "/") or y.startswith(x + "/"):
                return True
    return False


def _dependents(items: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Transitive dependent count: how much work an item unblocks."""
    reverse: dict[str, list[str]] = {}
    for item in items:
        for dep in item["depends_on"]:
            reverse.setdefault(dep, []).append(item["id"])
    memo: dict[str, set[str]] = {}

    def reach(node: str) -> set[str]:
        if node not in memo:
            memo[node] = set()
            out: set[str] = set()
            for child in reverse.get(node, []):
                out.add(child)
                out |= reach(child)
            memo[node] = out
        return memo[node]

    return {item["id"]: len(reach(item["id"])) for item in items}


def ready(data: dict[str, Any], role: str | None = None) -> list[dict[str, Any]]:
    items = data["items"]
    index = _index(items)
    in_flight = [i for i in items if i["status"] in IN_FLIGHT]
    weight = _dependents(items)
    out: list[dict[str, Any]] = []
    for item in items:
        if item["status"] != "open":
            continue
        if role and item["owner_role"] != role:
            continue
        unmet = [d for d in item["depends_on"] if index[d]["status"] != "merged"]
        if unmet:
            continue
        conflicts = [f["id"] for f in in_flight if _overlaps(_footprint(item), _footprint(f))]
        out.append({
            "id": item["id"], "title": item["title"], "tier": item["tier"],
            "owner_role": item["owner_role"], "needs_adr": item["needs_adr"],
            "unblocks": weight[item["id"]], "conflictsWith": conflicts,
        })
    out.sort(key=lambda r: (bool(r["conflictsWith"]), TIERS.index(r["tier"]), -r["unblocks"], r["id"]))
    return out


# --------------------------------------------------------------------------
# transitions
# --------------------------------------------------------------------------

def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def transition(
    data: dict[str, Any], item_id: str, to: str, *, agent: str,
    note: str = "", expect: str | None = None, evidence: str | None = None,
) -> dict[str, Any]:
    if not agent.strip():
        raise QueueError("--agent is required and must be non-empty")
    if to not in STATUSES:
        raise QueueError(f"unknown status {to!r}")
    index = _index(data["items"])
    item = index.get(item_id)
    if item is None:
        raise QueueError(f"unknown item {item_id}")
    current = item["status"]
    if expect is not None and current != expect:
        raise QueueError(f"{item_id}: expected status {expect!r} but found {current!r} (stale view; refetch)")
    if to not in TRANSITIONS[current]:
        raise QueueError(f"{item_id}: illegal transition {current} -> {to}")
    if to == "claimed":
        unmet = [d for d in item["depends_on"] if index[d]["status"] != "merged"]
        if unmet:
            raise QueueError(f"{item_id}: unmet dependencies {unmet}")
        busy = [i["id"] for i in data["items"]
                if i["status"] in IN_FLIGHT and _overlaps(_footprint(item), _footprint(i))]
        if busy:
            raise QueueError(f"{item_id}: file footprint overlaps in-flight {busy}")
        item["claimedBy"] = agent
    if to == "open":
        item.pop("claimedBy", None)
    if to in {"green", "in_review", "merged"} and not (evidence or note):
        raise QueueError(f"{item_id}: moving to {to} requires --evidence (test log, PR URL, or SHA)")
    if to == "merged" and agent == item.get("claimedBy"):
        raise QueueError(f"{item_id}: separation of duties: claimant {agent!r} may not mark its own item merged")
    if to == "in_review" and agent != item.get("claimedBy"):
        raise QueueError(f"{item_id}: only the claimant may submit for review")
    item["status"] = to
    entry = {"at": _now(), "agent": agent, "from": current, "to": to}
    if note:
        entry["note"] = note
    if evidence:
        entry["evidence"] = evidence
    item.setdefault("history", []).append(entry)
    return item


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _mermaid(data: dict[str, Any]) -> str:
    lines = ["graph TD"]
    for item in data["items"]:
        node = item["id"].replace("CAPT-UPG-", "U")
        label = f'{item["id"].replace("CAPT-UPG-", "")} {item["title"][:38]} [{item["status"]}]'
        lines.append(f'  {node}["{label}"]')
        for dep in item["depends_on"]:
            lines.append(f'  {dep.replace("CAPT-UPG-", "U")} --> {node}')
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    p_ready = sub.add_parser("ready")
    p_ready.add_argument("--role", choices=sorted(ROLES))
    p_ready.add_argument("--json", action="store_true")
    p_show = sub.add_parser("show")
    p_show.add_argument("id")
    sub.add_parser("status")
    sub.add_parser("graph")
    p_set = sub.add_parser("set")
    p_set.add_argument("id")
    p_set.add_argument("status", choices=sorted(STATUSES))
    p_set.add_argument("--agent", required=True)
    p_set.add_argument("--note", default="")
    p_set.add_argument("--evidence")
    p_set.add_argument("--expect-status", dest="expect")
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("id")
    p_claim.add_argument("--agent", required=True)
    args = parser.parse_args(argv)

    try:
        if args.cmd in {"set", "claim"}:
            with _locked(args.backlog):
                data = load(args.backlog)
                problems = validate(data, args.repo_root)
                if problems:
                    raise QueueError("backlog invalid; refusing to mutate:\n  " + "\n  ".join(problems))
                if args.cmd == "claim":
                    item = transition(data, args.id, "claimed", agent=args.agent, expect="open")
                else:
                    item = transition(data, args.id, args.status, agent=args.agent,
                                      note=args.note, expect=args.expect, evidence=args.evidence)
                save(args.backlog, data)
            print(json.dumps({"id": item["id"], "status": item["status"],
                              "claimedBy": item.get("claimedBy")}))
            return 0

        data = load(args.backlog)
        if args.cmd == "validate":
            problems = validate(data, args.repo_root)
            for problem in problems:
                print("INVALID:", problem, file=sys.stderr)
            if not problems:
                print(f"valid: {len(data['items'])} items, acyclic")
            return 1 if problems else 0
        if args.cmd == "ready":
            rows = ready(data, args.role)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for r in rows:
                    flag = f"  (waits on in-flight {', '.join(r['conflictsWith'])})" if r["conflictsWith"] else ""
                    adr = " [ADR]" if r["needs_adr"] else ""
                    print(f"{r['tier']} {r['id']} unblocks={r['unblocks']} role={r['owner_role']}{adr}  {r['title']}{flag}")
            return 0
        if args.cmd == "show":
            shown = _index(data["items"]).get(args.id)
            if shown is None:
                raise QueueError(f"unknown item {args.id}")
            print(json.dumps(shown, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "status":
            counts: dict[str, int] = {}
            for item in data["items"]:
                counts[item["status"]] = counts.get(item["status"], 0) + 1
            print(json.dumps({"total": len(data["items"]), **dict(sorted(counts.items()))}))
            return 0
        if args.cmd == "graph":
            print(_mermaid(data))
            return 0
    except QueueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"io error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
