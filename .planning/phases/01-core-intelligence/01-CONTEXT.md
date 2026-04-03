# Phase 1: Core Intelligence - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning
**Source:** PRD Express Path (References/Signal_PRD_v2.2.md)

<domain>
## Phase Boundary

A web application where a sales manager uploads call recordings (or pastes transcripts), receives automated behavioral analysis with evidence-linked insights and coaching recommendations, and reviews base metrics that establish credibility alongside Gong.

**User model:** Single manager account per organization. Manager uploads calls and tags each with rep name, call type, and optional deal name.

**Input methods:**
- Audio file upload (mp3, wav, m4a, ogg, webm, mp4 — audio extracted from video)
- Transcript paste as alternative input (bypasses ASR, zero cost)

**Behavioral layer:** 10 frameworks at production quality + 25 scaffolded with placeholders. 3 infrastructure signals in Pass 1. 8 base metrics at zero LLM cost.

**Screens:** Dashboard (home), Calls List, Call Review (THE product), Upload Flow (single + bulk), Developer Settings.

**Infrastructure:** Provider-agnostic pipeline (ASR: AssemblyAI + Deepgram switchable; LLM: Claude + GPT-4o switchable per group). Prompt versioning. Evaluation infrastructure (promptfoo + golden dataset). Langfuse observability.

**Exit criteria:** 5 paying pilots, >60% insight acceptance rate, <10 min processing latency p95, <$1/call.
</domain>

<decisions>
## Implementation Decisions (all locked per PRD Section 5)

### Architecture
- FastAPI + Postgres + Redis + S3 + Clerk auth + Next.js
- ARQ + LangGraph for pipeline orchestration (replaces Celery)
- Package named `signalapp` (not `signal`) — avoids Python stdlib conflict
- Provider abstraction: ASR via Protocol (AssemblyAI + Deepgram), LLM via Protocol (Anthropic + OpenAI)
- All behavioral science encoded in prompts, not model weights

### Data Model
- Call: id, organization_id, rep_name, call_type, deal_name?, call_date, audio_url?, transcript_status, analysis_status
- TranscriptSegment: segment_id, call_id, segment_index, speaker_name, speaker_role, start_time_ms, end_time_ms, text
- AnalysisRun: id, call_id, settings_snapshot (JSONB), pass1_output (JSONB), framework_results (JSONB), status
- Settings: organization_id, settings_key, encrypted_settings_value (JSONB)

### Pipeline Flow
1. Upload → S3 (presigned URL, browser-direct)
2. ASR → AssemblyAI/Deepgram (webhook callback)
3. Preprocessing → speaker mapping, segment merging, cleanup
4. Pass 1 → hedge/sentiment/evaluative extraction (always runs)
5. Routing → pure Python ($0.00), decides which frameworks run
6. Pass 2 → 5 groups (A-E) via asyncio.gather, each = 1 batched LLM call
7. Insight prioritization → severity → confidence → actionability → $ → novelty

### Call Types
Discovery, Demo, Pricing, Negotiation, Close, Check-in, Other

### Routing (from FRAMEWORK_ROUTING_ARCHITECTURE.md)
- BLOCKED: framework never runs for this call type
- MANDATORY: always run (AIM pattern — absence IS the insight)
- CONTENT-GATED: runs only if Pass 1 signal detected
- Pinned: #8, #9, #15 always run regardless of routing
- Dependencies: #9→#8, #14→#5+#15, #17→#16

### Framework Groups
- Group A (Negotiation): #3, #4, #7, #12, #13
- Group B (Pragmatics): #1, #2, #6, #16
- Group C (Coaching): #5, #10, #11, #14, #15, #17
- Group D (Deal Health): empty (Phase 2)
- Group E (Emotion): #8 + #9 (combined prompt)

### Developer Settings
- ASR: provider toggle, API key, model, diarization on/off, speaker count, language
- LLM: per-group provider, model (pinned versions), temperature, max tokens, fallback
- Frameworks: on/off toggles, confidence thresholds (0-100)
- Pipeline: concurrent calls, retry count, timeout, debug mode
- Observability: Langfuse enable/key/dashboard link
- Cost: per-call readout

### Error Handling
- Audio too short (<2 min): warn but process
- Audio quality poor (ASR confidence <60%): warn banner
- Unsupported format: reject
- File >500MB: reject
- Duration >3 hours: reject
- Single speaker detected: warn, process anyway
- ASR failure: auto-retry once, then fail
- LLM failure (single group): partial results + retry
- LLM failure (all groups): fail + manual retry option
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Routing
- `References/FRAMEWORK_ROUTING_ARCHITECTURE.md` — Framework routing: 17 frameworks, 5 groups, AIM pattern, routing categories, Pass 1 signals, dependency enforcement. **READ THIS FIRST.**
- `References/LLM_RELIABILITY_GUIDE.md` — LLM patterns: retry logic, cost optimization, structured outputs via Instructor

### Behavioral Science
- `References/PCP_Summary.md` — PCP framework (Perception × Context × Permission): behavioral science foundation for all 20 signal clusters

### Product
- `References/Signal_PRD_v2.2.md` — Full PRD. Section 3 (roadmap), Section 5 (scope lock), Section 13 (pipeline architecture), Section 16 (data model), Section 18 (processing pipeline), Section 21 (build order)

### Competitive
- `References/Gong_Summary.md` — Competitive teardown. Identifies what Gong does NOT do (behavioral science gap = Signal's opportunity)

### Stack Decisions
- `References/Signal_Stack_Decision_Short.md` — Stack decisions: Next.js, FastAPI, Postgres, Redis, S3, Clerk, ARQ+LangGraph
</canonical_refs>

<specifics>
## Specific Ideas from PRD

### Build Order (15 slices, critical path: 1→2→6→7→8)
1. Project setup (Next.js + FastAPI + Postgres + Redis + S3 + Clerk)
2. ASR integration (AssemblyAI) + basic Call Review + wavesurfer.js
3. Transcript paste input (alternative to upload)
4. Base metrics + AI summary
5. Promptfoo + golden dataset + Langfuse
6. Pass 1 pipeline (hedge, sentiment, evaluative)
7. First framework end-to-end (Unanswered Questions #1) — "holy shit moment"
8. Remaining 9 frameworks in parallel
9. Framework scaffolding (all 35 frameworks listed)
10. Developer settings
11. Re-analysis + export
12. Onboarding (sample calls, wizard)
13. Bulk upload (50 files)
14. Dashboard home page
15. UI polish

### Audio Player Requirements
- wavesurfer.js waveform visualization
- Speed controls: 1x, 1.25x, 1.5x, 2x
- 15-second skip forward/back
- Click-to-seek from transcript

### Insight Card UX
- Each insight: score, severity (red/yellow/green), headline, evidence snippet
- Click evidence → transcript jumps + audio seeks
- Thumbs up/down feedback buttons
- Low-confidence results collapsed into "Additional Insights"

### Processing States
User-facing: processing (animated ◌), ready (● green), failed (✕ red), partial (◐ orange)
Developer: uploading → transcribing → preprocessing → analyzing_pass1 → analyzing_pass2_[A/B/C/D/E] → generating_insights → ready

### Batch Processing
- Up to 50 files per batch
- Processing LIFO within batch
- Concurrency limit: 3 simultaneous
- Rate limiting: 50 calls/day per user
</specifics>

<deferred>
## Deferred Ideas

- CRM integrations (Phase 2)
- Zoom cloud recording integration (Phase 2)
- Multi-user / rep logins (Phase 3)
- Real-time in-call coaching (Phase 5)
- Public API / framework builder (Phase 5)
- Deal-level views and tracking (Phase 2)
- Slack notifications (Phase 2)
- SSO / SOC 2 (Phase 4)
</deferred>

---

*Phase: 01-core-intelligence*
*Context gathered: 2026-04-04 via PRD Express Path*
