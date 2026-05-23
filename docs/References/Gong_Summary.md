# Gong — What It Is, What It Does, and How

**Source:** Gong.io Product Teardown — Signal Competitive Intelligence, March 22, 2026

---

## The One-Line Answer

Gong started as a call recording tool and has grown into a full **Revenue AI Operating System** — it records sales calls, transcribes them, analyzes them with AI, tracks deals, forecasts revenue, and now even sends emails and coaches reps, all in one platform.

**$300M+ ARR. 5,000+ companies. ~$60K average contract.**

---

## What Gong Actually Does — The 8 Things

### 1. Records and Transcribes Every Sales Call

Gong joins your Zoom, Teams, or Google Meet call automatically (as a bot or via native integration), records it, and produces a full transcript with speaker labels and timestamps.

- Works across Zoom (native), Teams (native), Google Meet (bot), phone dialers
- Has its own built-in dialer for outbound calls
- Transcripts are the foundation — everything else is built on top of them
- Supports multiple languages, auto-detects them
- Custom vocabulary for company-specific terms

> **The call page is the core of the product.** Split screen: analysis on the left, audio player on the right. Every other feature links back to a call.

---

### 2. Automatically Analyzes Every Call with AI

After a call ends, Gong runs multiple AI analyses without anyone asking:

**AI Brief (Summary)**
Generates a structured summary automatically:
- A short recap paragraph
- 10 key bullet points
- Next steps from both sides
- Different templates for different call types (demo calls, pricing calls, etc.)

**6 Interaction Metrics (called "Whisper")**

| Metric | What It Measures | Benchmark |
|--------|-----------------|-----------|
| Talk Ratio | How much the rep talked vs. listened | Stay under 65% |
| Longest Monologue | Rep's longest uninterrupted speech | Under 2.5 minutes |
| Longest Customer Story | Longest the buyer talked without interruption | Longer = better |
| Interactivity | How often the conversation switches back and forth | Higher = more engaging |
| Patience | How long the rep waits after the buyer stops talking | 0.6–1.0 seconds |
| Questions | How often the rep asks questions per hour | Higher = better |

**Topic Timeline**
Gong automatically detects what was being discussed at each moment in the call (Call Setup, Small Talk, Demo, Pricing, Next Steps, etc.) using patented unsupervised machine learning — it figures out topics on its own, not from keyword lists. This is patented and one of their strongest technical moats.

**Smart Trackers**
Detects whether specific concepts were discussed — e.g., "did the buyer mention budget?" — using AI that understands meaning, not just keywords. Admins set up trackers; Gong detects mentions automatically on every future call.

**Ask Anything / Gong Assistant**
Type a natural language question about a call — "What objections did the buyer raise?" — and Gong answers from the transcript. The newer "Gong Assistant" does multi-turn conversations with context across 60 calls and 500 emails at once. Usage grew 400%+ year over year.

---

### 3. Scores and Coaches Reps

**Scorecards**
Managers create evaluation forms (did the rep do X, Y, Z?) and either score calls manually or let the AI score every call automatically. The AI cites specific transcript moments as evidence for each score.

**Coaching Tools**
- Managers leave timestamped comments on specific call moments
- Reps can see how they compare to their team and top performers on every metric
- Call libraries: curate great calls for training new reps
- Snippets: clip specific moments from calls for coaching examples
- Initiative Boards: track whether a new sales methodology is actually being adopted — links training programs to real behavior change in calls

---

### 4. Tracks Deals and Warns About At-Risk Ones

Gong connects to your CRM (Salesforce, HubSpot, Dynamics) and overlays conversation data on top of deal data.

**Deal Board**
A table of all active deals with health scores, CRM fields editable directly in Gong (syncs back to CRM), and playbook compliance (is the rep following MEDDIC/BANT/Challenger?).

**AI Deal Predictor**
Trained on your company's own 2 years of historical closed deals (300+ signals), gives each deal a percentile score — "this deal has a better chance of closing than 80% of your other open deals." Updates daily.

**AI Deal Monitor — Automatic Warnings**

| Warning | What Triggers It |
|---------|-----------------|
| No activity | No calls or emails for X days |
| Customer disengaged | Buyer stopped showing up or responding |
| Red flag email | Buyer sent something that reads as a risk signal |
| Budget concerns | Budget mentioned negatively in a call |
| Single-threaded | Only 1 contact active — champion risk |
| Ghosting | Prospect gone quiet for N days |

These fire automatically without anyone asking. Gong checks every deal continuously.

---

### 5. Forecasts Revenue

Gong replaces spreadsheet-based forecasting:
- Reps submit their forecast numbers
- Managers adjust and override up the chain (rep → manager → VP → CRO)
- Leadership sees rollups across all teams
- The system applies historical conversion rates per pipeline stage
- Conversation signals (what was actually said in calls) feed into the forecast — not just CRM stage data

This is different from Clari (pure CRM math) because Gong knows what was actually discussed in every call.

---

### 6. Sends Emails and Runs Sales Outreach (Engage)

Gong has a full sales engagement tool competing directly with Outreach and Salesloft:

- **Flows (sequences):** Multi-step outreach campaigns — auto emails, manual emails, calls, LinkedIn messages, tasks
- **AI Email Composer:** Generates personalized follow-up emails from the call transcript automatically
- **Power Dialer:** Built-in dialer for outbound calling, auto-records everything
- **AI Tasker:** Surfaces what to do next based on your call data, sends daily to-do summaries via email and Slack

The key insight: because Gong owns both the outreach AND the call recording, it creates a closed loop — send email → book call → analyze call → coach → send next email — all in one system.

---

### 7. AI Agents — 15+ Named AIs Running in the Background

Gong's AI is organized into named, independently configurable agents managed from one place called "Agent Studio":

| Agent | What It Does |
|-------|-------------|
| AI Briefer | Generates call summaries automatically |
| AI Transcriber | Transcribes calls |
| AI Topic Tagger | Detects call topics (patented) |
| Whisper | Computes the 6 interaction metrics |
| AI Tracker | Detects smart tracker concepts |
| AI Deal Predictor | Scores deal health daily |
| AI Deal Monitor | Watches all deals for warning signs |
| AI Deal Reviewer | Scores playbook compliance per deal |
| AI Call Reviewer | Auto-scores calls on scorecards |
| Gong Assistant | Multi-turn conversational AI |
| AI Composer | Writes follow-up emails |
| AI Tasker | Surfaces next best actions |
| AI Trainer | Roleplay simulations for rep training |
| AI Theme Spotter | Finds patterns across many calls |
| AI Data Extractor | Pulls structured data from calls |

Each agent can be tested, previewed, and deployed independently.

---

### 8. Integrates Everything

Gong connects to essentially every tool in a sales stack:

- **CRM:** Salesforce, HubSpot, Dynamics 365 (bi-directional sync)
- **Meetings:** Zoom, Teams, Google Meet, Webex
- **Dialers:** RingCentral, Aircall, Dialpad, Outreach, SalesLoft
- **Email:** Gmail, Outlook (with open/click/reply tracking)
- **Messaging:** Slack, Teams
- **Data enrichment:** ZoomInfo, 6sense, LinkedIn Sales Navigator
- **AI interop:** MCP support for Salesforce Agentforce, Microsoft Copilot, HubSpot AI

---

## What Makes Gong Hard to Compete With

| Moat | Why It Matters |
|------|---------------|
| **3B+ interactions training data** | Proprietary dataset competitors can't replicate without years of scale |
| **Patented topic detection** | Unsupervised topic segmentation — no one else does it this way |
| **CRM integration depth** | Years of bi-directional sync, embedded Salesforce panels — deeply woven into workflows |
| **Conversation + revenue data in one place** | Forecasting with actual call signals, not just CRM stage changes |
| **Named agent architecture** | Modular AI — each capability is independently upgradeable |
| **MCP support (first in category)** | Bet on AI interoperability — Gong data feeds other AI systems |

---

## What Gong Does NOT Do — The Gap Signal Fills

Gong is **broad but shallow on analysis**. It tells you WHAT was said. It does not tell you WHAT IT MEANT.

| What Gong Does | What Gong Doesn't Do |
|---------------|----------------------|
| Counts questions asked | Classifies question quality (diagnostic vs. leading vs. closing) |
| Detects keywords and topics | Detects when a question was asked and then EVADED |
| Basic positive/negative sentiment | Detects emotional turning points with cause attribution |
| Tracks talk ratio % | Scores commitment quality (genuine vs. face-saving vs. deflecting) |
| Keyword-based methodology compliance | Behavioral science-based compliance scoring |
| Flags if "budget" was mentioned | Detects unconditional concessions and their dollar impact |
| Per-call deal health score | Commitment trajectory ACROSS multiple calls in a deal |

The proof this gap is real: In G2 reviews, multiple CROs, Directors of Sales, and Head of RevOps describe copying Gong transcripts into ChatGPT or Claude for better analysis because Gong's AI is too shallow. Gong's own power users are doing this manually. That is the exact behavior Signal productizes.

---

## Pricing — What It Actually Costs

| Package | Cost |
|---------|------|
| Core conversation intelligence | ~$1,600/user/year + $50K platform fee |
| Add Engage (outreach tools) | +$800/user/year |
| Add Forecast | +$700/user/year |
| Fully loaded (all modules) | ~$3,000–$3,500/user/year |
| 50-seat team, full stack | ~$150K–$200K/year |
| 200-seat enterprise | ~$400K–$600K/year |

No self-serve. Everything is custom-quoted, annual contracts only.

---

## The Strategic Picture

Gong's trajectory is **breadth over depth**. Every year they add a new product line:
- Gong Engage (sales outreach) — competes with Outreach, SalesLoft
- Gong Forecast — competes with Clari
- Gong Enable (Feb 2026) — competes with Seismic, Highspot

Every new product line makes Gong stickier and harder to remove. But it also means engineering resources go toward building new surfaces rather than deepening the intelligence layer.

**That horizontal expansion is exactly what creates the opening for Signal.** Gong is building more products. The intelligence inside those products is staying shallow. The analysis layer is being neglected while the platform grows wider.
