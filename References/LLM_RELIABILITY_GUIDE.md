# LLM Reliability Engineering
## Getting Correct Answers and Preventing Hallucinations in Production Systems

**Audience:** Engineers building LLM-native products
**Context:** Behavioral analysis pipelines where incorrect outputs directly affect real decisions
**Philosophy:** The LLM is powerful but unreliable. The *system* around it must be deterministic and verifiable.

---

## Table of Contents

1. [Understanding Why LLMs Go Wrong](#1-understanding-why-llms-go-wrong)
2. [Prompt Engineering for Correctness](#2-prompt-engineering-for-correctness)
3. [Structural Architecture Patterns](#3-structural-architecture-patterns)
4. [Hallucination Prevention Techniques](#4-hallucination-prevention-techniques)
5. [Post-Generation Verification](#5-post-generation-verification)
6. [Evaluation Infrastructure](#6-evaluation-infrastructure)
7. [Industry Approaches](#7-industry-approaches)
8. [The Complete Reliability Stack](#8-the-complete-reliability-stack)

---

## 1. Understanding Why LLMs Go Wrong

Before fixing the problem, understand what kind of problem you have. LLM failures fall into four distinct categories, each requiring a different treatment.

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM FAILURE TAXONOMY                         │
├──────────────────────┬──────────────────────────────────────────┤
│ Type                 │ What it looks like                       │
├──────────────────────┼──────────────────────────────────────────┤
│ Hallucination        │ Fabricated facts. Model invents quotes,  │
│                      │ timestamps, events that never happened.  │
│                      │ Feels confident. Is wrong.               │
├──────────────────────┼──────────────────────────────────────────┤
│ Confabulation        │ Real patterns stretched. Model finds     │
│                      │ the pattern it was asked to find because │
│                      │ it was asked. Confirmation bias in code. │
├──────────────────────┼──────────────────────────────────────────┤
│ Miscalibration       │ Correct finding, wrong confidence.       │
│                      │ Model says 0.9 for a weak signal and     │
│                      │ 0.7 for a strong one. Scores are noise.  │
├──────────────────────┼──────────────────────────────────────────┤
│ Semantic Drift       │ Correct at the surface, wrong underneath.│
│                      │ "The buyer was evasive" — technically    │
│                      │ true in output, wrong in clinical sense. │
└──────────────────────┴──────────────────────────────────────────┘
```

> **Key insight:** Most reliability engineering focuses only on hallucination. Confabulation is equally damaging and far less discussed. A model asked to find concessions will find concessions — even in a clean call — because it was asked.

---

## 2. Prompt Engineering for Correctness

### 2.1 The Closed-World Contract

The most impactful single change: explicitly constrain the model to one source of truth. Without this, the model uses training knowledge to fill gaps — and fills them wrong.

**❌ Open-world prompt (dangerous):**
```
Analyze this sales call transcript and identify any moments 
where the buyer evaded questions.
```

The model will draw on everything it knows about sales conversations to find patterns — including patterns that aren't in your transcript.

**✅ Closed-world prompt:**
```
You are analyzing a closed document.

SOURCE OF TRUTH: Only the transcript between <transcript> tags.
You have no other knowledge about this conversation.

RULES:
1. Every claim must be supported by verbatim text from the transcript.
2. If the evidence is absent: output null. Do NOT generate a 
   low-confidence guess. Null is the correct and honest answer.
3. "I don't know" and "not found" are valid, correct outputs.
4. You may not infer what a speaker "probably meant" unless you 
   quote the exact words you are inferring from.
5. You may not create timestamps. All timestamps come from 
   the segment metadata provided.

<transcript>
{transcript_content}
</transcript>
```

The phrase **"null is the correct and honest answer"** is specifically important. LLMs are trained to be helpful — they default to generating something. Validating null as correct suppresses confabulation.

---

### 2.2 Cite Before You Claim

Force the model to anchor every claim in verbatim text *before* making the claim. This is the single most effective anti-hallucination prompt pattern for document analysis.

**The wrong order (analysis → evidence):**
```
Find all cases where the buyer evaded questions.
For each evasion, provide the transcript evidence.
```
The model finds a pattern, then hunts for evidence to support it. This produces fabricated or misattributed citations.

**The right order (evidence → analysis):**
```
Step 1: For every question the rep asked, copy the buyer's 
        EXACT response verbatim from the transcript.
        Format: { "question": "...", "response": "..." }
        If you cannot find the exact response, write: NOT_FOUND.

Step 2: For each question-response pair you found,
        classify the response as one of:
        [answered | vague | topic_change | counter_question]

Step 3: For any response classified as non-answered,
        write the insight using only the text from Step 1.

You cannot make a claim that Step 1 did not establish.
```

**Example of what this prevents:**

```
Without cite-first:
  Insight: "Buyer evaded the budget question at 18:22"
  Evidence: "That's something we'd need to discuss internally"
  Reality: The buyer said this at 31:05, not 18:22. And it was
           about stakeholder alignment, not budget.

With cite-first:
  Step 1 output: { "question": "Who approves the budget?",
                   "response": "Let me think — actually, what 
                   about the implementation side of things?" }
                 [segment_id: S_0034, timestamp: 23:15]
  
  Step 2: topic_change (buyer redirected mid-sentence)
  
  Insight: Correctly cites S_0034 at 23:15 with the exact words.
```

---

### 2.3 Structured Decomposition — Break Complex Tasks Apart

Every additional inference step in a single prompt multiplies error probability. A prompt doing 5 things has 5 chances to go wrong, and errors in step 2 corrupt steps 3, 4, and 5 silently.

**The wrong approach (one prompt, everything):**
```
From this transcript:
1. Find all questions the rep asked
2. Determine which ones were evaded
3. Classify each evasion type
4. Score overall evasion severity
5. Generate a coaching recommendation
6. Write an insight card headline
```

**The right approach (pipeline of focused prompts):**

```
┌─────────────────────────────────────────────────────────────┐
│  PASS A: Extract                                            │
│  Task: Copy all rep questions verbatim                      │
│  Risk: LOW (extraction, no interpretation)                  │
│  Validation: Are these interrogative sentences? (regex)     │
│  Output: [{ segment_id, timestamp, exact_text }]           │
└──────────────────────────┬──────────────────────────────────┘
                           │ Validated output only
┌──────────────────────────▼──────────────────────────────────┐
│  PASS B: Match                                              │
│  Task: Find the buyer's response to each question           │
│  Risk: LOW (segment lookup with context window)             │
│  Validation: Does response segment follow question? (time)  │
│  Output: [{ question_id, response_segment_id, response }]  │
└──────────────────────────┬──────────────────────────────────┘
                           │ Validated pairs only
┌──────────────────────────▼──────────────────────────────────┐
│  PASS C: Classify                                           │
│  Task: Classify each response                               │
│  Risk: MEDIUM (interpretation on verified text)             │
│  Validation: Confidence + alternative explanation check     │
│  Output: [{ pair_id, classification, confidence }]         │
└──────────────────────────┬──────────────────────────────────┘
                           │ Only high-confidence classifications
┌──────────────────────────▼──────────────────────────────────┐
│  PASS D: Synthesize                                         │
│  Task: Generate insight card from confirmed evasions        │
│  Risk: LOW (synthesis on verified data)                     │
│  Output: Final insight with evidence links                  │
└─────────────────────────────────────────────────────────────┘
```

Each pass has a narrow task, a validation gate, and only passes verified output downstream. An error in Pass A is caught before it corrupts Pass B, C, D.

---

### 2.4 Negative Examples in Few-Shot Prompts

Most prompts demonstrate correct outputs. The model never learns what a wrong detection looks like — so it applies the pattern too broadly.

Including "this is NOT an evasion" examples dramatically reduces false positives.

```python
FEW_SHOT_EXAMPLES = [

    # ✅ Correct detection
    {
        "question": "Who has final sign-off on the budget?",
        "response": "That's a good question. Let me think about— "
                    "actually, can we revisit the implementation timeline?",
        "classification": "topic_change",
        "confidence": 0.91,
        "reasoning": "Buyer began answering, then redirected mid-sentence "
                     "to an unrelated topic without providing any information "
                     "about budget authority."
    },

    # ❌ NOT an evasion — direct answer
    {
        "question": "Who has final sign-off on the budget?",
        "response": "That would be our CFO, David Chen. He's the one "
                    "who needs to approve anything over $50K.",
        "classification": "answered",
        "confidence": 1.0,
        "reasoning": "Buyer named a specific person and provided context. "
                     "Direct, specific answer. No evasion present."
    },

    # ⚠️ Vague but not evasive — correctly flagged as uncertain
    {
        "question": "What's your evaluation timeline?",
        "response": "We're hoping to move fairly quickly on this.",
        "classification": "vague_response",
        "confidence": 0.55,
        "reasoning": "Buyer acknowledged the question and gave a directional "
                     "answer but without specifics. This is vague but not "
                     "deliberately evasive. Flag at low confidence — "
                     "do not classify as evasion."
    },

    # ❌ NOT an evasion — natural topic progression
    {
        "question": "How does your team currently handle reporting?",
        "response": "We use Salesforce for most of it, and actually that "
                    "connects to what I wanted to ask about your integrations...",
        "classification": "answered",
        "confidence": 0.82,
        "reasoning": "Buyer answered the question (Salesforce) then transitioned "
                     "naturally to a related topic. This is normal conversational "
                     "flow, not deliberate evasion."
    }
]
```

> **Industry practice (Anthropic, OpenAI):** Constitutional AI and RLHF both fundamentally rely on showing models what bad outputs look like alongside good ones. The same principle applies in prompt design. A model that has never seen a null/negative example will never return one.

---

### 2.5 Explicit Uncertainty Vocabulary

Constrain the model to a defined vocabulary for expressing certainty. This maps model language to calibrated confidence scores and prevents false confidence.

```
CONFIDENCE VOCABULARY — use only these phrases:

"The transcript directly shows..."    → Verbatim quote exists      (≥ 0.85)
"The transcript suggests..."          → Strong indirect evidence   (0.70-0.84)
"There are indicators that..."        → Moderate evidence          (0.55-0.69)
"It is possible that..."              → Weak or single-point       (0.40-0.54)
[Return null, no insight]             → Insufficient evidence      (< 0.40)

FORBIDDEN phrases (express false certainty):
- "definitely", "certainly", "clearly", "obviously"
- "the buyer is lying/manipulating/stalling"
- "this means..." (without a direct quote)
- "as we can see..." (unless citing verbatim text)
```

**Example of the difference this makes:**

```
Without vocabulary constraint:
  "The buyer is clearly trying to avoid the pricing conversation.
  They are definitely not ready to buy."
  → Sounds authoritative. Is an assertion. No evidence requirement.

With vocabulary constraint:
  "There are indicators that the buyer may be avoiding the pricing 
  topic (0.67 confidence). At 23:15 and 31:02, when pricing was 
  introduced, the buyer transitioned to implementation questions."
  → Honest about uncertainty. Evidence cited. User can verify.
```

---

### 2.6 Chain-of-Thought with Mandatory Uncertainty Declaration

Force the model to reason step by step AND explicitly state its uncertainty at each step. This surfaces weak reasoning before it becomes a confident-sounding output.

```
For each piece of evidence you cite:

CLAIM: [What you're asserting]
QUOTE: [The exact verbatim text that supports this]
SEGMENT: [The segment ID of that text]
ALTERNATIVE EXPLANATIONS: [List 1-2 innocent explanations for 
    this behavior. If you can list a strong alternative, 
    lower your confidence by 0.15.]
CONFIDENCE: [0.0-1.0, adjusted for alternative explanations]

If CONFIDENCE < 0.50, do not include this in the insight output.
Include it only in the raw analysis field for debugging.
```

**Why this works:** When forced to generate alternative explanations, the model often realizes the evidence is weaker than it initially assessed. The confidence adjustment is automatic without requiring a separate critique pass.

---

## 3. Structural Architecture Patterns

### 3.1 Extractive-Before-Abstractive Pipeline

Separate fact-gathering (low hallucination risk) from interpretation (higher risk). Never mix them in the same prompt.

```
┌─────────────────────────────────────────────────────────┐
│  EXTRACTIVE PHASE                                       │
│  "What did the speakers actually say?"                  │
│  Temperature: 0.0                                       │
│  Task: Copy, identify, locate                           │
│  Output: Verified facts only                            │
│                                                         │
│  Examples:                                              │
│  • Copy all commitment statements verbatim              │
│  • List all dollar amounts mentioned                    │
│  • Extract all questions asked by the rep               │
│  • Identify segment IDs of emotional language           │
└─────────────────────────┬───────────────────────────────┘
                          │ Programmatically validated
┌─────────────────────────▼───────────────────────────────┐
│  ABSTRACTIVE PHASE                                      │
│  "What does what they said mean?"                       │
│  Temperature: 0.05-0.15                                 │
│  Task: Classify, interpret, score                       │
│  Input: Only verified facts from extractive phase       │
│                                                         │
│  Examples:                                              │
│  • Classify commitments as genuine/face-saving          │
│  • Score the quality of the rep's questions             │
│  • Detect evasion in matched question-response pairs    │
└─────────────────────────────────────────────────────────┘
```

The abstractive phase operates on text that has already been verified to exist in the transcript. It cannot hallucinate a quote because the quotes it works with were validated before it received them.

---

### 3.2 Segment-Anchored Context Windows

Instead of giving the model the full transcript (10,000+ tokens) and asking it to find things, give it only the segments relevant to the framework being run.

**Why full-transcript prompts hallucinate more:**
- Large contexts increase the chance of segment confusion (model mixes up timestamps)
- Model has more "material" to confabulate patterns from
- Attention diffuses — early segments are underrepresented

**Segment-filtered approach:**

```python
def build_focused_context(
    framework_id: str,
    segments: list[TranscriptSegment]
) -> str:
    """
    For each framework, extract only the segments that matter.
    Smaller, focused context = less hallucination.
    """
    
    if framework_id == "unanswered_questions":
        # Only question-adjacent segments: the question + next 3 segments
        return extract_qa_windows(segments, window_size=3)
    
    elif framework_id == "money_left_on_table":
        # Only pricing-discussion segments (detected by topic segmentation)
        return extract_topic_segments(segments, topic="pricing")
    
    elif framework_id == "emotional_turning_points":
        # All segments, but condensed: only speaker-turn boundaries
        # (where emotional shifts would appear)
        return extract_turn_transitions(segments)
    
    elif framework_id in ["call_structure", "commitment_trajectory"]:
        # These genuinely need the full transcript
        return format_full_transcript(segments)
    
    # Default: full transcript with section markers
    return format_full_transcript(segments)
```

> **Measured impact:** Anthropic's research on retrieval-augmented generation shows that focused, relevant context reduces hallucination rates by 30-50% compared to full-document prompting. The model can't confuse segments it wasn't given.

---

### 3.3 Temperature as a First-Class Design Decision

Temperature is not a single setting — it should be calibrated per task type.

```python
TEMPERATURE_MAP = {
    # DETERMINISTIC — zero creativity, pure extraction
    "extract_quotes":              0.0,
    "extract_timestamps":          0.0,
    "extract_dollar_amounts":      0.0,
    "identify_question_segments":  0.0,
    
    # NEAR-DETERMINISTIC — classification with defined categories
    "classify_evasion_type":       0.05,
    "classify_commitment_quality": 0.05,
    "classify_emotion_type":       0.05,
    "score_question_quality":      0.10,
    
    # CONTROLLED — interpretation with some flexibility
    "frame_match_analysis":        0.10,
    "subconversation_detection":   0.15,
    "call_structure_analysis":     0.10,
    
    # GENERATIVE — creative output is acceptable
    "generate_coaching_advice":    0.20,
    "generate_call_summary":       0.25,
    "generate_insight_headline":   0.15,
}
```

**The rule:** As the task becomes more extractive and verifiable, temperature approaches zero. As it becomes more generative and interpretive, temperature can increase — but never above 0.3 in production.

---

### 3.4 The Self-Critique Pass

A second, lightweight LLM call that reviews the first call's output with an adversarial lens. The reviewer has one job: find reasons to reject the insight.

```python
SELF_CRITIQUE_PROMPT = """
You are a skeptical fact-checker reviewing a claim about a sales call.

CLAIM: "{headline}"
CITED EVIDENCE: "{transcript_excerpt}"
SEGMENT: {segment_id} at {timestamp}

Your job is to challenge this claim, not support it.

Evaluate:
1. Does the evidence DIRECTLY support the claim, or could it be interpreted 
   differently? (Direct / Indirect / Weak)
   
2. What is the most charitable innocent explanation for this behavior?
   (e.g., "the buyer may have naturally transitioned topics, not deliberately evaded")
   
3. Is the evidence strong enough to show a manager and influence coaching?
   Answer: SHOW / DOWNGRADE / SUPPRESS
   
SHOW     = Evidence is clear and direct. Manager should see this.
DOWNGRADE = Evidence supports the claim but weakly. Show with lower confidence.
SUPPRESS  = Evidence is too weak or ambiguous. Do not show.

Be conservative. A false positive shown to a manager damages product trust
more than a real insight missed.
"""

async def apply_self_critique(insight: Insight, transcript: str) -> Insight:
    critique = await llm.complete_structured(
        system_prompt=SELF_CRITIQUE_PROMPT.format(
            headline=insight.headline,
            transcript_excerpt=insight.evidence[0].quote,
            segment_id=insight.evidence[0].segment_id,
            timestamp=insight.evidence[0].timestamp_display
        ),
        response_model=CritiqueResult
    )
    
    if critique.verdict == "SUPPRESS":
        insight.suppressed = True
        insight.suppression_reason = critique.innocent_explanation
        
    elif critique.verdict == "DOWNGRADE":
        insight.confidence *= 0.75
        insight.severity = downgrade_severity(insight.severity)
        
    return insight
```

> **When to apply it:** Not on every insight (cost and latency). Apply to 🔴 Red severity insights only — these are the ones that most directly influence manager behavior and are most damaging if wrong.

---

### 3.5 Consistency Gate — Run Twice, Compare

For your highest-stakes frameworks, run the same analysis twice at low temperature. Agreement = high reliability. Disagreement = model is uncertain, regardless of individual confidence scores.

```python
async def run_with_consistency_check(
    framework_id: str,
    transcript: str,
    model: str
) -> FrameworkResult:
    
    if framework_id not in HIGH_STAKES_FRAMEWORKS:
        # Standard single run
        return await run_framework(framework_id, transcript, model)
    
    # Run twice
    run_1, run_2 = await asyncio.gather(
        run_framework(framework_id, transcript, model),
        run_framework(framework_id, transcript, model)
    )
    
    agreement_score = compare_results(run_1, run_2)
    
    if agreement_score >= 0.85:
        # Runs agree — high reliability
        merged = merge_runs(run_1, run_2)
        merged.confidence = min(1.0, merged.confidence * 1.15)  # Boost
        return merged
        
    elif agreement_score >= 0.60:
        # Runs partially agree — moderate reliability
        merged = merge_runs(run_1, run_2)
        merged.headline += " (verify — mixed signals detected)"
        return merged
        
    else:
        # Runs disagree significantly — model is uncertain
        # Do not amplify the model's own uncertainty
        return FrameworkResult(
            framework_id=framework_id,
            severity="yellow",
            confidence=0.45,
            headline="Mixed signals — manual review recommended",
            disagreement_data={"run_1": run_1, "run_2": run_2}
        )

# Which frameworks get consistency checking?
HIGH_STAKES_FRAMEWORKS = {
    "money_left_on_table",    # Dollar amounts — wrong numbers = no credibility
    "commitment_quality",     # Deal-determining — wrong call = wrong coaching
    "subconversation_detector" # Hypothesis-based — high false positive risk
}
```

---

## 4. Hallucination Prevention Techniques

### 4.1 The Timestamp Contract

Timestamps are the most commonly hallucinated element in transcript analysis. The model has seen many examples with timestamps and will confidently generate plausible-looking ones that are wrong.

**Solution: the model never generates timestamps. Ever.**

```python
# ❌ Wrong schema — trusts the model to produce correct timestamps
class EvidenceRef(BaseModel):
    timestamp: str        # "23:15" — model-generated, unverified
    quote: str
    speaker: str

# ✅ Right schema — model provides segment ID, timestamp comes from DB
class EvidenceRef(BaseModel):
    segment_id: str       # "S_0034" — looked up in database
    quote: str            # Verified against actual segment text
    speaker: str
    # timestamp is NEVER in this schema

# Post-processing: resolve segment_id → timestamp from ground truth
def resolve_timestamps(evidence_refs: list[EvidenceRef]) -> list[ResolvedEvidence]:
    resolved = []
    for ref in evidence_refs:
        segment = db.get_segment(ref.segment_id)
        
        if not segment:
            # Segment ID doesn't exist — hallucinated reference
            log.warning(f"Hallucinated segment ID: {ref.segment_id}")
            continue
            
        resolved.append(ResolvedEvidence(
            segment_id=ref.segment_id,
            timestamp_ms=segment.start_time_ms,           # Ground truth
            timestamp_display=format_ts(segment.start_time_ms),  # "23:15"
            quote=ref.quote,
            speaker=segment.speaker_label,
            verified=True
        ))
    
    return resolved
```

The timestamp the user sees in the UI always comes from the database. It cannot be wrong because the model never generated it.

---

### 4.2 Quote Verification — Fuzzy String Matching

Every quote the model produces must be verified against the actual transcript segment.

```python
from difflib import SequenceMatcher

def verify_quote(
    claimed_quote: str,
    segment_id: str,
    transcript_segments: dict[str, TranscriptSegment]
) -> QuoteVerificationResult:
    """
    Verifies that a model-generated quote actually appears in the transcript.
    
    Returns:
        - VERIFIED: Quote closely matches actual segment text
        - PARTIAL: Quote is partially correct (model paraphrased)
        - HALLUCINATED: Quote doesn't match segment at all
    """
    
    segment = transcript_segments.get(segment_id)
    if not segment:
        return QuoteVerificationResult(
            status="HALLUCINATED",
            similarity=0.0,
            note="Segment ID does not exist in transcript"
        )
    
    similarity = SequenceMatcher(
        None,
        claimed_quote.lower().strip(),
        segment.text.lower()
    ).ratio()
    
    if similarity >= 0.80:
        return QuoteVerificationResult(status="VERIFIED", similarity=similarity)
    
    elif similarity >= 0.55:
        # Model paraphrased — replace with actual segment text
        return QuoteVerificationResult(
            status="PARTIAL",
            similarity=similarity,
            corrected_quote=segment.text,  # Use actual text instead
            note=f"Model paraphrased. Using actual segment text."
        )
    
    else:
        # Clear hallucination
        return QuoteVerificationResult(
            status="HALLUCINATED",
            similarity=similarity,
            note=f"Claimed quote ({similarity:.0%} match) does not appear in segment"
        )

# Action per status:
# VERIFIED    → Use as-is
# PARTIAL     → Replace model quote with actual segment text, slight confidence reduction
# HALLUCINATED → Suppress this evidence reference, reduce overall insight confidence
```

---

### 4.3 Minimum Evidence Requirements

Structural rules that prevent a single ambiguous moment from producing a Red insight.

```python
MINIMUM_EVIDENCE = {
    Severity.RED: {
        "min_evidence_count": 2,          # Must have 2+ independent segments
        "min_confidence": 0.75,
        "requires_verbatim_quote": True,
        "max_alternative_explanations": 0  # No strong innocent explanations allowed
    },
    Severity.ORANGE: {
        "min_evidence_count": 1,
        "min_confidence": 0.65,
        "requires_verbatim_quote": True,
        "max_alternative_explanations": 1
    },
    Severity.YELLOW: {
        "min_evidence_count": 1,
        "min_confidence": 0.50,
        "requires_verbatim_quote": False,
        "max_alternative_explanations": 2
    },
    Severity.GREEN: {
        "min_evidence_count": 1,
        "min_confidence": 0.60,
        "requires_verbatim_quote": False,
        "max_alternative_explanations": 3
    }
}

def meets_evidence_requirements(
    insight: Insight,
    severity: Severity
) -> tuple[bool, str]:
    reqs = MINIMUM_EVIDENCE[severity]
    
    verified_evidence = [e for e in insight.evidence if e.verified]
    
    if len(verified_evidence) < reqs["min_evidence_count"]:
        return False, f"Requires {reqs['min_evidence_count']} evidence segments, found {len(verified_evidence)}"
    
    if insight.confidence < reqs["min_confidence"]:
        return False, f"Confidence {insight.confidence:.2f} below threshold {reqs['min_confidence']}"
    
    if reqs["requires_verbatim_quote"] and not any(e.status == "VERIFIED" for e in verified_evidence):
        return False, "Red/Orange severity requires at least one verbatim-verified quote"
    
    return True, "OK"
```

> **Why this prevents confabulation:** A model asked to find concessions in a clean call might find one borderline moment. The minimum evidence requirement means that borderline moment cannot surface as Red — it becomes Yellow at best, with low confidence. The manager sees "possible minor issue" not "deal at risk."

---

### 4.4 Segment ID Validation Before Anything Else

Before processing any model output, run a fast existence check on all segment IDs. This is cheap (DB lookup) and catches the most dangerous hallucination immediately.

```python
def validate_segment_references(
    framework_output: dict,
    valid_segment_ids: set[str]
) -> dict:
    """
    First validation pass: check all segment IDs exist.
    This runs BEFORE any other processing.
    """
    
    def check_evidence(evidence_list: list[dict]) -> list[dict]:
        valid_evidence = []
        for ev in evidence_list:
            sid = ev.get("segment_id")
            if not sid:
                log.warning("Evidence reference missing segment_id")
                continue
            if sid not in valid_segment_ids:
                log.warning(f"Hallucinated segment ID: {sid}")
                # Do not include this evidence
                continue
            valid_evidence.append(ev)
        return valid_evidence
    
    # Check all evidence references recursively
    if "evidence" in framework_output:
        framework_output["evidence"] = check_evidence(framework_output["evidence"])
    
    # If all evidence was hallucinated, suppress the entire insight
    if framework_output.get("evidence") == []:
        framework_output["suppress"] = True
        framework_output["suppression_reason"] = "All evidence references were invalid"
    
    return framework_output
```

**This runs as the very first post-processing step.** A hallucinated segment ID is the most reliable signal that the model fabricated the entire evidence chain.

---

### 4.5 Honeypot Test Cases — Red-Teaming Your Prompts

Build a library of test transcripts specifically designed to trigger hallucinations. Run every new prompt version against these before production.

```python
HALLUCINATION_HONEYPOTS = [
    {
        "name": "clean_call_no_issues",
        "description": "A well-executed call with no red flags",
        "transcript": CLEAN_CALL_TRANSCRIPT,
        "expected": {
            "max_red_insights": 0,
            "max_orange_insights": 1,
            "min_green_insights": 1
        },
        "failure_means": "Framework is finding problems that don't exist (confabulation)"
    },
    {
        "name": "question_answered_fully",
        "description": "Rep asks budget question, buyer answers directly with specifics",
        "transcript": DIRECT_ANSWER_TRANSCRIPT,
        "expected": {
            "unanswered_questions.evaded_count": 0,
            "unanswered_questions.severity": "green"
        },
        "failure_means": "Evasion framework is too aggressive — misclassifying answers as evasions"
    },
    {
        "name": "no_concessions_made",
        "description": "Rep holds firm on pricing throughout",
        "transcript": NO_CONCESSION_TRANSCRIPT,
        "expected": {
            "money_left_on_table.unconditional_count": 0
        },
        "failure_means": "Concession framework is confabulating concessions from normal pricing discussion"
    },
    {
        "name": "timestamp_boundary_check",
        "description": "10-minute call — all timestamps must be < 10:00",
        "transcript": TEN_MINUTE_TRANSCRIPT,
        "expected_validation": lambda output: (
            all(
                parse_timestamp(ev.get("timestamp", "0:00")) < 600000
                for insight in output.get("insights", [])
                for ev in insight.get("evidence", [])
            )
        ),
        "failure_means": "Model generating timestamps beyond the actual call duration"
    },
    {
        "name": "cultural_communication_style",
        "description": "High-context communication that sounds indirect but is not evasive",
        "transcript": HIGH_CONTEXT_TRANSCRIPT,
        "expected": {
            "unanswered_questions.evaded_count": 0
        },
        "failure_means": "Framework is misreading cultural communication style as evasion"
    }
]
```

> **Industry practice (Google DeepMind):** Adversarial evaluation — deliberately trying to break your own system — is standard practice before any production deployment. The goal is to find failure modes before customers do.

---

## 5. Post-Generation Verification

### 5.1 The Verification Pipeline

Every model output passes through a deterministic verification stack before becoming visible to users.

```
LLM Output (raw)
      │
      ▼
┌─────────────────────────────────────────┐
│  GATE 1: Schema Validation              │
│  Tool: Pydantic + Instructor            │
│  Catches: Structural errors, missing    │
│           required fields               │
│  On fail: Retry with stricter prompt    │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 2: Segment ID Existence           │
│  Tool: Database lookup                  │
│  Catches: Hallucinated segment refs     │
│  On fail: Remove invalid evidence refs  │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 3: Quote Fuzzy Match              │
│  Tool: SequenceMatcher (> 0.75)         │
│  Catches: Fabricated or wrong quotes    │
│  On fail: Replace with actual text or   │
│           reduce confidence             │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 4: Timestamp Resolution           │
│  Tool: DB lookup from segment_id        │
│  Catches: Model-generated timestamps    │
│  Action: Replace all timestamps from DB │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 5: Minimum Evidence Check         │
│  Tool: Evidence count + confidence      │
│  Catches: Single-signal Red insights    │
│  On fail: Downgrade severity or         │
│           suppress entirely             │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 6: Self-Critique Pass             │
│  Tool: Second LLM call (adversarial)    │
│  Applies to: Red insights only          │
│  Catches: Weak evidence dressed as      │
│           strong findings               │
│  On fail: Suppress or downgrade         │
└─────────────────────────┬───────────────┘
                          │
                          ▼
┌─────────────────────────────────────────┐
│  GATE 7: Cross-Framework Consistency    │
│  Tool: Post-processing synthesis        │
│  Catches: Isolated findings with no     │
│           corroboration                 │
│  Action: Boost if corroborated,         │
│          reduce if contradicted         │
└─────────────────────────┬───────────────┘
                          │
                          ▼
                   Verified Insight
                 (safe to show user)
```

---

### 5.2 Calibrated Confidence from Verifiable Components

Never ask the model "how confident are you?" That produces uncalibrated scores. Build confidence from verifiable sub-signals.

```python
class CalibratedConfidence:
    """
    Confidence computed from measurable evidence quality,
    not from the model's self-assessment.
    """
    
    evidence_count: int            # Number of verified segments
    quote_verification_score: float  # Average fuzzy match score
    alternative_explanations: int    # Number of innocent explanations
    pattern_recurrence: int          # How many times does pattern appear?
    cross_framework_agreement: int   # How many frameworks agree?
    
    def compute(self) -> float:
        score = 0.40  # Base score
        
        # More verified evidence = more confidence
        score += min(0.20, self.evidence_count * 0.07)
        
        # Higher quote quality = more confidence
        score += (self.quote_verification_score - 0.75) * 0.15
        
        # More recurrence = more confidence (patterns beat single instances)
        score += min(0.15, (self.pattern_recurrence - 1) * 0.08)
        
        # Alternative explanations reduce confidence
        score -= self.alternative_explanations * 0.08
        
        # Cross-framework agreement boosts confidence
        score += self.cross_framework_agreement * 0.05
        
        return max(0.0, min(1.0, score))

# Example:
confidence = CalibratedConfidence(
    evidence_count=3,              # +0.21
    quote_verification_score=0.88, # +0.02
    alternative_explanations=1,    # -0.08
    pattern_recurrence=2,          # +0.08
    cross_framework_agreement=1    # +0.05
).compute()
# = 0.40 + 0.21 + 0.02 + 0.08 - 0.08 + 0.05 = 0.68
```

---

## 6. Evaluation Infrastructure

### 6.1 The Golden Dataset

A set of manually annotated calls where a human has determined the correct output for every framework. The ground truth that everything is measured against.

```python
# Golden dataset entry structure
@dataclass
class GoldenEntry:
    call_id: str
    transcript: str
    expected_outputs: dict[str, FrameworkOutput]
    
    # The human annotation
    annotator_notes: str
    annotation_date: str
    
    # Edge case classification
    is_edge_case: bool
    edge_case_type: Optional[str]  # "natural_topic_transition", "cultural_style", etc.

GOLDEN_DATASET = [
    GoldenEntry(
        call_id="golden_001",
        transcript=PRICING_CALL_TRANSCRIPT,
        expected_outputs={
            "unanswered_questions": FrameworkOutput(
                evaded_count=2,
                severity="red",
                evidence_segments=["S_0034", "S_0078"]
            ),
            "money_left_on_table": FrameworkOutput(
                unconditional_count=1,
                estimated_value_usd=18000,
                severity="orange"
            )
        },
        annotator_notes="Clear budget authority evasion at S_0034, S_0078. "
                        "Single unconditional discount at S_0091.",
        edge_case_type=None
    ),
    
    # Edge case: natural topic transition that looks like evasion
    GoldenEntry(
        call_id="golden_005",
        transcript=NATURAL_TRANSITION_TRANSCRIPT,
        expected_outputs={
            "unanswered_questions": FrameworkOutput(
                evaded_count=0,     # ← The model often gets this wrong
                severity="green"
            )
        },
        annotator_notes="Rep asked about timeline. Buyer answered with a range "
                        "then naturally moved to a related topic. This is NOT evasion.",
        is_edge_case=True,
        edge_case_type="natural_topic_transition"
    )
]
```

**Minimum dataset size:** 5 calls to start, expanding to 20+ over time. Each negative feedback event that's clearly correct becomes a new golden entry — the dataset grows organically from usage.

---

### 6.2 Promptfoo Evaluation Configuration

```yaml
# eval_unanswered_questions.yaml
description: "Evaluation suite for Unanswered Questions framework v1"

prompts:
  - file://prompts/group_b/unanswered_questions_v1.py
  - file://prompts/group_b/unanswered_questions_v2.py  # New version being tested

providers:
  - id: anthropic:claude-sonnet-4-20250514
    config:
      temperature: 0.05

tests:
  - description: "Detects clear budget authority evasion"
    vars:
      transcript: "{{golden_001_transcript}}"
      pass1_output: "{{golden_001_pass1}}"
    assert:
      - type: javascript
        value: |
          const output = JSON.parse(output);
          return output.evaded_count === 2
               && output.severity === "red"
               && output.evidence.some(e => e.segment_id === "S_0034")
               && output.evidence.some(e => e.segment_id === "S_0078");
        
  - description: "Does NOT flag natural topic transitions as evasion"
    vars:
      transcript: "{{golden_005_transcript}}"
    assert:
      - type: javascript
        value: |
          const output = JSON.parse(output);
          // This is the critical regression test
          return output.evaded_count === 0 && output.severity === "green";

  - description: "Returns null on clean call with no evasion"
    vars:
      transcript: "{{clean_call_transcript}}"
    assert:
      - type: javascript
        value: |
          const output = JSON.parse(output);
          return output.evaded_count === 0;

# Regression gate: if any metric drops by >5% vs. baseline, block deployment
threshold:
  precision: 0.80
  recall: 0.75
  f1: 0.77
```

---

### 6.3 Metrics That Actually Matter

```python
class FrameworkEvalMetrics:
    """
    Evaluation metrics for a single framework across the golden dataset.
    """
    
    # Standard ML metrics
    precision: float    # Of all insights surfaced, what % were correct?
    recall: float       # Of all real issues in golden dataset, what % were found?
    f1: float          # Harmonic mean — the single number to optimize
    
    # Signal-specific metrics
    evidence_accuracy: float     # Do cited segments contain the claimed behavior?
    severity_accuracy: float     # Was severity correctly classified?
    confidence_calibration: float  # Does the confidence score predict correctness?
    
    # Business impact metrics
    false_positive_rate: float   # How often does it fire when nothing is there?
    false_negative_rate: float   # How often does it miss real issues?
    
    def regression_gate(self, baseline: "FrameworkEvalMetrics") -> bool:
        """
        Returns True if this version can be deployed.
        Any metric that drops >5% from baseline = blocked.
        """
        metrics = ["precision", "recall", "f1", "evidence_accuracy", "severity_accuracy"]
        for metric in metrics:
            current = getattr(self, metric)
            base = getattr(baseline, metric)
            if current < base * 0.95:  # >5% drop
                print(f"BLOCKED: {metric} dropped from {base:.2f} to {current:.2f}")
                return False
        return True
```

---

## 7. Industry Approaches

### 7.1 How Major Companies Handle LLM Reliability

| Company | Product | Approach | Key Technique |
|---------|---------|----------|---------------|
| **Anthropic** | Claude | Constitutional AI + RLHF | Model trained to critique its own outputs before finalizing |
| **Microsoft** | Azure OpenAI | Azure AI Content Safety | Separate classifier validates model output before delivery |
| **Google DeepMind** | Gemini | Chain-of-thought + tool use | Forces reasoning trace, uses tools for fact retrieval not memory |
| **Perplexity AI** | Search | Citation-first architecture | Every claim must have a retrievable citation; uncited claims blocked |
| **Cursor** | Code editor | Multi-model verification | Code suggestions verified by a separate model for correctness |
| **Harvey AI** | Legal | Human-in-the-loop + retrieval | High-stakes claims always grounded in retrieved documents, not model memory |
| **Glean** | Enterprise search | RAG with source attribution | Model never answers from memory; always retrieves source first |

---

### 7.2 Retrieval-Augmented Generation (RAG) — The Most Widely Adopted Pattern

The most common industry solution to hallucination: **don't ask the model to remember things; ask it to analyze things you give it**.

For Signal, RAG means: the model does not recall what a "typical sales evasion sounds like" from training data. It receives the exact transcript segments and classifies what it sees.

```
Traditional LLM:
  Question → Model's memory → Answer
  Hallucination risk: HIGH (model fills gaps from training data)

RAG Pattern:
  Question → Retrieve relevant segments → Model + segments → Answer
  Hallucination risk: LOW (model reasons over provided text, not memory)
```

Signal's architecture is naturally RAG-compatible — every analysis prompt includes the actual transcript. The additional step is making this explicit: **block all paths where the model might be reasoning from general knowledge rather than the provided text**.

---

### 7.3 Constitutional AI (Anthropic) — Applied to Prompt Engineering

Anthropic's Constitutional AI trains models using a set of principles that guide self-critique. The same principle can be applied at the prompt level.

**The technique applied to Signal's prompts:**

```
BEHAVIORAL CONSTITUTION FOR THIS ANALYSIS:

Before generating any insight, check your output against these principles:

1. EVIDENCE PRINCIPLE: Every claim has a verbatim quote from the transcript.
   If this principle is violated, remove the claim.
   
2. HUMILITY PRINCIPLE: Where evidence is weak, say so explicitly.
   "Possible" is more honest than "indicates." Use it.
   
3. NULL PRINCIPLE: No insight is better than a wrong insight.
   If you cannot find clear evidence, return null.
   
4. ALTERNATIVE PRINCIPLE: For every pattern you detect, generate
   the most charitable innocent explanation. If it's plausible,
   reduce your confidence.
   
5. IMPACT PRINCIPLE: This analysis influences how a manager coaches
   a real person. False positives have real consequences.
   Default to caution.

Self-check: Before producing your final output, verify each insight
against all 5 principles. Remove any that fail.
```

This in-prompt constitution functions similarly to how Constitutional AI guides model behavior — but at the prompt level, no fine-tuning required.

---

### 7.4 The "Least Privilege" Prompt Pattern

From security engineering: give the model only what it needs to do its specific task. No more.

```python
# ❌ Over-privileged prompt (gives model too much context, too many tasks)
prompt = f"""
You are an expert sales coach with deep knowledge of behavioral psychology,
sales methodologies (SPIN, MEDDIC, Challenger), negotiation theory, and
communication science.

Here is a complete sales call transcript:
{full_transcript}  # 8,000 tokens

Analyze everything. Find all issues. Generate comprehensive coaching.
"""

# ✅ Least-privilege prompt (narrow task, relevant context only)
prompt = f"""
You are analyzing question-response pairs from a sales call.
Your only task: determine if the buyer answered each question.
You have no other role.

Here are the relevant transcript segments:
{qa_pairs_only}  # 800 tokens — only the relevant pairs

For each pair: answered / vague / evaded / counter_question.
Nothing else. No coaching. No analysis. No interpretation beyond classification.
"""
```

The narrow prompt:
- Has less surface area for the model to confabulate
- Has a specific, verifiable output format
- Cannot be sidetracked into "helpful" extra analysis
- Runs in a fraction of the tokens

---

### 7.5 Human-in-the-Loop at the Right Granularity

Not all decisions need human verification. The industry standard is calibrated human review based on stakes and uncertainty.

```
┌────────────────────────────────────────────────────────────┐
│                HUMAN REVIEW DECISION MATRIX                │
├──────────────────────┬───────────────────────────────────  │
│ High Stakes +        │                                      │
│ Low Confidence       │  HUMAN REVIEW REQUIRED               │
│                      │  (e.g., Red insight, conf < 0.65)    │
├──────────────────────┼──────────────────────────────────────┤
│ High Stakes +        │                                      │
│ High Confidence      │  SHOW WITH FEEDBACK BUTTONS          │
│                      │  (Red insight, conf > 0.80)          │
├──────────────────────┼──────────────────────────────────────┤
│ Low Stakes +         │                                      │
│ Low Confidence       │  SHOW IN FULL RESULTS ONLY           │
│                      │  (Yellow insight, conf < 0.65)       │
├──────────────────────┼──────────────────────────────────────┤
│ Low Stakes +         │                                      │
│ High Confidence      │  SHOW AUTOMATICALLY                  │
│                      │  (Yellow/Green, conf > 0.70)         │
└──────────────────────┴──────────────────────────────────────┘
```

For Signal: thumbs up/down on insight cards is the human-in-the-loop mechanism. The feedback is not just for UX — it's the primary mechanism for expanding the golden dataset and identifying where the pipeline fails.

---

## 8. The Complete Reliability Stack

### 8.1 Everything Together

```python
async def run_reliable_analysis(
    call_id: str,
    transcript_segments: list[TranscriptSegment],
    frameworks: list[str],
    config: PipelineConfig
) -> list[VerifiedInsight]:
    
    # ── PASS 1: Infrastructure (shared signals) ──────────────────
    pass1_result = await run_pass1(transcript_segments)
    
    # ── PASS 2: Framework Analysis ───────────────────────────────
    raw_results = await asyncio.gather(*[
        run_framework_with_reliability(
            framework_id=fw,
            segments=filter_segments_for_framework(fw, transcript_segments),
            pass1=pass1_result,
            config=config
        )
        for fw in frameworks
    ])
    
    # ── POST-PROCESSING: Verification Stack ──────────────────────
    verified_insights = []
    
    for raw in raw_results:
        if raw is None:
            continue
        
        # Gate 1: Schema validation (Pydantic)
        # → Already enforced by Instructor at generation time
        
        # Gate 2: Segment ID existence
        raw = validate_segment_references(raw, valid_ids=get_valid_segment_ids(call_id))
        if raw.get("suppress"):
            continue
        
        # Gate 3: Quote verification
        raw = verify_all_quotes(raw, transcript_segments)
        
        # Gate 4: Timestamp resolution (never trust model-generated timestamps)
        raw = resolve_timestamps_from_db(raw, transcript_segments)
        
        # Gate 5: Minimum evidence requirements
        passes, reason = meets_evidence_requirements(raw, raw.severity)
        if not passes:
            raw.severity = downgrade_severity(raw.severity)
        
        # Gate 6: Self-critique (Red insights only)
        if raw.severity == Severity.RED:
            raw = await apply_self_critique(raw, transcript_segments)
        
        if not raw.suppressed:
            verified_insights.append(raw)
    
    # Gate 7: Cross-framework triangulation
    verified_insights = apply_triangulation(verified_insights)
    
    # Gate 8: Calibrated confidence (replace model confidence with computed)
    for insight in verified_insights:
        insight.confidence = compute_calibrated_confidence(insight)
    
    # Final: Filter by confidence threshold
    surfaced_insights = [
        i for i in verified_insights
        if i.confidence >= config.min_confidence_to_surface
    ]
    
    return sorted(surfaced_insights, key=lambda i: (i.severity_rank, -i.confidence))
```

---

### 8.2 The Reliability Principles (Summary)

```
1. CLOSED WORLD
   The transcript is the only truth.
   "I don't know" is always a valid answer.
   Null is better than wrong.

2. CITE BEFORE CLAIM
   Anchor every analysis in verbatim text.
   Evidence first. Interpretation second. Never the reverse.

3. NEVER TRUST MODEL TIMESTAMPS
   Timestamps always come from the database via segment IDs.
   The model identifies segments; the system resolves their time.

4. DECOMPOSE COMPLEXITY
   One prompt, one task. Chain verified outputs.
   Errors caught early don't compound downstream.

5. TEMPERATURE IS DESIGN
   Extraction: 0.0. Classification: 0.05. Interpretation: 0.10.
   Creativity only where creativity is needed.

6. MINIMUM EVIDENCE
   A single data point is not a pattern.
   Red requires two independent verified evidence segments. Always.

7. VERIFY PROGRAMMATICALLY
   Segment IDs checked against the database.
   Quotes fuzzy-matched against actual text.
   The system, not the model, is the source of truth.

8. CALIBRATE CONFIDENCE
   Don't ask the model how confident it is.
   Compute confidence from verifiable sub-signals.

9. TEST FOR ABSENCE
   Include null/negative cases in every evaluation suite.
   A model that can't return green on a clean call is confabulating.

10. MAKE FAILURE HONEST
    When uncertain: show confidence scores.
    When wrong: log it, learn from it, expand the golden dataset.
    The worst outcome is silent failure.
```

---

### 8.3 The Feedback Loop — Turning Failures into Assets

Every wrong answer is training data for making the next answer right.

```
User sees insight → thumbs down
        │
        ▼
Log: {insight_id, framework_id, prompt_version, model, call_id}
        │
        ▼
Developer reviews Langfuse trace:
  → What was the exact prompt input?
  → What was the exact model output?
  → Why did it go wrong?
        │
        ▼
Categorize the failure:
  A. Prompt ambiguity (the prompt was unclear)
  B. Missing negative example (model never saw this edge case)
  C. Confidence miscalibration (finding is real but confidence was too high)
  D. Evidence hallucination (cited text doesn't exist)
        │
        ▼
Fix:
  A → Rewrite the ambiguous part of the prompt
  B → Add this case as a negative few-shot example
  C → Adjust confidence calibration logic
  D → Tighten quote verification threshold
        │
        ▼
Add this transcript + expected output to golden dataset
        │
        ▼
Run promptfoo eval → regression gate → deploy if passes
        │
        ▼
System is now smarter for this failure mode. Forever.
```

This flywheel — negative feedback → golden dataset entry → better prompt → better output → less negative feedback — is the compounding advantage that makes the system improve with use rather than plateau at launch quality.

---

*The goal is not a perfect LLM. The goal is a system where LLM imperfection is contained, labeled honestly, and converted into improvement signal. Build the walls first. Then make them smarter.*
