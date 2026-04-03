---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-04-03T20:11:06.350Z"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 1
  completed_plans: 0
---

# Signal — Project State

**Project:** Signal — Behavioral Sales Intelligence
**Updated:** 2026-04-04

---

## Project Status

**Phase:** 1 (Active Development)
**Overall Status:** Planning

---

## Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| API | FastAPI (Python) | Async-native, Pydantic, OpenAPI |
| Database | Postgres + JSONB | Relational + flexible schema |
| Storage | AWS S3 | Presigned URLs for browser-direct upload |
| Queue | ARQ + Redis | Async-native, replaces Celery |
| Pipeline | LangGraph | Checkpointing, pipeline visibility |
| LLM | Anthropic SDK + OpenAI SDK + Instructor | Structured outputs |
| Observability | Langfuse | All LLM calls logged |
| Testing | promptfoo | Golden dataset evaluation |
| Auth | Clerk | Pre-built auth, fast implementation |

---

## Architecture Decisions (ADRs)

### ADR-001: ARQ + LangGraph over Celery

**Status:** Executing Phase 01
**Decision:** Replace Celery + Redis 8-queue model with ARQ + LangGraph
**Rationale:** Celery is sync-first (conflicts with async stack); 8 queues = 8x operational complexity; manual checkpointing fragile; LangGraph provides automatic checkpointing and pipeline visibility.

### ADR-002: Provider Abstraction (ASR + LLM)

**Status:** Final
**Decision:** All providers abstract via Protocol interfaces. ASR: AssemblyAI + Deepgram. LLM: Anthropic + OpenAI. Runtime switchable.
**Rationale:** Prevents lock-in; enables model comparison; zero changes to pipeline when adding providers.

### ADR-003: Package Naming

**Status:** Final
**Decision:** Python package named `signalapp` (not `signal`)
**Rationale:** `signal` conflicts with Python stdlib `signal` module, breaking asyncio-based libraries (FastAPI/Starlette/anyio).

### ADR-004: Routing Architecture

**Status:** Final
**Decision:** Pure Python routing ($0.00), no LLM for routing decisions. Pass 1 always runs. Frameworks categorized as BLOCKED/MANDATORY/CONTENT-GATED. AIM pattern for key frameworks.
**Rationale:** 25-45% cost reduction with zero accuracy risk.

---

## Signal Clusters (20 Foundational Signals)

| # | Cluster | Example Frameworks Powered |
|---|---------|--------------------------|
| 1 | Prosodic-Complexity | System 1/2, Cognitive Load, Confidence |
| 2 | Disfluency-Uncertainty | Deception markers, Anxiety, Epistemic Stance |
| 3 | Pronoun-Identity | Social Identity, Locus of Control |
| 4 | Sentiment-Valence | Emotion Regulation, Burnout, Resilience |
| 5 | Vocabulary-Richness | Openness, Intelligence, Creativity |
| 6 | Turn-Taking-Power | Dominance, Leadership, Psychological Safety |
| 7 | Semantic-Coherence | Deception, Rumination, Coherence |
| 8 | Syntactic-Complexity | System 2 reasoning, Cognitive Capacity |
| 9 | Temporal-Pacing | Cognitive Load, Urgency, Anxiety |
| 10 | Article-Concreteness | Psychological Distance, Construal Level |
| 11 | Hedging-Qualification | Certainty, Confidence, Deception |
| 12 | Comparison-Contrast | Divergent Thinking, Decision Quality |
| 13 | Referential-Clarity | Theory of Mind, Mentalizing |
| 14 | Negation-Avoidance | Prevention Focus, Loss Aversion |
| 15 | Evidentiality-Grounding | Argument Strength, Credibility |
| 16 | Imperative-Control | Dominance, Persuasion, Leadership Style |
| 17 | Narrative-Structure | Storytelling, Engagement |
| 18 | Self-Other-Distance | Alliance, Empathy, Theory of Mind |
| 19 | Volition-Agency | Self-Efficacy, Growth Mindset |
| 20 | Social-Norm-Alignment | Conformity, Groupthink |

---

## Phase 1 Frameworks (17 in Routing Architecture)

| # | Framework | Group | Status |
|---|-----------|-------|--------|
| 1 | Unanswered Questions | B | Production |
| 2 | Commitment Quality Score | B | Production |
| 3 | BATNA Detection | A | Production |
| 4 | Money Left on Table | A | Production |
| 5 | Question Quality Score | C | Production |
| 6 | Commitment Thermometer | B | Production |
| 7 | First Number Tracker | A | Production |
| 8 | Emotional Turning Points | E | Production (PINNED) |
| 9 | Emotional Trigger Analysis | E | Production (PINNED) |
| 10 | Frame Match Score | C | Production |
| 11 | Close Attempt Analysis | C | Production |
| 12 | Deal Health at Close | A | Production |
| 13 | Deal Timing Intelligence | A | Production |
| 14 | Methodology Compliance | C | Production |
| 15 | Call Structure Analysis | C | Production (PINNED) |
| 16 | Pushback Classification | B | Production |
| 17 | Objection Response Score | C | Production |

---

## Current Work

### Active Sprint

Initial planning and project bootstrap.

### Recently Completed

- Project documentation organized in References/
- FRAMEWORK_ROUTING_ARCHITECTURE.md created
- PCP behavioral science foundation documented

### Blockers

None currently.

---

## Build Progress (Phase 1 Slices)

| Slice | Status | Notes |
|-------|--------|-------|
| 1 | Not Started | Project setup |
| 2 | Not Started | ASR + basic Call Review |
| 3 | Not Started | Transcript paste |
| 4 | Not Started | Base metrics + AI summary |
| 5 | Not Started | Promptfoo + Langfuse |
| 6 | Not Started | Pass 1 pipeline |
| 7 | Not Started | First framework |
| 8 | Not Started | Remaining frameworks |
| 9 | Not Started | Framework scaffolding |
| 10 | Not Started | Developer settings |
| 11 | Not Started | Re-analysis + export |
| 12 | Not Started | Onboarding |
| 13 | Not Started | Bulk upload |
| 14 | Not Started | Dashboard |
| 15 | Not Started | UI polish |

---

## Key Files

| File | Purpose |
|------|---------|
| `References/Signal_PRD_v2.2.md` | Full product specification |
| `References/FRAMEWORK_ROUTING_ARCHITECTURE.md` | Framework execution routing |
| `References/PCP_Summary.md` | PCP behavioral science foundation |
| `References/LLM_RELIABILITY_GUIDE.md` | LLM usage patterns |
| `References/Gong_Summary.md` | Competitive analysis |

---

*State version 1.0 — initialized 2026-04-04*
