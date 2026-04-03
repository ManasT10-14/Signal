# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Signal** is a post-call behavioral intelligence platform that analyzes sales conversations using validated psychological and behavioral science frameworks. It extracts meaning from audio recordings and transcripts to detect question evasion, commitment quality, emotional dynamics, concession patterns, negotiation leverage, and coaching opportunities.

**Current status:** Active development — Milestone 1 in progress. Core pipeline (LangGraph nodes), DB layer, ASR adapter, and FastAPI entry are implemented. Package renamed to `signalapp` (see note below).

## Architecture Decisions (Finalized)

### Tech Stack
- **API:** FastAPI (Python)
- **Database:** Postgres with JSONB
- **Storage:** AWS S3
- **Queue:** ARQ + Redis (replaces Celery — async-native)
- **Pipeline Orchestration:** LangGraph (inside ARQ jobs)
- **LLM Integration:** Instructor, Pydantic, Anthropic SDK, OpenAI SDK
- **Observability:** Langfuse
- **Testing:** promptfoo

### Key ADR: ARQ + LangGraph over Celery
The PRD originally specified Celery + Redis with 8 separate queues. This was replaced because:
- Celery is sync-first, conflicts with async stack
- 8 queues = 8x operational complexity
- Manual `completed_at` checkpointing is fragile
- LangGraph provides automatic checkpointing and pipeline visibility

### Framework Routing
- 17 behavioral frameworks in Phase 1
- Routing is pure Python ($0.00) — no LLM calls for routing decisions
- Pass 1 always runs and extracts: hedge map, sentiment trajectory, evaluative language
- Each framework is BLOCKED, MANDATORY, or OPTIONAL based on call type + Pass 1 signals
- "Absence Is Meaningful" (AIM) pattern: framework absence is itself a signal

### Signal Clusters (20 foundational signals)
The platform builds 20 signal extraction pipelines that collectively power 236+ behavioral frameworks:
1. Prosodic-Complexity, 2. Disfluency-Uncertainty, 3. Pronoun-Identity, 4. Sentiment-Valence, 5. Vocabulary-Richness, 6. Turn-Taking-Power, 7. Semantic-Coherence, 8. Syntactic-Complexity, 9. Temporal-Pacing, 10. Article-Concreteness, 11. Hedging-Qualification, 12. Comparison-Contrast, 13. Referential-Clarity, 14. Negation-Avoidance, 15. Evidentiality-Grounding, 16. Imperative-Control, 17. Narrative-Structure, 18. Self-Other-Distance, 19. Volition-Agency, 20. Social-Norm-Alignment

## Repository Structure

```
/
├── References/                    # All project documentation
│   ├── Signal_PRD_v2.2.md        # Complete product specification
│   ├── Signal_Intelligence_Stack_v1.0.md  # Intelligence layer design
│   ├── FRAMEWORK_ROUTING_ARCHITECTURE.md   # Framework execution routing
│   ├── PCP_Summary.md             # Perception × Context × Permission framework
│   ├── LLM_RELIABILITY_GUIDE.md  # LLM usage patterns and reliability
│   ├── Gong_Summary.md           # Competitive analysis
│   └── *.html                     # Rendered versions of some docs
├── References/.claude/
│   └── settings.local.json        # Python permissions (pdfplumber, PyPDF2, fitz)
└── CLAUDE.md                      # This file
```

## When Building Signal

1. **Start with the PRD** (`Signal_PRD_v2.2.md`) — it is the source of truth for all requirements
2. **Follow the Build Order** in PRD Section 21 — vertical slices, not horizontal layers
3. **Framework routing table** in `FRAMEWORK_ROUTING_ARCHITECTURE.md` defines which frameworks run per call type
4. **PCP framework** (`PCP_Summary.md`) defines the behavioral science foundation
5. **LLM Reliability Guide** covers prompt patterns, retry logic, and cost optimization

## PDF Reference Materials

The `References/` directory contains PDFs that inform the design:
- `Signal_PRD_v2.2.md` → `pcp_public.pdf` (source reference)
- `Gong_Summary.md` → `MUST_Gong_Product_Tear...` (competitive teardown)
- `Signal_DPR_v1_Part_Two.pdf` — earlier decision record

Python PDF parsing is pre-authorized in `settings.local.json` for: `PyPDF2`, `pdfplumber`, `PyMuPDF`.

## Package Naming Note

The Python package is named `signalapp` (not `signal`) because `signal` conflicts with Python's stdlib `signal` module, which breaks asyncio-based libraries (FastAPI/Starlette/anyio). Always import from `signalapp.` not `signal.`.
