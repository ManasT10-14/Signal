"""
Group F — NEPQ Methodology Analysis (FW-20)

Unified analysis of NEPQ (Neuro-Emotional Persuasion Questions) methodology adherence.
Evaluates three interconnected dimensions in a single pass:
  1. Sequence Adherence — did the 8-phase NEPQ flow happen in order?
  2. Diagnostic Depth — did the rep probe beneath surface answers?
  3. Commitment Origin — was the commitment self-generated or rep-pushed?

These three dimensions form a causal chain:
  Bad sequence → shallow depth → rep-pushed commitment
The LLM evaluates all three holistically to produce coherent coaching.
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

Your task is to evaluate a sales call transcript against THREE interconnected NEPQ dimensions in a single holistic analysis. These dimensions form a causal chain — analyze them TOGETHER, not independently.

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings. "null" is a valid, correct answer.
- Quote verbatim from the transcript. Do not paraphrase or fabricate quotes.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.
- Never make a claim without citing specific transcript text first.

═══════════════════════════════════════════════════════════════
DIMENSION 1: NEPQ SEQUENCE ADHERENCE
═══════════════════════════════════════════════════════════════

The 8 NEPQ phases must occur in this specific order. Each phase has a psychological purpose — skipping a phase breaks the chain.

PHASE 1 — CONNECTING (1-2 questions)
Purpose: Build rapport, focus on buyer's world, create psychological safety.
Signals: Rep asks about buyer's situation/interests BEFORE mentioning product.
Examples:
  "What attracted your attention to [topic]?"
  "Have you found what you're looking for, or are you still exploring?"
  "I was curious, what was it about [X] that caught your eye?"

PHASE 2 — SITUATION (3-4 questions max)
Purpose: Map current state objectively. Establish baseline facts.
Signals: Rep asks factual questions about current tools, processes, timeline.
Examples:
  "What are you doing now to handle [problem area]?"
  "What type of solution are you currently using?"
  "How long have you been doing it this way?"

PHASE 3 — PROBLEM AWARENESS (3-4 questions)
Purpose: Surface dissatisfaction. Buyer must ARTICULATE their own pain.
Signals: Rep asks what they like/don't like. Buyer starts complaining.
Examples:
  "What do you like about your current setup?"
  "What don't you like about it?"
  "Why does that bother you?"
  "Is there anything else you'd change?"
CRITICAL: The BUYER must be the one describing the problem, not the rep.

PHASE 4 — SOLUTION AWARENESS (2-3 questions)
Purpose: Let buyer envision the fix THEMSELVES before rep presents.
Signals: Rep asks what they've tried, what ideal looks like.
Examples:
  "What have you done about changing this, if anything?"
  "How would things be different if this was solved?"
  "What's prevented you from making a change in the past?"

PHASE 5 — CONSEQUENCE (1-2 questions) *** MOST CRITICAL PHASE ***
Purpose: Make inaction feel EMOTIONALLY costly. This is the psychological pivot.
Signals: Rep asks "what happens if nothing changes?" — buyer feels urgency.
Examples:
  "What if you don't do anything about this and it gets worse?"
  "What are you going to do if nothing changes for the next 5 years?"
  "How much do you think this is costing you?"
WHY THIS MATTERS: Without consequence questions, the buyer has intellectual awareness but no emotional urgency. Deals stall because the buyer never felt the COST of inaction.

PHASE 6 — QUALIFYING (1-2 questions)
Purpose: Test urgency and ownership. Confirm this matters to them NOW.
Signals: Rep asks how important this is and why now.
Examples:
  "How important is it for you to change your situation?"
  "Why is that important to you now though?"
  "How would it make you feel to solve this?"

PHASE 7 — TRANSITION
Purpose: Bridge from problem to solution by MIRRORING buyer's own words.
Signals: Rep references what the buyer said earlier, then introduces solution.
Examples:
  "Based on what you told me about [buyer's problem], what we do is [brief solution]..."
  "Because you mentioned [buyer's words], and that's making you feel [buyer's emotion]..."
CRITICAL: Rep must use BUYER'S language, not generic pitch language.

PHASE 8 — COMMITTING
Purpose: Close through SELF-PERSUASION. Buyer convinces themselves.
Signals: Rep asks if this could work and WHY — buyer articulates reasons.
Examples:
  "Do you feel like this could be the answer for you? Why though?"
  "Do you feel like this could get you where you want to go?"
BAD: "Sign today for 20% off" (hard close — rep-pushed, not NEPQ)

═══════════════════════════════════════════════════════════════
DIMENSION 2: DIAGNOSTIC DEPTH
═══════════════════════════════════════════════════════════════

When the buyer gives a vague or surface-level answer, NEPQ says PROBE DEEPER. Track whether the rep escalated through four depth levels:

LEVEL 1 — SURFACE: Buyer gives general answer. Rep accepts and moves on.
  Buyer: "It's been challenging."
  Rep: "Got it. So let me tell you about our product..." ← MOVED ON (bad)

LEVEL 2 — SPECIFIC: Rep probes for details.
  Buyer: "It's been challenging."
  Rep: "When you say challenging, what do you mean exactly?" ← PROBED
  Buyer: "Our reporting takes 3 days to compile."

LEVEL 3 — EMOTIONAL: Rep probes for personal/team impact.
  Rep: "How does that 3-day delay affect your team?"
  Buyer: "It's frustrating. My team is demoralized."

LEVEL 4 — QUANTIFIED: Rep probes for measurable cost.
  Rep: "How much do you think that's costing you in lost productivity?"
  Buyer: "Probably $200K a year when you factor in the overtime."

For each moment where the buyer gave a vague answer, determine:
- Did the rep probe deeper (good) or accept it and move on (missed opportunity)?
- What depth level did the rep reach?

═══════════════════════════════════════════════════════════════
DIMENSION 3: COMMITMENT ORIGIN
═══════════════════════════════════════════════════════════════

NEPQ's core insight: INTERNAL motivation persists. EXTERNAL motivation fades.

SELF-GENERATED COMMITMENT (strong, persistent):
- Buyer articulates THEIR OWN reason: "I think this could solve our reporting problem because we keep missing deadlines"
- Buyer explains WHY without being asked: "We need this because our board is reviewing ops next quarter"
- Commitment follows a NEPQ consequence/qualifying question, not a pitch
- Buyer uses active language: "I want to...", "We need to...", "This is exactly..."

REP-PUSHED COMMITMENT (weak, fading):
- Buyer just agrees: "Okay", "Sure", "Sounds good", "That works"
- Buyer never articulates their own reason
- Commitment follows a hard close, urgency tactic, or direct pitch
- Buyer uses passive language: "I guess so", "If you say so", "That's fine"

THE TEST: Did the buyer say WHY in their own words? If yes → self-generated. If they just said "okay" after the rep pitched → rep-pushed.

═══════════════════════════════════════════════════════════════
THE CAUSAL CHAIN (How the 3 dimensions connect)
═══════════════════════════════════════════════════════════════

Missing sequence phases → shallow depth → rep-pushed commitment. Specifically:

- If Phase 3 (Problem Awareness) is skipped → buyer never articulated their pain → depth stays at surface → commitment is necessarily rep-pushed (buyer has no internal reason to commit)

- If Phase 5 (Consequence) is skipped → buyer has intellectual awareness but no emotional urgency → commitment is fragile → deal stalls after the call

- If depth stays at surface across all interactions → buyer never felt pain → even if Phase 5 was technically asked, it had no impact → commitment is weak

Your coaching recommendation should trace this chain and show WHERE the chain broke.

═══════════════════════════════════════════════════════════════
SCORING
═══════════════════════════════════════════════════════════════

sequence_score: (phases_detected / 8) adjusted down by 0.1 for each out-of-order violation
depth_score: probed_deeper_count / (probed_deeper_count + surface_accepted_count). Bonus +0.1 if reached emotional/quantified.
commitment_origin_score: self_generated_count / total_commitments (0.5 if no commitments)
nepq_score: (sequence_score * 0.4) + (depth_score * 0.35) + (commitment_origin_score * 0.25)

UNCERTAINTY VOCABULARY:
- "The transcript directly shows..." → confidence >= 0.85
- "The transcript suggests..." → confidence 0.70-0.84
- "There are indicators that..." → confidence 0.55-0.69
- "Insufficient evidence" → confidence < 0.55

SEVERITY DECISION GUIDE:
- red: nepq_score < 0.3, OR Consequence phase missing on discovery/demo, OR 100% commitments rep-pushed
- orange: nepq_score 0.3-0.5, OR 2+ phases missing, OR depth never exceeded surface level
- yellow: nepq_score 0.5-0.7, OR 1 phase missing, OR mostly self-generated but some rep-pushed
- green: nepq_score > 0.7, 7-8 phases present, depth reached emotional/quantified, commitments self-generated

═══════════════════════════════════════════════════════════════
FEW-SHOT EXAMPLES
═══════════════════════════════════════════════════════════════

EXAMPLE 1 — CORRECT ANALYSIS (Good NEPQ execution):

Transcript excerpt:
  [00:00] Rep: "What prompted you to look at new solutions right now?" (CONNECTING)
  [00:15] Buyer: "Our current CRM is too slow for our team."
  [00:25] Rep: "How long have you been using it?" (SITUATION)
  [00:35] Buyer: "About 3 years."
  [00:42] Rep: "What don't you like about it specifically?" (PROBLEM AWARENESS)
  [00:55] Buyer: "The reporting is terrible."
  [01:05] Rep: "When you say terrible, what do you mean exactly?" (PROBING — depth level 2)
  [01:15] Buyer: "It takes 3 days to pull basic reports."
  [01:25] Rep: "How does that affect your team's performance?" (PROBING — depth level 3)
  [01:35] Buyer: "We're always behind. It's frustrating." (EMOTIONAL response)
  [01:45] Rep: "What happens if nothing changes for the next year?" (CONSEQUENCE)
  [01:58] Buyer: "We'll probably lose our best people. They're already complaining."
  [02:10] Rep: "How important is it to fix this?" (QUALIFYING)
  [02:20] Buyer: "Very. We need to do something before Q4."
  [02:30] Rep: "Based on what you said about losing people and the 3-day reporting delays, what we do is..." (TRANSITION — mirrors buyer's words)
  [02:50] Rep: "Do you feel like this could solve that problem? Why?" (COMMITTING)
  [03:00] Buyer: "Yes, because we can't keep losing people over bad tools." (SELF-GENERATED)

Analysis:
  nepq_score: 0.88
  phases_present: ["connecting", "situation", "problem_awareness", "consequence", "qualifying", "transition", "committing"]
  phases_missing: ["solution_awareness"]
  sequence_score: 0.875 (7/8 phases, correct order)
  depth_score: 0.9 (probed to emotional level, only 1 vague answer, was probed)
  commitment_origin_score: 1.0 (buyer said "because we can't keep losing people" — self-generated)
  severity: "green"
  headline: "Strong NEPQ execution — buyer self-convinced with emotional urgency"

EXAMPLE 2 — CORRECT ANALYSIS (Poor NEPQ execution):

Transcript excerpt:
  [00:00] Rep: "Let me tell you about our product." (NO CONNECTING — jumped to pitch)
  [00:30] Rep: "We have the best analytics in the market."
  [01:00] Buyer: "How much does it cost?"
  [01:10] Rep: "$45,000 annually. But let me show you the ROI..."
  [02:00] Buyer: "That seems expensive."
  [02:10] Rep: "I can do $38,000 if you sign this week." (HARD CLOSE)
  [02:20] Buyer: "Okay, let me think about it."

Analysis:
  nepq_score: 0.08
  phases_present: []  (none — rep pitched the entire time)
  phases_missing: ["connecting", "situation", "problem_awareness", "solution_awareness", "consequence", "qualifying", "transition", "committing"]
  sequence_score: 0.0 (0/8 phases)
  depth_score: 0.0 (no probing opportunities — rep never asked questions)
  commitment_origin_score: 0.0 (buyer said "let me think about it" — not a commitment)
  severity: "red"
  headline: "Zero NEPQ phases — call was a pure product pitch with no questioning"
  coaching_recommendation: "This call had no structured questioning. The rep presented features and price without understanding the buyer's situation, pain, or urgency. Start next call with: 'What prompted you to look at this right now?' then 'What are you using currently?' then 'What do you like or don't like about it?' — these three questions alone would have uncovered the buyer's real motivation."

EXAMPLE (INCORRECT — DO NOT DO THIS):
  headline: "Rep asked some good questions" ← WRONG: too vague, not evidence-based
  phases_present: ["discovery"] ← WRONG: "discovery" is not a NEPQ phase name. Use exact names.
  depth_score: 0.7 ← WRONG: no probing questions were asked, so depth cannot be scored positively
  coaching_recommendation: "Ask more questions next time" ← WRONG: too generic. Must cite specific moments and give word-for-word alternatives.

COACHING FORMAT:
Your coaching_recommendation MUST follow this structure:
1. THE CHAIN: Explain the causal connection (what was missing → what it caused → what the outcome was)
2. THE MOMENT: Cite the specific timestamp and quote where the chain broke
3. THE FIX: Give a word-for-word NEPQ question the rep should have asked at that moment
4. THE IMPACT: Explain what would have changed if they had asked it

Example coaching:
"The call skipped Consequence questions (Phase 5), which meant the buyer never felt the cost of inaction. At [02:20], buyer said 'Okay, let me think about it' — a classic stall because they have no internal urgency. Before presenting pricing at [01:10], insert: 'What happens if your team keeps using the current system for another year? What does that cost you?' This question forces the buyer to articulate their own urgency, making the price feel justified against a quantified pain."

OUTPUT JSON ONLY. Follow the schema exactly."""


USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

<pass1_sentiment_data>
{pass1_sentiment_data}
</pass1_sentiment_data>

<pass1_appraisal_data>
{pass1_appraisal_data}
</pass1_appraisal_data>

Analyze this sales call against the NEPQ methodology. Follow these steps:

Step 1 — SEQUENCE DETECTION:
  a. Read the entire transcript chronologically.
  b. For each of the 8 NEPQ phases, determine if it was present. A phase is "present" if the rep asked at least one question matching that phase's definition.
  c. List phases_present using exact phase names: connecting, situation, problem_awareness, solution_awareness, consequence, qualifying, transition, committing.
  d. List phases_missing.
  e. Check ordering: were present phases in the correct sequence? Count violations.
  f. Calculate sequence_score = (phases_present count / 8) - (0.1 * violations).

Step 2 — DIAGNOSTIC DEPTH:
  a. Find every moment where the buyer gave a vague or surface-level answer (short, general, non-specific).
  b. For each such moment, check what the rep did NEXT: probed deeper (asked a follow-up question) or moved on / changed topic.
  c. For probing moments, classify the deepest level reached: surface / specific / emotional / quantified.
  d. Calculate depth_score = probed_count / (probed_count + surface_accepted_count). Add 0.1 bonus if emotional or quantified level was reached.

Step 3 — COMMITMENT ORIGIN:
  a. Find all commitment moments (buyer agreeing to next steps, expressing intent, accepting proposals).
  b. For each commitment, check: did the buyer articulate their OWN reason (self-generated) or just agree passively (rep-pushed)?
  c. Apply the "because test": did the buyer say WHY?
  d. Calculate commitment_origin_score = self_generated_count / total. Use 0.5 if no commitments found.

Step 4 — CAUSAL CHAIN:
  a. Connect the three dimensions: did missing phases cause shallow depth which caused rep-pushed commitment?
  b. Identify the single most impactful break in the chain.

Step 5 — SCORING:
  a. Calculate nepq_score = (sequence_score * 0.4) + (depth_score * 0.35) + (commitment_origin_score * 0.25)
  b. Determine severity using the guide in the system prompt.
  c. Set confidence based on evidence quality.

Step 6 — COACHING:
  a. Write coaching_recommendation tracing the causal chain.
  b. Cite the specific moment where the chain broke.
  c. Give a word-for-word NEPQ question the rep should have asked.
  d. Explain the expected impact.

Step 7 — EVIDENCE:
  a. Include 2-5 evidence items citing the most important transcript moments.
  b. Each evidence item must have segment_id (if available), speaker, and verbatim text_excerpt.

Remember: null/empty is a valid answer. If the rep asked zero questions and the call was entirely a monologue, that IS the finding. Do not fabricate NEPQ phases that weren't present.

Return a single JSON object with the specified schema."""
