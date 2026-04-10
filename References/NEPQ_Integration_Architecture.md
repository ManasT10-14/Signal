# NEPQ Integration into Signal — Final Architecture

## What Is NEPQ?

NEPQ (Neuro-Emotional Persuasion Questions) is a sales questioning methodology created by Jeremy Miner at 7th Level. Its core principle: **people buy on emotion and justify with logic.** Instead of pitching and closing, the rep asks a structured sequence of questions that leads the buyer to convince themselves.

Traditional sales: Rep talks 80%, buyer listens → external motivation → fades after the call.
NEPQ sales: Buyer talks 80%, rep asks questions → internal motivation → persists and strengthens.

## Why We Integrated NEPQ

### What Signal Had (Diagnostic)
Signal's 17 frameworks answer: *"What behavioral patterns exist in this call?"*
- FW-01: Did the buyer evade questions?
- FW-02: Were commitments genuine?
- FW-05: Were the rep's questions diagnostic or leading?
- FW-15: Did the call have proper structure?

### What NEPQ Adds (Prescriptive)
NEPQ answers: *"Did the rep follow a proven methodology, and WHERE EXACTLY did they deviate?"*

This transforms coaching from generic to surgical:
- **Before:** "Rep should ask better questions"
- **After:** "At [02:22] the buyer said 'It's been challenging.' You moved on. NEPQ says probe: 'When you say challenging, what do you mean?' — this is where surface conversations become deals."

### Competitive Advantage
No competitor (Gong, Chorus, Clari) scores NEPQ compliance. This is a genuine differentiator.

## Architecture Decision: One Unified Framework

### Why Not 3 Separate Frameworks?

We initially designed three NEPQ frameworks:
1. Sequence Adherence — did the 8 phases happen?
2. Diagnostic Depth — did the rep probe beneath surface answers?
3. Commitment Origin — was the commitment self-generated?

**We consolidated them into one.** Here's why:

**The causal chain argument.** The three dimensions aren't independent — they form a causal chain:
```
Missing phases → shallow depth → rep-pushed commitment
```
Specifically: if the rep skips Consequence questions (Phase 5), the buyer never feels urgency, so their commitment at the end is passive agreement, not self-generated conviction. A single LLM pass can trace this chain. Three separate prompts each see the transcript but can't cross-reference findings.

**The coherent coaching argument.** A sales manager doesn't want three separate scores. They want ONE narrative: "You skipped Phase 5, which meant the buyer never felt urgency, which is why they said 'let me think about it' instead of 'this is exactly what we need.' Here's exactly what to say next time."

**The cost argument.** One LLM call instead of three. On a 4-minute transcript, this saves ~16,000 input tokens per analysis.

**The context-sharing argument.** When the LLM evaluates all three dimensions in one pass, it can connect insights: "The depth stayed surface-level because the rep skipped Problem Awareness (Phase 3), which meant there were no vague answers to probe — the buyer was never asked about their pain in the first place."

## The Framework: FW-20 — NEPQ Methodology Analysis

**Group:** F (Methodology Intelligence)
**ID:** 20
**Lives in:** `signalapp/prompts/groups/group_f/nepq_analysis_v1.py`

### What It Evaluates

One LLM call producing three sub-scores and a unified coaching narrative:

#### Sub-Score 1: Sequence Adherence (40% weight)

Did the rep's questions follow the 8-phase NEPQ sequence?

| Phase | Purpose | Key Signal |
|-------|---------|-----------|
| 1. Connecting | Build rapport | Rep asks about buyer's world before product |
| 2. Situation | Map current state | "What are you using now?" |
| 3. Problem Awareness | Surface dissatisfaction | "What don't you like about it?" |
| 4. Solution Awareness | Buyer envisions fix | "What have you tried to change this?" |
| **5. Consequence** | **Make inaction costly** | **"What happens if nothing changes?"** |
| 6. Qualifying | Test urgency | "How important is this to you now?" |
| 7. Transition | Mirror buyer's words | "Based on what you said about..." |
| 8. Committing | Self-persuasion close | "Do you feel this could work? Why?" |

Phase 5 (Consequence) is the most critical. Without it, the buyer has awareness but no urgency.

#### Sub-Score 2: Diagnostic Depth (35% weight)

When the buyer gives a vague answer, did the rep probe deeper?

```
Level 1 — SURFACE:    "It's challenging." → Rep moves on (BAD)
Level 2 — SPECIFIC:   "What do you mean by challenging?" → "Reporting takes 3 days"
Level 3 — EMOTIONAL:  "How does that affect your team?" → "They're frustrated and demoralized"
Level 4 — QUANTIFIED: "What's that costing you?" → "About $200K a year in overtime"
```

Each missed probing opportunity is a coaching moment.

#### Sub-Score 3: Commitment Origin (25% weight)

Was the buyer's commitment self-generated or rep-pushed?

| Self-Generated (strong) | Rep-Pushed (weak) |
|------------------------|-------------------|
| "I think this could solve our reporting problem because..." | "Okay, sounds good" |
| Buyer explains WHY in their own words | Buyer just agrees |
| Follows consequence/qualifying questions | Follows hard close or pitch |
| Active language: "I want to...", "We need to..." | Passive: "I guess so", "That's fine" |

**The test:** Did the buyer say WHY in their own words? Yes → self-generated. No → rep-pushed.

### Overall Score

```
nepq_score = (sequence_score * 0.40) + (depth_score * 0.35) + (commitment_origin_score * 0.25)
```

### Severity

| Severity | Criteria |
|----------|----------|
| RED | nepq_score < 0.30, OR Consequence missing on discovery/demo, OR 100% rep-pushed |
| ORANGE | nepq_score 0.30-0.50, OR 2+ phases missing, OR depth never exceeded surface |
| YELLOW | nepq_score 0.50-0.70, OR 1 phase missing, OR mostly self-generated with some rep-pushed |
| GREEN | nepq_score > 0.70, 7-8 phases present, emotional/quantified depth reached |

### Routing

| Call Type | FW-20 Status | Why |
|-----------|:------------|-----|
| Discovery | **MANDATORY** | Full NEPQ flow expected — this is where methodology matters most |
| Demo | **MANDATORY** | Rep should use NEPQ to transition from pain to solution |
| Pricing | Content-gated (`has_rep_questions`) | NEPQ relevant if rep asks questions during pricing |
| Negotiation | Content-gated (`has_rep_questions`) | NEPQ relevant if questioning is part of negotiation |
| Close | Content-gated (`has_rep_questions`) | Mostly Phase 6-8 |
| Check-in | **BLOCKED** | Too informal for methodology scoring |

### Coaching Output Format

Every coaching recommendation follows the causal chain:

```
1. THE CHAIN: What was missing → what it caused → what the outcome was
2. THE MOMENT: Specific timestamp and quote where the chain broke
3. THE FIX: Word-for-word NEPQ question the rep should have asked
4. THE IMPACT: What would have changed
```

**Example:**
> "The call skipped Consequence questions (Phase 5), which meant the buyer never felt the cost of inaction. At [02:20], buyer said 'Okay, let me think about it' — a classic stall because they have no internal urgency. Before presenting pricing at [01:10], insert: 'What happens if your team keeps using the current system for another year? What does that cost you?' This forces the buyer to articulate their own urgency, making the price feel justified against a quantified pain."

## How It Fits Signal's Architecture

### Pipeline Flow
```
Pass 1 → Route → Execute Groups → Verify → Insights → Summary → Store
                        │
                        ├── Group A (Negotiation)      — parallel
                        ├── Group B (Pragmatic)         — parallel
                        ├── Group C (Strategic Clarity)  — parallel
                        ├── Group E (Emotional)          — parallel
                        └── Group F (NEPQ)               — parallel ← NEW
```

### Group Layout
```
Group A: Negotiation Intelligence     — 5 frameworks
Group B: Pragmatic Intelligence       — 4 frameworks
Group C: Strategic Clarity            — 6 frameworks
Group D: (reserved — Phase 2)         — 0 frameworks
Group E: Emotional Resonance          — 2 frameworks (PINNED)
Group F: NEPQ Methodology             — 1 framework  ← NEW
                                        ─────────────
                                        18 frameworks total
```

### What Existing Frameworks Cover vs. What NEPQ Adds

| Existing Framework | What It Already Knows | What NEPQ Adds |
|---|---|---|
| FW-05: Question Quality | Question is diagnostic/leading/rhetorical | Was it in the RIGHT PHASE of the NEPQ sequence? |
| FW-15: Call Structure | Opening/discovery/demo/close phases present | Were the 8 NEPQ-SPECIFIC phases present and in order? |
| FW-02: Commitment Quality | Commitment is genuine/face-saving | Was the commitment SELF-GENERATED or REP-PUSHED? |
| FW-08/09: Emotion | Emotion shifted at this moment | Did the rep INTENTIONALLY trigger it with Phase 5 consequence questions? |
| FW-01: Unanswered Questions | Buyer evaded this question | Did the rep PROBE DEEPER after evasion or accept it? |

NEPQ doesn't duplicate these frameworks. It asks questions they can't answer because it requires understanding the conversation as a **flow**, not as isolated behavioral signals.

### Cost

- **+1 LLM call** when Group F is active (~$0.002-0.005)
- Blocked on check_in → zero cost on check-in calls
- Content-gated on pricing/negotiation/close → only runs if rep actually asked questions
- **Average cost increase across all call types: ~10-15%**

## Files

| File | Purpose |
|------|---------|
| `signalapp/prompts/groups/group_f/nepq_analysis_v1.py` | The unified NEPQ prompt with all 3 dimensions |
| `signalapp/prompts/groups/group_f/__init__.py` | Group F documentation |
| `signalapp/domain/routing.py` | FW-20 routing spec in ROUTING_TABLE, Group F in GROUP_MEMBERSHIP |
| `signalapp/domain/framework.py` | FW-20 in FRAMEWORK_REGISTRY |
| `signalapp/domain/frameworks.py` | FW-20 in FRAMEWORK_NAMES |
| `signalapp/pipeline/nodes/execute_groups.py` | FW-20 in FW_PROMPT_MAP, Group F in GROUP_LLM_CONFIG_KEY |
| `signalapp/app/config.py` | `llm_group_f` configuration |

## Summary

NEPQ integration adds one framework (FW-20) in one new group (F) that evaluates three interconnected dimensions of sales methodology in a single LLM pass. It answers the question no other framework can: **"Did the rep follow a proven questioning methodology, and where exactly did they deviate?"** — with word-for-word coaching on what to say differently next time.
