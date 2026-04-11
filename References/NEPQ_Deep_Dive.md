# NEPQ Deep Dive: How the Score Works + Is This the Best Architecture?

---

## The 3 Sub-Scores Explained

The NEPQ score is calculated from three dimensions, each measuring a different aspect of the rep's questioning technique. Let me walk through all three using the **same example transcript** so you can see how they connect.

### Example Transcript (Negotiation Call)

```
[00:00] Sarah (rep): Thanks for hopping on, Mike. What prompted you to 
       look at new solutions right now?
[00:15] Mike (buyer): We've been struggling with our current CRM. It's slow.
[00:25] Sarah (rep): How long have you been using it?
[00:35] Mike (buyer): About 3 years now.
[00:42] Sarah (rep): Got it. So our platform does real-time analytics and 
       costs $42,000 annually.
[01:00] Mike (buyer): That's higher than we expected.
[01:10] Sarah (rep): I can do $38,000 with annual billing.
[01:20] Mike (buyer): Let me think about it.
```

---

### Sub-Score 1: Sequence Adherence (40% of total)

**What it measures:** Did the rep follow the 8-phase NEPQ sequence in order?

**The 8 phases and what happened in our example:**

| Phase | Present? | Evidence |
|-------|:--------:|----------|
| 1. Connecting | YES | "What prompted you to look at new solutions right now?" — focuses on buyer's world |
| 2. Situation | YES | "How long have you been using it?" — maps current state |
| 3. Problem Awareness | NO | Rep never asked "What don't you like about it?" or "Why is it slow?" |
| 4. Solution Awareness | NO | Rep never asked "What have you tried to fix this?" |
| 5. Consequence | NO | Rep never asked "What happens if nothing changes?" |
| 6. Qualifying | NO | Rep never asked "How important is fixing this to you?" |
| 7. Transition | NO | Rep jumped straight to pricing instead of saying "Based on what you told me about the slowness..." |
| 8. Committing | NO | No self-persuasion close. Rep used discount (hard close). |

**Score calculation:**
```
Phases detected: 2 out of 8
Sequence violations: 1 (jumped from Situation directly to pitch — skipped 5 phases)
sequence_score = (2/8) - (0.1 × 1) = 0.25 - 0.10 = 0.15
```

**What this means:** The rep opened well (Connecting + Situation) but then abandoned the NEPQ framework entirely and jumped to pitching the product. The buyer never articulated their pain, never envisioned a solution, and never felt the cost of inaction. Result: "Let me think about it."

**What SHOULD have happened after [00:35]:**
```
[00:42] Sarah: "What don't you like about your current CRM?"          ← Phase 3
[00:55] Mike: "The reporting is terrible. Takes 3 days."
[01:05] Sarah: "3 days — how does that affect your team?"              ← Phase 3 deeper
[01:15] Mike: "We're always behind on forecasting."
[01:25] Sarah: "What have you tried to fix this?"                      ← Phase 4
[01:35] Mike: "We looked at add-ons but nothing worked."
[01:45] Sarah: "What happens if nothing changes for another year?"     ← Phase 5
[01:58] Mike: "We'll probably lose our best people."
[02:10] Sarah: "How important is solving this to you right now?"       ← Phase 6
[02:20] Mike: "Very. Our board is reviewing ops next quarter."
[02:30] Sarah: "Based on what you said about losing people and         ← Phase 7
       the 3-day delays, what we do is..."
[02:50] Sarah: "Do you feel like this could solve that? Why?"          ← Phase 8
[03:00] Mike: "Yes, because we can't keep losing people over tools."   ← SELF-GENERATED
```

---

### Sub-Score 2: Diagnostic Depth (35% of total)

**What it measures:** When the buyer gave a vague answer, did the rep probe deeper or accept it and move on?

**The 4 depth levels:**

```
SURFACE     → Buyer says something general. Rep moves on.           (BAD)
SPECIFIC    → Rep asks "What do you mean?" Buyer gives details.     (OKAY)
EMOTIONAL   → Rep asks "How does that affect you?" Buyer expresses feeling. (GOOD)
QUANTIFIED  → Rep asks "What's that costing you?" Buyer gives numbers.  (BEST)
```

**What happened in our example:**

| Moment | Buyer Said | Rep Did | Depth Level |
|--------|-----------|---------|:-----------:|
| [00:15] | "We've been struggling with our current CRM. It's slow." | Asked a factual follow-up ("How long?") but NOT a depth probe ("What do you mean by slow?") | SURFACE — accepted |
| [01:00] | "That's higher than we expected." | Immediately offered discount instead of asking "What were you expecting?" or "What's your budget?" | SURFACE — accepted |

**Score calculation:**
```
Probing moments found: 2
Times rep probed deeper: 0
Times rep accepted surface answer: 2
Deepest level reached: surface

depth_score = 0 / (0 + 2) = 0.00
```

**What this means:** The buyer said "It's slow" — a classic vague answer. NEPQ says the rep should have asked "When you say slow, what do you mean exactly?" which would have gotten specifics ("Reporting takes 3 days"), then "How does that affect your team?" (emotional), then "What's that costing you?" (quantified). The rep never probed once.

**The depth escalation that should have happened:**

```
Level 1 (SURFACE):  Mike: "It's slow."
                    Sarah: "Got it." → MOVED ON ← this is what happened

Level 2 (SPECIFIC): Sarah: "When you say slow, what do you mean exactly?"
                    Mike: "Reporting takes 3 days to compile."

Level 3 (EMOTIONAL): Sarah: "How does that 3-day delay affect your team?"
                     Mike: "It's frustrating. My team is demoralized. They feel 
                            like they're working with one hand tied behind their back."

Level 4 (QUANTIFIED): Sarah: "How much do you think that's costing you annually?"
                      Mike: "When you factor in overtime and missed deadlines... 
                             probably $200K a year."
```

At Level 4, the buyer has QUANTIFIED their pain ($200K/year). Now when Sarah says "our solution is $42,000" — the buyer instantly sees $42K vs $200K saved. The price sells itself.

---

### Sub-Score 3: Commitment Origin (25% of total)

**What it measures:** When the buyer committed (or didn't), was it their OWN idea or did the rep push it?

**The two types:**

```
SELF-GENERATED (strong, persists after the call):
  Buyer: "I think this is exactly what we need because we keep 
          losing deals to slow reporting." 
  → Buyer articulated THEIR OWN reason
  → Internal motivation — they'll follow through

REP-PUSHED (weak, fades after the call):
  Rep: "I can do $38,000 if you sign this week."
  Buyer: "Let me think about it."
  → Rep used urgency/discount
  → External pressure — buyer will ghost
```

**What happened in our example:**

| Moment | What Happened | Type |
|--------|--------------|:----:|
| [01:20] | Buyer: "Let me think about it" after rep offered discount | NOT EVEN A COMMITMENT — this is a stall |

**Score calculation:**
```
Total commitments: 0 (buyer stalled, never committed)
Self-generated: 0
Rep-pushed: 0
commitment_origin_score = 0.5 (default when no commitments found — neutral)
```

**What this means:** The buyer didn't commit at all. "Let me think about it" is not a commitment — it's a polite rejection. This happened BECAUSE the rep skipped Phases 3-6 (the buyer never felt their own pain), so when asked to pay $42K, the buyer had no internal reason to say yes.

**Contrast with a self-generated commitment:**

```
[02:50] Sarah: "Do you feel like this could solve the reporting problem 
        you mentioned? Why do you think so?"
[03:00] Mike: "Yes, actually. Because if we keep doing 3-day reports, 
        we'll lose Sarah and Tom — they're already looking. And the $200K 
        in overtime alone makes $42K look like nothing."
```

Mike just convinced HIMSELF. He cited his own pain ($200K overtime), his own risk (losing Sarah and Tom), and his own logic ($42K < $200K). This commitment persists because it's HIS reasoning, not Sarah's pitch.

---

### Overall NEPQ Score

```
nepq_score = (sequence_score × 0.40) + (depth_score × 0.35) + (commitment_origin_score × 0.25)
           = (0.15 × 0.40) + (0.00 × 0.35) + (0.50 × 0.25)
           = 0.06 + 0.00 + 0.125
           = 0.185 → 19%

Severity: RED (below 0.30)
```

**The coaching output would trace the causal chain:**

> "This call scored 19% on NEPQ methodology. The root cause: after learning the buyer's CRM is 'slow' at [00:15], you jumped to pricing at [00:42] without asking Problem Awareness questions. The buyer never articulated their specific pain, never felt the cost of inaction, and had no internal reason to commit — which is why they said 'let me think about it.'
>
> **The fix:** After [00:35] ('About 3 years now'), ask: 'What don't you like about it specifically?' Then when they answer, probe deeper: 'How does that affect your team day to day?' Then: 'What happens if nothing changes for another year?' These three questions would have taken 90 seconds and transformed the call from a price negotiation into a consultative partnership."

---

## Honest Architectural Assessment: Is This the Best?

### What's Good About the Current Architecture

1. **The causal chain model is correct.** Sequence → Depth → Commitment is genuinely how NEPQ works. Analyzing all three in one LLM pass lets the model trace causation.

2. **One LLM call is efficient.** The model reads the transcript once and evaluates three dimensions. No redundant scanning.

3. **The prompt is well-structured.** Few-shot examples, severity guide, coaching template — the LLM has clear instructions.

4. **Routing is correct.** Mandatory on discovery/demo (where NEPQ matters most), blocked on check-in, content-gated elsewhere.

### What Could Be Better: Cross-Framework Intelligence

Here's the honest truth: **the current NEPQ framework operates in isolation.** It runs in parallel with Groups A-E and does NOT see their outputs. This means:

#### Redundancy That Exists Today

| NEPQ Detects | Other Framework Also Detects | Redundant? |
|---|---|---|
| "Buyer gave vague answer" | FW-01 (Unanswered Questions) classifies as "vague" | YES — both scan for the same event |
| "Rep asked a diagnostic question" | FW-05 (Question Quality) classifies as "open/diagnostic" | YES — both classify question types |
| "Buyer committed" | FW-02 (Commitment Quality) evaluates strength | YES — both find commitment moments |
| "Emotion shifted" | FW-08 (Emotional Turning Points) detects shift | PARTIAL — NEPQ checks if Phase 5 caused it |

#### Would Cross-Framework Data Make NEPQ Better?

**Theoretically: Yes, marginally.** If NEPQ could see FW-01's evasion list, it wouldn't need to re-scan for vague answers. If it could see FW-05's question classifications, it could map them to NEPQ phases more accurately. If it could see FW-08's emotional shift data, it could validate whether Phase 5 consequence questions actually triggered an emotional response.

**Practically: No, not worth the complexity.** Here's why:

1. **The LLM is reading the same transcript.** Whether it detects "buyer gave vague answer at [00:15]" independently or receives it from FW-01, it arrives at the same finding. The transcript is the source of truth, not another framework's interpretation.

2. **Cross-framework dependency creates fragility.** If Group F depends on Group B's output, then Group F can't run until Group B finishes. Currently all groups run in parallel (~5 seconds total). Adding a dependency chain makes it sequential (~8-10 seconds). Worse: if Group B fails, Group F also fails.

3. **The marginal accuracy gain is tiny.** NEPQ's strength is the CAUSAL CHAIN analysis — connecting sequence to depth to commitment. No other framework provides this. The individual detections (vague answers, question types) are simple enough that the LLM gets them right independently.

4. **The real bottleneck is coaching quality, not detection accuracy.** Whether the system detects 95% or 98% of vague-answer moments doesn't matter. What matters is the coaching recommendation — "at this exact moment, say THIS instead." The current prompt already handles this well.

### What WOULD Genuinely Improve NEPQ

Instead of cross-framework wiring (high complexity, low payoff), these changes would have higher impact:

#### 1. Call-Type-Specific Phase Weighting

Currently all 8 phases are weighted equally. But NEPQ applies differently per call type:

| Call Type | Emphasize | De-Emphasize |
|-----------|-----------|-------------|
| Discovery | Phases 1-6 (full exploration) | Phases 7-8 (too early to close) |
| Demo | Phases 1, 7-8 (they know the problem, focus on transition+commit) | Phases 2-6 (already covered in discovery) |
| Pricing | Phases 5-6 (consequence of staying small, qualifying urgency) | Phases 1-4 (already known) |
| Close | Phase 8 (self-persuasion close) | Phases 1-5 (already explored) |

**Improvement:** Add `call_type` to the NEPQ prompt and weight phases accordingly. A discovery call that nails Phases 1-6 but skips 7-8 should score GREEN (it's a discovery — you're not supposed to close). Currently it would score YELLOW (2 phases missing).

#### 2. Rep-Specific Coaching Patterns

Currently coaching is generic to the call. But if a rep consistently skips Phase 5 (Consequence) across multiple calls, the coaching should escalate:

- Call 1: "You skipped consequence questions. Try asking 'What happens if nothing changes?'"
- Call 5: "You've skipped consequence questions on 4 of your last 5 calls. This is your #1 coaching priority. Practice this question until it's automatic."

**This requires Phase 2 cross-call analysis** (not available yet).

#### 3. Consequence Effectiveness Validation

The current NEPQ prompt checks IF Phase 5 was present. But it doesn't validate if the consequence question WORKED — did the buyer's language actually shift after the question? Did they move from analytical to emotional?

**Improvement:** Add a validation step in the prompt: "After identifying Phase 5, check the buyer's NEXT response. Did their language shift from factual ('We use System X') to emotional ('We're frustrated/worried/concerned')? If the buyer's response to the consequence question was still analytical, the consequence question was ineffective — flag this and suggest a more pointed alternative."

### Final Recommendation

**Keep the current architecture.** The unified single-framework approach in Group F is the right call. The 3-sub-score model with the causal chain is correct. Cross-framework data would add complexity without meaningful accuracy improvement.

**Two improvements worth making (future):**
1. Call-type-specific phase weighting in the prompt (small change, high impact)
2. Consequence effectiveness validation (medium change, medium impact)

**One improvement for Phase 2:**
3. Cross-call rep coaching patterns (requires multi-call infrastructure)

None of these require architectural changes. #1 and #2 are prompt-level improvements. #3 is a Phase 2 feature.
