# Phase 1: Core Intelligence — Plan 01 Summary

**Plan:** 01 (Backend Completion)
**Completed:** 2026-04-04
**Duration:** 702 seconds (~11.7 minutes)
**Tasks:** 7 tasks across 6 waves completed

## Wave Structure

| Wave | Tasks | Status | Commits |
|------|-------|--------|---------|
| 1 | pyproject.toml (skipped - exists), ASR/S3 removal | ✅ | cdd77f2, ec1e5e0 |
| 2 | Feedback persistence fix, LLM guard | ✅ | 375968a, 426263c |
| 3A | Paste-transcript endpoint | ✅ | cdd77f2 |
| 3B | Integration tests | ✅ | 4ff908a |
| 4A | Streamlit integration | ✅ | 8c11d29 |
| 4B | Evidence linking | ✅ | ec1e5e0 |
| 5 | Dockerfile, docker-compose, CI/CD | ✅ | a1a98fd |
| 6 | End-to-end verification | ⏸️ | — |

## Commits

| Hash | Message |
|------|---------|
| cdd77f2 | feat(01-core-intelligence): initial signalapp package — pipeline, API, DB layer |
| 375968a | fix(01-core-intelligence): fix insight feedback persistence with explicit session commit |
| 426263c | feat(01-core-intelligence): add LLM availability guard in execute_groups_node |
| 4ff908a | test(01-core-intelligence): add integration test fixtures and pipeline node tests |
| 8c11d29 | feat(01-core-intelligence): refactor streamlit_app to use real signalapp modules |
| ec1e5e0 | feat(01-core-intelligence): add evidence linking and transcript sync in streamlit_app |
| a1a98fd | feat(01-core-intelligence): add Dockerfile, docker-compose.yml, and CI/CD workflows |

## Key Decisions Made

- **ASR/S3 modules removed** (transcript-only mode) — deleted adapters/asr/, adapters/storage/, jobs/transcription.py
- **webhooks.py replaced with 404 stub** — ASR webhooks disabled
- **Config cleaned** — Removed AWS S3 and ASR config fields from AppConfig
- **Feedback persistence fixed** — Using `async with session_scope()` with explicit commit and refresh
- **LLM guard added** — `execute_groups_node` fails fast with explicit warning when no LLM configured
- **Paste-transcript endpoint created** — POST /api/v1/calls/paste-transcript with full segment parsing
- **Dockerfile + docker-compose** — Streamlit + Postgres with health checks
- **CI/CD workflows** — GitHub Actions for tests and Docker deploy

## Files Created/Modified

### Created
- `signalapp/` — full Python package (75 files, initial commit cdd77f2)
- `signalapp/tests/conftest.py` — shared pytest fixtures
- `Dockerfile` — Python 3.11-slim + Streamlit
- `docker-compose.yml` — Streamlit + Postgres services
- `init.sql` — Postgres initialization
- `.streamlit/config.toml` — Signal teal theme
- `.github/workflows/ci.yml` — test + lint workflow
- `.github/workflows/deploy.yml` — Docker build/push workflow

### Modified
- `signalapp/api/webhooks.py` — replaced ASR webhook with 404 stub
- `signalapp/app/config.py` — removed ASR/S3/AWS config fields
- `signalapp/api/calls.py` — added paste-transcript endpoint, disabled audio upload
- `signalapp/db/repository.py` — fixed update_feedback with explicit session commit
- `signalapp/pipeline/nodes/execute_groups.py` — added LLM availability guard
- `signalapp/tests/integration/test_pipeline.py` — added ExecuteGroups and RoutingTableCompleteness tests
- `streamlit_app.py` — signalapp imports, backend connection indicator, evidence linking, transcript tab

## Test Results

- **138 unit tests**: PASSED ✅
- **19 integration tests**: PASSED ✅
- **All tests pass** including routing completeness and LLM stub tests

## Verification Results

### Completed (Automated)
- `python -c "import signalapp; print('OK')"` — PASSED
- Transcript parsing with role detection — PASSED
- LLM guard check (no creds → False, with key → True) — PASSED
- All pytest tests — 157/157 PASSED

### Pending (Human Verification Required)
- Docker build: `docker build -t signalapp-test .` — requires Docker runtime
- FastAPI backend startup: `uvicorn signalapp.app.main:app --reload --port 8000`
- Paste-transcript endpoint with curl
- Full pipeline end-to-end with LLM

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyproject.toml was OneDrive placeholder**
- **Found during:** Initial state check
- **Issue:** Root `pyproject.toml` existed as OneDrive placeholder (not synced), `signalapp/pyproject.toml` was the real file
- **Fix:** Signalapp package was already installed from signalapp/ directory; no action needed
- **Files modified:** None
- **Commit:** cdd77f2

**2. [Rule 1 - Bug] test_routing_table_has_all_required_keys used dict check on dataclass**
- **Found during:** Task 3B test run
- **Issue:** `ROUTING_TABLE` values are `FrameworkRoutingSpec` dataclass, not dict
- **Fix:** Changed `key in entry` to `hasattr(entry, attr)`
- **Files modified:** signalapp/tests/integration/test_pipeline.py
- **Commit:** 4ff908a

### Known Stubs

- `streamlit_app.py` `generate_mock_results()` still generates mock framework results — the real pipeline requires a running backend with LLM configured
- `check_backend_connection()` will always return False without a running FastAPI backend at `http://localhost:8000`

## Next Steps

Phase 2: Full LLM pipeline integration — see `.planning/phases/02-xxx/02-PLAN.md` when available.

---
*Plan: 01-core-intelligence/01-PLAN.md | Phase: 01-core-intelligence | Status: Executing*
