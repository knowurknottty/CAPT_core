# Mental Model — How CAPT Works

The shortest correct mental model:

> **The model becomes stateless. CAPT becomes stateful.**

Here is the whole system on one screen:

```text
                        Human
                          |
                          v
                  ┌─────────────┐
                  │ CAPT Runtime │   the thing you interact with
                  └─────────────┘
                          |
        ┌─────────────────┼─────────────────┐
        |                 |                 |
   ┌────┴────┐     ┌──────┴──────┐   ┌──────┴──────┐
   │  Memory  │     │ Governance / │   │   Evidence   │
   │          │     │  Authority   │   │             │
   │ durable, │     │ nothing runs │   │ proof,      │
   │ model-   │     │ without      │   │ verification│
   │ indep.   │     │ approval     │   │ claims      │
   └──────────┘     └──────────────┘   └─────────────┘
                          |
                  ┌──────┴────────┐
                  │ Recovery/Event │
                  │ Store + ckpt   │
                  └───────────────┘
                          |
                          v
                 Replaceable Models
          (LM Studio, Ollama, OpenRouter, MLX, ...)
```

## Reading the diagram

1. **Human** is the final authority. Nothing consequential happens without the
   operator's approval.
2. **CAPT Runtime** is the one surface you talk to. It is not a library you
   bolt on — it is the stateful core surrounding the model.
3. Four responsibilities hang off the runtime:
   - **Memory** — durable knowledge that survives model changes and restarts.
   - **Governance / Authority** — missions, approvals, grants. Execution is
     gated; it does not just happen.
   - **Evidence** — proof, verification results, and claim decisions. This is
     how CAPT answers "did this really happen?"
   - **Recovery / EventStore + checkpoints** — the ordered event history that
     lets you stop, restart, and resume without repeating completed work.
4. **Replaceable Models** sit below the line. They are transient, pluggable
   inference components. They never own CAPT state.

## The two sentences that anchor everything

- **A model is transient and replaceable. CAPT owns the durable memory,
  governed state, evidence, authority, execution history, context policy, and
  recovery around it.**
- **The model becomes stateless. CAPT becomes stateful.**

## Terminology you will meet (progressive disclosure)

Only learn these when you need them:

| Term | Meaning (plain) |
|---|---|
| Runtime | the stateful core you start with `capt start` |
| Memory | durable knowledge; `capt memory store/search` |
| Mission | a governed objective that requires approval |
| Evidence | records that something was done and verified |
| Approval | the human gate before consequential execution |
| Checkpoint | a saved, authoritative state snapshot |
| EventStore | the ordered history CAPT uses for recovery |
| ClaimGuard | the check that decides whether a claim is supportable |
| ContextPack | how CAPT decides what context to keep and discard |
| Driver | a connector to a replaceable model |

Deep subsystem names (CTP, KHSB, Foundry, DriverHost, Memory Governor) are
implementation details. You do not need them to use CAPT. The glossary in the
architecture docs explains them for readers who want that depth.

## Source of the picture

Every deeper document references this same shape and terminology. If you see a
component in a deep doc, it lives somewhere on this diagram — above the model
line (CAPT's job) or below it (a replaceable model).