# Model Providers

Status: **v0.6 P1 (planned).** This page is honest about where model-provider
configuration stands today and what is coming.

## Where things are

CAPT's runtime already hosts **bounded drivers** (the architecture's model
connectors) and the cross-model continuity proof works at the seeded/demo level.
However, there is **not yet** a unified normal-human model-provider
configuration surface.

There is no `capt models list/add/test/use` today. Model/driver configuration is
internal (DriverHost), so a normal user cannot yet point CAPT at a model with
simple commands. This is scheduled P1 productization work.

Consequence: **do not assume every driver that imports is a supported
normal-user path.** See [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md) for what is
operator-facing.

## Intended provider set (P1 target)

When the unified surface lands, it should cover at least:

- LM Studio
- Ollama
- llama.cpp
- MLX / mlx_lm
- vLLM
- OpenRouter
- Hermes compatibility

Each provider guide should say: prerequisites, discovery/configuration, context
limit, credentials (if any), health check, first governed call, limitations.

## What you can do today

- Run the deterministic first-success path (see [START_HERE](../START_HERE.md)) —
  it needs no model at all.
- Run the demos ([DEMOS.md](DEMOS.md)) — they use public interfaces and the
  seeded demo mission.
- Inspect the internal driver architecture via
  [ARCHITECTURE.md](ARCHITECTURE.md) if you are an integrator.

If you need model-backed governed execution now, you are an advanced/expert
user and should use the harness's governed command operations and driver wiring
per the architecture and plugin docs.