# Signal

**Post-call behavioral intelligence for sales teams.**

Signal analyzes sales conversations using validated psychological and behavioral science frameworks. It extracts meaning from audio recordings and transcripts to detect question evasion, commitment quality, emotional dynamics, concession patterns, negotiation leverage, and coaching opportunities.

## Architecture

- **API:** FastAPI (`signalapp/app/main.py`)
- **Pipeline:** LangGraph 9-stage pipeline (`signalapp/pipeline/`) — base metrics → Pass 1 extraction → routing → framework execution → 7-gate verification → insights → segment coaching → summary → store
- **Frameworks:** 18 behavioral frameworks across 5 groups (Negotiation, Pragmatic, Strategic, Emotional, NEPQ). Routing is pure Python ($0.00) using Pass 1 signals.
- **Database:** Postgres with JSONB (SQLite for local dev)
- **LLM:** Vertex AI / Gemini, with Anthropic + OpenAI adapters (`signalapp/adapters/llm/`)
- **UI:** Streamlit dashboard (`streamlit_app.py`)

## Quickstart

```bash
# Install (editable, with dev tooling)
pip install -e ".[dev]"

# Run the API (Railway/production entry point)
python start.py            # serves signalapp.app.main:app on $PORT

# Run the Streamlit UI (point it at the API)
SIGNAL_BACKEND_URL=http://localhost:8000 streamlit run streamlit_app.py
```

### Docker

```bash
docker-compose up          # API + Postgres (mounts ./signalapp and ./streamlit_app.py)
```

## Tests

```bash
pytest signalapp/tests/unit/         # unit (routing, framework outputs)
pytest signalapp/tests/integration/  # integration (full pipeline)
ruff check signalapp/                # lint
```

## Repository Layout

```
/
├── signalapp/          # Python package (FastAPI + LangGraph pipeline)
│   ├── adapters/       # LLM + ASR adapters
│   ├── api/            # FastAPI routers (calls, insights, webhooks)
│   ├── app/            # App config, dependencies, main entry
│   ├── db/             # Models + repository
│   ├── domain/         # Core domain (call, framework, routing, insight)
│   ├── jobs/           # ARQ job queue + pipeline orchestration
│   ├── pipeline/       # LangGraph nodes + intelligence layer
│   ├── prompts/        # Pass 1 + per-framework prompt templates
│   ├── reliability/    # Circuit breaker, cost tracker, retry
│   └── tests/          # Unit + integration tests
├── docs/               # Project documentation (PRD, frameworks, status)
│   └── References/      # PRD, framework routing, NEPQ/PCP docs, PDFs
├── streamlit_app.py    # Streamlit UI (root — required by deploy config)
├── start.py            # Production entry point (root — required by Docker)
├── pyproject.toml      # Package + build config
├── requirements.txt    # Runtime dependencies (used by Dockerfile)
├── Dockerfile          # Production image
└── docker-compose.yml  # Local dev (API + Postgres)
```

> **Package naming:** the Python package is `signalapp` (not `signal`) because `signal` shadows Python's stdlib `signal` module, which breaks asyncio-based libraries. Always import from `signalapp.`.

See [`CLAUDE.md`](CLAUDE.md) for contributor guidance and [`docs/`](docs/) for the full product specification.
