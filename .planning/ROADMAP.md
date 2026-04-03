# Signal — Project Roadmap

**Project:** Signal — Behavioral Sales Intelligence
**Version:** 1.0
**Status:** Active
**Last Updated:** 2026-04-04

---

## Vision

"Gong tells you what was said. Signal tells you what it meant."

Signal is a post-call behavioral intelligence platform that analyzes sales conversations using validated psychological and behavioral science frameworks. It extracts meaning from audio recordings and transcripts to detect question evasion, commitment quality, emotional dynamics, concession patterns, negotiation leverage, and coaching opportunities.

**Beachhead:** Sales managers at B2B SaaS companies with 25-200 person sales teams, running $150-200K ACV deals, who already use Gong or Chorus and find it shallow.

---

## Five-Phase Roadmap

```
Phase 1          Phase 2            Phase 3            Phase 4            Phase 5
┌──────────┐    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ SMART    │    │ DEAL         │   │ COACHING     │   │ REVENUE      │   │ BEHAVIORAL   │
│ CALL     │───▶│ ANALYST      │──▶│ ENGINE       │──▶│ SCIENTIST    │──▶│ INTELLIGENCE │
│ ANALYZER │    │              │   │              │   │              │   │ PLATFORM     │
├──────────┤    ├──────────────┤   ├──────────────┤   ├──────────────┤   ├──────────────┤
│ Single   │    │ + Deals      │   │ + Multi-user │   │ + Executive  │   │ + Public API │
│ user     │    │ + CRM sync   │   │ + Rep logins │   │ + Enterprise │   │ + Framework  │
│ Upload   │    │ + Zoom       │   │ + Coaching   │   │ + SSO/SOC2   │   │   Builder    │
│ 10 FWs   │    │ + 7 new FWs  │   │ + Baselines  │   │ + ROI proof  │   │ + Real-time  │
│ 4 screens│    │ + Search     │   │ + Skill gaps │   │ + Audit logs │   │ + Multi-lang │
│          │    │ + Slack      │   │ + 4 new FWs  │   │ + 3 new FWs  │   │ + Marketplace│
└──────────┘    └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
Exit: 5 pilots   Exit: 15 custs   Exit: 30+ custs   Exit: 3 enterprise  Exit: API >10%
Accept >60%      CRM >50%         Rep engage >40%    SOC 2 certified     5+ integrations
<10min/call      Risk acc >70%    Behavior change    Churn <2%           Real-time live
```

---

## Phase 1: Core Intelligence — "The Smart Call Analyzer"

**Phase:** 1
**Name:** Core Intelligence
**Status:** In Progress (Plan: `.planning/phases/01-core-intelligence/01-PLAN.md`)
**Goal:** Transcript paste input only. Fix broken/missing backend modules. Connect Streamlit to FastAPI. Deploy with Docker.

### Phase Boundary
Transcript paste as primary (and only) input. No audio upload, no ASR. FastAPI backend + Streamlit frontend. Behavioral analysis pipeline (Pass 1 + Routing + Framework execution + Insights).

### Status
**Plan 01:** ✅ COMPLETED (2026-04-04)
- ASR/S3 modules removed
- Feedback persistence fixed
- LLM availability guard added
- Paste-transcript endpoint implemented
- Integration tests added (157 tests passing)
- Streamlit refactored to use signalapp modules
- Evidence linking and transcript sync added
- Dockerfile + docker-compose + CI/CD added

### Deliverables (Phase 1 Scope)
- **Input:** Transcript paste only (no audio)
- **Behavioral layer:** 10 frameworks at production quality + 25 scaffolded placeholders
- **Backend:** FastAPI + Postgres + signalapp package
- **Frontend:** Streamlit testing harness connected to FastAPI
- **Deployment:** Dockerfile + docker-compose.yml + CI/CD

### Requirement IDs
- REQ-01: Transcript paste input + metadata stored in Postgres
- REQ-02: Pass 1 extraction (hedge, sentiment, evaluative)
- REQ-03: Framework routing (pure Python)
- REQ-04: Pass 2 framework groups executed via asyncio.gather
- REQ-05: Framework results stored in Postgres JSONB
- REQ-06: Verified insights generated + prioritized
- REQ-07: Insights surfaced via FastAPI endpoint
- REQ-08: Streamlit connected to FastAPI backend

### Build Slices (adapted for transcript-only)
| Slice | What | Depends | Status |
|-------|------|---------|--------|
| 1 | Backend completion: pyproject.toml, fix feedback persistence, LLM guard | - | ✅ Done |
| 2 | ASR/S3 removal | 1 | ✅ Done |
| 3 | Paste-transcript API endpoint | 1 | ✅ Done |
| 4 | Pipeline integration tests | 2, 3 | ✅ Done |
| 5 | Streamlit backend integration | 4 | ✅ Done |
| 6 | Evidence linking in Streamlit | 5 | ✅ Done |
| 7 | Deployment: Dockerfile, docker-compose, CI/CD | 5 | ✅ Done |

### Critical Path
`1 → 3 → 5 → 7`

### Canonical References
- `References/FRAMEWORK_ROUTING_ARCHITECTURE.md` — Framework routing (17 frameworks, 5 groups, AIM pattern)
- `References/PCP_Summary.md` — PCP behavioral science foundation
- `References/LLM_RELIABILITY_GUIDE.md` — LLM patterns and reliability

---

## Phase 2: Deal Intelligence + Integrations — "The Deal Analyst"

**Phase:** 2
**Name:** Deal Intelligence
**Status:** Future
**Goal:** Multi-call deal tracking with commitment trajectories. CRM sync. Zoom integration.

### Phase Boundary
Multi-call deal tracking with commitment trajectories across conversations. CRM sync. Zoom cloud recording integration. Cross-call search. Notifications.

### New Capabilities
- Multi-call deal view (commitment trajectory, BATNA evolution, engagement trend)
- Deal health scoring
- Deal risk alerts (Slack notifications)
- Cross-call search
- Zoom cloud recording integration
- Salesforce + HubSpot CRM sync
- Weekly email digests

### New Frameworks (7)
- BATNA Detection (#3)
- Methodology Compliance (#14)
- Buying Signal Strength (#30)
- Negotiation Power Index (#31)
- Agreement Quality (#12)
- Advanced Non-Answer Detection (#26)
- Emotional Influence Pattern (#29)

### Exit Criteria
- 15 paying customers
- CRM sync active on >50% of accounts
- Deal risk alert accuracy >70%

### Requirement IDs
- REQ-2.1 through REQ-2.N (deferred to Phase 2 planning)

---

## Phase 3: Team Intelligence + Coaching — "The Coaching Engine"

**Phase:** 3
**Name:** Team Coaching
**Status:** Future
**Goal:** Multi-user with roles. Rep logins. Behavioral baselines. Coaching dashboards.

### Phase Boundary
Multi-user with RBAC. Roles: Admin, Manager, Rep, RevOps. Rep behavioral baselines. Skill gap identification. Auto-generated coaching plans. Team comparison views.

### New Capabilities
- Multi-user RBAC (Admin, Manager, Rep, RevOps)
- Rep behavioral baselines
- Skill gap identification
- Auto-generated coaching plans
- Team comparison views (anonymous benchmarks)
- Rep self-review dashboards

### New Frameworks (4)
- Trust Trajectory (#32)
- Buyer State Diagnosis (#33)
- Emotional Resilience longitudinal (#35)
- Communication Authenticity Profile (#27)

### Exit Criteria
- 30+ customers
- Rep engagement rate >40%
- Measurable behavior change correlation

### Requirement IDs
- REQ-3.1 through REQ-3.N (deferred to Phase 3 planning)

---

## Phase 4: Executive Intelligence + Enterprise — "The Revenue Scientist"

**Phase:** 4
**Name:** Executive Intelligence
**Status:** Future
**Goal:** Executive dashboards. Enterprise features. ROI proof.

### Exit Criteria
- 3+ enterprise contracts (500+ seats each)
- SOC 2 certification
- Churn <2%

### Requirement IDs
- REQ-4.1 through REQ-4.N (deferred to Phase 4 planning)

---

## Phase 5: Platform + Ecosystem — "The Behavioral Intelligence Platform"

**Phase:** 5
**Name:** Platform
**Status:** Future
**Goal:** Public API. Custom framework builder. Real-time in-call coaching. Marketplace.

### Exit Criteria
- API revenue >10% of total
- 5+ partner integrations live
- 10+ custom framework customers
- Real-time coaching in production

### Requirement IDs
- REQ-5.1 through REQ-5.N (deferred to Phase 5 planning)

---

## Project-Wide Decisions

| Decision | Answer | Rationale |
|----------|--------|-----------|
| V1 user model | Single account, rep tagging | Right buyer persona (manager), minimal auth overhead, clean POC story |
| Audio input | Transcript paste only (Phase 1) | No ASR, zero cost. Audio upload deferred to Phase 2+ |
| LLM provider | Both Claude + GPT-4o + Gemini, switchable per group at runtime | Different models may excel on different framework types |
| Package naming | `signalapp` (not `signal`) | `signal` conflicts with Python stdlib `signal` module |
| Frontend | Streamlit (not Next.js) | Faster iteration per user constraint |
| Pipeline | ARQ + LangGraph | Async-native, per ADR |

---

*Roadmap version 1.1 — updated April 4, 2026 with Phase 1 plan*
