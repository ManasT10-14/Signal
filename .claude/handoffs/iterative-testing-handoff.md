# Handoff: Iterative Testing — Signal Milestone 1

## Session Context

**Package renamed:** `signal` → `signalapp` (shadows stdlib `signal`)
**Pipeline folder:** `langgraph` → `pipeline`
**Queue folder:** `queue` → `jobs` (shadows stdlib `queue`)
**Eval folder:** `eval` → `checks` (shadows Python builtin)

All internal imports updated. Pipeline compiles cleanly. Vertex AI confirmed working.

---

## Prerequisites (must be set up first)

### 1. Google Cloud Auth (Vertex AI)
```bash
gcloud auth application-default login
```
Verify:
```python
import google.auth
creds, proj = google.auth.default()
print(proj)  # should print your GCP project
```

### 2. Install dependencies
```bash
pip install -e ./signalapp
# OR in dev mode:
pip install aiosqlite google-cloud-aiplatform python-dotenv fastapi uvicorn sqlalchemy pydantic
```

### 3. .env file (copy from .env.example, fill in your values)
```bash
cp .env.example .env
```
Critical vars:
```bash
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_ENABLED=true
QUEUE_MODE=memory          # uses in-memory queue (no Redis needed)
SQLITE_URL=sqlite+aiosqlite:///./signal_dev.db  # no Postgres needed
```

---

## What Was Built — Component Map

```
signalapp/
├── app/
│   ├── config.py          # load_config(), get_config(), AppConfig dataclass
│   ├── dependencies.py     # FastAPI deps (DB session, auth, repos)
│   └── main.py            # create_app(), FastAPI entry point
├── adapters/
│   ├── llm/
│   │   ├── base.py        # LLMProvider ABC, LLMResponse, LLMConfig
│   │   └── gemini.py      # GeminiProvider (Vertex AI + direct API)
│   └── asr/
│       ├── base.py        # ASRProvider ABC, ASRSegment, ASRResult
│       └── assemblyai.py  # AssemblyAIProvider
├── domain/
│   ├── call.py            # Call, CallType, ProcessingStatus, Pass1Result
│   ├── framework.py       # FrameworkOutput, FrameworkResult, FRAMEWORK_REGISTRY
│   ├── routing.py        # route_frameworks(), Pass1GateSignals, RoutingDecision
│   ├── insight.py         # Insight, prioritize_insights()
│   └── transcript.py      # TranscriptSegment, Transcript
├── pipeline/              # (renamed from langgraph)
│   ├── state.py          # PipelineState TypedDict
│   ├── pipeline.py       # create_pipeline_workflow() → StateGraph
│   └── nodes/
│       ├── pass1_extract.py
│       ├── route.py
│       ├── execute_groups.py
│       ├── verify.py
│       ├── insights.py
│       ├── summary.py
│       └── store.py
├── jobs/                 # (renamed from queue)
│   ├── app.py            # get_arq_settings(), QUEUE_MODE
│   ├── memory.py         # MemoryQueue (drop-in Redis replacement)
│   └── jobs/
│       ├── pipeline.py    # run_pipeline_job() — wired to DB + pipeline
│       ├── transcription.py
│       └── preprocessing.py
├── db/
│   ├── models.py         # 10 SQLAlchemy models (cross-dialect: SQLite + Postgres)
│   └── repository.py      # Async repos: Call, Transcript, AnalysisRun, etc.
├── api/
│   ├── calls.py          # /api/v1/calls (list, get, upload)
│   ├── insights.py       # /api/v1/insights
│   └── webhooks.py      # /api/v1/webhooks/asr/assemblyai
├── prompts/
│   ├── pass1/
│   │   └── infrastructure_v1.py  # Pass1Output, SYSTEM_PROMPT, USER_PROMPT
│   └── groups/
│       ├── group_a/  # batna, money_left, deal_health, deal_timing, first_number, commitment_quality
│       ├── group_b/  # unanswered_questions, commitment_thermometer, pushback_classification
│       ├── group_c/  # question_quality, frame_match, close_attempt, methodology, call_structure, objection_response
│       └── group_e/  # emotional_turning_points
```

---

## Test Plan (iterative, start with smallest unit)

### Test 0 — Confirm Clean Imports
```python
# Run from /tmp to avoid signal shadow issue
import sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from signalapp.pipeline.pipeline import create_pipeline_workflow
app = create_pipeline_workflow()
print(app.nodes.keys())
# Expected: dict_keys(['__start__', 'pass1_extract', 'route_frameworks',
#                      'execute_groups', 'verify_results', 'generate_insights',
#                      'generate_summary', 'store_results'])
```

---

### Test 1 — LLM Adapter (no pipeline)
**File:** `signalapp/adapters/llm/gemini.py`

```python
import sys; sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')

# Load .env
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.env'))

from signalapp.adapters.llm.gemini import GeminiProvider
from signalapp.adapters.llm.base import LLMConfig
import asyncio

async def test():
    p = GeminiProvider()
    cfg = LLMConfig(model='gemini-2.5-flash', temperature=0.1, max_tokens=100, provider='gemini')

    # Test plain completion
    r = await p.complete('What is 2+2?', cfg)
    print('Plain:', r.content)

    # Test structured output
    from signalapp.prompts.pass1.infrastructure_v1 import Pass1Output, build_pass1_prompt
    SYSTEM, USER = build_pass1_prompt("[00:00] Rep (rep): Hello, how are you?\n[00:05] Buyer (buyer): I'm good thanks.")
    full = f"{SYSTEM}\n\n{USER}"
    result = await p.complete_structured(full, Pass1Output, cfg)
    print('Structured OK:', result.model_dump())
```
**What to verify:** Response quality, cost tracking, error handling

---

### Test 2 — Routing Engine (pure Python, no LLM)
**File:** `signalapp/domain/routing.py`

```python
from signalapp.domain.routing import route_frameworks, Pass1GateSignals

# Discovery call, no signals
signals = Pass1GateSignals(call_duration_minutes=15.0)
active, decisions = route_frameworks('discovery', signals)
print('Active frameworks:', sorted(active))
# Expected: {1, 2, 5, 6, 8, 9, 15} + maybe 14 if questions detected

# Pricing call with competitor mention
signals2 = Pass1GateSignals(
    has_competitor_mention=True,
    has_pricing_discussion=True,
    has_numeric_anchor=True,
    call_duration_minutes=20.0
)
active2, _ = route_frameworks('pricing', signals2)
print('Pricing active:', sorted(active2))
# Expected: should include {3, 4, 7} which are blocked on discovery
```
**What to verify:** AIM pattern, pinned frameworks always present, dependencies enforced

---

### Test 3 — Pass1 Node (pipeline → LLM call)
**File:** `signalapp/pipeline/nodes/pass1_extract.py`

```python
import asyncio, sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from signalapp.pipeline.nodes.pass1_extract import pass1_extract_node

async def test():
    state = {
        'call_id': 'test-123',
        'call_type': 'discovery',
        'transcript_segments': [
            {
                'segment_id': 'seg_001', 'segment_index': 0,
                'speaker_name': 'Rep', 'speaker_role': 'rep',
                'start_time_ms': 0, 'end_time_ms': 5000,
                'text': 'Hi, can I ask you a few questions about your business?',
                'word_count': 13
            },
            {
                'segment_id': 'seg_002', 'segment_index': 1,
                'speaker_name': 'Buyer', 'speaker_role': 'buyer',
                'start_time_ms': 5000, 'end_time_ms': 15000,
                'text': 'Sure, we are currently using a competitor product.',
                'word_count': 10
            }
        ]
    }
    result = await pass1_extract_node(state)
    print('pass1_gate_signals:', result.get('pass1_gate_signals'))
    print('has_competitor:', result['pass1_gate_signals']['has_competitor_mention'])
    # Expected: has_competitor=True (buyer mentioned competitor)
```
**What to verify:** Pass1GateSignals correctly derived from transcript, LLM call succeeds

---

### Test 4 — Route Node (no LLM)
**File:** `signalapp/pipeline/nodes/route.py`

```python
import asyncio, sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from signalapp.pipeline.nodes.route import route_node

async def test():
    state = {
        'call_id': 'test-123',
        'call_type': 'discovery',
        'pass1_gate_signals': {
            'has_competitor_mention': False,
            'has_pricing_discussion': False,
            'has_numeric_anchor': False,
            'has_objection_markers': False,
            'has_rep_questions': True,
            'has_close_language': False,
            'call_duration_minutes': 15.0
        }
    }
    result = await route_node(state)
    print('active_frameworks:', sorted(result['active_frameworks']))
    print('routing_decisions count:', len(result['routing_decisions']))
```
**What to verify:** Pure routing logic, decisions serializable to dicts for TypedDict

---

### Test 5 — Execute Groups Node (LLM calls)
**File:** `signalapp/pipeline/nodes/execute_groups.py`

```python
import asyncio, sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))
from signalapp.pipeline.nodes.execute_groups import execute_groups_node

async def test():
    state = {
        'call_id': 'test-123',
        'call_type': 'discovery',
        'active_frameworks': {1, 2, 6, 8, 9, 15},  # Only frameworks with prompts ready
        'pass1_result': {
            'hedge_data': [],
            'sentiment_data': [],
            'appraisal_data': [],
        },
        'transcript_segments': [
            {'segment_id': 'seg_001', 'segment_index': 0, 'speaker_name': 'Rep',
             'speaker_role': 'rep', 'start_time_ms': 0, 'end_time_ms': 5000,
             'text': 'Hi, how are you today?', 'word_count': 6},
            {'segment_id': 'seg_002', 'segment_index': 1, 'speaker_name': 'Buyer',
             'speaker_role': 'buyer', 'start_time_ms': 5000, 'end_time_ms': 12000,
             'text': 'I am good thanks for asking.', 'word_count': 7}
        ]
    }
    result = await execute_groups_node(state)
    print('framework_results keys:', list(result['framework_results'].keys()))
    print('errors:', result['framework_errors'])
```
**What to verify:** Frameworks run in parallel, errors don't crash other frameworks, results serialized to dicts

---

### Test 6 — Full Pipeline (end to end)
**File:** `signalapp/pipeline/pipeline.py`

```python
import asyncio, sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))
from signalapp.pipeline.pipeline import create_pipeline_workflow

async def test():
    app = create_pipeline_workflow()
    state = {
        'call_id': 'test-123',
        'call_type': 'discovery',
        'transcript_segments': [
            {'segment_id': 'seg_001', 'segment_index': 0, 'speaker_name': 'Rep',
             'speaker_role': 'rep', 'start_time_ms': 0, 'end_time_ms': 5000,
             'text': 'Hi, can I ask you about your challenges with data?', 'word_count': 10},
            {'segment_id': 'seg_002', 'segment_index': 1, 'speaker_name': 'Buyer',
             'speaker_role': 'buyer', 'start_time_ms': 5000, 'end_time_ms': 15000,
             'text': 'We struggle with reporting and our current vendor is expensive.', 'word_count': 11}
        ],
    }
    final = await app.ainvoke(state)
    print('Keys:', list(final.keys()))
    print('Active frameworks:', final['active_frameworks'])
    print('Insights count:', len(final['verified_insights']))
    print('Summary:', final.get('summary', {}).get('headline'))
    print('Errors:', final.get('errors', []))
```
**What to verify:** Full flow: pass1 → route → execute → verify → insights → summary → store

---

### Test 7 — DB Layer (SQLite)
**File:** `signalapp/db/repository.py`

```python
import asyncio, sys, uuid
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))
from signalapp.db.repository import init_db, get_session, CallRepository

async def test():
    await init_db(None)  # Uses config.db_url (SQLite by default)
    async for session in get_session():
        repo = CallRepository()
        call = await repo.create(
            org_id=uuid.uuid4(),
            uploaded_by=uuid.uuid4(),
            rep_name='John Doe',
            call_type='discovery',
            input_type='audio',
        )
        print('Call created:', call.id)
        print('Status:', call.processing_status)
```

---

### Test 8 — Memory Queue
**File:** `signalapp/jobs/memory.py`

```python
import asyncio, sys
sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from signalapp.jobs.memory import MemoryQueue, register_job

@register_job
async def dummy_job(ctx, x):
    return x * 2

async def test():
    q = MemoryQueue()
    await q.enqueue_job('dummy_job', 21)
    await q.run_until_complete(timeout=5.0)
    # Check result
    jobs = list(q._jobs.values())
    print('Status:', jobs[0].status)
    print('Result:', jobs[0].result)
```

---

### Test 9 — API Server
**File:** `signalapp/app/main.py`

```python
import sys; sys.path.insert(0, 'C:/Users/offic/OneDrive/Desktop/ThoughtOS')
from signalapp.app.main import create_app
app = create_app()
# Run: uvicorn signalapp.app.main:app --reload --port 8000
# Then curl http://localhost:8000/health
```

---

## Known Issues / TODOs

| Item | Status | Notes |
|---|---|---|
| `store_results` node | Stub | Logs output, no actual DB write |
| `load_call` / `load_segments` in pipeline.py | Stub | Uses repo directly instead |
| Group prompt stubs (A, C, E) | Stubs | Basic structure only, need real prompt engineering |
| `_store_results` in pipeline job | Has placeholder `framework_result_id` | Uses `uuid.UUID("00000000...")` |
| Transcription job | Incomplete | ASR submission works, webhook handler needs call_id mapping |
| FastAPI auth | Stub | Returns dev UUID in dev mode |
| SQLite + async | Works but slow | Fine for dev; switch to Postgres for prod |
| aiosqlite | May need install | `pip install aiosqlite` |

---

## Debugging Tips

**ImportError / ModuleNotFoundError:**
- Are you running from `/tmp`? The `signalapp` package must be in `sys.path` and you must NOT be inside the `ThoughtOS` dir when running Python (stdli `signal` module shadow)
- Are `__pycache__` files stale? Delete them: `find signalapp -name __pycache__ -exec rm -rf {} + 2>/dev/null; true`

**Vertex AI 404 errors:**
- Model name wrong. Use `gemini-2.5-flash` not `gemini-2.5-flash-preview-04-17`
- To list available models: `client.models.list()` then filter for `gemini` in name

**Pipeline hangs:**
- `pass1_extract` or `execute_groups` likely waiting on LLM call
- Check `GEMINI_API_KEY` / `GOOGLE_CLOUD_PROJECT` env vars
- Add `print` debugging inside nodes

**State dict errors:**
- All state values must be JSON-serializable (TypedDict constraint)
- No Pydantic models or custom classes in state — only dicts/lists/sets/primitives
- If a node returns a Pydantic model, call `.model_dump()` before returning

---

## Running the Full App

```bash
# From ThoughtOS root
cd /tmp  # IMPORTANT: avoid signal shadow
export PYTHONPATH=$PYTHONPATH:C:/Users/offic/OneDrive/Desktop/ThoughtOS

# Or use dotenv directly in code
uvicorn signalapp.app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs (if `SIGNAL_ENV=development`)
