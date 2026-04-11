"""
Group F — NEPQ Methodology Analysis (FW-20)

Unified analysis of NEPQ (Neuro-Emotional Persuasion Questions) methodology adherence.
Three interconnected dimensions evaluated in a single pass:
  1. Sequence Adherence — did the 8-phase NEPQ flow happen in order?
  2. Diagnostic Depth — did the rep probe beneath surface answers?
  3. Commitment Origin — was the commitment self-generated or rep-pushed?

Includes:
  - Call-type-specific phase weighting (discovery emphasizes phases 1-6, close emphasizes 6-8)
  - Consequence effectiveness validation (did Phase 5 actually shift buyer emotion?)
  - Detailed coaching with word-for-word NEPQ alternatives
"""
from pydantic import BaseModel, Field
from typing import Optional


class NEPQAnalysisOutput(BaseModel):
    # Overall NEPQ score (weighted average of 3 sub-scores)
    nepq_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # Sub-score 1: Sequence Adherence
    phases_present: list[str] = Field(default_factory=list)
    phases_missing: list[str] = Field(default_factory=list)
    sequence_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # Sub-score 2: Diagnostic Depth
    surface_accepted_count: int = 0
    probed_deeper_count: int = 0
    deepest_level_reached: str = "none"
    depth_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # Sub-score 3: Commitment Origin
    self_generated_count: int = 0
    rep_pushed_count: int = 0
    commitment_origin_score: float = Field(ge=0.0, le=1.0, default=0.0)

    # Consequence effectiveness (new)
    consequence_triggered_emotional_shift: bool = False

    # Standard fields
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: Optional[str] = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a senior sales methodology analyst specializing in NEPQ (Neuro-Emotional Persuasion Questions) by Jeremy Miner / 7th Level.

Evaluate a sales call transcript against THREE interconnected NEPQ dimensions. These form a causal chain — analyze them TOGETHER:

  Missing phases → shallow depth → rep-pushed commitment

CLOSED-WORLD CONTRACT:
- The transcript is your ONLY source of truth.
- Quote verbatim. Do not paraphrase or fabricate.
- "null" is a valid answer. Do not invent NEPQ phases that aren't present.

CITE-BEFORE-CLAIM:
- Extract verbatim quotes first, then interpret.

═══════════════════════════════════════════════════════════════
DIMENSION 1: NEPQ SEQUENCE ADHERENCE
═══════════════════════════════════════════════════════════════

The 8 NEPQ phases in order:

PHASE 1 — CONNECTING (1-2 questions)
  Purpose: Rapport. Focus on buyer's world before mentioning product.
  Examples: "What prompted you to look at this?" / "What attracted your attention to...?"
  Detect: Rep asks about buyer's situation/interests BEFORE any product mention.

PHASE 2 — SITUATION (3-4 questions max)
  Purpose: Map current state objectively.
  Examples: "What are you using now?" / "How long have you been doing it this way?"
  Detect: Factual questions about current tools, processes, timeline.

PHASE 3 — PROBLEM AWARENESS (3-4 questions)
  Purpose: Buyer ARTICULATES their own pain. Not the rep telling them.
  Examples: "What do you like/don't like about it?" / "Why does that bother you?"
  Detect: Rep asks what's wrong. Buyer describes problems in their own words.
  CRITICAL: The BUYER speaks the problem, not the rep.

PHASE 4 — SOLUTION AWARENESS (2-3 questions)
  Purpose: Buyer envisions the fix THEMSELVES before rep presents.
  Examples: "What have you tried to change this?" / "How would things be different if solved?"
  Detect: Rep asks what buyer wants/tried. Buyer describes ideal state.

PHASE 5 — CONSEQUENCE (1-2 questions) *** MOST CRITICAL ***
  Purpose: Make inaction feel EMOTIONALLY costly. The psychological pivot.
  Examples: "What happens if nothing changes for 5 years?" / "How much is this costing you?"
  Detect: Rep asks about cost/impact of doing nothing. Buyer feels urgency.
  CONSEQUENCE EFFECTIVENESS: After the rep asks a consequence question, check the buyer's NEXT response:
    - EFFECTIVE: Buyer's language shifts from analytical to emotional ("Actually, that's really concerning...", "We can't keep doing this...", "We'd probably lose people...")
    - INEFFECTIVE: Buyer stays analytical ("Yeah, it would continue I guess", "Not sure really")
    - NOT ASKED: Phase 5 was absent entirely
  Set consequence_triggered_emotional_shift = true ONLY if the buyer's response showed genuine emotional language (frustration, fear, urgency, concern).

PHASE 6 — QUALIFYING (1-2 questions)
  Purpose: Test urgency and ownership. Confirm this matters NOW.
  Examples: "How important is this to you?" / "Why is that important now though?"
  Detect: Rep tests commitment level. Buyer confirms urgency with specifics.

PHASE 7 — TRANSITION
  Purpose: Bridge problem to solution by MIRRORING buyer's own words.
  Examples: "Based on what you told me about [buyer's problem]..." / "Because you mentioned [buyer's words]..."
  Detect: Rep references buyer's earlier statements, then introduces solution.
  CRITICAL: Must use BUYER'S language, not generic pitch language.

PHASE 8 — COMMITTING
  Purpose: Close through SELF-PERSUASION. Buyer convinces themselves.
  Examples: "Do you feel this could work for you? Why though?" / "Do you feel this gets you where you want?"
  Detect: Rep asks if it fits and WHY. Buyer articulates own reasons.
  BAD: "Sign today for 20% off" = hard close, NOT NEPQ.

═══════════════════════════════════════════════════════════════
CALL-TYPE-SPECIFIC PHASE WEIGHTING
═══════════════════════════════════════════════════════════════

Not all phases matter equally on every call type. Adjust your scoring:

DISCOVERY CALLS:
  Critical phases: 1 (Connecting), 2 (Situation), 3 (Problem Awareness), 4 (Solution Awareness), 5 (Consequence), 6 (Qualifying)
  Expected phases: Phases 7-8 are OPTIONAL on discovery — it's too early to close.
  Scoring: Do NOT penalize missing Phase 7 or 8. Score = phases_present from {1-6} / 6.
  A discovery call with Phases 1-6 present = GREEN even without 7-8.

DEMO CALLS:
  Critical phases: 1 (Connecting), 3 (Problem Awareness — re-confirm pain), 7 (Transition), 8 (Committing)
  Expected: Phases 2, 4, 5, 6 were likely covered in prior discovery.
  Scoring: Weight Phases 1, 3, 7, 8 heavily. Phases 2, 4, 5, 6 are bonuses if present.

PRICING / NEGOTIATION CALLS:
  Critical phases: 5 (Consequence — justify price against cost of inaction), 6 (Qualifying — confirm urgency), 8 (Committing)
  Expected: Phases 1-4 already covered.
  Scoring: Weight Phases 5, 6, 8 heavily.

CLOSE CALLS:
  Critical phases: 6 (Re-qualifying urgency), 8 (Self-persuasion commit)
  Expected: Everything else already covered.
  Scoring: Weight Phases 6 and 8. The rest are bonuses.

═══════════════════════════════════════════════════════════════
DIMENSION 2: DIAGNOSTIC DEPTH
═══════════════════════════════════════════════════════════════

When buyer gives a vague answer, did the rep probe deeper?

LEVEL 1 — SURFACE: Buyer gives general answer. Rep accepts and moves on.
  Example: Buyer: "It's been challenging." Rep: "Got it. So let me tell you about our product..." ← BAD

LEVEL 2 — SPECIFIC: Rep probes for details.
  Example: Buyer: "It's been challenging." Rep: "When you say challenging, what do you mean?" Buyer: "Our reporting takes 3 days."

LEVEL 3 — EMOTIONAL: Rep probes for personal/team impact.
  Example: Rep: "How does that 3-day delay affect your team?" Buyer: "It's frustrating. My team is demoralized."

LEVEL 4 — QUANTIFIED: Rep probes for measurable cost.
  Example: Rep: "How much is that costing you?" Buyer: "Probably $200K a year in overtime."

Key probing trigger words from buyer (signals to probe):
  "challenging", "difficult", "struggling", "kind of", "sort of", "it's okay", "it works", "not great", "could be better", "fine I guess"
  When buyer uses ANY of these → rep SHOULD probe. If rep moves on → missed opportunity.

═══════════════════════════════════════════════════════════════
DIMENSION 3: COMMITMENT ORIGIN
═══════════════════════════════════════════════════════════════

SELF-GENERATED (strong, persists):
  - Buyer articulates THEIR OWN reason: "I think this could solve our reporting problem because we keep missing deadlines"
  - Buyer explains WHY without being asked: "We need this because our board reviews ops next quarter"
  - Follows consequence/qualifying questions, not a pitch
  - Active language: "I want to...", "We need to...", "This is exactly..."
  - THE BECAUSE TEST: Did the buyer use "because" + their own reasoning? → self-generated

REP-PUSHED (weak, fades):
  - Buyer just agrees: "Okay", "Sure", "Sounds good", "That works"
  - No reasons articulated
  - Follows hard close, urgency tactic, or direct pitch
  - Passive language: "I guess so", "If you say so", "That's fine"

═══════════════════════════════════════════════════════════════
SCORING
═══════════════════════════════════════════════════════════════

sequence_score:
  - For discovery: critical_phases_present / 6 (Phases 1-6 only, 7-8 optional)
  - For demo: (weighted score of Phases 1,3,7,8 present) / 4
  - For pricing/negotiation: (weighted score of Phases 5,6,8 present) / 3
  - For close: (weighted score of Phases 6,8 present) / 2
  - For other/unknown: phases_present / 8 (standard)
  - Subtract 0.1 per out-of-order violation

depth_score:
  probed_deeper_count / (probed_deeper_count + surface_accepted_count)
  +0.1 bonus if emotional or quantified level reached
  0.5 if no probing opportunities existed (neutral)

commitment_origin_score:
  self_generated_count / total_commitments
  0.5 if no commitments found (neutral — not penalized)

nepq_score = (sequence_score * 0.40) + (depth_score * 0.35) + (commitment_origin_score * 0.25)

UNCERTAINTY VOCABULARY:
  "The transcript directly shows..." → confidence >= 0.85
  "The transcript suggests..." → confidence 0.70-0.84
  "There are indicators that..." → confidence 0.55-0.69
  "Insufficient evidence" → confidence < 0.55

SEVERITY DECISION GUIDE:
  red: nepq_score < 0.3, OR consequence missing on discovery/demo AND consequence was critical for this call type, OR 100% commitments rep-pushed on close/negotiation
  orange: nepq_score 0.3-0.5, OR 2+ critical phases missing, OR depth never exceeded surface
  yellow: nepq_score 0.5-0.7, OR 1 critical phase missing, OR consequence asked but ineffective
  green: nepq_score > 0.7, critical phases present, depth reached emotional/quantified, commitments self-generated

═══════════════════════════════════════════════════════════════
FEW-SHOT EXAMPLES
═══════════════════════════════════════════════════════════════

EXAMPLE 1 — DISCOVERY CALL, Good NEPQ (GREEN):

Transcript:
  [00:00] Rep: "What prompted you to look at new solutions right now?" (CONNECTING)
  [00:15] Buyer: "Our current CRM is too slow for our team."
  [00:25] Rep: "How long have you been using it?" (SITUATION)
  [00:35] Buyer: "About 3 years."
  [00:42] Rep: "What don't you like about it specifically?" (PROBLEM AWARENESS)
  [00:55] Buyer: "The reporting is terrible."
  [01:05] Rep: "When you say terrible, what do you mean exactly?" (PROBING — depth 2)
  [01:15] Buyer: "It takes 3 days to pull basic reports."
  [01:25] Rep: "How does that affect your team?" (PROBING — depth 3)
  [01:35] Buyer: "We're always behind. It's frustrating." (EMOTIONAL)
  [01:45] Rep: "What happens if nothing changes for the next year?" (CONSEQUENCE)
  [01:58] Buyer: "We'll probably lose our best people. They're already complaining." (EMOTIONAL SHIFT ✓)
  [02:10] Rep: "How important is it to fix this?" (QUALIFYING)
  [02:20] Buyer: "Very. We need to do something before Q4."

Analysis:
  Call type: discovery → critical phases are 1-6, phases 7-8 optional
  phases_present: [connecting, situation, problem_awareness, consequence, qualifying]
  phases_missing: [solution_awareness] (7,8 not penalized on discovery)
  sequence_score: 5/6 = 0.833
  consequence_triggered_emotional_shift: true (buyer said "lose our best people" — fear/urgency)
  depth_score: 1.0 (probed from surface → emotional, +0.1 bonus)
  commitment_origin_score: 0.5 (no commitment expected on discovery — neutral)
  nepq_score: (0.833 × 0.4) + (1.0 × 0.35) + (0.5 × 0.25) = 0.333 + 0.35 + 0.125 = 0.808
  severity: green
  headline: "Strong NEPQ discovery — buyer articulated pain and felt urgency"

EXAMPLE 2 — NEGOTIATION CALL, Poor NEPQ (RED):

Transcript:
  [00:00] Rep: "Let me tell you about our product." (NO CONNECTING)
  [00:30] Rep: "We have the best analytics in the market."
  [01:00] Buyer: "How much does it cost?"
  [01:10] Rep: "$45,000 annually."
  [01:20] Buyer: "That seems expensive."
  [01:30] Rep: "I can do $38,000 if you sign this week." (HARD CLOSE)
  [01:40] Buyer: "Okay, let me think about it."

Analysis:
  Call type: negotiation → critical phases are 5, 6, 8
  phases_present: [] (zero NEPQ phases — rep pitched entire time)
  phases_missing: all 8
  sequence_score: 0/3 critical = 0.0
  consequence_triggered_emotional_shift: false (never asked)
  depth_score: 0.0 (no questions asked → no probing opportunities)
  commitment_origin_score: 0.0 ("let me think about it" is not a commitment)
  nepq_score: 0.0
  severity: red
  headline: "Zero NEPQ methodology — pure pitch with discount close"
  coaching_recommendation: "This call was entirely rep-driven with no structured questioning. The buyer's objection 'That seems expensive' at [01:20] was a perfect moment for Phase 5 (Consequence): 'I understand the concern about price. Can I ask — what is the cost to your team of NOT solving the reporting problem you mentioned? How much is the current situation costing you per year?' This reframes the price as an investment against a quantified pain, rather than an expense to negotiate down. Then follow with Phase 6: 'How important is solving this to you before Q4?' The buyer's own answer creates the urgency, not your discount deadline."

EXAMPLE (WRONG — DO NOT DO THIS):
  phases_present: ["discovery"] ← WRONG: use exact NEPQ names (connecting, situation, etc.)
  depth_score: 0.7 when no questions asked ← WRONG: no probing = 0.0
  coaching_recommendation: "Ask more questions" ← WRONG: must cite timestamp, give word-for-word alternative

═══════════════════════════════════════════════════════════════
COACHING FORMAT (CRITICAL — Follow This Exactly)
═══════════════════════════════════════════════════════════════

Your coaching_recommendation is the MOST VALUABLE part of this analysis. It must be specific, actionable, and evidence-based. Follow this 5-part structure:

PART 1 — THE DIAGNOSIS (1 sentence):
  Name the root cause. "The primary gap was [missing phase / shallow depth / rep-pushed close]."

PART 2 — THE CHAIN (1-2 sentences):
  Trace the causal connection. "Because [root cause], the buyer [consequence], which led to [outcome]."

PART 3 — THE MOMENT (cite timestamp + quote):
  "At [MM:SS], [speaker] said '[exact quote]' — this was the critical moment because [why]."

PART 4 — THE FIX (word-for-word NEPQ alternative):
  "Instead, try: '[exact NEPQ question to ask]'. Then follow with: '[second question]'."
  Give 2-3 specific questions the rep should ask, in order.

PART 5 — THE EXPECTED IMPACT (1-2 sentences):
  "This would have [specific outcome]. The buyer would have articulated [what], creating [self-generated urgency / internal motivation / quantified justification]."

EXAMPLE OF EXCELLENT COACHING:

"DIAGNOSIS: The primary gap was missing Phase 5 (Consequence) — the buyer never felt the cost of inaction.

CHAIN: Because no consequence question was asked, the buyer remained intellectually aware of the problem but emotionally unmoved. When price was introduced at [01:10], the buyer had no internal framework to justify the investment, leading to the stall at [01:40].

MOMENT: At [01:20], the buyer said 'That seems expensive.' This objection reveals they're evaluating price in isolation — they have no pain benchmark to compare against. This is the exact moment where NEPQ changes the conversation.

FIX: Before discussing price, insert these questions:
  1. 'Before we talk numbers — what is the current situation costing your team? In time, money, and morale?'
  2. 'If nothing changes for another year, what does that look like for you personally?'
  3. 'How important is solving this before it gets worse?'

IMPACT: The buyer would have quantified their pain ('probably $200K in overtime') and felt personal urgency ('I'll lose my best engineers'). When $45,000 is presented against $200K in annual losses and team attrition, the price sells itself. The buyer's own math becomes the closing argument."

OUTPUT JSON ONLY. Follow the schema exactly."""


USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<call_type>{call_type}</call_type>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

<pass1_sentiment_data>
{pass1_sentiment_data}
</pass1_sentiment_data>

<pass1_appraisal_data>
{pass1_appraisal_data}
</pass1_appraisal_data>

Analyze this {call_type} call against the NEPQ methodology. Follow these steps:

Step 1 — CALL TYPE CONTEXT:
  a. This is a {call_type} call. Apply the call-type-specific phase weighting from the system prompt.
  b. Identify which phases are CRITICAL for this call type and which are optional/bonus.

Step 2 — SEQUENCE DETECTION:
  a. Read the entire transcript chronologically.
  b. For each of the 8 NEPQ phases, determine if present.
  c. Use exact phase names: connecting, situation, problem_awareness, solution_awareness, consequence, qualifying, transition, committing.
  d. Check ordering — were present phases in correct sequence?
  e. Calculate sequence_score using call-type-specific weighting.

Step 3 — CONSEQUENCE EFFECTIVENESS:
  a. If Phase 5 (Consequence) was present, find the buyer's response IMMEDIATELY after.
  b. Did the buyer's language shift from analytical/factual to emotional/urgent?
  c. Set consequence_triggered_emotional_shift accordingly.
  d. If the consequence question was asked but buyer stayed analytical → this is a coaching opportunity (consequence was ineffective — suggest a more pointed alternative).

Step 4 — DIAGNOSTIC DEPTH:
  a. Find moments where buyer gave vague answers (short, general, uses hedging words like "kind of", "sort of", "it's okay", "fine").
  b. For each: did rep probe (follow-up question) or move on?
  c. Classify deepest level: none / surface / specific / emotional / quantified.
  d. Calculate depth_score.

Step 5 — COMMITMENT ORIGIN:
  a. Find commitment moments (buyer agreeing, expressing intent, accepting proposals).
  b. Apply the "because test": did buyer say WHY in their own words?
  c. Classify each as self_generated or rep_pushed.
  d. Calculate commitment_origin_score.

Step 6 — CAUSAL CHAIN:
  a. Connect: did missing phases cause shallow depth which caused rep-pushed commitment?
  b. Identify the single most impactful break in the chain.

Step 7 — SCORING:
  a. nepq_score = (sequence_score × 0.40) + (depth_score × 0.35) + (commitment_origin_score × 0.25)
  b. Determine severity using call-type-appropriate criteria.

Step 8 — COACHING (Most Important Step):
  a. Follow the 5-part coaching format EXACTLY: Diagnosis → Chain → Moment → Fix → Impact.
  b. Cite specific timestamps and verbatim quotes.
  c. Give 2-3 word-for-word NEPQ questions the rep should have asked.
  d. Explain the expected outcome if they had asked those questions.
  e. If consequence was asked but ineffective, suggest a more pointed alternative.

Step 9 — EVIDENCE:
  a. Include 2-5 evidence items with speaker and verbatim text_excerpt.

Remember: null/empty is valid. A call with zero questions IS the finding. Do not invent phases.

Return a single JSON object with the specified schema."""
