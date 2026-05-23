# Signal — Project Status

**Last Updated:** 2026-04-03
**Phase:** Phase 1 (Core Intelligence — "The Smart Call Analyzer")
**Overall Completion:** ~78%

---

## Executive Summary

The backend intelligence layer is **structurally complete** — all 7 LangGraph pipeline nodes are implemented, the routing engine is functional, and 15 of 17 framework prompts are written. The critical gaps blocking MVP are: no `pyproject.toml`/`requirements.txt`, no tests, two stub modules that need completion (Deepgram ASR, S3 storage), and the reliability/checks modules that are empty.

The frontend (Next.js per PRD) has not been started.

---

## 1. Completed Modules

### 1.1 FastAPI Application Layer

| Module | File | Status | Notes |
|--------|------|--------|-------|
| App factory + CORS | `signalapp/app/main.py` | ✅ Complete | Lifespan events, error handlers, health endpoint |
| Config loading | `signalapp/app/config.py` | ✅ Complete | `AppConfig` dataclass, per-group LLM config, env var loading |
| Dependency injection | `signalapp/app/dependencies.py` | ✅ Complete | `DBSession`, `CurrentUserID`, repository injection |

### 1.2 API Routes

| Endpoint | File | Status |
|----------|------|--------|
| `GET /api/v1/calls` | `signalapp/api/calls.py` | ✅ Complete |
| `GET /api/v1/calls/{id}` | `signalapp/api/calls.py` | ✅ Complete |
| `POST /api/v1/calls/upload` | `signalapp/api/calls.py` | ✅ Complete (S3 stubbed) |
| `GET /api/v1/insights/call/{id}` | `signalapp/api/insights.py` | ✅ Complete |
| `POST /api/v1/insights/{id}/feedback` | `signalapp/api/insights.py` | ⚠️ Stub — does not persist |
| `POST /api/v1/webhooks/asr/assemblyai` | `signalapp/api/webhooks.py` | ✅ Complete |
| `GET /api/v1/webhooks/asr/assemblyai` | `signalapp/api/webhooks.py` | ✅ Complete |
| `GET /health` | `signalapp/app/main.py` | ✅ Complete |

### 1.3 Database Layer

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| 11 SQLAlchemy models | `signalapp/db/models.py` | ✅ Complete | Org, User, Call, Transcript, TranscriptSegment, AnalysisRun, Pass1Result, FrameworkResult, Insight, BaseMetric, Setting. Cross-dialect JSONB/GUID. |
| Repository classes (CRUD) | `signalapp/db/repository.py` | ✅ Complete | All entities have async CRUD. `init_db()` bootstraps schema. |

### 1.4 Domain Models

| Component | File | Status |
|-----------|------|--------|
| Call entity + Pass1Result | `signalapp/domain/call.py` | ✅ Complete |
| TranscriptSegment + Transcript | `signalapp/domain/transcript.py` | ✅ Complete |
| Routing engine | `signalapp/domain/routing.py` | ✅ Complete — fully matches `FRAMEWORK_ROUTING_ARCHITECTURE.md` |
| FrameworkOutput + Severity + FRAMEWORK_REGISTRY | `signalapp/domain/framework.py` | ✅ Complete |
| Insight entity + prioritization | `signalapp/domain/insight.py` | ✅ Complete |

### 1.5 Pipeline (LangGraph — 7 Nodes)

```
START → pass1_extract → route_frameworks → execute_groups → verify_results → generate_insights → generate_summary → store_results → END
```

| Node | File | Status |
|------|------|--------|
| `pass1_extract` | `signalapp/pipeline/nodes/pass1_extract.py` | ✅ Complete |
| `route_frameworks` | `signalapp/pipeline/nodes/route.py` | ✅ Complete |
| `execute_groups` | `signalapp/pipeline/nodes/execute_groups.py` | ✅ Complete |
| `verify_results` | `signalapp/pipeline/nodes/verify.py` | ✅ Complete |
| `generate_insights` | `signalapp/pipeline/nodes/insights.py` | ✅ Complete |
| `generate_summary` | `signalapp/pipeline/nodes/summary.py` | ✅ Complete |
| `store_results` | `signalapp/pipeline/nodes/store.py` | ✅ Complete |

### 1.6 Framework Prompts (15 of 17)

All prompts are in `signalapp/prompts/groups/`:

| Group | Frameworks | Status |
|-------|-----------|--------|
| **Pass 1** | Hedge map, Sentiment trajectory, Evaluative language | ✅ `infrastructure_v1.py` |
| **Group A** | BATNA (#3), Money Left (#4), First Number (#7), Deal Health (#12), Deal Timing (#13) | ✅ All 5 complete |
| **Group B** | Unanswered Questions (#1), Commitment Quality (#2), Commitment Thermometer (#6), Pushback (#16) | ✅ All 4 complete |
| **Group C** | Question Quality (#5), Frame Match (#10), Close Attempt (#11), Methodology (#14), Call Structure (#15), Objection Response (#17) | ✅ All 6 complete |
| **Group D** | (reserved for Phase 2) | ⏸️ Empty |
| **Group E** | Emotional Turning Points (#8) + Emotional Triggers (#9) | ✅ Combined prompt |

**Not implemented:** FW-09 standalone (combined into #8), Group D frameworks.

### 1.7 Adapters

| Adapter | File | Status |
|---------|------|--------|
| LLM Provider ABC | `signalapp/adapters/llm/base.py` | ✅ Complete |
| Gemini Provider (Vertex + direct) | `signalapp/adapters/llm/gemini.py` | ✅ Complete |
| ASR Provider ABC | `signalapp/adapters/asr/base.py` | ✅ Complete |
| AssemblyAI Provider | `signalapp/adapters/asr/assemblyai.py` | ✅ Complete |
| Deepgram Provider | `signalapp/adapters/asr/deepgram.py` | ❌ Stub — `raise NotImplementedError` |
| S3 Storage | `signalapp/adapters/storage/` | ❌ Empty — local file fallback only |

### 1.8 Jobs / Queue

| Component | File | Status |
|-----------|------|--------|
| ARQ settings | `signalapp/jobs/app.py` | ✅ Complete |
| Memory queue (dev replacement) | `signalapp/jobs/memory.py` | ✅ Complete |
| Transcription job | `signalapp/jobs/transcription.py` | ✅ Complete |
| Preprocessing job | `signalapp/jobs/preprocessing.py` | ✅ Complete |
| Pipeline job | `signalapp/jobs/pipeline.py` | ✅ Complete |

---

## 2. Partially Complete Modules

### 2.1 `signalapp/api/insights.py` — Feedback endpoint

**Issue:** `POST /api/v1/insights/{insight_id}/feedback` returns `{"ok": True}` without persisting to the database.

```python
# Current implementation (line 51-55):
@router.post("/{insight_id}/feedback")
async def submit_insight_feedback(insight_id: uuid.UUID, feedback: InsightFeedback):
    # TODO: persist feedback to Insight model
    return {"ok": True}
```

**Fix needed:** Write feedback to the `insight` table's `feedback` and `feedback_at` fields.

### 2.2 `signalapp/api/calls.py` — S3 upload

**Issue:** When AWS credentials are not configured, upload falls back to local file storage at `/tmp/signalapp/uploads/`. This is a valid dev fallback but not production-ready.

**Fix needed:** Either implement full S3 adapter or accept local storage for MVP (with a clear warning in the UI).

---

## 3. Broken / Stub-Only Modules

### 3.1 `signalapp/adapters/asr/deepgram.py`

**Issue:** Module exists but every method raises `NotImplementedError`.

```python
async def submit(self, audio_url: str) -> str:
    raise NotImplementedError("Deepgram provider not yet implemented")
```

**Impact:** Runtime provider switching between AssemblyAI and Deepgram (per PRD Section 5.1, decision #3) will fail if Deepgram is selected.

**Fix needed:** Implement `DeepgramProvider` matching `ASRProvider` ABC.

### 3.2 `signalapp/adapters/storage/__init__.py`

**Issue:** Empty module. No S3 adapter exists.

**Impact:** Audio files cannot be stored in S3. The current local fallback works for single-instance dev but breaks in multi-instance production.

**Fix needed:** Implement `S3StorageAdapter` with `upload`, `download`, `delete`, and `get_signed_url` methods using `boto3`.

---

## 4. Missing Modules

### 4.1 `signalapp/reliability/` — LLM Reliability Patterns

**Status:** Empty module (only `__init__.py`).

**What PRD specifies (LLM Reliability Guide):**
- Retry logic with exponential backoff
- Circuit breaker pattern for LLM calls
- Fallback model switching
- Cost tracking per call
- Rate limiting
- Timeout handling

**Fix needed:** Implement `RetryConfig`, `CircuitBreaker`, `CostTracker`, `RateLimiter` in `signalapp/reliability/`.

### 4.2 `signalapp/checks/` — Quality Verification Gates

**Status:** Empty module (only `__init__.py`).

**What PRD specifies (Section 13):**
- 7-gate verification per framework result
- Gate 1: All required fields present
- Gate 2: Score within valid range
- Gate 3: Severity is valid enum value
- Gate 4: Evidence references point to real transcript segments
- Gate 5: Confidence score present and valid
- Gate 6: Coaching recommendation non-empty for low-confidence results
- Gate 7: No hallucinated timestamps

**Note:** The `verify_results` pipeline node (`pipeline/nodes/verify.py`) already implements a version of this. The `checks/` module is likely intended as standalone utility functions that can be used outside the pipeline context.

### 4.3 Tests

**Status:** `signalapp/tests/` contains only empty `__init__.py` stubs.

**What PRD requires (Section 22):**
- Prompt evaluation against golden datasets (using promptfoo)
- Unit tests for routing logic
- Unit tests for framework prompt outputs
- Integration tests for pipeline execution
- Shadow mode testing for routing accuracy

**Minimum MVP test requirements:**
1. `tests/unit/test_routing.py` — verify routing table decisions match specification
2. `tests/unit/test_framework_outputs.py` — verify prompt schemas produce valid outputs
3. `tests/integration/test_pipeline.py` — verify full pipeline executes without errors

---

## 5. Deployment Blockers

### 5.1 No `pyproject.toml` or `requirements.txt`

**Impact:** Cannot install dependencies. Cannot deploy.

**Status:** `requirements.txt` was created during this review, but `pyproject.toml` still needs to be created.

### 5.2 No `.env` Documentation for Production

**Issue:** `.env.example` exists but doesn't document which variables are required vs optional for production.

**Required for production:**
- `DATABASE_URL` (Postgres, not SQLite)
- `REDIS_URL`
- `GEMINI_API_KEY` or `GOOGLE_CLOUD_PROJECT` + `VERTEX_AI_LOCATION`
- `ASSEMBLYAI_API_KEY`
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_S3_BUCKET_NAME`
- `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` + `LANGFUSE_HOST`

### 5.3 No Deployment Configuration

**Missing:**
- `Dockerfile`
- `docker-compose.yml` for local dev (Postgres + Redis)
- Any CI/CD pipeline configuration

---

## 6. Technical Debt

### 6.1 Routing engine requires Pass1Result but doesn't handle missing data gracefully

In `signalapp/domain/routing.py`, `extract_gate_signals()` assumes `Pass1Result` has all fields populated. If Pass 1 fails, the routing engine may raise `AttributeError`.

**Affected code:** `signalapp/domain/routing.py`, `extract_gate_signals()`

### 6.2 `enforce_dependencies()` in routing has no logging

When a framework is removed due to dependency failure, no audit log is written. For debugging routing behavior in production, this is needed.

### 6.3 Pipeline `execute_groups_node` uses synchronous mock data in dev

The `FW_PROMPT_MAP` in `pipeline/nodes/execute_groups.py` maps frameworks to prompt files correctly, but the mock responses used during dev without LLM credentials produce generic data. No "real LLM not configured" guard exists — it silently falls back to mock data.

### 6.4 Repository `get_call()` doesn't eager-load relationships

In `signalapp/db/repository.py`, `CallRepository.get()` loads the `Call` model without `selectinload` for relationships like `transcript`, `analysis_runs`, `insights`. This causes N+1 query problems on the Call Review page.

### 6.5 `pass1_extract_node` has hardcoded model selection

```python
# signalapp/pipeline/nodes/pass1_extract.py line 47:
model="claude-sonnet-4-20250514",
```

Model selection should come from `AppConfig.llm_groups["default"]` or the Pass 1 config group.

---

## 7. Exact MVP Completion Checklist

Based on PRD Sections 5, 21 (Build Order), and 22 (Success Metrics).

### 7.1 Must Fix Before MVP

- [ ] Create `pyproject.toml` with proper package metadata
- [ ] Fix `submit_insight_feedback()` to persist to database
- [ ] Implement `DeepgramProvider` (or remove from provider switcher)
- [ ] Implement `S3StorageAdapter` (or confirm local-only is acceptable for MVP)
- [ ] Implement `signalapp/reliability/` module (retry logic, circuit breaker, cost tracking)
- [ ] Write `tests/unit/test_routing.py`
- [ ] Write `tests/unit/test_framework_outputs.py`
- [ ] Write `tests/integration/test_pipeline.py`
- [ ] Add `Dockerfile` and `docker-compose.yml`
- [ ] Document all required `.env` variables in `.env.example`
- [ ] Guard `execute_groups_node` with LLM availability check (fail fast if no LLM configured)
- [ ] Fix `CallRepository.get()` to eager-load relationships

### 7.2 Should Fix Before MVP

- [ ] Add audit logging to `enforce_dependencies()`
- [ ] Externalize Pass 1 model selection to config
- [ ] Add "LLM not configured" warning banner to Streamlit testing interface
- [ ] Implement `asr_confidence` and `version` tracking on Transcript model
- [ ] Add cursor-based pagination to `list_calls` endpoint

### 7.3 Nice to Have for MVP

- [ ] Promptfoo evaluation suite for golden dataset regression testing
- [ ] Langfuse integration for observability (already in requirements, needs config)
- [ ] Bulk upload API endpoint (PRD Section 10A)
- [ ] Cost-per-call tracking dashboard endpoint

---

## 8. Phase 1 Build Order (from PRD Section 21)

PRD specifies vertical slices. Current status mapped against that order:

| # | Slice | Description | Status |
|---|-------|-------------|--------|
| 1 | Database + Models | SQLAlchemy models, migrations | ✅ Complete |
| 2 | API Skeleton | FastAPI routes, CRUD endpoints | ✅ Complete |
| 3 | Repository Layer | All entity CRUD | ✅ Complete |
| 4 | Base Metrics | 8 metrics computed from transcript | ✅ Complete (in `preprocessing.py`) |
| 5 | Pass 1 Infrastructure | Hedge, sentiment, evaluative language | ✅ Complete |
| 6 | Routing Engine | Pure-Python framework routing | ✅ Complete |
| 7 | Framework Prompts (Groups A–E) | 15 framework prompts | ✅ 15/17 complete |
| 8 | LangGraph Pipeline | 7-node graph | ✅ Complete |
| 9 | LLM Adapter | Gemini provider | ✅ Complete |
| 10 | ASR Adapter | AssemblyAI provider | ✅ Complete |
| 11 | ARQ Jobs | Transcription + pipeline jobs | ✅ Complete |
| 12 | **Frontend** | Next.js app (not started) | ❌ Not started |
| 13 | Upload Flow | Audio + transcript paste | ⚠️ API done, no frontend |
| 14 | Calls List | Table + filters + pagination | ⚠️ API done, no frontend |
| 15 | Call Review | Insights + transcript + player | ⚠️ API done, no frontend |
| 16 | Developer Settings | ASR/LLM/Framework config panel | ⚠️ API done, no frontend |
| 17 | Sample Calls | Seed data for onboarding | ❌ Not started |
| 18 | Auth | Clerk integration | ❌ Not started |
| 19 | Deployment | Docker + env config | ❌ Not started |
| 20 | Tests + Evaluation | promptfoo + regression suite | ❌ Not started |

---

## 9. Streamlit Testing Interface

A Streamlit app has been created at `streamlit_app.py` in the project root to serve as a backend testing harness and demo surface. It provides:

- **Upload tab:** Upload audio or paste transcript, select call type, submit for analysis
- **Calls List tab:** View all submitted calls with status
- **Call Review tab (simulation):** See framework results, insights, call stats, and summary

This is a testing tool only — the production frontend per PRD is Next.js.
