# Signal — Requirements

**Project:** Signal — Behavioral Sales Intelligence
**Version:** 1.0
**Status:** Active

---

## Phase 1 Requirements

### REQ-1.1: Audio File Upload
**Type:** Functional
**Priority:** P0
**Description:** Users can upload audio files (mp3, wav, m4a, ogg, webm, mp4) for analysis. Audio is extracted and stored in S3. System initiates ASR transcription.

**Acceptance Criteria:**
- All 6 audio formats accepted without error
- Files >500MB rejected with user-facing error message
- Files >3 hours rejected with user-facing error message
- Upload progress indicator shown to user
- Audio extracted from video formats (mp4)

---

### REQ-1.2: Transcript Paste Input
**Type:** Functional
**Priority:** P0
**Description:** Users can paste transcript text directly, bypassing ASR. Supports multiple formats: Gong, Zoom, Otter, plain text. Skips ASR entirely (zero cost).

**Acceptance Criteria:**
- Gong format auto-detected and parsed correctly
- Zoom format auto-detected and parsed correctly
- Otter format auto-detected and parsed correctly
- Plain text handled as single-speaker
- Base metrics show warning that audio-derived metrics require upload
- Transcript flows directly to Pass 1 pipeline

---

### REQ-1.3: ASR Integration (AssemblyAI + Deepgram)
**Type:** Infrastructure
**Priority:** P0
**Description:** Provider-agnostic ASR layer with AssemblyAI as primary and Deepgram as fallback. Webhook-based job submission. Runtime switchable via Developer Settings.

**Acceptance Criteria:**
- AssemblyAI transcription completes with diarization
- Speaker labels assigned (Speaker 1, Speaker 2, etc.)
- Word-level timestamps in output
- Deepgram produces equivalent output when selected
- Switching provider mid-pipeline doesn't affect in-flight calls
- TranscriptResult stored with segments in Postgres

---

### REQ-1.4: Pass 1 — Infrastructure Signal Extraction
**Type:** Behavioral Pipeline
**Priority:** P0
**Description:** Pass 1 extracts three infrastructure signals from every transcript: hedge map (epistemic/strategic), sentiment trajectory (per-segment scores + notable shifts), evaluative language (affect/judgment/appraisal). Derives routing flags for framework gating.

**Acceptance Criteria:**
- Hedge density computed per segment
- Sentiment score computed per segment
- Notable sentiment shifts detected (threshold: 0.4 delta)
- Evaluative language tagged per target
- Pass1GateSignals derived: has_competitor_mention, has_pricing_discussion, has_numeric_anchor, has_objection_markers, has_rep_questions, has_close_language
- Pass 1 output stored in DB, linked to call_id
- Pass 1 always runs regardless of call type

---

### REQ-1.5: Framework Routing
**Type:** Behavioral Pipeline
**Priority:** P0
**Description:** 17 Phase 1 frameworks routed by call type + Pass 1 signals. Routing is pure Python ($0.00). Three categories: BLOCKED, MANDATORY, CONTENT-GATED. AIM (Absence Is Meaningful) pattern for key frameworks.

**Acceptance Criteria:**
- All 17 frameworks assigned to routing categories per FRAMEWORK_ROUTING_ARCHITECTURE.md
- Routing decisions logged (for shadow mode evaluation)
- AIM pattern implemented for BATNA (#3) and Close Attempt (#11)
- Pinned frameworks (#8, #9, #15) never removed by routing
- Dependency cascade enforced: #9→#8, #14→#5+#15, #17→#16
- Short call guard: <8 min calls remove {13, 14}

---

### REQ-1.6: Framework Execution (10 Production + 25 Scaffolded)
**Type:** Behavioral Pipeline
**Priority:** P0
**Description:** 10 frameworks at production quality. 25 frameworks scaffolded with placeholder entries. Frameworks execute in 5 prompt groups (A-E) via asyncio.gather. Each group = one batched LLM call.

**Acceptance Criteria:**
- All 10 Phase 1 production frameworks return structured output
- Output schema per framework includes: score, severity, confidence, headline, evidence (segment refs), coaching recommendation
- 25 scaffolded frameworks show placeholder UI entry with "Coming Soon" badge
- Group A (Negotiation): #3, #4, #7, #12, #13
- Group B (Pragmatics): #1, #2, #6, #16
- Group C (Coaching): #5, #10, #11, #14, #15, #17
- Group D (Deal Health): empty in Phase 1 (scaffolded)
- Group E (Emotion): #8, #9
- #8 and #9 combined into single LLM prompt

---

### REQ-1.7: Insight Prioritization & Display
**Type:** Functional
**Priority:** P0
**Description:** Framework results sorted by severity → confidence → actionability → dollar impact → novelty. Top 3-5 surfaced to user. Low-confidence results suppressed or collapsed.

**Acceptance Criteria:**
- Results sorted per prioritization algorithm
- Top 3-5 insights displayed on Call Review
- Low-confidence results (< threshold) collapsed into "Additional Insights" section
- Each insight shows: score, severity (red/yellow/green), headline, evidence snippet
- Click evidence → transcript jumps to segment + audio seeks
- Thumbs up/down feedback buttons on each insight

---

### REQ-1.8: Base Metrics (8 Metrics, Zero LLM Cost)
**Type:** Functional
**Priority:** P0
**Description:** 8 metrics computed from diarization/transcript data without LLM calls. Talk ratio, WPM, longest monologue, question count, filler density, interruption count, response latency, silence ratio.

**Acceptance Criteria:**
- All 8 metrics computed from transcript segments and timing data
- Metrics displayed in Call Stats tab
- Metrics compared to team average (Phase 3, deferred)
- Metrics computed synchronously (no queue)
- Metrics available even if LLM analysis fails

---

### REQ-1.9: AI Call Summary
**Type:** Functional
**Priority:** P1
**Description:** Single LLM call generates structured call summary: recap, key decisions, action items, open questions, deal assessment.

**Acceptance Criteria:**
- Summary generated via single LLM call (separate from frameworks)
- Summary includes: recap paragraph, key decisions list, action items list, open questions list, deal assessment
- Summary displayed in dedicated tab
- Summary regenerated on re-analysis

---

### REQ-1.10: Developer Settings
**Type:** Infrastructure
**Priority:** P1
**Description:** Runtime configuration panel for ASR provider, LLM models (per group), framework toggles, pipeline settings, Langfuse observability, cost tracking.

**Acceptance Criteria:**
- ASR provider toggle (AssemblyAI/Deepgram) takes effect on next call
- LLM model selector per group with pinned version dropdowns
- Framework on/off toggles with status badges (Production/Beta/Placeholder)
- Framework confidence threshold number inputs
- Concurrent calls slider, retry count, timeout settings
- Langfuse enable/disable + project key + dashboard link
- Cost per-call readout
- All settings stored as encrypted JSONB in Settings table

---

### REQ-1.11: Re-Analysis & Export
**Type:** Functional
**Priority:** P2
**Description:** Users can re-run analysis on existing calls with different model/settings. Insights can be copied or exported.

**Acceptance Criteria:**
- Re-analyze button triggers fresh analysis run with current settings
- Previous results archived, not overwritten
- Settings snapshot stored with each run
- Insight copy-to-clipboard button
- Insight export as PDF
- Share link generation (read-only)

---

### REQ-1.12: Bulk Upload
**Type:** Functional
**Priority:** P1
**Description:** Upload up to 50 audio files simultaneously. Spreadsheet-style metadata grid. Batch processing with progress tracking.

**Acceptance Criteria:**
- 50-file multi-select works
- Metadata grid with editable rep name, call type, deal name, date per file
- CSV import option for metadata
- Batch status shown: "X/50 complete, Y in progress, Z queued"
- Processing LIFO within batch
- Auto-fill rep name for similar filenames
- Rate limiting enforced (50 calls/day per user)

---

### REQ-1.13: Onboarding
**Type:** Functional
**Priority:** P2
**Description:** First-run experience: sample calls (pre-analyzed), wizard, empty state designs.

**Acceptance Criteria:**
- 3 sample calls pre-loaded with full analysis
- First-run wizard walks through key features
- Empty states designed for all pages
- Call-to-action prompts on empty states

---

### REQ-1.14: Dashboard
**Type:** Functional
**Priority:** P1
**Description:** Home page with aggregate stats, recent calls needing attention, rep overview table.

**Acceptance Criteria:**
- Aggregate stats: total calls, avg processing time, insight acceptance rate
- Recent calls table (last 10) with status badges
- Rep overview table with call counts and avg scores
- "Needs attention" call filter

---

### REQ-1.15: UI Polish
**Type:** Non-Functional
**Priority:** P2
**Description:** Design system tokens applied. Loading/error/empty states. Responsive layout. Animations.

**Acceptance Criteria:**
- Design system fully implemented
- Loading skeletons on all async content
- Error states with retry actions
- Empty states with CTA
- Mobile-responsive layout
- Micro-interactions on key actions

---

## Phase 2 Requirements (Deferred)

- REQ-2.1: Deal entity (first-class)
- REQ-2.2: Multi-call deal view with trajectories
- REQ-2.3: Zoom cloud recording integration
- REQ-2.4: Salesforce + HubSpot CRM sync
- REQ-2.5: Deal health scoring
- REQ-2.6: Deal risk alerts (Slack)
- REQ-2.7: Cross-call search
- REQ-2.8: Weekly email digests
- REQ-2.9: New frameworks (#3, #14, #30, #31, #12, #26, #29)

---

## Phase 3 Requirements (Deferred)

- REQ-3.1: Multi-user RBAC
- REQ-3.2: Rep login
- REQ-3.3: Behavioral baselines
- REQ-3.4: Skill gap identification
- REQ-3.5: Auto-generated coaching plans
- REQ-3.6: Team comparison views
- REQ-3.7: Rep self-review dashboards
- REQ-3.8: New frameworks (#32, #33, #35, #27)

---

## Data Model Requirements

### Call Record
```
Call {
  id: uuid (PK)
  organization_id: uuid (FK)
  rep_name: string
  call_type: enum(discovery/demo/pricing/negotiation/close/check_in/other)
  deal_name: string?
  call_date: date
  audio_url: string? (S3 URL)
  transcript_status: enum(pending/processing/ready/failed/partial)
  analysis_status: enum(pending/processing/ready/failed/partial)
  created_at: timestamp
  updated_at: timestamp
}
```

### TranscriptSegment
```
TranscriptSegment {
  segment_id: uuid (PK)
  call_id: uuid (FK)
  segment_index: int
  speaker_name: string
  speaker_role: enum(rep/buyer/unknown)
  start_time_ms: int
  end_time_ms: int
  text: text
}
```

### AnalysisRun
```
AnalysisRun {
  id: uuid (PK)
  call_id: uuid (FK)
  settings_snapshot: jsonb
  pass1_output: jsonb
  framework_results: jsonb
  status: enum(processing/ready/failed/partial)
  error_message: string?
  created_at: timestamp
  completed_at: timestamp?
}
```

### FrameworkResult (within AnalysisRun.framework_results)
```
FrameworkResult {
  framework_id: int
  score: float?
  severity: enum(red/yellow/green)?
  confidence: float
  headline: string
  evidence: list[{segment_id, text, start_time_ms}]
  coaching_recommendation: string
}
```

---

*Requirements version 1.0 — derived from Signal PRD v2.2*
