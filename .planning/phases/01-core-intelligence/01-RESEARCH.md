# Phase 1: Core Intelligence - Research

**Researched:** 2026-04-04
**Domain:** Behavioral sales intelligence pipeline — ARQ + LangGraph + LLM framework orchestration + FastAPI backend + Streamlit frontend
**Confidence:** HIGH (project has substantial existing code confirming most patterns)

## Summary

Signal Phase 1 backend is a LangGraph-orchestrated LLM pipeline that extracts behavioral insights from sales call transcripts. The core pipeline (Pass 1 infrastructure extraction + Pass 2 framework groups A/B/C/E) is already scaffolded in `signalapp/pipeline/`. The main research questions are about completing integration patterns that are not yet implemented: Streamlit-to-FastAPI real backend connectivity, S3 presigned URL upload, JSONB query optimization, and the ARQ+LangGraph checkpointing pattern for resumable workflows.

**Primary recommendation:** Focus Phase 1 implementation on completing the transcript-paste-to-insights flow with the mock LLM provider, then swap in real providers. The existing scaffold (pipeline nodes, routing, framework prompts) is well-architected. The main gaps are: (1) FastAPI endpoints for Streamlit to call, (2) ARQ worker registration, (3) S3 upload flow, (4) JSONB queries for insight retrieval.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Frontend:** Streamlit (NOT Next.js) — per user scope constraint
- **Backend:** FastAPI
- **Pipeline:** ARQ + LangGraph (already replaces Celery per ADR)
- **Package:** `signalapp` (not `signal`)
- **LLM:** Provider abstraction (Anthropic + OpenAI + Gemini as interchangeable providers)
- **No ASR/audio upload:** transcript paste as primary input
- **Focus:** Core behavioral pipeline working first

### Data Model (locked)
- `Call`: id, organization_id, rep_name, call_type, deal_name?, call_date, audio_url?, transcript_status, analysis_status
- `TranscriptSegment`: segment_id, call_id, segment_index, speaker_name, speaker_role, start_time_ms, end_time_ms, text
- `AnalysisRun`: id, call_id, settings_snapshot (JSONB), pass1_output (JSONB), framework_results (JSONB), status
- `Settings`: organization_id, settings_key, encrypted_settings_value (JSONB)

### Pipeline Flow (locked)
1. Upload to S3 (presigned URL, browser-direct) OR transcript paste
2. Pass 1 always runs (hedge/sentiment/evaluative extraction)
3. Routing (pure Python, $0.00)
4. Pass 2: groups A-E via asyncio.gather, each = 1 batched LLM call
5. Insight prioritization → severity → confidence → actionability → $ → novelty

### Call Types (locked)
Discovery, Demo, Pricing, Negotiation, Close, Check-in, Other

### Framework Groups (locked)
- Group A (Negotiation): #3, #4, #7, #12, #13
- Group B (Pragmatics): #1, #2, #6, #16
- Group C (Coaching): #5, #10, #11, #14, #15, #17
- Group D: empty (Phase 2)
- Group E (Emotion): #8 + #9 (combined prompt)

### Phase Requirements
From `.planning/phases/01-core-intelligence/01-CONTEXT.md`:
- Phase boundary: behavioral analysis pipeline, transcript paste input, framework routing
- Build Order slices: 1 → 2 → 6 → 7 → 8 (critical path)
- Focus on getting core behavioral pipeline working first

### Deferred Ideas (OUT OF SCOPE)
- CRM integrations (Phase 2)
- Zoom cloud recording integration (Phase 2)
- Multi-user / rep logins (Phase 3)
- Real-time in-call coaching (Phase 5)
- Public API / framework builder (Phase 5)
- Deal-level views and tracking (Phase 2)
- Slack notifications (Phase 2)
- SSO / SOC 2 (Phase 4)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-01 | Transcript paste input + metadata → stored in Postgres | Section 5 below: Postgres JSONB schema for segments + transcript |
| REQ-02 | Pass 1 extraction (hedge, sentiment, evaluative) via LLM | Already implemented in `signalapp/pipeline/nodes/pass1_extract.py` |
| REQ-03 | Framework routing (pure Python, $0.00) | Already implemented in `signalapp/domain/routing.py` + `signalapp/pipeline/nodes/route.py` |
| REQ-04 | Pass 2 framework groups (A/B/C/E) executed via asyncio.gather | Already implemented in `signalapp/pipeline/nodes/execute_groups.py` |
| REQ-05 | Framework results stored in Postgres JSONB | Section 5 below: JSONB schema patterns + GIN indexing |
| REQ-06 | Verified insights generated + prioritized | Already scaffolded in `signalapp/pipeline/nodes/insights.py` + `verify.py` |
| REQ-07 | Insights surfaced via FastAPI endpoint | Section 4 below: Streamlit + FastAPI integration |
| REQ-08 | S3 presigned URL for future audio upload | Section 6 below: boto3 presigned URL pattern |
| REQ-09 | ARQ worker enqueuing pipeline job | Section 1 below: ARQ + LangGraph integration pattern |
| REQ-10 | Framework prompt engineering (structured outputs) | Section 7 below: Instructor patterns + AIM pattern |
</phase_requirements>

---

## Research Question 1: ARQ + LangGraph Integration

**How to integrate LangGraph inside ARQ workers? What's the pattern for checkpointing and state persistence? How does the job queue interact with LangGraph's state management?**

### Existing Code Review

The project already has the core integration pattern in `signalapp/jobs/pipeline.py`:

```python
async def run_pipeline_job(ctx: dict, call_id: str, force_reanalyze: bool = False) -> dict:
    # 1. Load call + segments from DB
    # 2. Build initial state dict
    # 3. Run LangGraph workflow
    app = create_pipeline_workflow()
    final_state = await app.ainvoke(state)
    # 4. Store results
    await _store_results(call_uuid, final_state)
```

ARQ supports async natively. The `ctx` dict received by the job function is the ARQ context (contains redis connection, session, etc.). The current implementation runs `app.ainvoke(state)` directly inside the ARQ worker.

### Checkpointing Pattern

LangGraph's built-in checkpointing saves state after each node:

```python
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# In app startup:
checkpointer = AsyncRedisSaver.from_conn_string(config.redis_url)

# When compiling the graph:
app = create_pipeline_workflow().compile(checkpointer=checkpointer)

# In ARQ job:
final_state = await app.ainvoke(
    state,
    config={"configurable": {"thread_id": f"call-{call_id}"}}
)
```

This enables **resume after interruption**: if the worker crashes mid-pipeline, the next job can check for an existing checkpoint and resume from the last completed node rather than restarting from scratch.

### Idempotency (Already in Code)

The `signalapp/jobs/pipeline.py` already implements idempotency via `AnalysisRun` records with `completed_at` timestamps. The PRD specifies:

> "Each pipeline stage stores its output independently with a `completed_at` timestamp. Resume logic: check which stages have output, skip completed stages, resume from first incomplete stage."

This means the ARQ job does NOT need to use LangGraph's checkpointing for correctness — the DB is the source of truth. LangGraph checkpointing would add recovery speed but is not required for correctness.

### Partial Failure Handling

`asyncio.gather(*tasks, return_exceptions=True)` is already used in `execute_groups_node` (line 113):

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for fw_id, result in zip(fw_ids, results):
    if isinstance(result, Exception):
        framework_errors[fw_id] = str(result)
    elif result is not None:
        framework_results[fw_id] = result.model_dump()
```

This means a single framework failure does NOT crash the pipeline. Per PRD: "LLM failure (single group): partial results + retry."

### Worker Registration Pattern

ARQ workers are registered by pointing the ARQ CLI at the module containing the job functions:

```bash
arq signalapp.jobs.app.WorkerSettings
```

The `signalapp/jobs/app.py` defines `get_arq_settings()` returning the worker config. The `run_pipeline_job` function is decorated by `register_job` from `signalapp/jobs/memory.py` which also registers it with the ARQ worker.

### Key Pattern

```python
# signalapp/jobs/pipeline.py
async def run_pipeline_job(ctx: dict, call_id: str, ...) -> dict:
    """ARQ job — runs LangGraph pipeline for a single call."""
    # Load from DB (idempotent — re-run safe)
    call = await call_repo.get_by_id(call_uuid)
    segments = await transcript_repo.get_segments_for_call(call_uuid)

    # Build initial state (NOT checkpoint resume — DB is truth)
    state = {
        "call_id": call_id,
        "call_type": call.call_type,
        "transcript_segments": [...],
    }

    # Run pipeline
    app = create_pipeline_workflow()
    final_state = await app.ainvoke(state)

    # Store to DB (idempotent overwrite)
    await _store_results(call_uuid, final_state)
    return {"status": "complete", "call_id": call_id}
```

**Important:** The current implementation does NOT use LangGraph checkpointing for state persistence — it reconstructs state from the DB at job start and writes results to the DB at job end. This is the correct pattern per the PRD's idempotency design.

---

## Research Question 2: Instructor + Pydantic for Structured Outputs

**Best patterns for using Instructor with Anthropic SDK for framework result extraction. How to handle partial failures within a batched framework group call?**

### Existing Implementation: Gemini Native JSON Schema

The codebase uses **Gemini's native JSON schema** (NOT Instructor) in `signalapp/adapters/llm/gemini.py`:

```python
gen_config = types.GenerateContentConfig(
    temperature=config.temperature,
    max_output_tokens=config.max_tokens,
    response_mime_type="application/json",
    response_schema=response_model,  # Pydantic model passed directly
)
response = client.models.generate_content(
    model=config.model,
    contents=prompt,
    config=gen_config,
)
parsed = response_model.model_validate_json(response.text)
```

This is a valid approach — Instructor is needed for providers that don't have native JSON schema support (e.g., OpenAI with `response_format`). For Gemini (and Anthropic via their API), native JSON schema is simpler and equally reliable.

### Instructor Pattern (for Anthropic/OpenAI if needed)

If Anthropic SDK is used directly (without Instructor), structured output requires Instructor as a wrapper:

```python
# Pattern if migrating to Instructor + Anthropic
import instructor
from anthropic import Anthropic

client = instructor.from_anthropic(Anthropic())

# Pydantic model for each framework output
class BatnaDetectionOutput(BaseModel):
    has_mentioned_alternative: bool
    buyer_leverage_score: float = Field(ge=0.0, le=1.0)
    severity: str
    # ... full schema

# In framework execution:
result = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": full_prompt}],
    response_model=BatnaDetectionOutput,
)
```

### Partial Failures Within a Batched Group Call

Each group call currently runs ALL its frameworks in a single prompt (batched). The `execute_groups_node` calls each framework independently but sends a combined prompt. If the combined LLM call fails, the entire group fails — the `return_exceptions=True` in `asyncio.gather` handles per-framework failures, not per-group failures.

**Per-group failure handling:**

```python
async def execute_groups_node(state: PipelineState) -> dict:
    # ...
    tasks = []
    for fw_id in fw_ids:
        task = _run_framework(...)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Individual framework errors are tracked
    framework_errors = {}
    for fw_id, result in zip(fw_ids, results):
        if isinstance(result, Exception):
            framework_errors[fw_id] = str(result)
```

The `_run_framework` function already catches all exceptions and returns a stub output:

```python
except Exception as e:
    return _stub_framework_output(fw_id, f"LLM call failed: {str(e)}")
```

Per PRD: "LLM failure (single group): partial results + retry." The stub output allows partial results to be stored and displayed, with a retry mechanism available via the re-analyze button.

### Structured Output Schema Pattern (from existing code)

The framework output schemas are well-designed in the existing code. Example from `batna_detection_v1.py`:

```python
class BatnaDetectionOutput(BaseModel):
    has_mentioned_alternative: bool = False
    alternative_count: int = 0
    buyer_leverage_score: float = Field(ge=0.0, le=1.0)
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str
    alternative_mentions: list[AltMentionInstance] = Field(default_factory=list)

    # AIM output when no alternatives found
    is_aim_null_finding: bool = False
    aim_output: str = ""
    coaching_recommendation: str
```

Key patterns confirmed from `LLM_RELIABILITY_GUIDE.md`:
- **Closed-world contract**: "The transcript is your only source of truth" in system prompts
- **Cite-before-claim**: Evidence anchored in verbatim segment references
- **Null as valid output**: Explicit AIM null-finding templates
- **Calibrated confidence**: Field with `ge=0.0, le=1.0` constraints

---

## Research Question 3: Streamlit + FastAPI Integration

**Streamlit as frontend calling FastAPI backend. Auth patterns (Streamlit auth vs separate auth service). How to handle streaming/status updates from FastAPI to Streamlit.**

### Current State

The existing `streamlit_app.py` is a **mock/testing harness** with hardcoded sample data and `generate_mock_results()`. It does NOT call a real FastAPI backend. The FastAPI backend (`signalapp/app/main.py`) exists but has no Streamlit integration yet.

### FastAPI Endpoints Needed

Based on the PRD Section 17 API design, these are the endpoints Streamlit needs:

```python
# POST /api/calls/paste-transcript — primary input method for Phase 1
POST /api/calls/paste-transcript
Body: {
    "rep_name": str,
    "call_type": str,  # "discovery" | "demo" | "pricing" | ...
    "deal_name": str | null,
    "transcript_text": str,
    "call_date": str  # ISO date
}
Response: { "call_id": uuid, "status": "processing" }

# GET /api/calls/{id} — poll for status
GET /api/calls/{id}
Response: { "call_id": uuid, "status": "processing" | "ready" | "failed" | "partial" }

# GET /api/calls/{id}/insights — get top insights
GET /api/calls/{id}/insights
Response: { "insights": [...], "count": int }

# GET /api/calls/{id}/frameworks — get all framework results
GET /api/calls/{id}/frameworks
Response: { "frameworks": [...], "active": [fw_ids], "groups": [...] }
```

### Streamlit-to-FastAPI Connection Pattern

```python
# streamlit_app.py — FastAPI client
import streamlit as st
import requests

BACKEND_URL = "http://localhost:8000"

def get_api_headers():
    """Get auth headers from session state."""
    token = st.session_state.get("auth_token")
    if not token:
        st.error("Please log in first")
        st.stop()
    return {"Authorization": f"Bearer {token}"}

def submit_transcript_paste(rep_name: str, call_type: str, transcript_text: str, deal_name: str = None):
    response = requests.post(
        f"{BACKEND_URL}/api/calls/paste-transcript",
        json={
            "rep_name": rep_name,
            "call_type": call_type,
            "deal_name": deal_name,
            "transcript_text": transcript_text,
        },
        headers=get_api_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["call_id"]

def poll_call_status(call_id: str, poll_interval: int = 5) -> str:
    """Poll until status is 'ready' or 'failed'."""
    while True:
        response = requests.get(
            f"{BACKEND_URL}/api/calls/{call_id}",
            headers=get_api_headers(),
        )
        status = response.json()["status"]
        if status in ("ready", "failed", "partial"):
            return status
        time.sleep(poll_interval)

def get_insights(call_id: str) -> list[dict]:
    response = requests.get(
        f"{BACKEND_URL}/api/calls/{call_id}/insights",
        headers=get_api_headers(),
    )
    return response.json()["insights"]
```

### Authentication Pattern

**Option A: Streamlit native auth (`st.login`)**

Streamlit 1.37+ provides native `st.login()` and `st.logout()`:

```python
# streamlit_app.py
if "auth_token" not in st.session_state:
    st.login()

if st.user:
    st.session_state["auth_token"] = st.user.token  # JWT from identity provider
```

This requires an identity provider (Clerk, Auth0, etc.) configured in Streamlit's secrets.

**Option B: Separate FastAPI auth with Clerk**

Per PRD: "Clerk JWT verification middleware on all routes." Streamlit would:
1. Use Clerk's hosted UI (redirect to Clerk for login)
2. Receive JWT in URL callback
3. Store JWT in session state
4. Pass JWT as Bearer token to FastAPI

**Recommendation for Phase 1:** Use a **simplified auth pattern** — a shared secret or API key in `.env` that Streamlit sends as a header. This defers full Clerk integration while enabling real backend testing. Clerk integration is well-specified in the PRD and can be added as a later slice.

```python
# Simplified Phase 1 auth
BACKEND_API_KEY = st.secrets.get("BACKEND_API_KEY", "")

def get_headers():
    return {"X-API-Key": BACKEND_API_KEY}
```

### Polling Pattern (Status Updates)

Streamlit doesn't support SSE/WebSocket natively in the same way as Next.js. The polling pattern from PRD Section 17.5 is correct:

```python
# In Streamlit callback or form submission
if submitted:
    call_id = submit_transcript_paste(...)
    st.session_state["current_call_id"] = call_id
    st.session_state["status"] = "processing"
    st.rerun()

# In the render function
call_id = st.session_state.get("current_call_id")
if call_id and st.session_state.get("status") == "processing":
    status = poll_call_status(call_id)
    if status == "ready":
        st.session_state["status"] = "ready"
        st.session_state["insights"] = get_insights(call_id)
        st.rerun()
    elif status == "failed":
        st.error("Processing failed. Try again.")
```

Streamlit's `st.progress` + `st.spinner` can provide UX feedback during polling. The 5-second polling interval matches PRD specification.

---

## Research Question 4: Postgres JSONB for Framework Results

**Schema design for storing variable-structure framework outputs (each framework returns different fields). How to query across frameworks efficiently.**

### Existing Schema

From `signalapp/db/models.py`, the `FrameworkResult` model:

```python
class FrameworkResult(BaseModel):
    id: UUID
    analysis_run_id: UUID
    framework_id: str  # "FW-01", "FW-02", etc.
    framework_version: str
    prompt_version: str
    model_used: str
    model_version: str
    prompt_group: str  # "A" | "B" | "C" | "D" | "E"
    score: float | None  # 0-100, nullable
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float  # 0.0-1.0
    headline: str  # max 80 chars
    explanation: str
    evidence: list  # array of segment refs — JSONB
    coaching_recommendation: str
    raw_output: dict  # full LLM response — JSONB
    tokens_input: int
    tokens_output: int
    latency_ms: int
    cost_usd: float
    created_at: datetime
```

The `evidence` and `raw_output` fields are JSONB.

### JSONB Schema Design Patterns

From Postgres JSONB best practices:

**1. Maintain predictable structure within unpredictable outer shell**

Each framework's `raw_output` has a different shape, but within each framework, fields are consistent. The Pydantic models enforce this at the application layer.

**2. Use GIN indexes for queryable JSONB fields**

```sql
-- Index for evidence lookups
CREATE INDEX idx_framework_result_evidence
ON framework_results USING GIN (evidence jsonb_path_ops);

-- Index for raw_output severity lookups
CREATE INDEX idx_framework_result_severity
ON framework_results ((raw_output->>'severity'));

-- Composite index for common query pattern
CREATE INDEX idx_framework_result_run_severity
ON framework_results (analysis_run_id, (raw_output->>'severity'));
```

**3. Expression indexes for cross-framework queries**

For the insight prioritization query (severity + confidence + actionability):

```sql
-- Find all red/orange insights across all frameworks for a call
SELECT fr.*, fw.framework_name
FROM framework_results fr
JOIN framework_runs ON fr.framework_run_id = fr.id
WHERE fr.analysis_run_id = :run_id
AND fr.raw_output->>'severity' IN ('red', 'orange')
ORDER BY
    CASE fr.raw_output->>'severity'
        WHEN 'red' THEN 1
        WHEN 'orange' THEN 2
        WHEN 'yellow' THEN 3
        WHEN 'green' THEN 4
    END,
    (fr.raw_output->>'confidence')::float DESC;
```

### Query Pattern: Cross-Framework Insight Aggregation

```python
# Get all insights for a call, sorted by priority
async def get_call_insights(call_id: UUID, session) -> list[Insight]:
    query = """
        SELECT
            fr.framework_id,
            fr.severity,
            fr.confidence,
            fr.headline,
            fr.explanation,
            fr.evidence,
            fr.coaching_recommendation,
            fr.raw_output
        FROM framework_results fr
        JOIN analysis_runs ar ON fr.analysis_run_id = ar.id
        WHERE ar.call_id = :call_id
        ORDER BY
            CASE fr.severity
                WHEN 'red' THEN 1
                WHEN 'orange' THEN 2
                WHEN 'yellow' THEN 3
                WHEN 'green' THEN 4
            END,
            fr.confidence DESC
    """
    # ...
```

### Hybrid Schema Pattern (for Phase 2+)

The current design stores all variable outputs in `raw_output` JSONB with structured fields (severity, headline, score) as top-level columns. This is the right approach for Phase 1 — it enables:
- Fast filtering/sorting on top-level columns (indexed)
- Full framework-specific data in `raw_output` (flexible)
- Query across frameworks using top-level columns

---

## Research Question 5: S3 for Transcript Storage

**Even without ASR, S3 is still useful for storing uploaded transcript files. Pattern for browser-direct upload to S3 with presigned URLs from FastAPI.**

### Use Case for Phase 1 (Transcript Paste)

Even with transcript paste as the primary input, S3 is useful for:
1. Storing the original transcript file (if user uploads a .txt/.pdf)
2. Storing ASR output for future audio upload feature
3. Storing the "raw" transcript before any processing

### FastAPI Presigned URL Endpoint

```python
# signalapp/api/calls.py
from fastapi import APIRouter, HTTPException
import boto3
from botocore.config import Config
import uuid

router = APIRouter()

s3_client = boto3.client(
    "s3",
    region_name="us-east-1",
    config=Config(signature_version="s3v4")
)

BUCKET_NAME = "signal-transcripts"  # per-environment config


@router.get("/api/calls/upload-url")
async def get_upload_url(
    filename: str,
    content_type: str = "text/plain",
    org_id: str = Depends(get_current_org_id),
) -> dict:
    """
    Generate a presigned PUT URL for browser-direct S3 upload.

    The browser uploads directly to S3 (no server proxy).
    After upload, browser calls /api/calls/register-upload to create the Call record.
    """
    key = f"transcripts/{org_id}/{uuid.uuid4()}/{filename}"

    presigned_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,  # 1 hour
    )

    return {
        "upload_url": presigned_url,
        "key": key,
        "expires_in": 3600,
    }


@router.post("/api/calls/register-upload")
async def register_upload(
    payload: UploadRegisterPayload,
    org_id: str = Depends(get_current_org_id),
):
    """
    Called by browser after S3 upload completes.
    Creates Call record and enqueues transcription job.
    """
    # Create Call record
    call = await call_repo.create(
        org_id=org_id,
        rep_name=payload.rep_name,
        call_type=payload.call_type,
        deal_name=payload.deal_name,
        audio_s3_key=payload.s3_key,  # for ASR path
        input_type="audio",
        processing_status="processing",
    )

    # Enqueue transcription job (or pipeline directly for paste)
    await enqueue_job("run_transcription_job", call.id)

    return {"call_id": str(call.id), "status": "processing"}
```

### Browser-Side Upload Pattern

```javascript
// In Streamlit (using streamlit.components.v1 or pydeck)
async function uploadToS3(file, uploadUrl) {
    const response = await fetch(uploadUrl, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type }
    });
    if (!response.ok) throw new Error("Upload failed");
    return true;
}

// In Streamlit Python:
import streamlit as st
import requests

def get_presigned_url(filename: str, content_type: str) -> str:
    r = requests.get(
        f"{BACKEND_URL}/api/calls/upload-url",
        params={"filename": filename, "content_type": content_type},
        headers=get_headers(),
    )
    return r.json()["upload_url"]
```

### Transcript Paste Path (Phase 1 Priority)

For transcript paste, the flow is simpler — no S3 needed:

```python
@router.post("/api/calls/paste-transcript")
async def create_call_from_transcript(
    payload: PasteTranscriptPayload,
    org_id: str = Depends(get_current_org_id),
):
    """
    Primary Phase 1 input method: paste transcript directly.
    Stores transcript text in Postgres, skips ASR entirely.
    """
    # Parse and segment the transcript
    segments = parse_transcript(payload.transcript_text)

    # Create Call record
    call = await call_repo.create(
        org_id=org_id,
        rep_name=payload.rep_name,
        call_type=payload.call_type,
        deal_name=payload.deal_name,
        input_type="paste",
        processing_status="processing",
    )

    # Store transcript segments
    for idx, seg in enumerate(segments):
        await segment_repo.create(
            call_id=call.id,
            segment_index=idx,
            speaker_name=seg.speaker_name,
            speaker_role=seg.speaker_role,  # "rep" | "buyer" | "unknown"
            start_time_ms=seg.start_time_ms,
            end_time_ms=seg.end_time_ms,
            text_content=seg.text,
        )

    # Enqueue pipeline job (ARQ)
    await enqueue_job("run_pipeline_job", str(call.id))

    return {"call_id": str(call.id), "status": "processing"}
```

---

## Research Question 6: Pass 1 Signal Extraction

**What are the practical patterns for hedge detection, sentiment analysis, and evaluative language extraction using LLMs? How to structure the Pass 1 prompt for consistent structured output?**

### Existing Implementation

The project already has a well-designed Pass 1 implementation in `signalapp/pipeline/nodes/pass1_extract.py` and `signalapp/prompts/pass1/infrastructure_v1.py`. Key patterns confirmed:

### Schema Design

```python
class HedgeInstance(BaseModel):
    segment_id: str
    hedge_text: str
    hedge_type: str  # "epistemic" | "politeness" | "strategic"
    confidence: float = Field(ge=0.0, le=1.0)

class SentimentPoint(BaseModel):
    segment_id: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    notable_shift: bool  # True if delta from previous > 0.3

class AppraisalInstance(BaseModel):
    segment_id: str
    appraisal_type: str  # "affect" | "judgment" | "appreciation"
    target: str  # "product", "team", "timeline", "price"
    polarity: str  # "strongly_positive" | "positive" | "neutral" | "negative" | "strongly_negative"
    text_excerpt: str
```

### Closed-World Contract Pattern

From `infrastructure_v1.py`:

```
SYSTEM: You are analyzing a sales call transcript. Your task is to extract three infrastructure signals that other analysis frameworks will consume.

BEHAVIORAL CONSTITUTION FOR THIS ANALYSIS:
1. EVIDENCE PRINCIPLE: Every classification must be anchored in verbatim text from the transcript.
2. NULL PRINCIPLE: If a signal is absent, output it as absent (empty list or false). Do NOT fabricate.
3. PRECISION PRINCIPLE: Hedge types, sentiment scores, and appraisal classifications must be specific and accurate.
4. CLOSED WORLD: The transcript is your only source. Do not infer speaker intent beyond what the text shows.
```

### Per-Segment Extraction (not summary)

Pass 1 extracts **per-segment** signals, not aggregate summaries. This enables downstream frameworks to filter by segment. The `segment_id` field is the key linking mechanism:

```python
# Pass 1 output per segment
hedges: list[HedgeInstance]  # One entry per hedging phrase per segment
sentiment_trajectory: list[SentimentPoint]  # One entry per segment
evaluative_language: list[AppraisalInstance]  # One entry per appraisal per segment
```

This is the right design — downstream frameworks like Unanswered Questions filter segments to question-adjacent ones; the Emotion framework uses the full trajectory.

### Gate Signal Derivation

From `pass1_extract_node.py` (lines 76-88):

```python
signals = Pass1GateSignals(
    has_competitor_mention=result.contains_comparison_language,
    has_pricing_discussion=result.contains_dollar_amount,
    has_numeric_anchor=result.first_number_speaker is not None,
    has_objection_markers=_detect_objections(result.evaluative_language),
    has_rep_questions=_detect_rep_questions(state["transcript_segments"]),
    has_close_language=_detect_close_language(state["transcript_segments"]),
    call_duration_minutes=result.transiment_duration_minutes,
)
```

The gate signals are derived from Pass 1 output (boolean flags) and passed to the routing function. This matches the routing architecture exactly.

### Temperature Setting

Per `LLM_RELIABILITY_GUIDE.md` temperature map:

| Task | Temperature |
|------|-------------|
| Extract hedge type per segment | 0.0 (deterministic) |
| Sentiment score per segment | 0.0 (deterministic) |
| Appraisal classification | 0.05 (near-deterministic) |

The existing config should set Pass 1 temperature to **0.0** (extraction task).

---

## Research Question 7: Framework Prompt Engineering Basics

**What are the key patterns for writing effective framework prompts that produce consistent structured outputs? How to handle the "absence = insight" (AIM) pattern in prompts?**

### Existing Framework Prompts (Reviewed)

The codebase has well-engineered prompts. Key patterns confirmed:

### 1. Closed-World Contract

Every framework system prompt starts with the closed-world contract:

```
You are a precise sales call analyst. Your ONLY task is to [specific task].
RULES:
1. Every claim must cite verbatim text from the transcript.
2. If evidence is absent: output "not_found". Do NOT generate a low-confidence guess.
3. "I don't know" and "not found" are valid, correct outputs.
```

### 2. Cite-Before-Claim (Evidence-First)

The `unanswered_questions_v1.py` prompt uses a step-by-step evidence-first structure:

```
Step 1: List all questions the rep asked. Copy EXACT question text with segment_id.
Step 2: For each question, find the buyer's immediate response.
Step 3: Classify each response.
Step 4: Calculate counts and severity.
Step 5: Generate coaching recommendation.
```

This is the cite-before-claim pattern from `LLM_RELIABILITY_GUIDE.md` — extract evidence first, then interpret, never the reverse.

### 3. AIM Pattern Implementation

The `batna_detection_v1.py` prompt explicitly handles the AIM pattern:

```
---
AIM PATTERN — MANDATORY ON pricing/negotiation/close CALLS:
If no alternative mentions are found, do NOT return empty/null. Return:
- has_mentioned_alternative: false
- alternative_count: 0
- buyer_leverage_score: 0.85 (weak BATNA = rep has leverage)
- is_aim_null_finding: true
- aim_output: "No alternatives mentioned. Weak BATNA — buyer has limited walkaway options."
- severity: "green"
- headline: "Weak buyer BATNA — leverage confirmed"
- explanation: "Buyer did not reference any alternatives during this call. This suggests they have limited walkaway options and the rep has pricing leverage."
- coaching_recommendation: "Hold the pricing position. Without competitive alternatives, the buyer has less bargaining power."
```

This is the correct implementation: when the framework runs (mandatory call type) but finds nothing, it outputs a structured null-finding that is itself meaningful.

### 4. Severity Scale Definition

Framework prompts include explicit severity rules:

```
Severity rules:
- red: 3+ evaded OR topic_change on critical topics (budget, timeline, authority)
- orange: 2 evaded/topic_changes
- yellow: 1 evaded or vague response on non-critical topic
- green: All questions answered or vague on minor topics
```

### 5. Negative Examples in Few-Shot

The `LLM_RELIABILITY_GUIDE.md` specifies this pattern (not yet in framework prompts):

```python
FEW_SHOT_EXAMPLES = [
    # Correct detection
    {"question": "...", "response": "...", "classification": "topic_change", ...},
    # NOT an evasion — direct answer
    {"question": "...", "response": "The CFO David approves...", "classification": "answered", ...},
    # Vague but not evasive
    {"question": "...", "response": "We're hoping to move fairly quickly", "classification": "vague_response", ...},
]
```

The `unanswered_questions_v1.py` prompt has examples inline but not in this structured few-shot format. For Phase 1 production quality, adding structured few-shot examples would improve accuracy.

### 6. Confidence Calibration

All framework outputs include an explicit `confidence` field (0.0-1.0). The `LLM_RELIABILITY_GUIDE.md` recommends computing confidence from verifiable sub-signals rather than trusting the model's self-assessment:

```python
class CalibratedConfidence:
    evidence_count: int
    quote_verification_score: float
    alternative_explanations: int
    pattern_recurrence: int

    def compute(self) -> float:
        score = 0.40  # Base
        score += min(0.20, self.evidence_count * 0.07)
        score += (self.quote_verification_score - 0.75) * 0.15
        score -= self.alternative_explanations * 0.08
        # ...
```

The current implementation uses the LLM's self-assessed confidence directly. For Phase 2, implementing calibrated confidence computation would improve accuracy.

### Key Prompt Patterns Summary

| Pattern | Implementation Status |
|---------|----------------------|
| Closed-world contract | ✅ In all framework prompts |
| Cite-before-claim | ✅ Step-by-step in unanswered_questions |
| AIM pattern | ✅ Explicit in batna_detection |
| Negative examples | ⚠️ Inline examples, not structured few-shot |
| Explicit severity rules | ✅ In unanswered_questions |
| Segment ID references | ✅ All frameworks reference segment_id (not timestamps) |
| Temperature per task | ⚠️ Not yet configured per framework type |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | API framework | Python-native async, Pydantic v2 integration, OpenAPI auto-generation |
| Pydantic | 2.x | Data validation | Enforces schema at LLM boundary, defines all framework output models |
| LangGraph | 0.2+ | Pipeline orchestration | Checkpointing, state management, conditional edges |
| ARQ | 0.1+ | Job queue | Async-native, Redis-backed, per the ADR replacing Celery |
| asyncpg | 0.30+ | Postgres driver | FastAPI async Postgres access |
| boto3 | latest | AWS S3 | Presigned URL generation |
| `google-genai` | latest | Gemini SDK | Current LLM provider (Anthropic/OpenAI via provider abstraction) |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `langgraph-checkpoint-redis` | LangGraph Redis checkpointing | Recovery speed (not required for correctness — DB is source of truth) |
| `python-jose` | JWT handling | Clerk JWT verification in FastAPI middleware |
| `pydantic-settings` | Settings management | Config from env vars |
| `alembic` | DB migrations | Schema evolution |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Instructor (for Anthropic) | Native JSON schema | Native is simpler for Gemini/Anthropic; Instructor needed only for OpenAI |
| Celery | ARQ | ARQ is async-native (per ADR — already decided) |
| SQLAlchemy | asyncpg directly | Asyncpg is simpler for this use case; SQLAlchemy adds ORM overhead |
| `psycopg2` | asyncpg | sync vs async — FastAPI needs async DB driver |

**Installation:**
```bash
pip install fastapi uvicorn pydantic pydantic-settings asyncpg boto3 arq langgraph google-genai
```

---

## Architecture Patterns

### Project Structure
```
signalapp/
├── app/
│   ├── main.py          # FastAPI app entry
│   ├── config.py         # Settings (from env)
│   └── dependencies.py   # Auth, DB session, queue
├── api/
│   ├── calls.py         # /api/calls/* endpoints
│   ├── insights.py       # /api/calls/{id}/insights
│   └── webhooks.py       # ASR provider callbacks
├── db/
│   ├── models.py         # Pydantic models (DB schema)
│   └── repository.py      # Data access layer
├── adapters/
│   ├── llm/
│   │   ├── base.py       # LLMProvider protocol
│   │   ├── gemini.py     # Gemini implementation
│   │   ├── anthropic.py   # Anthropic implementation (Phase 2)
│   │   └── openai.py     # OpenAI implementation (Phase 2)
│   ├── asr/
│   │   ├── base.py       # ASRProvider protocol
│   │   └── assemblyai.py # AssemblyAI implementation
│   └── storage/
│       └── s3.py         # S3 presigned URL generation
├── pipeline/
│   ├── state.py          # PipelineState TypedDict
│   ├── pipeline.py       # create_pipeline_workflow()
│   └── nodes/
│       ├── pass1_extract.py
│       ├── route.py
│       ├── execute_groups.py
│       ├── verify.py
│       ├── insights.py
│       ├── summary.py
│       └── store.py
├── domain/
│   ├── routing.py        # Routing table, should_run_framework()
│   ├── framework.py      # FrameworkOutput, Severity enum
│   ├── call.py           # Call domain model
│   └── transcript.py     # TranscriptSegment domain model
├── jobs/
│   ├── app.py            # ARQ worker settings
│   ├── pipeline.py       # run_pipeline_job (ARQ job func)
│   ├── transcription.py  # ASR transcription job
│   └── memory.py         # In-memory queue (dev)
├── prompts/
│   ├── pass1/
│   │   └── infrastructure_v1.py
│   └── groups/
│       ├── group_a/      # batna_detection, money_left_on_table, etc.
│       ├── group_b/      # unanswered_questions, commitment_quality, etc.
│       ├── group_c/      # question_quality, call_structure, etc.
│       └── group_e/      # emotional_turning_points
└── reliability/
    ├── retry.py          # Retry logic
    ├── circuit_breaker.py # Cost circuit breaker
    └── cost_tracker.py   # Per-call cost tracking
```

### Key Flow: Transcript Paste to Insights

```
Streamlit (paste transcript)
    │
    │ POST /api/calls/paste-transcript
    ▼
FastAPI (creates Call + TranscriptSegments in Postgres)
    │
    │ Enqueue: run_pipeline_job(call_id)
    ▼
ARQ Worker (async job)
    │
    ├─► Pass1ExtractNode (LLM call → hedge/sentiment/appraisal)
    │       │
    │       ▼
    │   RouteNode (pure Python → active frameworks)
    │       │
    │       ▼
    │   ExecuteGroupsNode (asyncio.gather → Group A/B/C/E LLM calls)
    │       │
    │       ▼
    │   VerifyNode (7-gate verification)
    │       │
    │       ▼
    │   InsightsNode (prioritization)
    │       │
    │       ▼
    │   SummaryNode (LLM summary generation)
    │       │
    │       ▼
    │   StoreNode (write to DB)
    │
    ▼
Streamlit polls GET /api/calls/{id}/insights
    │
    ▼
Insight cards displayed
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Routing decisions | LLM-based routing | Pure Python table lookup | Routing costs $0.00; LLM adds latency + cost + failure mode |
| Framework execution orchestration | Custom asyncio task management | LangGraph StateGraph | LangGraph provides checkpointing, retry, state management built-in |
| JSON schema enforcement | String parsing + regex | Pydantic model validation | Pydantic enforces schema at LLM boundary; regex breaks on model changes |
| Transcript segmentation | Rule-based parsing | LLM-based segmentation | Sales conversations have irregular turn-taking; rules fail on overlap/pause |
| Timestamp generation | Trust LLM timestamps | Store segment IDs, resolve from DB | LLM hallucinates timestamps; DB is ground truth |

**Key insight:** The LLM is the source of behavioral analysis. Everything else (routing, state management, persistence, verification) must be deterministic and verifiable.

---

## Common Pitfalls

### Pitfall 1: LLM Confabulation on "No Signal" Cases

**What goes wrong:** Frameworks produce confident-seeming output on calls where the signal is absent. The model fills the vacuum because it was asked to find something.

**Why it happens:** The "cite-before-claim" pattern is not enforced, or negative examples are absent from the prompt.

**How to avoid:** Explicit null templates + negative examples in every framework prompt. The AIM pattern MUST produce a valid structured output (severity: "green", headline: "No X detected") rather than null.

**Warning signs:** A framework produces identical confidence scores across all calls regardless of content. Framework fires at same rate on clean calls as on problematic calls.

### Pitfall 2: Schema Drift Between Framework Outputs

**What goes wrong:** Each framework's Pydantic model evolves independently. The `raw_output` JSONB in Postgres accumulates incompatible schemas.

**Why it happens:** No schema versioning strategy. Framework prompts are updated but old outputs remain in the DB.

**How to avoid:** Every framework output model has a `version` field. Prompt versioning is logged in `AnalysisRun.settings_snapshot`. Re-analysis regenerates `raw_output` with current schema.

### Pitfall 3: Routing Gate Uses Pass 1 Output Incorrectly

**What goes wrong:** Pass 1 content gates (e.g., `has_competitor_mention`) use low-confidence detections to block frameworks that should run.

**Why it happens:** Content signal thresholds are too high. Per routing architecture: "Use low confidence thresholds for routing gates — better to over-trigger than miss."

**How to avoid:** Gate signals use simple boolean derivations (exact text match, count). Framework output confidence is separate from routing gate confidence.

### Pitfall 4: Long Transcript Context Degrading Quality

**What goes wrong:** Full transcript (10,000+ tokens) passed to all frameworks causes attention diffusion, segment confusion, higher hallucination rates.

**Why it happens:** Naive implementation passes full transcript to every framework prompt.

**How to avoid:** Segment-filtered context windows per framework. Only frameworks that genuinely need full transcript (call_structure, frame_match) receive it. Others receive question-adjacent segments or topic-filtered segments.

---

## Code Examples

### Routing Decision (from `signalapp/domain/routing.py`)

```python
@dataclass
class FrameworkRoutingSpec:
    fw_id: int
    mandatory_for: set[str] = field(default_factory=set)
    blocked_for: set[str] = field(default_factory=set)
    required_signal: str | None = None

def should_run_framework(fw_id: int, call_type: str, signals: Pass1GateSignals) -> bool:
    spec = ROUTING_TABLE[fw_id]
    if fw_id in PINNED_FRAMEWORKS: return True
    if call_type in spec.blocked_for: return False
    if call_type in spec.mandatory_for: return True  # AIM: bypass content gate
    if spec.required_signal: return bool(getattr(signals, spec.required_signal, False))
    return True
```

### Pass 1 Gate Signal Extraction

```python
signals = Pass1GateSignals(
    has_competitor_mention=result.contains_comparison_language,
    has_pricing_discussion=result.contains_dollar_amount,
    has_numeric_anchor=result.first_number_speaker is not None,
    has_objection_markers=_detect_objections(result.evaluative_language),
    has_rep_questions=_detect_rep_questions(segments) >= 3,
    has_close_language=_detect_close_language(segments),
    call_duration_minutes=result.transcript_duration_minutes,
)
```

### Framework Group Batched Execution

```python
async def execute_groups_node(state: PipelineState) -> dict:
    tasks = []
    for fw_id in active_frameworks:
        group_id = FW_PROMPT_MAP[fw_id][0]
        config_key = GROUP_LLM_CONFIG_KEY[group_id]
        task = _run_framework(fw_id, ...)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Handle individual failures gracefully
    for fw_id, result in zip(active_frameworks, results):
        if isinstance(result, Exception):
            framework_errors[fw_id] = str(result)
        elif result:
            framework_results[fw_id] = result.model_dump()
```

### Presigned URL Generation (FastAPI)

```python
@router.get("/api/calls/upload-url")
async def get_upload_url(filename: str, content_type: str = "text/plain"):
    key = f"transcripts/{org_id}/{uuid.uuid4()}/{filename}"
    presigned_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=3600,
    )
    return {"upload_url": presigned_url, "key": key}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery + Redis (per PRD v2.1) | ARQ + Redis | Phase 1 ADR | Async-native, simpler queue model |
| Next.js frontend | Streamlit frontend | Per user constraint | Faster iteration, simpler POC |
| Custom routing ML model | Pure Python routing table | Phase 1 | Zero cost, deterministic, no training data needed |
| Full-transcript prompting | Segment-filtered context | Phase 1 (per LLM guide) | 30-50% hallucination reduction |
| Model self-assessed confidence | Calibrated confidence from evidence | Phase 2 (future) | More accurate confidence scores |
| Single framework per LLM call | Batched frameworks per group | Phase 1 | 4-5x cost reduction per group |

---

## Open Questions

1. **Transcript format parsing for paste input**
   - What formats to support? Gong export, Zoom transcript, Otter, plain text?
   - Current `parse_transcript()` in streamlit_app.py only handles `[MM:SS] Speaker (role): text`
   - Recommendation: Support Gong format as v1 (most common), add more parsers in subsequent phases

2. **Speaker role detection for pasted transcripts**
   - The `[MM:SS] Speaker (role): text` format requires explicit `(rep)` or `(buyer)` labels
   - Gong exports use different labels (e.g., "Agent", "Customer")
   - Need a mapping table for common transcript formats
   - Recommendation: Start with Gong format mapping, add others as needed

3. **Re-analysis granularity**
   - PRD specifies `force_reanalyze` flag re-runs from specified stage
   - Currently not implemented — re-analysis re-runs entire pipeline
   - Recommendation: Implement stage-level re-analysis in Phase 2

4. **Golden dataset for promptfoo evaluation**
   - LLM_RELIABILITY_GUIDE.md specifies 5 manually annotated calls minimum
   - No golden dataset exists yet in the codebase
   - Recommendation: Create 5 annotated calls in Phase 1 as part of Slice 5 (promptfoo setup)

---

## Environment Availability

Step 2.6: SKIPPED (no external tool dependencies beyond code)

**Phase 1 backend dependencies are all Python packages installable via pip:**
- FastAPI, Pydantic, asyncpg, boto3, arq, langgraph, google-genai — all pip-installable
- Postgres, Redis, S3 — assumed to be provided (per PRD infrastructure decisions)
- No system-level tools or CLIs required beyond Python 3.11+

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` or `pyproject.toml` [tools.pytest] |
| Quick run command | `pytest signalapp/tests/unit/ -x -q` |
| Full suite command | `pytest signalapp/tests/ -q --tb=short` |

### Existing Test Infrastructure
- `signalapp/tests/unit/test_routing.py` — routing table correctness
- `signalapp/tests/unit/test_framework_outputs.py` — Pydantic schema validation
- `signalapp/tests/integration/test_pipeline.py` — end-to-end pipeline (scaffolded)
- No conftest.py yet — shared fixtures needed

### Phase Requirements Test Map
| Req ID | Behavior | Test Type | Command | File |
|--------|----------|-----------|---------|------|
| REQ-01 | Transcript paste → segments stored | unit | `pytest tests/test_transcript_paste.py -x` | MISSING |
| REQ-02 | Pass 1 extraction produces hedge/sentiment/appraisal | unit | `pytest tests/test_pass1.py -x` | MISSING |
| REQ-03 | Routing table decisions match spec | unit | `pytest signalapp/tests/unit/test_routing.py -x` | ✅ exists |
| REQ-04 | Framework groups execute in asyncio.gather | integration | `pytest signalapp/tests/integration/test_pipeline.py -x` | ⚠️ scaffolded |
| REQ-05 | JSONB framework results stored + queryable | integration | `pytest tests/test_framework_results.py -x` | MISSING |
| REQ-06 | Insights prioritized by severity/confidence | unit | `pytest tests/test_insights.py -x` | MISSING |
| REQ-07 | FastAPI endpoints return correct JSON | integration | `pytest tests/test_api.py -x` | MISSING |
| REQ-09 | ARQ job enqueues and executes pipeline | integration | `pytest tests/test_arq_jobs.py -x` | MISSING |

### Wave 0 Gaps
- [ ] `signalapp/tests/conftest.py` — shared fixtures (db_session, sample_transcript, sample_call)
- [ ] `signalapp/tests/unit/test_transcript_paste.py` — REQ-01
- [ ] `signalapp/tests/unit/test_pass1.py` — REQ-02
- [ ] `signalapp/tests/unit/test_insights.py` — REQ-06
- [ ] `signalapp/tests/integration/test_api.py` — REQ-07
- [ ] `signalapp/tests/integration/test_arq_jobs.py` — REQ-09
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`

---

## Sources

### Primary (HIGH confidence)
- `signalapp/pipeline/state.py` — PipelineState TypedDict confirms LangGraph state schema
- `signalapp/jobs/pipeline.py` — ARQ job function + idempotency pattern
- `signalapp/pipeline/nodes/execute_groups.py` — asyncio.gather pattern for framework execution
- `signalapp/prompts/pass1/infrastructure_v1.py` — Pass 1 prompt engineering patterns
- `signalapp/prompts/groups/group_b/unanswered_questions_v1.py` — Framework prompt structure
- `signalapp/prompts/groups/group_a/batna_detection_v1.py` — AIM pattern implementation
- `signalapp/domain/routing.py` — Routing table + should_run_framework
- `signalapp/adapters/llm/gemini.py` — Native JSON schema pattern
- `References/LLM_RELIABILITY_GUIDE.md` — Full reliability patterns
- `References/FRAMEWORK_ROUTING_ARCHITECTURE.md` — Routing spec
- `References/Signal_PRD_v2.2.md` Sections 5, 13, 16, 17, 18, 21

### Secondary (MEDIUM confidence)
- https://arq-docs.helpmanual.io/ — ARQ async integration patterns
- https://pypi.org/project/langgraph-checkpoint-redis/ — LangGraph Redis checkpointing pattern
- https://www.postgresql.org/docs/current/datatype-json.html — JSONB best practices
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html — Presigned URL pattern

### Tertiary (LOW confidence — needs verification)
- Instructor Python SDK patterns — not confirmed from official docs; existing code uses native Gemini schema
- Streamlit `st.login` / `st.logout` patterns — documentation reference only; not tested in this codebase
- LangGraph checkpointing + ARQ integration — not implemented in current codebase; pattern is inferred from library docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing code confirms all major libraries and versions
- Architecture: HIGH — routing, pipeline, and framework patterns confirmed in existing code
- Pitfalls: MEDIUM — patterns documented in LLM_RELIABILITY_GUIDE.md, not all implemented yet

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days — behavioral pipeline patterns are stable)
