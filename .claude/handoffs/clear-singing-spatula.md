# Handoff: Signal Intelligence Layer — Milestone 1 Progress

## ⚠️ Package Renamed: `signal` → `signalapp`

The Python package was renamed from `signal` to `signalapp` because the name `signal` shadows Python's stdlib `signal` module, which breaks asyncio-based libraries (FastAPI/Starlette/anyio) when running from inside the project directory.

All internal imports now use `from signalapp.xxx import yyy`.

## What Was Built

### Core Foundation Files

**signalapp/app/**
- `config.py` — AppConfig with env var loading, LLM group configs
- `dependencies.py` — FastAPI deps (DB session, auth, repositories)
- `main.py` — FastAPI app entry with lifespan, CORS, routers

**signalapp/adapters/llm/**
- `base.py` — LLMProvider ABC interface
- `gemini.py` — GeminiProvider with native JSON schema output

**signalapp/domain/**
- `routing.py` — Full routing engine (17 frameworks, AIM pattern)
- `framework.py` — FrameworkOutput, FrameworkResult, FRAMEWORK_REGISTRY
- `insight.py` — Insight entity, prioritization
- `transcript.py` — TranscriptSegment, Transcript
- `call.py` — Call aggregate, Pass1Result

**signalapp/prompts/pass1/**
- `infrastructure_v1.py` — Pass1Output schema, SYSTEM_PROMPT, USER_PROMPT

**signalapp/prompts/groups/group_a/**
- `batna_detection_v1.py`, `money_left_on_table_v1.py`, `deal_health_v1.py`, `deal_timing_v1.py`, `first_number_tracker_v1.py`, `commitment_quality_v1.py`

**signalapp/prompts/groups/group_b/**
- `unanswered_questions_v1.py`, `commitment_thermometer_v1.py`, `pushback_classification_v1.py`

**signalapp/prompts/groups/group_c/**
- `question_quality_v1.py`, `frame_match_v1.py`, `close_attempt_v1.py`, `methodology_v1.py`, `call_structure_v1.py`, `objection_response_v1.py`

**signalapp/prompts/groups/group_e/**
- `emotional_turning_points_v1.py` (covers FW-08 + FW-09)

**signalapp/langgraph/**
- `state.py` — PipelineState TypedDict (LangGraph-compatible)
- `pipeline.py` — StateGraph: START → pass1_extract → route_frameworks → execute_groups → verify_results → generate_insights → generate_summary → store_results → END

**signalapp/langgraph/nodes/**
- `pass1_extract.py` — LLM call, Pass1GateSignals derivation
- `route.py` — Pure Python routing (zero LLM cost)
- `execute_groups.py` — Parallel fan-out via asyncio.gather
- `verify.py` — 7-gate quality checks
- `insights.py` — Severity → confidence prioritization
- `summary.py` — Heuristic summary generation
- `store.py` — DB persistence stub

**signalapp/db/**
- `models.py` — SQLAlchemy 1.4 compatible models (10 tables per ERD in PRD Section 16)
- `repository.py` — Async repository pattern (Call, Transcript, AnalysisRun, Pass1Result, FrameworkResult, Insight, BaseMetric)

**signalapp/adapters/asr/**
- `base.py` — ASRProvider ABC
- `assemblyai.py` — AssemblyAI implementation with polling

**signalapp/queue/jobs/**
- `pipeline.py` — run_pipeline_job() ARQ function
- `transcription.py` — submit_transcription_job(), handle_transcription_webhook()
- `preprocessing.py` — run_preprocessing_job() with base metrics computation

**signalapp/api/**
- `calls.py` — /api/v1/calls (list, get, upload)
- `insights.py` — /api/v1/insights (get call insights, submit feedback)
- `webhooks.py` — /api/v1/webhooks/asr/assemblyai

## What's Remaining for Milestone 1

- DB layer needs real Postgres + asyncpg (SQLite for local testing)
- ARQ worker setup (Redis dependency)
- Prompt refinement (all stubs except group_b/unanswered_questions)
- End-to-end integration test

## Key Constraints to Remember
- Gemini 2.5 Flash uses native `response_json_schema` (NOT Instructor)
- ARQ for queuing, LangGraph for orchestration
- LLM Reliability Guide is mandatory
- **Package is `signalapp`** — never `signal`

## Testing Requirements
- **Gemini API key**: Set `GEMINI_API_KEY` env var
- **PostgreSQL**: Set `DATABASE_URL` env var
- **Redis**: Set `REDIS_URL` env var (for ARQ)
- **AWS S3**: Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`

## Next Session
DB layer is wired but needs a live Postgres instance. Prompt stubs need real prompt engineering. The pipeline is fully wired and compiles cleanly.
