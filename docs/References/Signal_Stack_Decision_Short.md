# Signal — Tech Stack for the Intelligence Layer

| | |
|--|--|
| **Author** | Manas Tiwari |
| **Version** | 3.0 |
| **Date** | March 31, 2026 |
| **Scope** | Intelligence layer only — everything else in PRD v2.2 is unchanged |

---

## The 30-Second Version

The PRD uses **Celery** — a job queue built in 2009 for synchronous Python — to manage an async pipeline across 8 separate queues with hundreds of lines of custom coordination code. Signal's entire stack is async. These two things conflict, and the conflict shows up as bugs in production.

We replace Celery with two focused tools:

- **ARQ** — a modern async job queue. Same Redis. Handles who gets processed and when.
- **LangGraph** — a pipeline orchestrator. Handles what happens step by step inside each job.

Same Redis. Same Postgres. Same everything else. Just a cleaner engine.

---

## Why We Are Dropping Celery

Celery was designed for sync Python. Every LLM call in Signal is async. The mismatch creates four real problems:

**1. Async conflict.** Running async code inside Celery requires `asyncio.run()` — a workaround that causes event loop bugs and deadlocks. Not theoretical. This happens in production.

**2. 8 queues = 8 failure points.** The PRD chains the pipeline across 8 separate queues. When a call gets stuck, you trace a `call_id` jumping across 8 queues and 8 worker logs to find out why.

**3. Fragile parallelism.** Running 4 framework groups simultaneously requires Celery's `chord` — its most notoriously unreliable feature. The most critical step of Signal's pipeline sits on the least stable Celery primitive.

**4. Manual crash recovery.** The PRD's resume-on-crash logic is custom code: check `completed_at` timestamps before each stage, handle every edge case by hand, and maintain this forever. One missed write and a crashed call reruns from scratch — burning API cost for nothing.

---

## Why ARQ

ARQ is Celery rebuilt for async Python. Identical concept — jobs go into Redis, workers pick them up — but designed for `async/await` from the ground up.

The entire Signal setup:

```python
async def process_call(ctx, call_id: str):
    await pipeline.ainvoke({"call_id": call_id})

class WorkerSettings:
    functions = [process_call]
    max_jobs = 3        # 3 calls at once
    job_timeout = 600   # 10 min max
    max_tries = 3       # auto-retry on failure
```

This replaces 8 Celery queues, 8 worker configs, and ~100 lines of configuration. Same Redis underneath. Nothing else changes.

---

## Why LangGraph

LangGraph replaces the manual pipeline coordination — the `completed_at` logic, the Celery chords, the task chaining. Define the pipeline once as a graph, and it handles execution, state, parallelism, and crash recovery automatically.

Signal's pipeline maps to it exactly:

```
preprocess → pass1 → [group_a ‖ group_b ‖ group_c ‖ group_e] → translate
```

Three things it gives us that the PRD's approach cannot:

**1. Crash recovery for free.**
LangGraph saves state to Postgres after every node. Crash mid-pipeline — ARQ retries, LangGraph reads the checkpoint, resumes from the last completed step. No wasted compute. No wasted API cost. No custom code.

```
PRD:        crash after Pass1 → retry from scratch → re-run ASR + Pass1 (costs money)
LangGraph:  crash after Pass1 → retry → resume from parallel groups (zero waste)
```

**2. Parallel groups without Celery chords.**
All 4 framework groups run simultaneously via native async — clean, reliable, no inter-queue coordination needed.

**3. Scales into every future phase without re-architecture.**

| Phase | What's Needed | How LangGraph Handles It |
|-------|--------------|--------------------------|
| P2 — Deal Intelligence | State across multiple calls in a deal | Persistent state across graph runs |
| P3 — Coaching Engine | Conditional paths based on rep baseline | Conditional edges, built-in |
| P5 — Real-time streaming | Stream insights as they generate | `.astream()` — one line, no rewrite |

The PRD's 8-queue approach needs re-architecting to support any of these. LangGraph accommodates them as additive changes.

---

## Before vs Now

| | PRD — Celery | Recommended — ARQ + LangGraph |
|--|-------------|-------------------------------|
| **Job queue** | Celery + Redis | ARQ + Redis |
| **Queues** | 8 | 1 |
| **Async support** | Broken — `asyncio.run()` hacks | Native throughout |
| **Parallel execution** | Celery `chord` (fragile) | `asyncio.gather` (reliable) |
| **Crash recovery** | Custom `completed_at` logic | LangGraph auto-checkpointing |
| **Coordination code** | ~300 lines | ~15 lines |
| **Debugging** | Trace across 8 queues | Single graph trace |
| **Phase 2-5 readiness** | Re-architecture required | Additive changes only |
| **Infrastructure cost** | Baseline | Identical |

---

## Honest Tradeoffs

**What we gain:** Native async, automatic crash recovery, 1 queue instead of 8, parallel execution without fragile primitives, a pipeline that scales into every phase without structural changes.

**What we give up:** Celery has a larger community and more Stack Overflow answers. ARQ has fewer. LangGraph adds two checkpoint tables to Postgres. These are real tradeoffs — they just don't outweigh the gains for Signal's specific architecture.

**Production readiness:** Both ARQ and LangGraph are production-ready. ARQ is used in production across the FastAPI ecosystem. LangGraph is built and maintained by LangChain Inc. and is deployed at scale commercially. This is not a bet on experimental software.

---

## Final Summary

Signal's pipeline is one thing: a call goes in, intelligence comes out. The PRD models it as 8 separate systems talking to each other. ARQ + LangGraph models it as what it actually is — one job, one pipeline, running cleanly from start to finish.

**ARQ** manages the line — who gets processed, when, and on which worker.
**LangGraph** runs the pipeline — every step, in order, in parallel where needed, resuming from checkpoints if anything goes wrong.

The infrastructure cost is identical. The coordination code drops from ~300 lines to ~15. The operational complexity is a fraction. And every future phase — deal intelligence, coaching, streaming, custom frameworks — plugs in without touching the foundation.

---

*Full decision record with all alternatives considered and risk analysis: `Signal_Intelligence_Stack_v1.0.md`*
