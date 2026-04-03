# Signal — Intelligence Layer Tech Stack
## Phase 1 Recommendation & Decision Record

**Document Type:** Architecture Decision Record (ADR)
**Version:** 3.0
**Date:** March 31, 2026
**Status:** Proposed — Pending Founder Approval
**Supersedes:** PRD v2.2 Section 5 (Decision #7) and Section 18

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What the PRD Currently Specifies](#2-what-the-prd-currently-specifies)
3. [What We Are Recommending Instead](#3-what-we-are-recommending-instead)
4. [The Full Recommended Stack](#4-the-full-recommended-stack)
5. [Why ARQ Over Celery](#5-why-arq-over-celery)
6. [Why LangGraph Over Raw Celery Chains](#6-why-langgraph-over-raw-celery-chains)
7. [How ARQ + LangGraph Work Together](#7-how-arq--langgraph-work-together)
8. [Alternatives Considered and Rejected](#8-alternatives-considered-and-rejected)
9. [Migration Path — Phase 2 and Beyond](#9-migration-path--phase-2-and-beyond)
10. [Cost Comparison](#10-cost-comparison)
11. [Risk Analysis](#11-risk-analysis)
12. [Final Decision Summary](#12-final-decision-summary)

---

## 1. Executive Summary

The PRD v2.2 specifies **Celery + Redis** for async job processing with raw Celery task chains handling the pipeline internally. This document recommends replacing that with **ARQ + Redis + LangGraph** — a cleaner, fully async stack where:

- **ARQ** handles job queuing and concurrency (replaces Celery)
- **LangGraph** handles pipeline orchestration inside each job (replaces manual Celery task chaining)
- **Redis** remains unchanged — same dependency, same cost

Everything else in the PRD stack remains exactly the same.

**The change is surgical. The benefit is significant.**

The rest of the stack — FastAPI, Postgres, AWS S3, Instructor, Pydantic, Langfuse, promptfoo — stays exactly as the PRD specifies. This is not a rewrite. It is a replacement of one queue library (Celery) with a better-suited one (ARQ), and the addition of a pipeline orchestration layer (LangGraph) that the PRD was handling manually and incorrectly.

---

## 2. What the PRD Currently Specifies

From PRD v2.2 Section 5, Decision #7:

> *"FastAPI (Python) + Postgres (JSONB) + AWS S3 + Redis + Celery"*
> *"Python for LLM ecosystem compatibility. JSONB for flexible framework outputs. Celery + Redis for async pipeline processing."*

And from Section 18.2:

> *"Celery + Redis. No BullMQ, no alternatives."*

The PRD then specifies **8 separate Celery queues**:

```
transcription
preprocessing
pass1
pass2_group_a
pass2_group_b
pass2_group_c
pass2_group_e
product_translation
```

Each queue has its own workers. Tasks pass `call_id` between queues. The pipeline coordinates via `completed_at` timestamps in Postgres — manually checking which stages are done before proceeding.

### Problems with this approach

**Problem 1 — Celery is a sync-first system fighting async.**

Signal's entire stack is async: FastAPI (async), Anthropic SDK (async), OpenAI SDK (async), AssemblyAI SDK (async). Celery was built in 2009 for synchronous Python. Its async support (`celery[eventlet]`, `celery[gevent]`) is bolted on and routinely causes subtle bugs — deadlocks, task leaks, event loop conflicts. Running `asyncio.run()` inside a Celery task (the common workaround) blocks the worker thread.

**Problem 2 — 8 queues is 8 things to configure, monitor, and debug.**

When something breaks (and it will), you need to check which of 8 queues failed, which worker dropped the message, and where the `call_id` got lost in transit. This is operational complexity with no benefit. Signal's pipeline is one logical unit — it should be one queue entry.

**Problem 3 — Manual checkpointing is fragile.**

The PRD's idempotency strategy is: check `completed_at` timestamps in Postgres before running each stage. This is custom logic that must be written, tested, and maintained. Every developer who touches the pipeline must understand this convention. It is easy to get wrong — a missed `completed_at` write means a stage re-runs on retry. A wrong query means a stage gets skipped.

**Problem 4 — No visibility into the pipeline's internal state.**

With 8 Celery queues, Celery Flower (the monitoring tool) shows you queue depths and task statuses — but it cannot show you "this call is currently on Group B, Group A finished 2 minutes ago." You have no graph of the pipeline's execution. Debugging a stuck call means querying multiple tables.

---

## 3. What We Are Recommending Instead

**One queue. One pipeline orchestrator. Full visibility. Zero manual checkpointing.**

```
PRD spec:     Celery (8 queues) + manual completed_at checkpointing
This doc:     ARQ   (1 queue)   + LangGraph automatic checkpointing
```

### The mental model

```
User uploads call
      │
      ▼
FastAPI → ARQ puts ONE job in Redis → returns instantly to user
                    │
                    ▼
         ARQ Worker picks up the job
                    │
                    ▼
         LangGraph runs the pipeline internally:
         ┌──────────────────────────────────────────────┐
         │  preprocess → pass1 → [A + B + C + E] → translate │
         │                                              │
         │  After each node: state saved to Postgres    │
         │  (automatic, no custom code needed)          │
         └──────────────────────────────────────────────┘
                    │
                    ▼
         Call status → "ready" → frontend notified
```

ARQ asks: **when should this job run and on which worker?**
LangGraph asks: **what happens step by step inside the job?**

They operate at completely different levels. They never conflict.

---

## 4. The Full Recommended Stack

### Intelligence Layer — Complete Stack

| Layer | Component | Purpose | Replaces (PRD) |
|-------|-----------|---------|----------------|
| **API** | FastAPI | HTTP endpoints, webhook handling | Same |
| **Job Queue** | **ARQ + Redis** | Async job queuing, concurrency control, worker management | Celery + Redis |
| **Pipeline Orchestration** | **LangGraph** | DAG execution, parallel groups, state management, checkpointing | 8 manual Celery queues + `completed_at` logic |
| **Structured LLM Outputs** | Instructor + Pydantic | Schema-enforced outputs from every LLM call | Same |
| **LLM Providers** | Anthropic SDK + OpenAI SDK (direct) | LLM API calls | Same |
| **ASR Providers** | AssemblyAI SDK + Deepgram SDK | Speech-to-text | Same |
| **LLM Retry Logic** | tenacity | Exponential backoff on LLM calls within nodes | Custom (PRD left unspecified) |
| **Observability** | Langfuse | Prompt tracing, cost tracking, A/B evals | Same |
| **Prompt Evaluation** | promptfoo | Golden dataset eval, regression gate | Same |
| **Primary Database** | Postgres (JSONB) | All application data + LangGraph checkpoint store | Same (adds checkpoint tables) |
| **Cache** | Redis | ARQ broker + application caching | Same |
| **Audio Storage** | AWS S3 | Audio file storage | Same |
| **Auth** | Clerk | Authentication | Same |

### What changed from the PRD

```
REMOVED:  Celery (celery[redis], celery[eventlet], flower)
ADDED:    ARQ
ADDED:    LangGraph (langgraph, langgraph-checkpoint-postgres)
ADDED:    tenacity (retry logic — PRD left this as "write it yourself")
UNCHANGED: Everything else
```

---

## 5. Why ARQ Over Celery

ARQ (Async Redis Queue) is a modern Python job queue built ground-up for async. It was created because Celery's async story is fundamentally broken for modern Python async applications.

### Code comparison — same task, two libraries

**Celery:**
```python
# celery_config.py — 40+ lines of configuration
app = Celery('signal')
app.config_from_object('celeryconfig')
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_concurrency=3,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # ... 20+ more settings
)

# tasks.py
@app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_call(self, call_id: str):
    try:
        # LangGraph is async. Celery is sync. Conflict.
        # You must do this awkward workaround:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(pipeline.ainvoke({"call_id": call_id}))
        loop.close()
    except Exception as exc:
        raise self.retry(exc=exc)
```

**ARQ:**
```python
# workers.py — 8 lines total
async def process_call(ctx, call_id: str):
    await pipeline.ainvoke({"call_id": call_id})  # native async, no gymnastics

class WorkerSettings:
    functions = [process_call]
    redis_settings = RedisSettings(host='localhost')
    max_jobs = 3
    job_timeout = 600  # 10 min max per call
    retry_jobs = True
    max_tries = 3
```

**Enqueueing (FastAPI route) — identical concept, ARQ is cleaner:**
```python
# Celery
process_call.delay(call_id)

# ARQ
await redis_pool.enqueue_job('process_call', call_id)
```

### Head-to-head comparison

| Feature | Celery | ARQ |
|---------|--------|-----|
| Native async support | No — bolted on via eventlet/gevent | Yes — built for async |
| FastAPI compatibility | Requires workarounds | First-class, same event loop |
| Configuration | 40-100+ lines | ~8 lines |
| Redis dependency | Yes | Yes (same) |
| Job retry | Yes | Yes |
| Concurrency control | Yes | Yes (`max_jobs`) |
| Job timeout | Yes | Yes |
| Priority queues | Yes | Yes |
| Monitoring UI | Flower (separate install) | ARQ dashboard (built-in) |
| Debug complexity | High | Low |
| Stack Overflow answers | Thousands | Fewer but sufficient |
| Active maintenance | Yes | Yes |
| Production usage | Massive (Instagram, etc.) | Growing — used by FastAPI-heavy companies |

### The one honest advantage Celery has

Celery has a larger community and more battle-hardened edge case handling. If something breaks with ARQ at 3am, there are fewer Stack Overflow answers. This is a real tradeoff.

**Why it doesn't outweigh ARQ's advantages for Signal:** Signal's pipeline is straightforward — one job type (`process_call`), one queue, well-understood failure modes. The cases where Celery's maturity matters (complex routing, canvas workflows, multi-broker setups) don't apply here. ARQ's simplicity reduces the surface area for bugs in the first place.

---

## 6. Why LangGraph Over Raw Celery Chains

The PRD's approach to pipeline orchestration is 8 Celery queues coordinated via `completed_at` timestamps. This is the highest-risk part of the PRD's architecture.

### What the PRD's pipeline actually looks like in code

```python
# PRD approach — pseudocode of what building this would require

@app.task
def transcription_task(call_id):
    result = run_asr(call_id)
    db.store_segments(call_id, result)
    db.update_stage(call_id, 'transcription', completed_at=now())
    preprocessing_task.delay(call_id)  # manually chain to next task

@app.task
def preprocessing_task(call_id):
    # Check if transcription is done (it should be, but just in case)
    if not db.stage_completed(call_id, 'transcription'):
        raise Exception("Transcription not done yet")  # now what?
    segments = db.get_segments(call_id)
    clean = preprocess(segments)
    db.store_clean_segments(call_id, clean)
    db.update_stage(call_id, 'preprocessing', completed_at=now())
    pass1_task.delay(call_id)

@app.task
def pass1_task(call_id):
    segments = db.get_segments(call_id)
    result = run_pass1_llm(segments)  # but Celery is sync, LLM SDK is async...
    db.store_pass1(call_id, result)
    db.update_stage(call_id, 'pass1', completed_at=now())
    # Now dispatch 4 parallel tasks — Celery group/chord
    group([
        group_a_task.s(call_id),
        group_b_task.s(call_id),
        group_c_task.s(call_id),
        group_e_task.s(call_id),
    ] | translate_task.s(call_id)).delay()  # Celery chord — notoriously buggy

# ... 4 more group tasks, 1 translate task
# Total: ~300 lines of boilerplate coordination code
# Every line is custom logic that can fail silently
```

This is not hypothetical complexity — this is what you would actually build following the PRD.

### What LangGraph looks like for the same pipeline

```python
# LangGraph approach

# Define the state (data that flows through the pipeline)
class SignalState(TypedDict):
    call_id: str
    segments: list
    pass1_result: dict
    group_results: dict
    insights: list
    summary: str

# Each step is a clean, testable async function
async def preprocess_node(state: SignalState) -> SignalState:
    segments = await run_asr_and_clean(state["call_id"])
    return {**state, "segments": segments}

async def pass1_node(state: SignalState) -> SignalState:
    result = await run_pass1_llm(state["segments"])
    return {**state, "pass1_result": result}

async def parallel_groups_node(state: SignalState) -> SignalState:
    # All 4 groups run simultaneously — native async
    a, b, c, e = await asyncio.gather(
        run_group_a(state["segments"], state["pass1_result"]),
        run_group_b(state["segments"], state["pass1_result"]),
        run_group_c(state["segments"], state["pass1_result"]),
        run_group_e(state["segments"], state["pass1_result"]),
    )
    return {**state, "group_results": {"a": a, "b": b, "c": c, "e": e}}

async def translate_node(state: SignalState) -> SignalState:
    insights = generate_insights(state["group_results"])
    summary = await generate_summary(state["segments"], state["group_results"])
    await db.update_call_status(state["call_id"], "ready")
    return {**state, "insights": insights, "summary": summary}

# Wire the graph — this IS the architecture diagram
workflow = StateGraph(SignalState)
workflow.add_node("preprocess", preprocess_node)
workflow.add_node("pass1", pass1_node)
workflow.add_node("parallel_groups", parallel_groups_node)
workflow.add_node("translate", translate_node)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "pass1")
workflow.add_edge("pass1", "parallel_groups")
workflow.add_edge("parallel_groups", "translate")
workflow.set_finish_point("translate")

# Attach checkpointer — this is the entire idempotency solution
checkpointer = PostgresSaver(db_connection)
pipeline = workflow.compile(checkpointer=checkpointer)
```

**Total coordination code: ~15 lines** (the graph wiring). The PRD approach requires ~300 lines of custom coordination that must be written, tested, and maintained.

### LangGraph's checkpointing vs PRD's manual `completed_at`

This is the most important difference.

**PRD approach — manual checkpointing:**
```
Server crashes after pass1_node completes
→ Celery retries the task from the beginning
→ Re-runs preprocessing (wasted compute)
→ Re-runs Pass1 LLM call (costs money — ~$0.10 per call)
→ Developer must manually verify completed_at logic works correctly
→ Edge cases: what if completed_at was written but data wasn't committed?
```

**LangGraph approach — automatic checkpointing:**
```
Server crashes after pass1_node completes
→ ARQ retries the task
→ LangGraph reads checkpoint from Postgres
→ "preprocess: done ✓, pass1: done ✓, parallel_groups: not started"
→ Resumes from parallel_groups only
→ Zero wasted compute, zero wasted API cost
→ No custom code — this is built into LangGraph
```

### LangGraph's Phase 2-5 value

| Phase | Requirement | LangGraph handles it |
|-------|------------|----------------------|
| P2 — Deal Intelligence | Track behavioral state across multiple calls in a deal. A deal's "commitment trajectory" evolves over 5 calls spanning weeks. | LangGraph's persistent state store naturally holds deal-level state across multiple graph runs. |
| P3 — Coaching Engine | Conditional analysis paths: "if rep's question quality is below baseline, run deeper diagnostic frameworks" | Conditional edges in LangGraph — `add_conditional_edges()` |
| P5 — Real-time streaming | Stream insights token-by-token as they're generated | LangGraph's `.astream()` — no architectural change required |
| P5 — Custom Framework Builder | Enterprise customers define their own frameworks → dynamic pipeline construction | LangGraph graphs can be constructed dynamically at runtime |

If you build the PRD's 8-queue Celery approach, adding Phase 2 longitudinal analysis means re-architecting the pipeline. LangGraph's graph model accommodates it naturally.

---

## 7. How ARQ + LangGraph Work Together

A common point of confusion: "Aren't ARQ and LangGraph both doing orchestration? Do they conflict?"

No. They operate at completely different levels and never touch the same concern.

```
┌──────────────────────────────────────────────────────────────────┐
│  ARQ's Domain: "WHO gets processed and WHEN"                     │
│                                                                  │
│  - 10 users upload simultaneously                               │
│  - ARQ queues 10 jobs in Redis                                  │
│  - 3 workers pick up 3 jobs (concurrency limit)                 │
│  - Other 7 jobs wait their turn                                 │
│  - Worker finishes → immediately picks next job                  │
│  - If worker crashes → ARQ retries the job on another worker    │
│                                                                  │
│  ARQ knows nothing about: transcripts, LLMs, frameworks         │
└─────────────────────────┬────────────────────────────────────────┘
                          │ hands one job to one worker
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  LangGraph's Domain: "WHAT happens inside the job"               │
│                                                                  │
│  - Receives: call_id                                            │
│  - Runs: preprocess → pass1 → [A||B||C||E] → translate          │
│  - Saves checkpoint after every node                            │
│  - If server crashes mid-node → resumes from last checkpoint    │
│  - Passes state between nodes automatically                     │
│                                                                  │
│  LangGraph knows nothing about: other users, queue depth        │
└──────────────────────────────────────────────────────────────────┘
```

**In code — the handoff:**
```python
# ARQ worker function — the handoff point
async def process_call(ctx, call_id: str):
    """
    ARQ calls this function when it's this call's turn.
    LangGraph takes over from here.
    """
    await pipeline.ainvoke(
        {"call_id": call_id, "segments": [], "pass1_result": {}, ...},
        config={"configurable": {"thread_id": call_id}}
        #                                      ↑
        #                        thread_id ties checkpoints to this call
    )

class WorkerSettings:
    functions = [process_call]
    max_jobs = 3          # ARQ's concurrency control
    job_timeout = 600
    max_tries = 3
```

One function. 6 lines. ARQ's entire integration with LangGraph.

---

## 8. Alternatives Considered and Rejected

### Temporal — "The Most Elegant Single System"

**What it is:** A durable workflow execution platform. One system that handles job queuing, pipeline orchestration, checkpointing, and retry — all at once. LangGraph and ARQ combined can be replaced entirely by Temporal.

**Why it's genuinely better at scale:**

Temporal's durability is fundamentally deeper than LangGraph checkpointing:
- LangGraph checkpoints to Postgres — if the Postgres connection drops during a write, you might lose the checkpoint
- Temporal's execution history is the source of truth — every activity's result is stored in Temporal's own database before proceeding. Crash anywhere, at any moment, and Temporal resumes automatically

```python
# Temporal — everything in one place
@workflow.defn
class SignalPipeline:
    @workflow.run
    async def run(self, call_id: str):
        segments = await workflow.execute_activity(preprocess, call_id)
        pass1 = await workflow.execute_activity(run_pass1, segments)

        group_a, group_b, group_c, group_e = await asyncio.gather(
            workflow.execute_activity(run_group_a, pass1),
            workflow.execute_activity(run_group_b, pass1),
            workflow.execute_activity(run_group_c, pass1),
            workflow.execute_activity(run_group_e, pass1),
        )
        await workflow.execute_activity(translate, [group_a, group_b, group_c, group_e])
```

**Why we are not choosing it for Phase 1:**

1. **Infrastructure overhead.** Temporal requires running a Temporal server (or paying for Temporal Cloud at ~$25-50/month). At pre-seed, adding a new stateful service to operate is real risk.
2. **Learning curve.** Temporal has concepts (workflows, activities, signals, queries) that take time to internalize correctly. Phase 1 needs to ship fast.
3. **Overkill for a 3-stage pipeline.** Pass1 → parallel groups → translate is simple enough that ARQ + LangGraph handles it without the overhead.

**When to migrate to Temporal:** Phase 2-3, when deal-level workflows need to stay alive across days or weeks as a deal progresses through multiple calls. A deal workflow that spans 3 weeks across 8 calls is exactly what Temporal was designed for.

---

### CrewAI — "Wrong Abstraction Entirely"

**What it is:** A multi-agent framework where autonomous agents with defined roles collaborate to complete tasks.

**Why we considered it:** LLMs + defined roles + parallel work sounds similar to Signal's framework groups.

**Why it is rejected:**

Signal's pipeline is **deterministic**. The same steps run in the same order on every call. There is no decision to make about what to do next — preprocess always runs first, pass1 always runs second, groups always run third.

CrewAI is designed for **autonomous** pipelines where the LLM decides what to do next — which tool to call, which agent to delegate to. This is the opposite of what Signal needs.

Concretely:
- CrewAI agents make decisions → Signal needs structured, reproducible outputs
- CrewAI's structured output story is weak → Signal requires Pydantic schema enforcement on every framework output
- CrewAI adds agent prompts, role definitions, memory management → none of this maps to Signal's frameworks
- CrewAI has no checkpointing → Signal needs resume-on-crash

CrewAI would require fighting the framework to get deterministic behavior. **Wrong tool.**

---

### LangChain (as LLM abstraction layer) — "Unnecessary Indirection"

**What it is:** A framework providing abstractions over LLM providers — chains, prompt templates, output parsers, memory, agents.

**Why we rejected it:**

The PRD correctly specifies calling Anthropic and OpenAI SDKs directly. Adding LangChain as a wrapper provides:
- A unified interface across providers ✓

At the cost of:
- Extra latency on every LLM call (LangChain adds processing overhead)
- Instructor (which Signal uses for structured outputs) works best with direct SDK calls
- LangChain's abstractions break or behave unexpectedly when Anthropic/OpenAI release new features
- Debugging becomes: "is this a Signal bug, a LangChain bug, or an Anthropic bug?"

**Decision: call Anthropic and OpenAI SDKs directly. Use Instructor for structured outputs. LangGraph for orchestration only — no LangChain elsewhere.**

---

### Modal — "Best Developer Experience, Wrong Stage"

**What it is:** A serverless compute platform for ML workloads. Define a Python function, decorate it with `@modal.function`, Modal handles scaling, containers, and execution.

**Why it is compelling:**
- Zero infrastructure management — no workers to run, no Redis to manage for queuing
- Auto-scaling: 1 user or 1,000 users, same code
- Pay per second of compute used, not per server

**Why we are not choosing it for Phase 1:**

1. **Vendor lock-in.** Signal's core processing pipeline becomes dependent on Modal's platform. If Modal has an outage, Signal cannot process calls. If Modal raises prices, Signal has no leverage.
2. **Cost at scale.** Modal's per-second pricing is economical at low volume but more expensive than running your own workers at 1,000+ calls/month.
3. **Unnecessary at pre-seed.** A single Hetzner VPS ($20/month) running ARQ workers handles Signal's Phase 1 load comfortably.

**When to reconsider Modal:** Phase 4-5, when enterprise customers create unpredictable traffic spikes and auto-scaling becomes genuinely valuable.

---

### Prefect — "Good Observability, Redundant Layer"

**What it is:** A Python-native workflow orchestration tool with a visual dashboard showing flow execution.

**Why it was considered:** Prefect's UI is genuinely good — you can see every workflow execution, every task, success/failure rates, run history.

**Why rejected:**

Signal already has Langfuse for LLM observability (the part that matters most). Adding Prefect would give a second observability layer for the pipeline coordination, which ARQ's built-in dashboard already covers adequately. Two monitoring systems for one pipeline is complexity without proportional benefit.

---

### Raw Python + asyncio (No Queue Library) — "Simplest Possible Approach"

**What it is:** Skip ARQ entirely. FastAPI receives uploads, spawns `asyncio.create_task()` for background processing, LangGraph handles the pipeline.

**Why it fails for Signal:**

`asyncio.create_task()` runs in the same process as FastAPI. If the web server restarts (deployment, crash), all in-flight tasks are lost — with no way to recover them. There is no queue. There is no retry. There is no concurrency control.

This is acceptable for a personal project with 1 user. It is not acceptable for a product with paying customers uploading calls they care about.

ARQ's entire value is: jobs survive server restarts (they're in Redis), concurrency is controlled (max_jobs), and retries are automatic (max_tries). These are non-negotiable for Signal.

---

## 9. Migration Path — Phase 2 and Beyond

This stack is designed with forward compatibility as a primary constraint.

### Phase 2 — Deal Intelligence

Deal-level behavioral tracking requires analyzing multiple calls as a unit. With LangGraph:

```python
# A deal workflow references and aggregates multiple call pipelines
class DealState(TypedDict):
    deal_id: str
    call_ids: list[str]
    call_results: list[dict]  # results from each call's pipeline
    commitment_trajectory: list[float]
    deal_health_score: float

# The deal pipeline runs after each new call is added to the deal
async def compute_trajectory_node(state: DealState) -> DealState:
    scores = [extract_commitment_score(r) for r in state["call_results"]]
    trajectory = compute_trajectory(scores)
    return {**state, "commitment_trajectory": trajectory}
```

No architectural change. A new LangGraph workflow. Same ARQ queue.

### Phase 3 — Conditional Coaching Paths

When rep baselines are established, certain frameworks should only run if the rep is below baseline:

```python
# LangGraph conditional edges — add this when Phase 3 ships
def route_after_baseline_check(state: SignalState) -> str:
    if state["rep_below_baseline"]:
        return "deep_diagnostic_node"   # run additional frameworks
    return "translate_node"             # proceed normally

workflow.add_conditional_edges(
    "baseline_check",
    route_after_baseline_check,
    {"deep_diagnostic_node": "deep_diagnostic_node", "translate_node": "translate_node"}
)
```

### Phase 2-3 — Temporal Migration

When deal workflows need to persist across days/weeks:

1. Temporal is introduced for deal-level workflows only
2. Individual call pipelines can stay on ARQ + LangGraph OR be ported to Temporal activities
3. Migration is additive — Temporal sits alongside ARQ, not instead of it, until the team is confident

### Phase 5 — Real-Time Streaming

LangGraph's streaming API is already built for this:

```python
# Phase 1: invoke (wait for full result)
await pipeline.ainvoke(state, config=config)

# Phase 5: stream (tokens as they arrive)
async for chunk in pipeline.astream(state, config=config):
    yield chunk  # stream insights to frontend as generated
```

One line change. No architectural rewrite.

---

## 10. Cost Comparison

Both stacks have identical variable costs (LLM, ASR). The infrastructure costs differ slightly.

| Component | PRD (Celery) | Recommended (ARQ) |
|-----------|-------------|-------------------|
| Redis | $0-10/month | $0-10/month (same) |
| Worker VPS (Celery/ARQ) | $20-40/month | $20-40/month (same) |
| Flower (Celery monitor) | $0 (open source, self-hosted) | $0 (ARQ dashboard built-in) |
| Temporal Cloud (Phase 2+) | Not applicable | $25-50/month |
| **Total infrastructure delta** | **Baseline** | **+$0 Phase 1, +$25-50 Phase 2+** |

Phase 1 cost is identical. The $25-50/month Temporal cost at Phase 2+ is offset by eliminated engineering time spent building and maintaining custom deal-level state management.

---

## 11. Risk Analysis

### Risks of the Recommended Stack (ARQ + LangGraph)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ARQ has fewer Stack Overflow answers than Celery | Medium | Low | ARQ's codebase is ~1,000 lines — readable enough to debug directly. LangGraph community is large and growing. |
| LangGraph API changes break the pipeline | Low | Medium | Pin LangGraph version. Run promptfoo evals before upgrading. LangGraph is production-stable. |
| LangGraph checkpointer schema migrations | Low | Low | LangGraph checkpoint tables are separate from Signal's application tables. Migrations are isolated. |
| Team unfamiliar with LangGraph | Low | Low | Founder already knows LangGraph. |

### Risks of the PRD Stack (Celery + manual chains)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Celery async/await conflicts | High | High | No clean mitigation — this is a fundamental Celery limitation |
| Celery chord bugs (parallel fan-out/fan-in) | Medium | High | Celery chords are notoriously fragile. Known issue in community. |
| Manual `completed_at` logic has edge cases | Medium | Medium | Requires extensive testing. Every new developer must understand the convention. |
| 8-queue debugging complexity | High | Medium | Operational burden that grows as the team grows |

---

## 12. Final Decision Summary

### Recommended Stack — One Line Per Component

```
FastAPI          →  API layer and webhook handling
ARQ + Redis      →  Job queue: who gets processed and when
LangGraph        →  Pipeline: what happens step by step inside each job
Instructor       →  Schema enforcement on every LLM output
Anthropic SDK    →  Direct Claude API calls (no LangChain wrapper)
OpenAI SDK       →  Direct GPT-4o API calls (no LangChain wrapper)
tenacity         →  Retry logic on LLM calls within pipeline nodes
Langfuse         →  LLM observability, cost tracking, prompt A/B testing
promptfoo        →  Golden dataset evaluation, regression gate on prompts
Postgres         →  Application data + LangGraph checkpoint store (same DB)
AWS S3           →  Audio file storage
Clerk            →  Authentication
```

### What we are NOT using and why

```
Celery           →  Sync-first, async is bolted on, 8-queue complexity
CrewAI           →  Wrong abstraction — agentic, Signal's pipeline is deterministic
LangChain        →  Unnecessary wrapper — breaks Instructor, adds latency
Modal            →  Vendor lock-in, wrong stage for pre-seed
Prefect          →  Redundant observability layer — Langfuse already covers it
Temporal         →  Phase 2-3 consideration, overkill for Phase 1
```

### The change from the PRD in one sentence

> Replace Celery's 8-queue manual pipeline with ARQ (one queue, pure async) and LangGraph (automatic orchestration with built-in checkpointing) — same Redis, same everything else, dramatically less coordination code to write and maintain.

---

*This document should be read alongside Signal PRD v2.2. All decisions in this document that conflict with PRD v2.2 Section 5 (Decision #7) and Section 18 supersede those decisions for the intelligence layer.*

*Frontend stack, auth, database schema, API design, and deployment infrastructure remain exactly as specified in the PRD.*
