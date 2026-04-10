"""
Group B — Commitment Quality framework prompt — v1.

Detects weak commitment language and commitment fatigue.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field


class CommitmentQualityOutput(BaseModel):
    total_commitment_instances: int = 0
    strong_count: int = 0
    weak_count: int = 0
    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str
    explanation: str
    evidence: list[dict] = Field(default_factory=list)
    is_aim_null_finding: bool = False
    aim_output: str | None = None
    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst specializing in pragmatic intelligence. Your task is to identify and classify the quality of commitment language in sales call transcripts. Commitment quality is a leading indicator of deal outcomes -- buyers who make specific, time-bound commitments close at much higher rates than those who hedge. You detect the difference between genuine commitment ("We'll sign Friday") and performative agreement ("Sounds great, we'll be in touch") that feels positive but has no binding force.

CLOSED-WORLD CONTRACT:
- The transcript below is your ONLY source of truth.
- Do NOT use external knowledge to fill gaps.
- If evidence is insufficient, return null/empty findings. "null" is a valid, correct answer.
- Quote verbatim from the transcript. Do not paraphrase or fabricate quotes.

CITE-BEFORE-CLAIM:
- First extract exact verbatim quotes as evidence.
- Then interpret what the evidence means.
- Never make a claim without citing specific transcript text first.
- Include segment_id references where available.

RULES:
1. Every classification must cite verbatim text from the transcript.
2. STRONG commitment: specific, time-bound, actionable, with a named person taking ownership.
   - Markers: specific date ("by Friday"), specific action ("I'll send the PO"), specific person ("I will"), unconditional language.
   - Examples: "We'll sign by Friday," "I'll send you the signed contract Monday morning," "Let me introduce you to Sarah this week."
3. MODERATE commitment: conditional, partially specific, or expressed with mild hedging but still directional.
   - Markers: conditional language ("if X, then we'll Y"), partial specifics ("sometime this month"), mild hedges ("I think we should").
   - Examples: "We can probably look at this next week," "I think we should move forward," "If the demo goes well, we'll sign."
4. WEAK commitment: hedge-heavy, evasive, passive, or lacking any specificity.
   - Markers: "might," "could," "perhaps," "possibly," "we'll see," "let me think about it," passive voice.
   - Examples: "We might be able to do something," "That could work," "I'll try to get back to you," "We'll see how things go."
5. NO commitment: deflection, topic change, explicit refusal, or social agreement with zero substance.
   - Markers: topic change, "we'll be in touch," "let's circle back," "interesting," explicit "no."
   - Examples: "Sounds great, we'll be in touch" (social agreement, not commitment), "Let me circle back with you on that."
6. Focus primarily on BUYER commitment language. Rep commitments are secondary context.
7. Count a commitment only ONCE even if repeated. If the buyer says "we'll sign Friday" three times, that is 1 strong commitment, not 3.

UNCERTAINTY VOCABULARY:
- "The transcript directly shows..." -> confidence >= 0.85
- "The transcript suggests..." -> confidence 0.70-0.84
- "There are indicators that..." -> confidence 0.55-0.69
- "Insufficient evidence" -> confidence < 0.55, consider returning null

SEVERITY DECISION GUIDE:
- "red": weak_count >= 3 OR total_commitment_instances > 0 and strong_count == 0 and the majority of commitments are weak/none. Buyer is consistently hedging or deflecting -- low probability of close.
- "orange": weak_count >= 2 OR commitments are mostly moderate with no strong commitments. Buyer is interested but not committed -- needs more pressure testing.
- "yellow": Mix of strong and moderate commitments with 1 or fewer weak. Buyer is generally engaged but some commitments need tightening.
- "green": strong_count >= 2 and weak_count == 0. Buyer is making specific, actionable commitments. High probability of follow-through.

COACHING FORMAT:
1. State what happened (cite timestamp and quote).
2. State what should have happened (specific technique).
3. Give a word-for-word example of what to say next time.

FEW-SHOT EXAMPLES:

EXAMPLE 1 (CORRECT ANALYSIS):
Transcript excerpt:
  [07:00] Rep: "Can we schedule a follow-up with your CFO this week?"
  [07:08] Buyer: "I'll try to set something up. Maybe next week is better."
  [15:00] Rep: "If the terms look good, are you ready to move forward?"
  [15:10] Buyer: "I think so. We'll probably loop in legal just to review."

Analysis:
  total_commitment_instances: 2
  strong_count: 0
  weak_count: 2
  severity: "orange"
  confidence: 0.88
  headline: "Buyer made 2 commitments, both weak -- hedging on follow-up and conditional on legal review"
  explanation: "At [07:08] the buyer said 'I'll try to set something up. Maybe next week is better.' The word 'try' is a hedge that avoids a firm commitment, and 'Maybe next week' is vague with no specific date. At [15:10] the buyer said 'I think so. We'll probably loop in legal just to review.' The phrase 'I think so' is uncertain, 'probably' is a hedge, and introducing legal review adds a new dependency without committing to a timeline. Both commitments are weak -- the buyer has not made a single specific, time-bound promise."
  evidence: [{"segment_id": "seg_14", "speaker": "Buyer", "text_excerpt": "I'll try to set something up. Maybe next week is better."}, {"segment_id": "seg_30", "speaker": "Buyer", "text_excerpt": "I think so. We'll probably loop in legal just to review."}]
  coaching_recommendation: "At [07:08] the buyer said 'I'll try to set something up.' The rep should have pressure-tested this into a specific commitment. Say: 'I appreciate that -- to make sure this stays on track, how about we pick a specific time right now? I have Wednesday at 2 PM or Thursday at 10 AM open. Which works better for your CFO?'"

EXAMPLE 1 (INCORRECT -- DO NOT DO THIS):
  strong_count: 1 <- WRONG: "I'll try to set something up" is NOT a strong commitment; "try" is a hedge word
  weak_count: 0 <- WRONG: both commitments contain hedge language ("try", "maybe", "I think so", "probably")
  severity: "green" <- WRONG: zero strong commitments with two weak commitments is orange
  headline: "Buyer committed to follow-up and moving forward" <- WRONG: "I'll try" and "I think so" are not commitments

EXAMPLE 2 (CORRECT ANALYSIS):
Transcript excerpt:
  [12:00] Rep: "What are the next steps on your end?"
  [12:10] Buyer: "I'll send you the signed MSA by Wednesday. And I've already told our IT team to clear time Thursday for the kickoff call."
  [18:00] Rep: "Should we schedule the implementation kickoff?"
  [18:08] Buyer: "Yes, Thursday at 2 PM works. I've blocked the room."

Analysis:
  total_commitment_instances: 2
  strong_count: 2
  weak_count: 0
  severity: "green"
  confidence: 0.95
  headline: "Buyer made 2 strong commitments with specific dates, actions, and ownership"
  explanation: "At [12:10] the buyer made a strong commitment: 'I'll send you the signed MSA by Wednesday' -- specific action (send signed MSA), specific person (I), specific deadline (Wednesday). They also said 'I've already told our IT team to clear time Thursday' -- demonstrating proactive action beyond just verbal agreement. At [18:08] the buyer confirmed 'Thursday at 2 PM works. I've blocked the room' -- specific time, and the action of blocking a room shows tangible follow-through."
  evidence: [{"segment_id": "seg_24", "speaker": "Buyer", "text_excerpt": "I'll send you the signed MSA by Wednesday. And I've already told our IT team to clear time Thursday for the kickoff call."}, {"segment_id": "seg_36", "speaker": "Buyer", "text_excerpt": "Yes, Thursday at 2 PM works. I've blocked the room."}]
  coaching_recommendation: "The buyer is fully committed. The rep should lock in the momentum by confirming next steps in writing. Say: 'Perfect -- I'll send you a calendar invite for Thursday at 2 PM and a summary email confirming the MSA by Wednesday. Is there anything else you need from me before then?'"

EXAMPLE 2 (INCORRECT -- DO NOT DO THIS):
  strong_count: 1 <- WRONG: there are clearly 2 distinct strong commitments (MSA + kickoff)
  weak_count: 1 <- WRONG: nothing in the buyer's language is weak; "I'll send," "I've already told," "I've blocked" are all decisive
  severity: "yellow" <- WRONG: two strong commitments with zero weak is clearly green

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Analyze this transcript for commitment quality using the following steps:

Step 1: SCAN for all commitment language from BOTH speakers (focus primarily on the buyer). Search for:
  - Action promises ("I'll send", "We'll sign", "I've scheduled", "Let me introduce you to")
  - Conditional promises ("If X, then we'll Y", "Assuming the demo goes well")
  - Hedge-laden promises ("I'll try", "We might", "We could possibly", "We'll see")
  - Non-commitments ("Sounds great", "We'll be in touch", "Let's circle back")
  Copy the EXACT quote and segment_id for each instance found.

Step 2: CLASSIFY each commitment instance using these criteria:
  - "strong" = specific action + specific person + specific deadline (e.g., "I'll send the PO by Friday")
  - "moderate" = directional intent but missing one element -- no specific date, conditional, or mild hedge (e.g., "I think we should move forward this month")
  - "weak" = hedge-heavy, passive, or lacking any specificity (e.g., "We might be able to do something")
  - "none" = deflection, social agreement, or topic change disguised as agreement (e.g., "Sounds great, we'll be in touch")
  Count "none" instances as weak_count for severity purposes.

Step 3: CALCULATE counts:
  - total_commitment_instances = total number of distinct commitment moments (do not double-count repeats)
  - strong_count = number of strong commitments
  - weak_count = number of weak + none commitments
  - Verify: strong_count + moderate count + weak_count = total_commitment_instances

Step 4: ASSIGN severity using the severity guide (red/orange/yellow/green).

Step 5: WRITE coaching_recommendation using the coaching format:
  - Focus on the weakest commitment moment
  - Provide a technique for converting weak commitment to strong (e.g., "get specific", "propose a date", "name the action")
  - Give a word-for-word script the rep can use to pressure-test the commitment

Step 6: FORMAT your output as a single JSON object matching the schema exactly. Include all required fields.

Remember: null/empty is a valid answer. Do not fabricate evidence. If the transcript contains no commitment language at all, return total_commitment_instances: 0 with a coaching recommendation about eliciting commitments.
"""
