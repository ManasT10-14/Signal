# Signal — Phased Implementation Plan

> **Input mode:** Transcript paste only. No audio files, no ASR transcription, no S3 storage. The user pastes a transcript directly. This dramatically simplifies the stack — no AssemblyAI, no Deepgram, no audio processing, no audio playback, no S3.

**Phase 1:** Backend Completion
**Phase 2:** Testing & Polish
**Phase 3:** Full-Stack Streamlit App
**Phase 4:** Deployment
**Phase 5:** Polish & Bug Fixes

---

## Phase 1 — Backend Completion

**Goal:** Fix all broken/missing backend modules. The backend processes transcripts only — no audio, no ASR, no S3.

### 1.1 Create `pyproject.toml`

**Files affected:**
- `pyproject.toml` (new)

**What:**
- Package name: `signalapp`
- Python >= 3.11
- All `requirements.txt` entries as dependencies (minus ASR/S3 packages)
- `signalapp` package with `__version__`
- Build system: `hatchling`

**Dependencies:** None
**Risks:** Low.

**Test cases:**
- `pip install -e .` succeeds
- `import signalapp` works

**Definition of Done:**
- `pip install -e .` installs without errors
- All existing modules import cleanly under the package

---

### 1.2 Fix `submit_insight_feedback()` persistence

**Files affected:**
- `signalapp/api/insights.py`

**What:**
- Replace the stub that returns `{"ok": True}` without persisting
- Look up `Insight` record by `insight_id`
- Write `feedback` enum and `feedback_at` timestamp to the DB row
- Return the updated insight

**Dependencies:** Phase 1.1
**Risks:** Low.

**Test cases:**
- POST `/api/v1/insights/{id}/feedback` with `positive` → DB row updated
- POST with `negative` → DB row updated
- POST with invalid UUID → 404
- Feedback already exists → overwritten with new value and timestamp

**Definition of Done:**
- `POST /insights/{id}/feedback` persists to DB and returns 200

---

### 1.3 Remove ASR and S3 modules

**Files affected:**
- `signalapp/adapters/asr/` (dir)
- `signalapp/adapters/storage/` (dir)
- `signalapp/jobs/transcription.py`
- `signalapp/api/webhooks.py`
- `signalapp/app/config.py`

**What:**
Audio and ASR are out of scope. Remove or stub the following:

- Delete `signalapp/adapters/asr/` directory entirely (AssemblyAI and Deepgram providers)
- Delete `signalapp/adapters/storage/` directory entirely (S3 storage)
- Remove or stub `signalapp/jobs/transcription.py` (ASR job)
- Remove or stub `signalapp/api/webhooks.py` (ASR webhook endpoints)
- Remove ASR-related env vars from `AppConfig` (`ASSEMBLYAI_API_KEY`, `DEEPGRAM_API_KEY`)
- Remove S3-related env vars from `AppConfig` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`)
- Remove `submit_transcription_job` from `signalapp/jobs/__init__.py`

**Keep:**
- `signalapp/domain/transcript.py` — the `TranscriptSegment` and `Transcript` domain models (used for parsing pasted transcripts)
- `signalapp/db/models.py` — `Transcript` table (stores pasted text, not audio references)

**Dependencies:** Phase 1.1
**Risks:** Medium. Need to verify no other code imports these modules.

**Test cases:**
- `import signalapp` succeeds with no ASR or S3 dependencies
- No code attempts to import `assemblyai`, `deepgram`, or `boto3` modules
- `pip install -e .` succeeds without those packages

**Definition of Done:**
- `signalapp/adapters/asr/` deleted
- `signalapp/adapters/storage/` deleted
- `signalapp/jobs/transcription.py` removed or stubbed
- `signalapp/api/webhooks.py` removed or stubbed
- App still starts and serves transcript-paste API without errors

---

### 1.4 Implement `signalapp/reliability/` module

**Files affected:**
- `signalapp/reliability/__init__.py` (new)
- `signalapp/reliability/retry.py` (new)
- `signalapp/reliability/circuit_breaker.py` (new)
- `signalapp/reliability/cost_tracker.py` (new)

**What:**

**`retry.py`:**
```python
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    exponential_base: float = 2.0
    max_delay: float = 30.0

async def with_retry(coro, config: RetryConfig) -> T
```

**`circuit_breaker.py`:**
```python
class CircuitBreaker:
    failures: int
    threshold: int = 5
    reset_timeout: float = 60.0
    state: Literal["closed", "open", "half-open"]

    async def call(coro) -> T
```

**`cost_tracker.py`:**
```python
@dataclass
class CallCost:
    call_id: str
    llm_cost_usd: float
    total_cost_usd: float
    model: str
    timestamp: datetime

class CostTracker:
    async def record(cost: CallCost)
    async def get_call_cost(call_id) -> CallCost
    async def get_total_cost_period(start, end) -> float
```

**Dependencies:** Phase 1.1, Phase 1.3
**Risks:** Medium. Circuit breaker state management in async context.

**Test cases:**
- Retry fires on first failure, succeeds on second attempt
- Retry exhausted → raises last exception
- Circuit breaker opens after 5 failures in 60s
- Circuit breaker half-open allows 1 test request
- CostTracker records and retrieves cost per call

**Definition of Done:**
- All 3 modules implemented and importable
- `with_retry` wraps LLM calls in `execute_groups_node`
- `CircuitBreaker` wraps LLM provider calls
- `CostTracker` called from `execute_groups_node` and `pass1_extract_node`

---

### 1.5 Guard `execute_groups_node` for LLM availability

**Files affected:**
- `signalapp/pipeline/nodes/execute_groups.py`

**What:**
- At the top of `execute_groups_node`, check if `GEMINI_API_KEY` or `GOOGLE_CLOUD_PROJECT` is set
- If neither is set, return stub results for all active frameworks (explicit, not silent)
- Log a warning that LLM is not configured

**Dependencies:** Phase 1.1, Phase 1.3
**Risks:** Low.

**Test cases:**
- No LLM credentials → returns stub results with warning log
- LLM credentials present → proceeds normally

**Definition of Done:**
- Pipeline fails fast and explicitly when no LLM is configured
- No silent mock data

---

### 1.6 Fix `CallRepository.get()` N+1 query problem

**Files affected:**
- `signalapp/db/repository.py`

**What:**
- Add `selectinload` for `transcript`, `analysis_runs`, `insights` relationships in `CallRepository.get()`
- Add a `get_with_details(call_id)` method for pages needing all related data

**Dependencies:** Phase 1.1
**Risks:** Low.

**Test cases:**
- `get_with_details(id)` returns call with transcript and insights preloaded
- No N+1 queries on Call Review page

**Definition of Done:**
- Call Review page loads without N+1 queries

---

### 1.7 Externalize Pass 1 model to config

**Files affected:**
- `signalapp/pipeline/nodes/pass1_extract.py`
- `signalapp/app/config.py`

**What:**
- Remove hardcoded `model="claude-sonnet-4-20250514"`
- Add `pass1_model` to `AppConfig.llm_groups`
- Read model from config in `pass1_extract_node`

**Dependencies:** Phase 1.1
**Risks:** Low.

**Test cases:**
- Changing `config.py` changes the model used in Pass 1

**Definition of Done:**
- No hardcoded model strings in `pass1_extract.py`

---

### Phase 1 Definition of Done

- [ ] `pyproject.toml` installs cleanly with `pip install -e .`
- [ ] `submit_insight_feedback()` persists to DB
- [ ] ASR and S3 modules removed — app starts without audio/ASR dependencies
- [ ] All 3 reliability modules implemented
- [ ] Pipeline fails fast when LLM not configured
- [ ] `CallRepository.get()` eager-loads relationships
- [ ] No hardcoded model strings in pipeline nodes
- [ ] All modules still importable after changes

---

## Phase 2 — Testing & Polish

**Goal:** Establish a test suite, then polish the Streamlit app by integrating real backend modules.

### 2.1 Unit tests: routing engine

**Files affected:**
- `signalapp/tests/unit/test_routing.py` (new)

**What:**
Test every entry in the routing table against `FRAMEWORK_ROUTING_ARCHITECTURE.md`.

```python
class TestShouldRunFramework:
    @pytest.mark.parametrize("fw_id", range(1, 18))
    @pytest.mark.parametrize("call_type", CALL_TYPES)
    def test_routing_table_completeness(fw_id, call_type):
        # Every fw × call_type has exactly one outcome

    def test_pinned_frameworks_always_run(self):
        # FW 8, 9, 15 return True for all call types

    def test_aim_frameworks_run_without_signal(self):
        # FW 3 on "pricing" → True even if has_competitor_mention=False
        # FW 11 on "demo" → True even if has_close_language=False

    def test_dependency_enforcement(self):
        # Remove FW 8 → FW 9 removed
        # Remove FW 5 or FW 15 → FW 14 removed
        # Remove FW 16 → FW 17 removed

    def test_short_call_removes_13_and_14(self):
        # call_duration_minutes < 8 → 13 and 14 removed (15 stays)

    def test_fail_open_on_error(self):
        # Exception in should_run_framework → returns True
```

**Dependencies:** Phase 1.1, Phase 1.5
**Risks:** Low.

**Definition of Done:**
- `pytest signalapp/tests/unit/test_routing.py` passes 100%
- Every routing rule from `FRAMEWORK_ROUTING_ARCHITECTURE.md` has a corresponding test

---

### 2.2 Unit tests: framework output schemas

**Files affected:**
- `signalapp/tests/unit/test_framework_outputs.py` (new)

**What:**
Test that each framework's Pydantic output model accepts valid inputs and rejects invalid ones.

```python
class TestBatnaDetectionOutput:
    def test_valid_output(self): ...
    def test_missing_required_field_raises(self): ...
    def test_severity_enum_validation(self): ...
    def test_confidence_clamped_to_0_1(self): ...
    def test_aim_null_finding_has_required_fields(self): ...

# ... one test class per framework (15 classes)
```

Also test that `_to_framework_output()` in `execute_groups.py` correctly maps each prompt's output schema to `FrameworkOutput`.

**Dependencies:** Phase 1.1
**Risks:** Low.

**Definition of Done:**
- All 15 framework output models validated
- `FrameworkOutput` returned correctly from all code paths

---

### 2.3 Integration tests: full pipeline

**Files affected:**
- `signalapp/tests/integration/test_pipeline.py` (new)

**What:**
End-to-end pipeline test with a pasted transcript.

```python
class TestPipelineExecution:
    async def test_full_pipeline_runs_without_error(self):
        # Run LangGraph pipeline on a transcript
        # Verify all 7 nodes complete without raising
        # Verify framework_results dict populated for active frameworks

    async def test_pipeline_stores_results(self):
        # Run pipeline, verify AnalysisRun, Pass1Result, FrameworkResult, Insight rows created

    async def test_pipeline_handles_missing_llm(self):
        # Run pipeline without LLM credentials
        # Verify stub results returned, not silent mock data

    async def test_insight_prioritization(self):
        # Verify top 5 sorted by severity → confidence
```

**Dependencies:** Phase 1.1, Phase 1.5, Phase 1.6, Phase 2.1
**Risks:** Medium. Pipeline tests need DB.

**Definition of Done:**
- All integration tests pass
- Pipeline completes without errors
- Results persisted to DB correctly

---

### 2.4 Streamlit: import real backend modules

**Files affected:**
- `streamlit_app.py`

**What:**
Replace all duplicated logic in Streamlit with imports from the actual `signalapp` package:

1. **Routing engine** — Import `route_frameworks`, `should_run_framework`, `Pass1GateSignals`, `ROUTING_TABLE`, `GROUP_MEMBERSHIP` from `signalapp.domain.routing`. Remove duplicated routing logic.

2. **Framework registry** — Import `FRAMEWORK_REGISTRY` from `signalapp.domain.framework`.

3. **Transcript parsing** — Import `TranscriptSegment`, `Transcript` from `signalapp.domain.transcript`.

4. **Base metrics** — Use actual base metric computation logic from `signalapp/jobs/preprocessing.py`.

5. **Pass1 gate signals** — Import `extract_gate_signals` from `signalapp.domain.routing`.

6. **Framework outputs** — Import actual Pydantic models from `signalapp.prompts.groups.*`.

**Fix circular imports:** If `signalapp` modules have FastAPI-only imports at module level (e.g., `fastapi` in `__init__.py`), guard them with `TYPE_CHECKING`.

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from signalapp.domain.routing import route_frameworks, Pass1GateSignals, ROUTING_TABLE
from signalapp.domain.framework import FRAMEWORK_REGISTRY
```

**Dependencies:** Phase 1.1, Phase 2.1
**Risks:** Medium. Circular import risk if signalapp has FastAPI-only top-level imports.

**Test cases:**
- `streamlit run streamlit_app.py` imports `signalapp.domain.routing` without errors
- Routing decisions in Streamlit match the Python unit tests

**Definition of Done:**
- `signalapp.domain.routing`, `signalapp.domain.framework`, `signalapp.domain.transcript` all imported and used in Streamlit
- Zero duplicated routing/domain logic in Streamlit

---

### 2.5 Streamlit: evidence linking and transcript sync

**Files affected:**
- `streamlit_app.py`

**What:**
Add clickable timestamps in insight cards that highlight the relevant transcript segment.

- Insight cards show evidence excerpts with timestamps: `[12:30]`
- Clicking a timestamp sets `st.session_state.active_segment_ts` and re-renders
- Transcript viewer highlights the active segment with a teal left border and subtle background

```python
# Insight card:
if st.button(f"📎 See {ev['timestamp']}", key=f"ev_{idx}"):
    st.session_state.active_segment_ts = ev["timestamp"]
    st.rerun()

# Transcript viewer:
for seg in segments:
    is_active = seg["start_str"] == st.session_state.get("active_segment_ts")
    style = "border-left:3px solid #0D9488;background:#F0FDF4;" if is_active else ""
    st.markdown(f"[{seg['start_str']}] **{seg['speaker']}**: {seg['text']}", unsafe_allow_html=True)
```

**Dependencies:** Phase 2.4
**Risks:** Low.

**Definition of Done:**
- Evidence timestamps are clickable and highlight transcript segments

---

### 2.6 Streamlit: Pass1 signals debug panel

**Files affected:**
- `streamlit_app.py`

**What:**
Show the actual Pass1 gate signals derived from transcript in the Routing Debug tab:

- Hedge density per segment
- Sentiment trajectory
- Evaluative language counts (affect/judgment/appraisal)
- Raw signal values that gate framework execution

This helps users understand why certain frameworks ran or didn't run.

**Dependencies:** Phase 2.4
**Risks:** Low.

**Definition of Done:**
- Pass1 signals displayed in Routing Debug tab with actual derived values

---

### Phase 2 Definition of Done

- [ ] `pytest signalapp/tests/unit/test_routing.py` passes 100%
- [ ] `pytest signalapp/tests/unit/test_framework_outputs.py` passes 100%
- [ ] `pytest signalapp/tests/integration/test_pipeline.py` passes 100%
- [ ] Streamlit imports `signalapp.domain.routing`, `.framework`, `.transcript` without errors
- [ ] Evidence timestamps are clickable and highlight transcript segments
- [ ] Pass1 signals debug panel shows actual gate signal values

---

## Phase 3 — Full-Stack Streamlit App

**Goal:** Build the complete Streamlit application covering all PRD product surfaces — Dashboard, Upload (transcript paste only), Calls List, Call Review, Settings.

> **No audio. No ASR. No S3. Users paste transcripts. Everything else works the same.**

---

### 3.1 Streamlit: multi-page architecture

**Files affected:**
- `streamlit_app.py` (refactor to use `st.navigation`)
- `pages/` directory

**What:**
Convert to Streamlit's native multi-page architecture:

```
streamlit_app.py          # Main entry
pages/
  01_Dashboard.py         # Aggregate stats, quick actions
  02_Analyze.py           # Paste transcript + metadata → run analysis
  03_Calls_List.py        # All calls with filters and status
  04_Call_Review.py       # The product — insights + transcript + stats
  05_Routing_Explorer.py  # Interactive routing table tool
  06_Settings.py          # LLM/Framework config
  07_Sample_Calls.py      # Pre-loaded demo calls
```

Use Streamlit's `st.navigation` for clean page switching.

**Dependencies:** Phase 2.4
**Risks:** Low.

**Definition of Done:**
- 7 pages accessible via Streamlit's native navigation
- No `if st.sidebar: ...` chains for page routing

---

### 3.2 Streamlit: Calls List page

**Files affected:**
- `pages/03_Calls_List.py`

**What:**
Per PRD Section 8 and wireframe 7B.2:

- Table with columns: Title, Rep, Type, Date, Duration, Status
- Second line per row: highest-severity insight headline preview
- Filter bar: Rep (text filter), Call Type (dropdown), Date range, Status (dropdown)
- Sort: click column header to toggle ascending/descending
- Row click → navigate to Call Review page
- Hover: 3-dot menu (⋮) with: Rename, Re-analyze, Delete
- Delete: confirmation modal
- Pagination: "Showing N of M calls" with Previous/Next
- Empty state: centered with "Upload Your First Call" CTA
- Calls load from backend via `GET /api/v1/calls`

**Dependencies:** Phase 3.1
**Risks:** Low.

**Definition of Done:**
- Matches PRD wireframe 7B.2
- All filters and pagination work
- Responsive at wide and narrow window sizes

---

### 3.3 Streamlit: Call Review page (core product)

**Files affected:**
- `pages/04_Call_Review.py`

**What:**
Per PRD Section 9 and wireframe 7B.3 — the primary product surface.

**Layout:** Two-column, 60/40 split.

**Left column:**
- **Transcript viewer (full height, scrollable):**
  - Search bar with match count and ↑↓ navigation
  - Each segment: `[MM:SS]` timestamp, speaker name (colored), text
  - Rep segments: blue background (`#DBEAFE`) with blue speaker text
  - Buyer segments: amber background (`#FEF3C7`) with amber speaker text
  - Active/highlighted segment: teal left border + light teal background
  - Click segment to highlight it (for evidence linking)
  - No audio player (transcript-only mode — no audio to play)

**Right column (tabs):**
- **💡 Insights tab:**
  - Top 3–5 insight cards sorted by severity → confidence
  - Each card: severity badge, framework name, score, headline, explanation, evidence excerpts with clickable timestamps, coaching recommendation in teal box, 👍👎 feedback buttons
  - Expandable: "All Framework Results (N/17)"
- **📊 Call Stats tab:**
  - Talk ratio: horizontal stacked bar (Rep % / Buyer %)
  - Questions: Rep count, Buyer count
  - Words/minute, Total segments, Rep/Buyer segment counts
  - Note: "Base metrics computed from transcript text. Audio-requiring metrics (silence ratio, response latency) require audio upload."
- **📝 Summary tab:**
  - AI-generated recap, key decisions, action items, open questions, deal assessment
  - Copy button: copies full summary as formatted text
- **🔬 Frameworks tab:**
  - All 17 frameworks grouped by group (A–E)
  - Each row: status badge (🟢 Production / 🟡 Beta / 🔴 Placeholder), framework name, severity dot, confidence %, one-line score summary
  - Expandable rows showing full explanation and coaching recommendation

**Processing state:** "Analyzing behavioral patterns..." with spinner, results appear incrementally as groups complete.

**Dependencies:** Phase 3.1, Phase 2.5 (evidence linking)
**Risks:** High. Most complex page.

**Definition of Done:**
- Matches PRD wireframe 7B.3 (transcript-only variant — no audio player)
- All 4 tabs functional
- Evidence timestamps link to transcript segments

---

### 3.4 Streamlit: Upload / Analyze flow

**Files affected:**
- `pages/02_Analyze.py`

**What:**
Per PRD wireframe 7B.4 (transcript paste variant — no audio tab):

**Single mode: Paste Transcript**

- Large text area with placeholder showing expected format:
  ```
  [00:00] Speaker (rep): Thanks for joining today...
  [00:15] Speaker (buyer): Happy to be here. I've reviewed the proposal...
  ```
- Auto-detect speaker labels and timestamps from Gong/Zoom/Otter format
- If format not recognized, treat entire text as single speaker turn and prompt user to fix format

**Metadata fields:**
- Rep Name: text input with autocomplete from previous uploads
- Call Type: dropdown (discovery/demo/pricing/negotiation/close/check_in/other)
- Deal Name: optional text input
- Date: date input defaulting to today
- Notes: optional text area

**After submit:**
- Call saved to DB via `POST /api/v1/calls/upload`
- Pipeline runs immediately (transcript → Pass1 → Routing → Frameworks → Insights)
- Redirect to Call Review page with "Processing..." state
- Real-time status updates as pipeline stages complete

**Transcript format detection:**
- Pattern: `[MM:SS] Name (role): text` — full parse
- Pattern: `Name: text` per line — simple parse with role detection
- Plain paragraph — single speaker mode with warning

**Dependencies:** Phase 3.1
**Risks:** Low.

**Definition of Done:**
- Paste submit → pipeline runs → Call Review shows results
- Transcript format auto-detected
- Metadata autocomplete works

---

### 3.5 Streamlit: Settings page

**Files affected:**
- `pages/06_Settings.py`

**What:**
Per PRD wireframe 7B.5 (LLM/Framework config only — no ASR config):

**Left sidebar navigation:** LLM Config, Frameworks, Cost Tracking

**LLM Config section:**
- Table with one row per prompt group (A–E)
- Columns: Group, Model (dropdown with pinned version strings), Temperature (slider), Max Tokens (number input)
- "Test Connection" button per group that calls the LLM with a short probe prompt

**Frameworks section:**
- Table of all 17 frameworks
- Columns: Name, Group, Status (🟢/🟡/🔴), Toggle (on/off), Confidence Threshold
- Batch toggles: "Enable All", "Disable All"
- Changes saved to Streamlit session state (and to DB via API)

**Cost Tracking section:**
- Estimated cost/call (last 10 calls average)
- Monthly total, Daily total
- Cost cap settings (warn at / hard stop at)
- "Open Langfuse Dashboard" link

**Dependencies:** Phase 3.1
**Risks:** Low.

**Definition of Done:**
- All settings sections functional
- Framework toggles persist during session

---

### 3.6 Streamlit: Sample Calls

**Files affected:**
- `pages/07_Sample_Calls.py`
- `data/sample_calls/` directory (JSON seed files)

**What:**
Per PRD Section 8A — 3 pre-analyzed sample calls bundled as JSON seed data.

**Sample Call 1: "Pricing Negotiation Gone Wrong"**
- Type: Pricing / Negotiation · Duration: 34 min · Rep: Alex · Buyer: Sarah
- Scenario: Two unconditional concessions ($21K total), buyer evaded budget authority questions
- Top insights: Money Left on Table (🔴), Unanswered Questions (🟠), Commitment Thermometer (🟠)

**Sample Call 2: "Strong Discovery Call"**
- Type: Discovery · Duration: 28 min · Rep: Maya · Buyer: James
- Scenario: Clear pain, timeline, budget range, decision-maker map — all signals green
- Top insight: Deal Timing — "Deal appears ready to advance"

**Sample Call 3: "Demo with Objections"**
- Type: Demo · Duration: 41 min · Rep: Jordan · Buyer: Taylor
- Scenario: 3 objections raised, competitor mentioned, close attempt at 38:47 deferred
- Top insights: Pushback Classification, BATNA Detection, Close Attempt Analysis

Each JSON file contains:
- `call_metadata`: id, rep, buyer, type, duration, date
- `transcript_segments`: `[{start_ms, speaker, role, text}]`
- `pass1_result`: hedge_data, sentiment_data, appraisal_data
- `framework_results`: full framework output dicts for all 17
- `insights`: prioritized top 5
- `base_metrics`: all 8 computed metrics

**Dependencies:** Phase 3.3
**Risks:** Medium. Curating realistic sample calls takes time.

**Definition of Done:**
- 3 sample calls bundled as JSON seed data
- All 3 render correctly on Call Review page
- Sample calls accessible from Dashboard and Sample Calls page

---

### 3.7 Streamlit: call state management and DB persistence

**Files affected:**
- `streamlit_app.py`
- `pages/04_Call_Review.py`
- `pages/03_Calls_List.py`
- `pages/02_Analyze.py`

**What:**
Connect the Streamlit UI to the real FastAPI backend:

- **Calls List:** `GET /api/v1/calls` → real data from Postgres
- **Call Review:** `GET /api/v1/calls/{id}` + `GET /api/v1/insights/call/{id}` → real results
- **Upload:** `POST /api/v1/calls/upload` → save transcript + metadata, trigger pipeline
- **Feedback:** `POST /api/v1/insights/{id}/feedback` → persist 👍/👎

Use `st.cache_data` with `ttl` for API response caching.

Add sidebar indicator: API connection status (connected/disconnected).

**Dependencies:** Phase 1.2, Phase 3.1
**Risks:** Medium. CORS may need configuration in FastAPI.

**Definition of Done:**
- Calls List loads real data from DB
- Call Review loads real framework results
- Upload submits transcript to pipeline
- Feedback persists to DB

---

### Phase 3 Definition of Done

- [ ] 7 pages via Streamlit native navigation
- [ ] Calls List: matches wireframe 7B.2, filters/pagination work, delete with confirmation
- [ ] Call Review: matches wireframe 7B.3 (transcript-only), all 4 tabs functional, evidence linking works
- [ ] Analyze/Upload: paste transcript → pipeline runs → Call Review shows results
- [ ] Settings: LLM Config + Frameworks + Cost Tracking functional
- [ ] 3 sample calls bundled as JSON, load instantly
- [ ] All pages backed by real API calls, not mock data

---

## Phase 4 — Deployment & Observability

**Goal:** Ship a production-ready deployment with Docker, environment configuration, CI/CD, and observability.

### 4.1 `Dockerfile`

**Files affected:**
- `Dockerfile` (new)

**What:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY signalapp/ ./signalapp/
COPY streamlit_app.py .
COPY pages/ ./pages/
COPY data/ ./data/
COPY pyproject.toml .

RUN pip install -e .

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

**Dependencies:** Phase 1.1
**Risks:** Low.

**Test cases:**
- `docker build -t signalapp .` succeeds
- `docker run -p 8501:8501 signalapp` starts Streamlit

**Definition of Done:**
- Docker image builds and Streamlit app runs on port 8501

---

### 4.2 `docker-compose.yml` for local dev

**Files affected:**
- `docker-compose.yml` (new)

**What:**
```yaml
services:
  streamlit:
    build: .
    ports: ["8501:8501"]
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - "./.env:/app/.env"

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: signal
      POSTGRES_USER: signal
      POSTGRES_PASSWORD: signal
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U signal"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

Note: Redis not needed (no ARQ queue for transcript-only mode — pipeline runs synchronously in-process).

**Dependencies:** Phase 4.1
**Risks:** Low.

**Definition of Done:**
- `docker compose up` starts Streamlit + Postgres without errors

---

### 4.3 `.env.example` documentation

**Files affected:**
- `.env.example`

**What:**
```bash
# ─── Database ───────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://signal:signal@localhost:5432/signal
# Required. Use sqlite+aiosqlite:///./signal_dev.db for local dev.

# ─── LLM ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here
# Required. Get from https://aistudio.google.com/

GOOGLE_CLOUD_PROJECT=your_gcp_project_id
# Optional. Required for Vertex AI. Leave blank for direct Gemini API.

VERTEX_AI_LOCATION=us-central1
# Default region for Vertex AI.

# ─── Streamlit ───────────────────────────────────────────────────────────
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_PORT=8501

# ─── Observability ──────────────────────────────────────────────────────────
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
# Optional. For cost tracking and prompt observability.
```

> ASR, S3, Redis env vars removed — not applicable to transcript-only mode.

**Dependencies:** Phase 1.1
**Risks:** Low.

**Definition of Done:**
- `.env.example` documents every variable
- New developer with 1 required key (GEMINI_API_KEY) + DATABASE_URL can run the app

---

### 4.4 CI/CD pipeline

**Files affected:**
- `.github/workflows/ci.yml` (new)
- `.github/workflows/deploy.yml` (new)

**What:**

**CI (`ci.yml`):**
```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -e ".[dev]"
      - run: pytest signalapp/tests/ -v
      - run: ruff check signalapp/
  streamlit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install streamlit
      - run: streamlit run streamlit_app.py & sleep 5 && kill $!
        # Smoke test: starts without import errors
```

**Deploy (`deploy.yml`):**
```yaml
on:
  push:
    branches: [main]
    tags: ['v*']
jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}
```

**Dependencies:** Phase 2 (tests passing), Phase 4.1, Phase 4.2
**Risks:** Low.

**Definition of Done:**
- CI passes on `main`
- Docker image pushed to GHCR on tag

---

### 4.5 Langfuse observability integration

**Files affected:**
- `signalapp/app/main.py`
- `signalapp/adapters/llm/gemini.py`
- `signalapp/pipeline/nodes/pass1_extract.py`
- `signalapp/pipeline/nodes/execute_groups.py`

**What:**
- Initialize Langfuse client in FastAPI lifespan
- Wrap all LLM calls with Langfuse callback
- Track `prompt_version`, `model`, `latency_ms`, `tokens`, `cost_usd`
- Attach `call_id` as trace ID to all spans
- Display cost data in Streamlit Settings page

**Dependencies:** Phase 1.1, Phase 4.3
**Risks:** Low.

**Definition of Done:**
- Langfuse dashboard shows all LLM calls with cost and latency
- Cost shown in Streamlit Settings page

---

### Phase 4 Definition of Done

- [ ] `Dockerfile` builds and Streamlit runs in container on port 8501
- [ ] `docker-compose.yml` starts Streamlit + Postgres
- [ ] `.env.example` documents all variables
- [ ] CI runs tests + lint on every PR
- [ ] Docker image pushed to GHCR on tag
- [ ] Langfuse traces visible per call with cost and latency

---

## Phase 5 — Polish & Bug Fixes

**Goal:** Resolve all remaining items. Ship a polished, stable MVP.

### 5.1 Audit logging for routing decisions

**Files affected:**
- `signalapp/domain/routing.py`

**What:**
Add structured logging to `enforce_dependencies()`:

```python
import structlog
logger = structlog.get_logger()

def enforce_dependencies(active, signals):
    ...
    for dependent, requirements in DEPENDENCY_RULES:
        if dependent in active and not requirements.issubset(active):
            active.discard(dependent)
            logger.warning(
                "framework_removed_by_dependency",
                dependent=dependent,
                removed_due_to=requirements - active,
            )
```

**Dependencies:** Phase 1.1, Phase 2.1
**Risks:** Low.

**Definition of Done:**
- Routing decisions logged with structured logs

---

### 5.2 Cursor-based pagination for `list_calls`

**Files affected:**
- `signalapp/api/calls.py`

**What:**
Replace offset pagination with cursor-based pagination:
- Cursor = `call_id` of last seen item
- Parameters: `?limit=20&after=cursor_id`
- Response includes `next_cursor` field

**Dependencies:** Phase 1.1
**Risks:** Low.

**Definition of Done:**
- `GET /api/v1/calls?limit=20` returns paginated results with `next_cursor`

---

### 5.3 Stable transcript segment IDs

**Files affected:**
- `signalapp/domain/transcript.py`

**What:**
Generate deterministic, stable segment IDs from `(transcript_id, segment_index)`:

```python
import hashlib

def make_segment_id(transcript_id: str, index: int) -> str:
    h = hashlib.sha256(f"{transcript_id}:{index}".encode()).hexdigest()[:16]
    return f"seg_{h}"
```

This enables evidence linking: framework outputs reference `segment_id`, which resolves to a segment in the stored transcript.

**Dependencies:** Phase 1.1
**Risks:** Low.

**Definition of Done:**
- Evidence references in framework outputs resolve to segment IDs
- Segment IDs stable across re-runs

---

### 5.4 Promptfoo golden dataset

**Files affected:**
- `eval/` directory (new)

**What:**
Set up promptfoo for regression testing of all 16 framework prompts.

```yaml
# promptfoo.yaml
providers:
  - openai:chat:gpt-4o
  - anthropic:messages:claude-sonnet-4-20250514

tests:
  - vars:
      transcript: "{{transcript}}"
    assert:
      - type: json-schema
        value: # framework-specific schema
      - type: latency
        threshold: 5000
```

Golden dataset: 3–5 curated transcripts per framework covering normal case, null case, and edge cases.

**Dependencies:** Phase 1.1
**Risks:** Medium. Golden dataset curation is time-consuming.

**Definition of Done:**
- `promptfoo.yaml` covers all 16 prompt groups
- ≥3 cases per framework
- CI runs `promptfoo evaluate` on PRs touching `prompts/`

---

### 5.5 Prompt preview in Streamlit

**Files affected:**
- `pages/04_Call_Review.py`

**What:**
Add an expandable section per framework in the Frameworks tab showing the actual prompt used:

- Read `SYSTEM_PROMPT` + `USER_PROMPT` from `signalapp/prompts/groups/group_*/fw_*.py`
- Display in `st.expander` with preformatted text

**Dependencies:** Phase 3.3
**Risks:** Low.

**Definition of Done:**
- Each framework in Frameworks tab has "View Prompt" expander

---

### 5.6 Final regression pass

**Files affected:**
- All `signalapp/` modules

**What:**
```bash
pytest signalapp/tests/ -v --cov=signalapp --cov-report=term-missing
ruff check signalapp/
```

Fix all failures.

**Dependencies:** Phase 5.1–5.5 complete
**Risks:** Low.

**Definition of Done:**
- 100% tests pass
- Coverage ≥ 80% on core modules (domain/, pipeline/, adapters/)
- `ruff check` clean on `signalapp/`

---

### Phase 5 Definition of Done

- [ ] Audit logging in `enforce_dependencies()`
- [ ] Cursor-based pagination on `GET /api/v1/calls`
- [ ] Stable transcript segment IDs
- [ ] Promptfoo golden dataset ≥3 cases per framework
- [ ] Prompt preview in Streamlit Frameworks tab
- [ ] Full test suite passes with ≥80% coverage on core modules
- [ ] `ruff check` clean on `signalapp/`

---

## Removed from Scope (Transcript-Only Mode)

The following were removed because audio/ASR is no longer in scope:

| Item | Reason |
|------|--------|
| AssemblyAI provider | No audio to transcribe |
| Deepgram provider | No audio to transcribe |
| S3StorageAdapter | No audio files to store |
| Audio player component | No audio to play |
| ASR webhook endpoints | No ASR callbacks |
| `submit_transcription_job` | No transcription step |
| Speaker activity bars | No audio to derive timing from |
| Silence ratio metric | Requires audio |
| Response latency metric | Requires audio |
| `transcription.py` job | No ASR needed |
| `webhooks.py` ASR routes | No ASR needed |

---

## Phase Summary

| Phase | Focus | Duration | Risk |
|-------|-------|----------|------|
| **Phase 1** | Backend Completion | ~2–3 days | Low |
| **Phase 2** | Testing & Polish | ~2–3 days | Low |
| **Phase 3** | Full-Stack Streamlit App | ~4–6 days | Medium |
| **Phase 4** | Deployment | ~1–2 days | Low |
| **Phase 5** | Polish & Bug Fixes | ~2–3 days | Low |

**Total estimated:** ~11–17 days

## Dependency Graph

```
Phase 1 (backend completion — remove ASR/S3)
    │
    ├─ Phase 2 (tests + Streamlit polish) ────────────────────────┐
    │                                                               │
    │   Phase 2 passes                                             │
    │    │                                                          │
    └────┼──────────────────────────────────────────────────────────┤
         │                                                           │
         ├─ Phase 3 (full-stack Streamlit app)                    │
         │    │                                                     │
         │    └──────────────────┐                                  │
         │                       │                                  │
         └──────────────────────┼──────────────────────────────────┘
                                │
         Phase 4 (deployment) ──┤  (parallel with Phase 3)
                                │
         Phase 5 (polish) ──────┘
```

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 5

---

## Quick-Start Commands

```bash
# Phase 1
pip install -e .

# Phase 2
pytest signalapp/tests/unit/test_routing.py -v
pytest signalapp/tests/unit/test_framework_outputs.py -v
pytest signalapp/tests/integration/test_pipeline.py -v

# Phase 3
streamlit run streamlit_app.py

# Phase 4
docker compose up --build

# Phase 5
pytest signalapp/tests/ -v --cov=signalapp
ruff check signalapp/
```
