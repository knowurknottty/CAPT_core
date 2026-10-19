# CAPT Core, explained simply

> **Audience:** first-time readers and non-specialists. **Scope:** source reviewed at [`0d8e46d`](https://github.com/knowurknottty/CAPT_core/tree/0d8e46d095243e80febd4e30f5ae52c9202316d9) on 2026-10-18. This is a conceptual guide, **not** a certification of a running installation.

## The problem CAPT is trying to solve

An AI model can produce useful answers, but a model's words are not durable operational records. In particular, a plausible answer is not proof that a tool ran, a task finished, a user approved something, or a side effect happened exactly once.

CAPT Core places a **governed runtime around models and tools**. Its design separates the part that generates suggestions (the model) from the part that records decisions, checks permissions, and admits evidence (the runtime).

## Think of it as an expedition logbook and control room

- **Model:** proposes what to say or do; its response remains an observation, not a verified fact.
- **Operator:** the person making choices and granting appropriately scoped approvals.
- **RuntimeService:** coordinates accepted commands and presents authoritative operations.
- **EventStore:** the durable record from which runtime state can be reconstructed.
- **Governance:** determines whether an action has the required authority, lease, and approval.
- **Evidence and verification:** keep “we saw an output” separate from “we established a claim.”
- **Memory and ContextPack:** manage retained information and what a model may actually receive.
- **Tools and providers:** perform bounded external work; they are not sources of authority merely because they returned successfully.

These are analogies. The actual boundaries are described in the [technical manual](TECHNICAL_MANUAL.md), [architecture](ARCHITECTURE.md), and [governance reference](GOVERNANCE.md).

## What a typical governed task means

1. An operator creates or requests work.
2. CAPT evaluates the applicable capability, policy, and approval requirements.
3. An authorized driver or tool may attempt the work.
4. CAPT receives an *untrusted* result or artifact candidate.
5. Evidence is recorded and, where required, separately verified.
6. The task or mission can reach its allowed state **only** through the governed completion boundary.

**Important:** a returned model message, provider health probe, consensus of models, or successful tool exit is not automatically a completed task.

## A real first step without a model account

If Python is installed, see [Start Here](../START_HERE.md) for installation. After installing, the read-only commands below show the public CLI surface:

```zsh
capt --version
capt --help
capt memory --help
```

As of the pinned source, the package/CLI reports **`capt-solo 0.5.0`**. That does not mean every feature on the development branch is certified as a version 0.5 release.

For a writable, local first exercise, use [Start Here](../START_HERE.md). That guide distinguishes the **standalone Solo memory store** from RuntimeService-managed context and ledger state.

## What CAPT does *not* promise automatically

- It does not make model answers intrinsically true.
- It does not make an unavailable provider or missing credential work.
- It does not turn an offline fixture into real-world provider or operating-system acceptance.
- It does not guarantee exactly-once external effects when the dispatch/result boundary is unknown; those cases require reconciliation.
- It does not establish a signed, notarized, publicly distributed macOS release just because a native Swift target exists.

## Where to go next

[Reader pathways](ONBOARDING.md) · [Glossary](GLOSSARY.md) · [User guide](USER_GUIDE.md) · [Current-state snapshot](CURRENT_STATE.md) · [Documentation index](README.md)
