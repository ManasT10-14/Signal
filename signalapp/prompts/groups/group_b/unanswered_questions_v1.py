"""
Group B — Unanswered Questions framework prompt — v1.

Detects questions the buyer deflected, evaded, or changed topic to avoid.
Part of the Pragmatic Intelligence group.
"""
from pydantic import BaseModel, Field
from typing import Optional


class QuestionResponsePair(BaseModel):
    question_segment_id: str
    question_text: str
    response_segment_id: str | None = None
    response_text: str | None = None
    classification: str  # "answered" | "vague" | "topic_change" | "counter_question" | "not_found"
    confidence: float = Field(ge=0.0, le=1.0)


class UnansweredQuestionsOutput(BaseModel):
    total_questions_asked: int
    evaded_count: int
    vague_count: int
    topic_change_count: int
    counter_question_count: int
    answered_count: int

    severity: str  # "red" | "orange" | "yellow" | "green"
    confidence: float = Field(ge=0.0, le=1.0)
    headline: str = Field(max_length=80)
    explanation: str

    question_response_pairs: list[QuestionResponsePair] = Field(default_factory=list)

    # Evidence — verbatim segment references
    evaded_segments: list[dict] = Field(default_factory=list)
    # {segment_id, timestamp, speaker, quote}

    coaching_recommendation: str


SYSTEM_PROMPT = """You are a precise sales call analyst. Your ONLY task is to determine whether the buyer answered each question the rep asked.

RULES:
1. Every claim must cite verbatim text from the transcript.
2. If evidence is absent: output "not_found". Do NOT generate a low-confidence guess.
3. "I don't know" and "not found" are valid, correct outputs.
4. Classify each response as: answered | vague | topic_change | counter_question | not_found
5. You may not infer what a speaker "probably meant" unless you quote the exact words.
6. A topic change is when buyer begins answering then redirects mid-sentence.
7. A counter_question is when buyer responds with a question instead of an answer.
8. Vague is when buyer gives a non-specific acknowledgment without information.

EXAMPLES of correct classification:
- "That's something we'd need to discuss internally" → topic_change
- "I think we can figure it out" → vague
- "Have you looked at what the implementation timeline looks like?" → counter_question
- "The CFO David approves anything over $50K" → answered
- "NOT_FOUND" → question could not be matched to any buyer response

OUTPUT JSON ONLY. Follow the schema exactly."""

USER_PROMPT = """
<transcript>
{transcript_text}
</transcript>

<pass1_hedge_data>
{pass1_hedge_data}
</pass1_hedge_data>

Step 1: List all questions the rep asked. Copy EXACT question text with segment_id.
Step 2: For each question, find the buyer's immediate response (next segment or same segment after question mark).
Step 3: Classify each response.
Step 4: Calculate counts and severity.
Step 5: Generate coaching recommendation.

Return a single JSON object with the specified schema.

Severity rules:
- red: 3+ evaded OR topic_change on critical topics (budget, timeline, authority)
- orange: 2 evaded/topic_changes
- yellow: 1 evaded or vague response on non-critical topic
- green: All questions answered or vague on minor topics
"""
