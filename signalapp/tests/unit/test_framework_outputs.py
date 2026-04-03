"""
Unit tests for framework output schemas.
Tests that Pydantic models correctly validate framework outputs.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from signalapp.domain.framework import (
    Severity,
    EvidenceType,
    EvidenceRef,
    FrameworkOutput,
    FRAMEWORK_REGISTRY,
)


# ─── Test Severity Enum ─────────────────────────────────────────────────────────


class TestSeverityEnum:
    def test_valid_severity_values(self):
        assert Severity.RED == "red"
        assert Severity.ORANGE == "orange"
        assert Severity.YELLOW == "yellow"
        assert Severity.GREEN == "green"

    def test_severity_from_string(self):
        assert Severity("red") == Severity.RED
        assert Severity("orange") == Severity.ORANGE
        assert Severity("yellow") == Severity.YELLOW
        assert Severity("green") == Severity.GREEN

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError):
            Severity("purple")


# ─── Test EvidenceRef ───────────────────────────────────────────────────────────


class TestEvidenceRef:
    def test_valid_evidence_ref(self):
        ref = EvidenceRef(
            segment_id="seg_abc123",
            start_time_ms=12000,
            end_time_ms=15000,
            speaker="buyer",
            text_excerpt="I think we need to discuss the pricing first.",
            evidence_type=EvidenceType.SEGMENT,
        )
        assert ref.segment_id == "seg_abc123"
        assert ref.start_time_ms == 12000
        assert ref.speaker == "buyer"

    def test_evidence_ref_defaults(self):
        ref = EvidenceRef(
            segment_id="seg_123",
            start_time_ms=0,
            end_time_ms=1000,
            speaker="rep",
            text_excerpt="Hello",
        )
        assert ref.evidence_type == EvidenceType.SEGMENT


# ─── Test FrameworkOutput ──────────────────────────────────────────────────────


class TestFrameworkOutput:
    """Test FrameworkOutput Pydantic model validation."""

    def test_valid_full_output(self):
        output = FrameworkOutput(
            framework_id="FW-01-101",
            framework_name="Unanswered Questions",
            score=75.0,
            severity=Severity.ORANGE,
            confidence=0.85,
            headline="3 questions evaded by buyer",
            explanation="The buyer deflected questions about timeline, budget, and decision-making authority.",
            evidence=[
                EvidenceRef(
                    segment_id="seg_001",
                    start_time_ms=12000,
                    end_time_ms=15000,
                    speaker="buyer",
                    text_excerpt="Let me get back to you on that.",
                )
            ],
            coaching_recommendation="Practice the SPIN technique — ask diagnostic questions to uncover implicit needs before moving to commitment.",
            raw_analysis={"question_count": 3, "deflection_pattern": "defer"},
        )
        assert output.framework_id == "FW-01-101"
        assert output.score == 75.0
        assert output.severity == Severity.ORANGE
        assert output.confidence == 0.85

    def test_valid_output_without_score(self):
        """Some frameworks may not produce a numeric score."""
        output = FrameworkOutput(
            framework_id="FW-03-101",
            framework_name="BATNA Detection",
            score=None,
            severity=Severity.GREEN,
            confidence=0.72,
            headline="Weak BATNA — buyer has no stated alternatives",
            explanation="No competitor references were detected during the call.",
            evidence=[],
            coaching_recommendation="Hold pricing position — buyer lacks leverage.",
        )
        assert output.score is None
        assert output.severity == Severity.GREEN

    def test_valid_aim_null_finding_output(self):
        """AIM frameworks produce output even when nothing is found."""
        output = FrameworkOutput(
            framework_id="FW-03-101",
            framework_name="BATNA Detection",
            score=None,
            severity=Severity.GREEN,
            confidence=0.80,
            headline="No alternatives detected — weak BATNA",
            explanation="Buyer did not reference any alternatives during this call.",
            evidence=[],
            coaching_recommendation="You have leverage. Hold the pricing position.",
            is_aim_null_finding=True,
            aim_output="No alternatives detected. Buyer's BATNA appears weak.",
        )
        assert output.is_aim_null_finding is True
        assert output.aim_output is not None

    def test_score_validation(self):
        """Score must be between 0 and 100 if provided."""
        # Valid score
        output = FrameworkOutput(
            framework_id="FW-01",
            framework_name="Test",
            score=50.0,
            severity=Severity.GREEN,
            confidence=0.5,
            headline="Test",
            explanation="Test explanation",
            coaching_recommendation="Test rec",
        )
        assert output.score == 50.0

        # Score above 100 should fail validation
        with pytest.raises(ValidationError):
            FrameworkOutput(
                framework_id="FW-01",
                framework_name="Test",
                score=150.0,
                severity=Severity.GREEN,
                confidence=0.5,
                headline="Test",
                explanation="Test explanation",
                coaching_recommendation="Test rec",
            )

        # Score below 0 should fail validation
        with pytest.raises(ValidationError):
            FrameworkOutput(
                framework_id="FW-01",
                framework_name="Test",
                score=-10.0,
                severity=Severity.GREEN,
                confidence=0.5,
                headline="Test",
                explanation="Test explanation",
                coaching_recommendation="Test rec",
            )

    def test_confidence_must_be_0_to_1(self):
        """Confidence must be between 0.0 and 1.0."""
        output = FrameworkOutput(
            framework_id="FW-01",
            framework_name="Test",
            severity=Severity.GREEN,
            confidence=0.5,
            headline="Test",
            explanation="Test explanation",
            coaching_recommendation="Test rec",
        )
        assert output.confidence == 0.5

        # Invalid confidence should fail
        with pytest.raises(ValidationError):
            FrameworkOutput(
                framework_id="FW-01",
                framework_name="Test",
                severity=Severity.GREEN,
                confidence=1.5,  # Invalid - must be <= 1.0
                headline="Test",
                explanation="Test explanation",
                coaching_recommendation="Test rec",
            )

        with pytest.raises(ValidationError):
            FrameworkOutput(
                framework_id="FW-01",
                framework_name="Test",
                severity=Severity.GREEN,
                confidence=-0.1,  # Invalid - must be >= 0.0
                headline="Test",
                explanation="Test explanation",
                coaching_recommendation="Test rec",
            )

    def test_headline_max_length(self):
        """Headline should be max 80 characters."""
        # Valid short headline
        output = FrameworkOutput(
            framework_id="FW-01",
            framework_name="Test",
            severity=Severity.GREEN,
            confidence=0.5,
            headline="A" * 80,
            explanation="Test explanation",
            coaching_recommendation="Test rec",
        )
        assert len(output.headline) == 80

        # Too long headline should fail
        with pytest.raises(ValidationError):
            FrameworkOutput(
                framework_id="FW-01",
                framework_name="Test",
                severity=Severity.GREEN,
                confidence=0.5,
                headline="A" * 81,  # Exceeds max_length=80
                explanation="Test explanation",
                coaching_recommendation="Test rec",
            )

    def test_default_values(self):
        """Test default values for optional fields."""
        output = FrameworkOutput(
            framework_id="FW-01",
            framework_name="Test",
            severity=Severity.GREEN,
            confidence=0.5,
            headline="Test headline",
            explanation="Test explanation",
            coaching_recommendation="Test rec",
        )
        assert output.score is None
        assert output.evidence == []
        assert output.raw_analysis == {}
        assert output.is_aim_null_finding is False
        assert output.aim_output is None

    def test_evidence_list(self):
        """Test evidence list handling."""
        output = FrameworkOutput(
            framework_id="FW-01",
            framework_name="Test",
            severity=Severity.GREEN,
            confidence=0.5,
            headline="Test",
            explanation="Test",
            coaching_recommendation="Test",
            evidence=[
                EvidenceRef(
                    segment_id="seg_1",
                    start_time_ms=1000,
                    end_time_ms=2000,
                    speaker="buyer",
                    text_excerpt="Quote 1",
                ),
                EvidenceRef(
                    segment_id="seg_2",
                    start_time_ms=3000,
                    end_time_ms=4000,
                    speaker="rep",
                    text_excerpt="Quote 2",
                ),
            ],
        )
        assert len(output.evidence) == 2


# ─── Test FRAMEWORK_REGISTRY ───────────────────────────────────────────────────


class TestFrameworkRegistry:
    """Test that the framework registry is complete."""

    def test_all_frameworks_1_to_17_defined(self):
        """All 17 Phase 1 frameworks should be in the registry."""
        for fw_id in range(1, 18):
            assert fw_id in FRAMEWORK_REGISTRY, f"Framework {fw_id} missing from registry"

    def test_frameworks_have_required_fields(self):
        """Each framework entry should have required fields."""
        required_fields = ["name", "group", "prompt_file", "severity_threshold"]
        for fw_id, fw_data in FRAMEWORK_REGISTRY.items():
            for field in required_fields:
                assert field in fw_data, f"Framework {fw_id} missing '{field}'"

    def test_pinned_frameworks_marked(self):
        """Frameworks 8, 9, 15 should be marked as pinned."""
        assert FRAMEWORK_REGISTRY[8].get("is_pinned") is True
        assert FRAMEWORK_REGISTRY[9].get("is_pinned") is True
        assert FRAMEWORK_REGISTRY[15].get("is_pinned") is True

    def test_group_membership_matches_routing(self):
        """Framework groups should match GROUP_MEMBERSHIP from routing."""
        from signalapp.domain.routing import GROUP_MEMBERSHIP

        for group_id, expected_fw_ids in GROUP_MEMBERSHIP.items():
            if group_id == "D":  # Phase 2 - skip
                continue
            for fw_id in expected_fw_ids:
                actual_group = FRAMEWORK_REGISTRY[fw_id]["group"]
                assert actual_group == group_id, f"FW {fw_id} group mismatch: expected {group_id}, got {actual_group}"


# ─── Test Severity Transitions ───────────────────────────────────────────────────


class TestSeverityTransitions:
    """Test severity level interpretation."""

    def test_severity_all_values_present(self):
        """All expected severity values should be present."""
        expected = {"red", "orange", "yellow", "green"}
        actual = {s.value for s in Severity}
        assert actual == expected

    def test_severity_string_values(self):
        """Severity string values should be lowercase."""
        for severity in Severity:
            assert severity.value == severity.value.lower()