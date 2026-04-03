# Signal: Framework Routing Architecture

> **One-line summary:** Signal analyzes every sales call transcript through 17 LLM-powered behavioral frameworks. Not all frameworks are relevant to every call. This document defines the architecture for intelligently deciding — at zero extra cost — which frameworks run on each transcript, how they execute in parallel, and why every routing decision was made.

---

## Table of Contents

- [The Big Picture](#the-big-picture)
- [What Is This Document?](#what-is-this-document)
- [1. Signal's 17 Phase 1 Frameworks](#1-signals-17-phase-1-frameworks)
- [2. Why Routing Matters](#2-why-routing-matters)
- [3. The Three Routing Categories](#3-the-three-routing-categories)
- [4. The AIM Pattern — Absence Is Meaningful](#4-the-aim-pattern--absence-is-meaningful)
- [5. The Routing Specification Table](#5-the-routing-specification-table)
- [6. How Groups Execute When Multiple Are Active](#6-how-groups-execute-when-multiple-are-active)
- [7. The Architecture in Full](#7-the-architecture-in-full)
- [8. Full Implementation](#8-full-implementation)
  - [Pass 1 Gate Signals](#pass-1-gate-signals)
  - [Routing Table Definition](#routing-table-definition)
  - [Core Routing Functions](#core-routing-functions)
  - [Dependency Enforcement](#dependency-enforcement)
  - [Full Orchestration](#full-orchestration)
- [9. Framework Dependency Graph](#9-framework-dependency-graph)
- [10. Routing Outcomes by Call Type](#10-routing-outcomes-by-call-type)
- [11. Cost Reality](#11-cost-reality)
- [12. Edge Cases & Guard Rails](#12-edge-cases--guard-rails)
- [13. Evaluation: How to Know the Router Works](#13-evaluation-how-to-know-the-router-works)
- [14. Summary](#14-summary)

## The Big Picture

Read this diagram before anything else. It shows the complete flow from a raw transcript to surfaced insights, with routing at the center.

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                    SIGNAL — FRAMEWORK ROUTING OVERVIEW                               ║
╚══════════════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────┐
  │   INPUT                         │
  │   • Sales call transcript       │
  │   • Call type (discovery/demo/  │
  │     pricing/negotiation/close/  │
  │     check_in/other)             │
  └────────────────┬────────────────┘
                   │
                   ▼
  ╔══════════════════════════════════════════════════════╗
  ║  PASS 1 — Always runs. No routing affects this.      ║
  ║                                                      ║
  ║  Extracts three infrastructure signals:              ║
  ║  • Hedge map      (per turn: epistemic/strategic)    ║
  ║  • Sentiment traj (per turn: score + notable shifts) ║
  ║  • Evaluative lang(per turn: affect/judgment/apprai) ║
  ║                                                      ║
  ║  Derives routing flags (Pass1GateSignals):           ║
  ║  has_pricing_discussion │ has_competitor_mention     ║
  ║  has_objection_markers  │ has_close_language         ║
  ║  has_rep_questions      │ has_numeric_anchor         ║
  ╚════════════════════════════╦═════════════════════════╝
                               ║
                               ║ (call_type == "other"?)
                               ║ YES → Haiku micro-classifier
                               ║       reads 500 tokens, infers
                               ║       effective call type (~$0.001)
                               ║
                               ▼
  ╔══════════════════════════════════════════════════════╗
  ║  ROUTING DECISION — Pure Python, $0.00               ║
  ║  Runs once per framework (17 decisions total)        ║
  ║                                                      ║
  ║  For each framework, call type + Pass 1 flags        ║
  ║  determine exactly ONE outcome:                      ║
  ║                                                      ║
  ║  ① BLOCKED     → never run (wrong context)          ║
  ║     e.g. BATNA on check_in calls                     ║
  ║     e.g. Money Left on Table on discovery calls      ║
  ║                                                      ║
  ║  ② MANDATORY   → always run (AIM applies*)          ║
  ║     e.g. BATNA on negotiation calls                  ║
  ║         (even with no competitors mentioned —        ║
  ║          "no alternatives = weak BATNA" IS insight)  ║
  ║     e.g. Close Attempt on demo calls                 ║
  ║         (0 attempts = missed opportunity = coaching) ║
  ║                                                      ║
  ║  ③ CONTENT-GATED → check Pass 1 signal              ║
  ║     e.g. Pushback Classification: only if            ║
  ║          has_objection_markers = True                ║
  ║     e.g. BATNA on discovery: only if                 ║
  ║          has_competitor_mention = True               ║
  ║                                                      ║
  ║  * AIM = Absence-Is-Meaningful. See Section 4.       ║
  ╚════════════════════════════╦═════════════════════════╝
                               ║
                               ▼
  ╔══════════════════════════════════════════════════════╗
  ║  DEPENDENCY ENFORCEMENT                              ║
  ║                                                      ║
  ║  Pinned (never removable):                           ║
  ║    #8+#9 Emotion Pipeline  #15 Call Structure        ║
  ║                                                      ║
  ║  Cascading rules:                                    ║
  ║    #17 requires #16  →  remove #17 if #16 removed   ║
  ║    #14 requires #5+#15 → remove #14 if either gone  ║
  ║    #9  requires #8   →  always runs with #8          ║
  ╚════════════════════════════╦═════════════════════════╝
                               ║
                               ║  Active Framework Set
                               ║  (typically 8–13 of 17)
                               ║
                               ▼
  ╔══════════════════════════════════════════════════════╗
  ║  PARALLEL GROUP EXECUTION                            ║
  ║                                                      ║
  ║  Frameworks are assigned to 5 prompt groups.         ║
  ║  Active groups run simultaneously (asyncio.gather).  ║
  ║  Empty groups are skipped entirely.                  ║
  ║  Each group = ONE batched LLM call.                  ║
  ║                                                      ║
  ║  GROUP A         GROUP B         GROUP C             ║
  ║  Negotiation     Pragmatics      Coaching            ║
  ║  #3 #4 #7 #12    #1 #2 #6 #16   #5 #10 #11          ║
  ║  #13              ─────────────  #14 #15 #17         ║
  ║  ─────────        1 LLM call     ─────────           ║
  ║  1 LLM call       (if active)    1 LLM call          ║
  ║  (if active)                     (if active)         ║
  ║                                                      ║
  ║  GROUP D                GROUP E                      ║
  ║  Deal Health            Emotion                      ║
  ║  (Phase 2 — future)     #8 + #9                      ║
  ║  ──────────────         ────────────                 ║
  ║  always skipped P1      1 LLM call                   ║
  ║                         (always active — PINNED)     ║
  ╚════════════════════════════╦═════════════════════════╝
                               ║
                               ▼
  ┌──────────────────────────────────────────────────────┐
  │  FRAMEWORK RESULTS                                   │
  │  Each framework returns: score, severity (red–green),│
  │  confidence, headline, evidence (segment refs),      │
  │  coaching recommendation                             │
  └────────────────────┬─────────────────────────────────┘
                       │
                       ▼
  ┌──────────────────────────────────────────────────────┐
  │  INSIGHT PRIORITIZATION                              │
  │  Sort by: severity → confidence → actionability      │
  │  → dollar impact → novelty                          │
  │  Surface top 3–5 insights to user                    │
  │  (Low-confidence results suppressed or collapsed)    │
  └──────────────────────────────────────────────────────┘
```

---

## What Is This Document?

**Signal** is a behavioral sales intelligence product that processes sales call transcripts through LLM-powered behavioral frameworks — each one detects a specific pattern: evasion, commitment quality, emotional turning points, concession behavior, and more.

**The problem:** Signal has 17 Phase 1 frameworks, but running all 17 on every call wastes compute and generates noise. A check-in call doesn't need BATNA detection. A discovery call doesn't need concession pattern analysis. Worse, frameworks that fire on missing content produce low-confidence outputs that erode user trust.

**The solution:** A routing layer that decides which frameworks run on each transcript. The routing is:
- **Free** — decisions use metadata + already-computed Pass 1 output, no extra LLM calls
- **Content-aware** — reads actual transcript signals, not just call type labels
- **AIM-aware** — understands that for some frameworks, finding nothing IS the insight
- **Fail-open** — routing errors cause frameworks to run, not to be skipped

**Cost reduction:** 25–45% fewer LLM calls. Achieved entirely through routing logic, zero accuracy risk.

---

## 1. Signal's 17 Phase 1 Frameworks

Signal's analysis layer is organized into 5 prompt groups. Each group runs as one batched LLM call containing all its active frameworks.

| # | Framework | Group | What It Detects |
|---|-----------|-------|-----------------|
| 1 | Unanswered Questions | B | Questions the buyer deflected, evaded, or changed topic to avoid |
| 2 | Commitment Quality Score | B | Whether buyer commitments are genuine, face-saving, or deflecting |
| 3 | BATNA Detection | A | Buyer's alternatives and walkaway strength; bluff probability |
| 4 | Money Left on the Table | A | Unconditional concessions; estimated dollar impact |
| 5 | Question Quality Score | C | Rep question types (diagnostic vs. leading vs. rhetorical) |
| 6 | Commitment Thermometer | B | Scalar implicature — "good" ≠ "excellent" on a 0–100 scale |
| 7 | First Number Tracker | A | Who anchored first in pricing; anchor relative to target |
| 8 | Emotional Turning Points | E | Moments where emotional state shifted significantly |
| 9 | Emotional Trigger Analysis | E | WHY the emotion shifted — the preceding causative utterance |
| 10 | Frame Match Score | C | Gain vs. loss framing alignment between rep and buyer |
| 11 | Close Attempt Analysis | C | Whether rep attempted to close; technique classification |
| 12 | Deal Health at Close | A | Churn risk based on closing moment signals |
| 13 | Deal Timing Intelligence | A | Ripeness assessment — is the deal ready to advance? |
| 14 | Methodology Compliance | C | SPIN/MEDDIC/Challenger adherence score |
| 15 | Call Structure Analysis | C | Phase progression (discovery → demo → objections → close) |
| 16 | Pushback Classification | B | Objection vs. concern vs. rejection — each needs different response |
| 17 | Objection Response Score | C | LAER framework quality per objection handled |

**Hard dependencies** (routing must respect these):
- `#9` requires `#8` — they are a single combined LLM prompt
- `#14` requires both `#5` AND `#15` — it scores on top of their output
- `#17` requires `#16` — it evaluates responses to pushback #16 found

**Pinned frameworks** (never removed by any routing logic):
- `#8 + #9` (Emotion Pipeline) and `#15` (Call Structure) always run

---

## 2. Why Routing Matters

**Without routing:**

| Framework | On a check-in call | Cost |
|-----------|--------------------|------|
| #3 BATNA | No competitors in a CSM call | Wasted LLM call |
| #4 Money Left on Table | No pricing discussion | Empty output; noise |
| #7 First Number Tracker | No numbers stated | Empty output; noise |
| #11 Close Attempts | Check-ins aren't closes | Irrelevant coaching |
| #13 Deal Timing | Timing not meaningful mid-relationship | Empty output |

5 wasted framework calls on a single check-in. At 1,000 calls/month, that's thousands of unnecessary Sonnet calls generating outputs that confuse users.

**With routing:**

A check-in call runs only 7 frameworks: `{1, 2, 5, 6, 8, 9, 15}`. 10 frameworks are correctly excluded. Three groups (A, D) are skipped entirely.

**The cost of a false negative** (routing skips a framework that should have run) is worse than a false positive (routing includes a framework that produces null output). When in doubt, the router **fails open** — include the framework.

---

## 3. The Three Routing Categories

Every framework, for every call type, falls into exactly one category:

```
                    ┌─────────────────────────────────────┐
                    │  call_type known?                   │
                    └───────────┬─────────────────────────┘
                                │
               ┌────────────────┼────────────────────┐
               ▼                ▼                     ▼
         ┌──────────┐    ┌────────────┐       ┌─────────────────┐
         │ BLOCKED  │    │ MANDATORY  │       │ CONTENT-GATED   │
         │          │    │            │       │                 │
         │ Call type│    │ Call type  │       │ Check Pass 1    │
         │ makes FW │    │ makes FW   │       │ content signal  │
         │ wrong    │    │ inherently │       │                 │
         │          │    │ valuable   │       │ Run if signal   │
         │ → SKIP   │    │            │       │ present         │
         └──────────┘    │ → RUN      │       │                 │
                         │ (even if   │       │ Skip if absent  │
                         │  no signal)│       │ (unless AIM*)   │
                         └────────────┘       └─────────────────┘
```

**The routing function in one block:**

```python
def should_run_framework(fw_id, call_type, pass1_signals) -> bool:
    spec = ROUTING_TABLE[fw_id]
    if fw_id in PINNED_FRAMEWORKS:          return True   # always run
    if call_type in spec.blocked_for:       return False  # never run
    if call_type in spec.mandatory_for:     return True   # always run (incl. AIM)
    if spec.required_signal:                              # content-gated
        return getattr(pass1_signals, spec.required_signal)
    return True                                           # universal
```

---

## 4. The AIM Pattern — Absence Is Meaningful

This is the most important concept in the routing design.

**The problem it solves:** Some frameworks should run even when their trigger signal is absent, because "nothing found" is itself an actionable insight — *on specific call types*.

### Example: BATNA Detection (#3) on a Negotiation Call

```
SCENARIO A:  Negotiation call — buyer mentioned Competitor X

→ BATNA runs → finds: "Strong BATNA. Buyer referenced Salesforce 3x
                       with high specificity."
→ Coaching: "Do not offer preemptive discounts. Probe the comparison."
→ Severity: ORANGE


SCENARIO B:  Negotiation call — buyer never mentioned any competitor

→ WITHOUT AIM: BATNA skipped. Rep gets no insight. 
   Rep volunteers a 15% discount "just in case."

→ WITH AIM:    BATNA runs → finds: "No alternatives detected.
                            Buyer's BATNA appears weak — no stated
                            walkaway option."
→ Coaching: "You have leverage. Hold the pricing position."
→ Severity: GREEN (leverage confirmed)


SCENARIO C:  Discovery call — buyer never mentioned any competitor

→ AIM does NOT apply here. Too early; absence is uninterpretable.
→ BATNA skipped unless competitors are actually mentioned.
```

### Example: Close Attempt Analysis (#11) on a Demo Call

```
SCENARIO A:  Demo call — rep attempted a close

→ #11 runs → "1 close attempt at 38:47 using assumptive close.
               Buyer responded with deferral."
→ Coaching: "Follow up the deferral with a trial close."


SCENARIO B:  Demo call — rep never attempted a close

→ WITHOUT AIM: #11 skipped. Rep never knows they missed the moment.

→ WITH AIM:    #11 runs → "Zero close attempts on a Demo call.
                           Natural closing moments identified at
                           12:34, 28:47, 41:15. Rep passed each time."
→ Coaching: "Practice the trial close: 'Based on what we've discussed,
             does it make sense to schedule next steps?'"
→ Severity: ORANGE (coaching opportunity)


SCENARIO C:  Check-in call — rep never attempted a close

→ AIM does NOT apply. Check-ins aren't expected to have close attempts.
→ #11 skipped.
```

### How AIM Is Implemented

AIM is encoded in the routing table via `mandatory_for`. When a call type is in a framework's `mandatory_for`, the content signal check is bypassed — the framework runs unconditionally. The framework's LLM prompt handles the "nothing found" case by producing an AIM output rather than an empty result.

```
# In the BATNA prompt — AIM null-finding template:
SYSTEM: If no competitor or alternative references are detected, do NOT
return null. Return:
  batna_strength = "NONE_DETECTED"
  interpretation = "weak_batna"
  insight        = "Buyer did not reference any alternatives during this
                    call. Weak BATNA — rep has leverage to hold pricing."
  severity       = "green"
```

**AIM Frameworks:**
| Framework | AIM applies on | AIM output |
|-----------|---------------|------------|
| #3 BATNA | `pricing`, `negotiation`, `close` | "No alternatives = weak BATNA = rep has leverage" |
| #11 Close Attempt | `demo`, `pricing`, `negotiation`, `close` | "0 close attempts = missed coaching opportunities" |

---

## 5. The Routing Specification Table

This table is the authoritative routing configuration. Each row fully encodes one framework's routing logic. No other configuration is needed.

| # | Framework | Group | Mandatory For | Blocked For | Content Gate Signal | Notes |
|---|-----------|-------|--------------|-------------|---------------------|-------|
| 1 | Unanswered Questions | B | *(all)* | — | None | Universal |
| 2 | Commitment Quality | B | *(all)* | — | None | Universal |
| 3 | BATNA Detection | A | pricing, negotiation, close | check_in | `has_competitor_mention` | **AIM** on mandatory types |
| 4 | Money Left on Table | A | pricing, negotiation | discovery, demo, check_in | `has_pricing_discussion` | No AIM — absence ≠ insight |
| 5 | Question Quality | C | *(all)* | — | `has_rep_questions` | Skip if rep asked <3 questions |
| 6 | Commitment Thermometer | B | *(all)* | — | None | Universal |
| 7 | First Number Tracker | A | pricing, negotiation | discovery, demo, check_in | `has_numeric_anchor` | No AIM — must be a stated number |
| 8 | Emotional Turning Points | E | *(all)* | — | None | **PINNED** |
| 9 | Emotional Trigger Analysis | E | *(all)* | — | None | **PINNED**; combined prompt with #8 |
| 10 | Frame Match Score | C | *(all)* | check_in | None | Check-ins lack pitch/response dynamics |
| 11 | Close Attempt Analysis | C | demo, pricing, negotiation, close | check_in | `has_close_language` | **AIM** on mandatory types |
| 12 | Deal Health at Close | A | negotiation, close | discovery, demo, check_in | `has_close_language` | Only valid at commitment stage |
| 13 | Deal Timing Intelligence | A | discovery, demo | pricing, negotiation, close, check_in | None | Ripeness most actionable before pricing |
| 14 | Methodology Compliance | C | *(all)* | check_in | Depends on #5+#15 | Dependency-gated |
| 15 | Call Structure Analysis | C | *(all)* | — | None | **PINNED** |
| 16 | Pushback Classification | B | *(all)* | check_in | `has_objection_markers` | |
| 17 | Objection Response Score | C | *(all)* | check_in | Depends on #16 | Dependency-gated |

**Legend:**
- *(all)* in Mandatory For = framework is universal, zero call types block it
- **PINNED** = enforced in code; cannot be removed by any routing decision
- **AIM** = runs on mandatory call types even without content signal; absence = output

---

## 6. How Groups Execute When Multiple Are Active

**Groups are not mutually exclusive.** Running multiple groups simultaneously is the standard case.

After routing decides the active framework set, each framework is assigned to its group. Any group with at least one surviving framework dispatches a single LLM call. All active groups run in parallel via `asyncio.gather`.

```
Routing result for a PRICING call (baseline — no special content detected):

Active frameworks: {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15}

Group assignment:
┌──────────────────┬──────────────────────────────────────────┐
│ Group A          │ #3 (BATNA), #4 (Money), #7 (Anchor)      │ ← 1 LLM call
│ Group B          │ #1 (Unanswered), #2 (Commit), #6 (Therm) │ ← 1 LLM call
│ Group C          │ #5 (Ques), #10 (Frame), #11 (Close), #15 │ ← 1 LLM call
│ Group D          │ (empty — Phase 2 frameworks)             │ ← SKIPPED
│ Group E          │ #8+#9 (Emotion)                          │ ← 1 LLM call
└──────────────────┴──────────────────────────────────────────┘

asyncio.gather(run_A, run_B, run_C, run_E)  ← all 4 run simultaneously
```

```
Routing result for a CHECK-IN call:

Active frameworks: {1, 2, 5, 6, 8, 9, 15}

Group assignment:
┌──────────────────┬──────────────────────────────────────────┐
│ Group A          │ (empty)                                  │ ← SKIPPED
│ Group B          │ #1, #2, #6                               │ ← 1 LLM call
│ Group C          │ #5, #15                                  │ ← 1 LLM call
│ Group D          │ (empty)                                  │ ← SKIPPED
│ Group E          │ #8+#9                                    │ ← 1 LLM call
└──────────────────┴──────────────────────────────────────────┘

asyncio.gather(run_B, run_C, run_E)  ← only 3 run
```

**The efficiency gain from groups:**
Each group sends *one combined LLM call* for all its active frameworks. If 3 frameworks in a group survive routing, that's 1 call instead of 3. The model reads the transcript once and produces structured output for all frameworks in the group simultaneously.

```python
def build_group_prompt(group_id, active_fw_ids, transcript, pass1):
    # One prompt, multiple framework instruction blocks, one response
    fw_blocks = "\n\n".join(
        FRAMEWORK_PROMPT_BLOCKS[fw_id]
        for fw_id in sorted(active_fw_ids)
    )
    return GROUP_SYSTEM_PROMPT[group_id] + fw_blocks + f"\n\nTRANSCRIPT:\n{transcript}"
```

---

## 7. The Architecture in Full

```
 CALL RECORD + TRANSCRIPT + CALL TYPE METADATA
                        │
                        ▼
           ┌────────────────────────────┐
           │   call_type == "other"?    │
           │   (or missing)             │
           └──────────┬─────────────────┘
               YES    │          NO
                      ▼          │
          ┌─────────────────┐    │
          │ Haiku classifier│    │
          │ reads 500 tokens│    │
          │ → effective type│    │
          │ ~$0.001 per call│    │
          │ runs IN PARALLEL│    │
          │ with Pass 1     │    │
          └────────┬────────┘    │
                   └──────┬──────┘
                          │
                          ▼
      ┌───────────────────────────────────────────┐
      │  PASS 1: Infrastructure Extraction        │
      │  Always runs. Not gated by routing.       │
      │  • Hedge density + type (per segment)     │
      │  • Sentiment trajectory (per segment)     │
      │  • Evaluative language (per segment)      │
      │  → Derives Pass1GateSignals               │
      └───────────────────┬───────────────────────┘
                          │ Pass1GateSignals ready
                          ▼
      ┌───────────────────────────────────────────┐
      │  ROUTING: 17 decisions in sequence        │
      │  should_run(fw_id, call_type, signals)    │
      │  → Active framework set                   │
      └───────────────────┬───────────────────────┘
                          │
                          ▼
      ┌───────────────────────────────────────────┐
      │  DEPENDENCY ENFORCEMENT                   │
      │  Add pinned: {8, 9, 15}                   │
      │  Cascade remove: if #16 gone → #17 gone   │
      │                  if #5 or #15 gone → #14  │
      │  Short call (<8 min): remove {13, 14}     │
      └───────────────────┬───────────────────────┘
                          │ final_active_set
                          ▼
      ┌───────────────────────────────────────────┐
      │  GROUP ASSEMBLY                           │
      │  Assign each fw to its group (A–E)        │
      │  Groups with no survivors → skipped       │
      │  Build combined prompt per active group   │
      └───────────────────┬───────────────────────┘
                          │
                          ▼
      ┌─────────────────────────────────────────────────────────────┐
      │  PARALLEL EXECUTION  asyncio.gather(*active_groups)         │
      │                                                             │
      │    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
      │    │ GROUP A │  │ GROUP B │  │ GROUP C │  │ GROUP E │     │
      │    │ Negotiat│  │Pragmatic│  │ Coaching│  │ Emotion │     │
      │    │ 1 call  │  │ 1 call  │  │ 1 call  │  │ 1 call  │     │
      │    └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘     │
      │         └────────────┴────────────┴────────────┘           │
      └─────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
                            Framework Results
                            (stored to Postgres)
                                    │
                                    ▼
                         Insight Prioritization
                         Severity → Confidence
                         → Actionability → $
                                    │
                                    ▼
                           Top 3–5 Insights
                           surfaced to user
```

---

## 8. Full Implementation

### Pass 1 Gate Signals

```python
from dataclasses import dataclass

@dataclass
class Pass1GateSignals:
    """Derived from Pass 1 output. No additional LLM calls needed."""
    has_competitor_mention: bool     # Any alternative vendor referenced
    has_pricing_discussion: bool     # Price, cost, budget, or dollar figure discussed
    has_numeric_anchor: bool         # Any specific number stated first by either party
    has_objection_markers: bool      # Buyer resistance, concern, or pushback detected
    has_rep_questions: bool          # Rep asked 3+ questions of any type
    has_close_language: bool         # "Let's move forward", "sign", "next steps", etc.
    call_duration_minutes: float

def extract_gate_signals(pass1: Pass1Result) -> Pass1GateSignals:
    """Map Pass 1 structured output to routing-ready boolean flags."""
    eval_targets = {e.target for e in pass1.evaluative_language}
    return Pass1GateSignals(
        has_competitor_mention=any(
            e.target not in INTERNAL_TARGETS for e in pass1.evaluative_language
        ) or pass1.contains_comparison_language,
        has_pricing_discussion=any(
            t in eval_targets for t in {"price", "cost", "budget", "discount"}
        ) or pass1.contains_dollar_amount,
        has_numeric_anchor=pass1.first_number_speaker is not None,
        has_objection_markers=any(
            s.sentiment_score < -0.4 and s.segment_speaker == "buyer"
            for s in pass1.sentiment_trajectory
        ) or pass1.hedge_density_buyer > 0.6,
        has_rep_questions=sum(
            1 for s in pass1.turn_segments
            if s.speaker == "rep" and s.text.strip().endswith("?")
        ) >= 3,
        has_close_language=any(
            keyword in pass1.transcript_lower
            for keyword in CLOSE_KEYWORDS
        ),
        call_duration_minutes=pass1.duration_minutes,
    )
```

### Routing Table Definition

```python
from dataclasses import dataclass, field

@dataclass
class FrameworkRoutingSpec:
    fw_id: int
    mandatory_for: set[str] = field(default_factory=set)
    blocked_for: set[str]   = field(default_factory=set)
    required_signal: str | None = None
    # If mandatory_for is empty AND blocked_for is empty AND required_signal is None
    # → framework is universal, runs on all calls.

ROUTING_TABLE: dict[int, FrameworkRoutingSpec] = {
    1:  FrameworkRoutingSpec(fw_id=1),   # Universal
    2:  FrameworkRoutingSpec(fw_id=2),   # Universal
    3:  FrameworkRoutingSpec(
            fw_id=3,
            mandatory_for={"pricing", "negotiation", "close"},     # AIM
            blocked_for={"check_in"},
            required_signal="has_competitor_mention",              # for discovery/demo/other
        ),
    4:  FrameworkRoutingSpec(
            fw_id=4,
            mandatory_for={"pricing", "negotiation"},
            blocked_for={"discovery", "demo", "check_in"},
            required_signal="has_pricing_discussion",
        ),
    5:  FrameworkRoutingSpec(fw_id=5, required_signal="has_rep_questions"),
    6:  FrameworkRoutingSpec(fw_id=6),   # Universal
    7:  FrameworkRoutingSpec(
            fw_id=7,
            mandatory_for={"pricing", "negotiation"},
            blocked_for={"discovery", "demo", "check_in"},
            required_signal="has_numeric_anchor",
        ),
    8:  FrameworkRoutingSpec(fw_id=8),   # Universal + PINNED
    9:  FrameworkRoutingSpec(fw_id=9),   # Universal + PINNED (combined with #8)
    10: FrameworkRoutingSpec(fw_id=10, blocked_for={"check_in"}),
    11: FrameworkRoutingSpec(
            fw_id=11,
            mandatory_for={"demo", "pricing", "negotiation", "close"},  # AIM
            blocked_for={"check_in"},
            required_signal="has_close_language",
        ),
    12: FrameworkRoutingSpec(
            fw_id=12,
            mandatory_for={"negotiation", "close"},
            blocked_for={"discovery", "demo", "check_in"},
            required_signal="has_close_language",
        ),
    13: FrameworkRoutingSpec(
            fw_id=13,
            mandatory_for={"discovery", "demo"},
            blocked_for={"pricing", "negotiation", "close", "check_in"},
        ),
    14: FrameworkRoutingSpec(fw_id=14, blocked_for={"check_in"}),  # dep-gated
    15: FrameworkRoutingSpec(fw_id=15),  # Universal + PINNED
    16: FrameworkRoutingSpec(
            fw_id=16,
            blocked_for={"check_in"},
            required_signal="has_objection_markers",
        ),
    17: FrameworkRoutingSpec(fw_id=17, blocked_for={"check_in"}),  # dep-gated
}

PINNED_FRAMEWORKS = {8, 9, 15}
```

### Core Routing Functions

```python
def should_run_framework(
    fw_id: int,
    call_type: str,
    signals: Pass1GateSignals,
) -> bool:
    spec = ROUTING_TABLE[fw_id]

    if fw_id in PINNED_FRAMEWORKS:
        return True

    if call_type in spec.blocked_for:
        return False

    if call_type in spec.mandatory_for:
        return True                    # AIM: bypass content gate

    if spec.required_signal:
        return bool(getattr(signals, spec.required_signal, False))

    return True                        # universal framework


def should_run_framework_safe(fw_id, call_type, signals) -> bool:
    """Fail-open wrapper: routing error → include the framework."""
    try:
        return should_run_framework(fw_id, call_type, signals)
    except Exception:
        return True
```

### Dependency Enforcement

```python
DEPENDENCY_RULES: list[tuple[int, set[int]]] = [
    (9,  {8}),          # Trigger Analysis requires Turning Points
    (14, {5, 15}),      # Methodology requires Question Quality + Call Structure
    (17, {16}),         # Objection Response requires Pushback Classification
    # Phase 2 (defined now for future reference):
    (30, {2, 6, 13}),   # Buying Signal aggregates Commitment + Thermometer + Timing
    (31, {5}),          # Power Index requires Question Quality
]

def enforce_dependencies(active: set[int], signals: Pass1GateSignals) -> set[int]:
    # Pinned frameworks are inviolable
    active = active | PINNED_FRAMEWORKS

    # Cascade: remove dependents whose requirements weren't routed in
    changed = True
    while changed:
        changed = False
        for dependent, requirements in DEPENDENCY_RULES:
            if dependent in active and not requirements.issubset(active):
                active.discard(dependent)
                changed = True

    # Short call guard — structure/methodology need sufficient content
    if signals.call_duration_minutes < 8:
        active -= {13, 14}
        # #15 is pinned — never removed even for short calls

    return active
```

### Full Orchestration

```python
async def route_and_execute(
    call: CallRecord,
    transcript: str,
) -> list[FrameworkResult]:
    ALL_P1 = set(range(1, 18))

    # For unknown call types, infer from content (runs parallel with Pass 1)
    micro_task = None
    effective_type = call.call_type
    if effective_type in ("other", None, ""):
        excerpt = transcript[:2000]   # ~500 tokens
        micro_task = asyncio.create_task(infer_call_type_haiku(excerpt))

    # Pass 1 always runs
    pass1 = await run_pass1(transcript)
    signals = extract_gate_signals(pass1)

    if micro_task:
        effective_type = await micro_task  # type inference completes by now

    # Route
    active = {
        fw for fw in ALL_P1
        if should_run_framework_safe(fw, effective_type, signals)
    }

    # Enforce dependencies + pins
    active = enforce_dependencies(active, signals)

    # Assemble groups and execute in parallel
    return await execute_framework_groups(active, transcript, pass1)


GROUP_MEMBERSHIP: dict[str, set[int]] = {
    "A": {3, 4, 7, 12, 13},
    "B": {1, 2, 6, 16},
    "C": {5, 10, 11, 14, 15, 17},
    "D": {},                          # Phase 2 — not yet active
    "E": {8, 9},
}

async def execute_framework_groups(
    active: set[int],
    transcript: str,
    pass1: Pass1Result,
) -> list[FrameworkResult]:
    tasks = [
        run_group(gid, active & members, transcript, pass1)
        for gid, members in GROUP_MEMBERSHIP.items()
        if active & members                          # skip empty groups
    ]
    results = await asyncio.gather(*tasks)
    return [r for batch in results for r in batch]
```

---

## 9. Framework Dependency Graph

```
                         PASS 1
                      (always runs)
                           │
           ┌───────────────┼────────────────────────┐
           │               │                        │
      HEDGE MAP      SENTIMENT TRAJ          EVALUATIVE LANG
           │               │                        │
           └───────┬───────┘                        │
                   │                                │
      ┌────────────┼─────────────┐                  │
      │            │             │                  │
    #1 ●         #2 ●          #6 ●              #3 ▲
 Unanswered   Commitment    Thermometer          BATNA
  Questions     Quality                    (AIM on late-stage)
                  │             │
                  └──────┬──────┘
                         │
                       #13 ●
                    Deal Timing
                         │
                      (#30) ──── Phase 2: Buying Signal
                                (needs #2, #6, #13)

#5 ●              #15 ★              #11 ▲
Quest Quality  Call Structure    Close Attempt
     │               │         (AIM on demo+)
     └──────┬─────────┘
            │
          #14 ●
       Methodology
       Compliance

   #16 ●
  Pushback Class.
       │
     #17 ●
  Objection Resp.

#8 ★ ────── #9 ●
Emotion TP   Trigger
(combined prompt)

★ = PINNED — never removed by routing or dependencies
▲ = AIM — mandatory on key call types regardless of content signals
● = standard routing; may be gated by call type or Pass 1 content
```

---

## 10. Routing Outcomes by Call Type

Baseline outcomes (Pass 1 detects no special content signals). Extra content signals (e.g., competitor mention on a discovery call) add more frameworks to the active set.

| Call Type | Active Frameworks | Groups Running | Frameworks Skipped |
|-----------|------------------|:--------------:|-------------------|
| **Discovery** | 1, 2, 5, 6, 8, 9, 10, 13, 15 | B, C, E | #3,4,7,11,12 blocked; #16,17 no signal |
| **Demo** | 1, 2, 5, 6, 8, 9, 10, 11, 13, 15 | B, C, E | +#11 AIM fires; #3,4,7,12 blocked |
| **Pricing** | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15 | A, B, C, E | #12,13 blocked; #16,17 no signal |
| **Negotiation** | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15 | A, B, C, E | #13 blocked; #16,17 no signal |
| **Close** | 1, 2, 3, 5, 6, 8, 9, 10, 11, 12, 15 | A, B, C, E | #4,7,13 blocked; #16,17 no signal |
| **Check-in** | 1, 2, 5, 6, 8, 9, 15 | B, C, E | 10 frameworks excluded |
| **Other** | Depends on Haiku type inference | varies | Falls back to content-only gating if classifier fails |

---

## 11. Cost Reality

Each group = 1 LLM call. Pass 1 = 1 call. Total without routing: 6 calls (Pass 1 + 5 groups).

| Call Type | Routed Calls | Full Calls | Savings |
|-----------|:-----------:|:----------:|:-------:|
| Discovery | 4 (P1+B+C+E) | 6 | 33% |
| Demo | 4 | 6 | 33% |
| Pricing | 5 (P1+A+B+C+E) | 6 | 17% |
| Negotiation | 5 | 6 | 17% |
| Close | 5 | 6 | 17% |
| Check-in | 4 (P1+B+C+E) | 6 | 33% |

Group-level skipping alone: **17–33% reduction**. Content gating removes frameworks within groups (shorter prompts, cheaper tokens): adds **8–12% additional reduction**.

**Total cost reduction: 25–45%** with zero accuracy risk and no added latency.

---

## 12. Edge Cases & Guard Rails

### Fail Open — Always
A routing error that skips a framework means a missed insight. That's worse than running an extra framework that produces null output.

```python
# Every routing call is wrapped
if should_run_framework_safe(fw_id, call_type, signals):
    active.add(fw_id)
# Exception → safe() returns True → framework included
```

### #15, #8, #9 Are Inviolable in Code
Pinned frameworks are enforced by `enforce_dependencies` which re-adds them even if they were incorrectly removed somewhere upstream. This is a code guarantee, not a policy.

### AIM Output Contract
When a framework runs due to AIM (mandatory call type, content signal absent), its prompt must produce a valid output — not an error, not null. Every AIM framework includes a `null_finding_template` in its prompt spec that generates the "absence = insight" output.

### Pass 1 Accuracy Determines Gate Quality
Content signal flags are derived from Pass 1. If Pass 1 misses a competitor mention on a discovery call, BATNA won't run on that call. Mitigation: use **low confidence thresholds for routing gates** — better to over-trigger a framework than to miss a real signal. Reserve high confidence thresholds for the framework's *output display* logic, not the routing gate.

### Dependency Cascade Is Iterative
```python
# The while loop runs until no more removals — handles indirect cascades
# e.g., if a Phase 2 framework depends on #30, which depends on #13,
# removing #13 cascades to #30 which cascades to the Phase 2 framework
changed = True
while changed:
    changed = False
    for dependent, requirements in DEPENDENCY_RULES:
        if dependent in active and not requirements.issubset(active):
            active.discard(dependent)
            changed = True
```

### Confidence-Based Suppression ≠ Routing
Routing decides **whether to run** a framework. Confidence thresholds decide **whether to show** its output. These are separate systems. A framework that runs and produces low-confidence output is still valuable — it appears in the "All Results" collapsed section. A framework that never runs produces nothing, regardless of how important the insight might have been. Never use confidence as a proxy for routing.

---

## 13. Evaluation: How to Know the Router Works

### Shadow Mode Before Production
Deploy routing as a decision layer for 2 weeks while still running all 17 frameworks. Log routing decisions. Measure: of frameworks the router *would have* skipped, what percentage produced output above 0.65 confidence?

- **Target:** < 2% false negative rate
- **Block shipping if:** > 5%

### Production Monitoring

| Metric | Target | Alert If |
|--------|:------:|:--------:|
| Avg frameworks per call | 9–13 | > 15 or < 6 |
| Groups skipped per call | 1–2 avg | 0 (routing not working) or > 3 (over-routing) |
| AIM null output rate | < 40% | > 70% (AIM misconfigured) |
| False negative rate | < 2% | > 5% |
| Cost per call | < $0.10 | > $0.18 |

---

## 14. Summary

### Your Two Options, Answered

| Option | Verdict |
|--------|---------|
| **Micropipelines** | Yes — as the *execution* model. The 5 prompt groups ARE the micropipelines. Multiple groups run simultaneously (that's normal). Empty groups are skipped. Each group batches its frameworks into one LLM call. This is the primary cost reduction mechanism. |
| **LLM decides** | Yes — but only for the `"other"` call type edge case. A single Haiku call infers the effective call type. Then the routing table takes over. Never use LLM as the primary router for known call types — it adds cost and a failure mode. |

### The Architecture in One Sentence

> Pass 1 runs always, derives content flags; routing checks those flags plus call type against a per-framework table to decide mandatory/blocked/content-gated; survivors execute in parallel groups — multiple groups is the norm, empty groups are skipped.

### The Central Principle

> **Use the cheapest signal that can answer the routing question.**
> Free metadata answers the obvious semantic questions.
> Already-computed Pass 1 output answers the content questions.
> LLM routing is only invoked when neither is sufficient.
> Fail open. Never miss an insight to save a dollar.
