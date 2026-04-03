"""
Transcript domain models — TranscriptSegment value object.
"""
from __future__ import annotations
from dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class TranscriptSegment:
    """
    A single segment of a transcript.
    Corresponds to a contiguous utterance by one speaker.
    """

    segment_id: str  # Unique: "seg_001"
    segment_index: int  # Order: 0, 1, 2, ...
    speaker_name: str  # "Rahul" or "Buyer"
    speaker_role: str  # "rep" | "buyer" | "unknown"
    start_time_ms: int  # milliseconds
    end_time_ms: int
    text: str  # Cleaned text
    word_count: int

    def to_llm_format(self) -> str:
        """Format for LLM prompts: [timestamp] Speaker: text"""
        mins, secs = divmod(self.start_time_ms // 1000, 60)
        timestamp = f"{mins:02d}:{secs:02d}"
        return f"[{timestamp}] {self.speaker_name} ({self.speaker_role}): {self.text}"

    def to_segment_display(self) -> str:
        """Format for UI display."""
        mins, secs = divmod(self.start_time_ms // 1000, 60)
        return f"{mins:02d}:{secs:02d} — {self.speaker_name}: {self.text}"


class Transcript(BaseModel):
    """Full transcript with segments."""

    transcript_id: str
    call_id: str
    full_text: str  # Raw concatenated text
    segments: list[TranscriptSegment]  # Parsed segments
    language: str = "en"
    asr_provider: str = "unknown"
    asr_confidence: float = 0.0

    def to_llm_input(self) -> str:
        """Format transcript for LLM consumption."""
        return "\n".join(seg.to_llm_format() for seg in self.segments)

    def get_segment_by_id(self, segment_id: str) -> TranscriptSegment | None:
        return next((s for s in self.segments if s.segment_id == segment_id), None)

    def get_valid_segment_ids(self) -> set[str]:
        return {s.segment_id for s in self.segments}
