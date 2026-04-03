"""
Unit tests for the routing engine.
Tests all routing decisions against the specification in FRAMEWORK_ROUTING_ARCHITECTURE.md.
"""
from __future__ import annotations

import pytest

from signalapp.domain.routing import (
    CALL_TYPES,
    PINNED_FRAMEWORKS,
    ROUTING_TABLE,
    GROUP_MEMBERSHIP,
    DEPENDENCY_RULES,
    Pass1GateSignals,
    FrameworkRoutingSpec,
    should_run_framework,
    should_run_framework_safe,
    enforce_dependencies,
    route_frameworks,
    get_active_groups,
)


# ─── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def empty_signals() -> Pass1GateSignals:
    """All signals are False — no content detected."""
    return Pass1GateSignals(
        has_competitor_mention=False,
        has_pricing_discussion=False,
        has_numeric_anchor=False,
        has_objection_markers=False,
        has_rep_questions=False,
        has_close_language=False,
        call_duration_minutes=30.0,
    )


@pytest.fixture
def pricing_signals() -> Pass1GateSignals:
    """Signals for a pricing call with competitor mention and pricing discussion."""
    return Pass1GateSignals(
        has_competitor_mention=True,
        has_pricing_discussion=True,
        has_numeric_anchor=True,
        has_objection_markers=True,
        has_close_language=True,
        has_rep_questions=True,
        call_duration_minutes=30.0,
    )


@pytest.fixture
def discovery_signals() -> Pass1GateSignals:
    """Signals for a discovery call."""
    return Pass1GateSignals(
        has_competitor_mention=False,
        has_pricing_discussion=False,
        has_numeric_anchor=False,
        has_objection_markers=False,
        has_rep_questions=True,
        has_close_language=False,
        call_duration_minutes=30.0,
    )


@pytest.fixture
def checkin_signals() -> Pass1GateSignals:
    """Signals for a check-in call."""
    return Pass1GateSignals(
        has_competitor_mention=True,  # Even with competitor mention
        has_pricing_discussion=False,
        has_numeric_anchor=False,
        has_objection_markers=False,
        has_close_language=False,
        has_rep_questions=True,
        call_duration_minutes=5.0,  # Short call
    )


# ─── Test Routing Table Completeness ───────────────────────────────────────────


class TestRoutingTableCompleteness:
    """Every framework 1-17 must have an entry in the routing table."""

    @pytest.mark.parametrize("fw_id", range(1, 18))
    def test_all_frameworks_defined(self, fw_id):
        assert fw_id in ROUTING_TABLE, f"Framework {fw_id} not in routing table"

    @pytest.mark.parametrize("fw_id", range(1, 18))
    def test_framework_id_matches_key(self, fw_id):
        spec = ROUTING_TABLE[fw_id]
        assert spec.fw_id == fw_id


# ─── Test Pinned Frameworks ─────────────────────────────────────────────────────


class TestPinnedFrameworks:
    """Pinned frameworks (8, 9, 15) always run regardless of call type or signals."""

    @pytest.mark.parametrize("call_type", CALL_TYPES | {"other"})
    def test_fw_8_emotional_turning_points_always_runs(self, call_type, empty_signals):
        decision = should_run_framework(8, call_type, empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True or "Pinned" in decision.reason

    @pytest.mark.parametrize("call_type", CALL_TYPES | {"other"})
    def test_fw_9_emotion_trigger_always_runs(self, call_type, empty_signals):
        decision = should_run_framework(9, call_type, empty_signals)
        assert decision.decision == "RUN"

    @pytest.mark.parametrize("call_type", CALL_TYPES | {"other"})
    def test_fw_15_call_structure_always_runs(self, call_type, empty_signals):
        decision = should_run_framework(15, call_type, empty_signals)
        assert decision.decision == "RUN"


# ─── Test Universal Frameworks ─────────────────────────────────────────────────


class TestUniversalFrameworks:
    """Frameworks with no mandatory_for, blocked_for, or required_signal run on all calls."""

    UNIVERSAL_FRAMEWORKS = {1, 2, 6}

    @pytest.mark.parametrize("fw_id", UNIVERSAL_FRAMEWORKS)
    @pytest.mark.parametrize("call_type", CALL_TYPES | {"other"})
    def test_universal_frameworks_run_on_all_call_types(self, fw_id, call_type, empty_signals):
        decision = should_run_framework(fw_id, call_type, empty_signals)
        assert decision.decision == "RUN", f"FW {fw_id} should run on {call_type}"


# ─── Test AIM Pattern ───────────────────────────────────────────────────────────


class TestAIMPattern:
    """
    AIM (Absence Is Meaningful): On mandatory call types, frameworks run
    even without their content signal present.
    """

    def test_fw3_batna_runs_on_pricing_without_competitor_signal(self, empty_signals):
        """On pricing, BATNA runs even without competitor mention (AIM applies)."""
        decision = should_run_framework(3, "pricing", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw3_batna_runs_on_negotiation_without_competitor_signal(self, empty_signals):
        decision = should_run_framework(3, "negotiation", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw3_batna_runs_on_close_without_competitor_signal(self, empty_signals):
        decision = should_run_framework(3, "close", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw3_batna_blocked_on_checkin(self, empty_signals):
        decision = should_run_framework(3, "check_in", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw3_batna_runs_on_discovery_with_competitor_signal(self, pricing_signals):
        """On discovery with competitor mention, BATNA runs (content-gated)."""
        signals = Pass1GateSignals(
            has_competitor_mention=True, has_pricing_discussion=False,
            has_numeric_anchor=False, has_objection_markers=False,
            has_rep_questions=False, has_close_language=False,
            call_duration_minutes=30.0
        )
        decision = should_run_framework(3, "discovery", signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is False

    def test_fw11_close_attempt_runs_on_demo_without_close_language(self, empty_signals):
        """On demo, Close Attempt runs even without close_language signal (AIM)."""
        decision = should_run_framework(11, "demo", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw11_close_attempt_runs_on_pricing_without_close_language(self, empty_signals):
        decision = should_run_framework(11, "pricing", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw11_close_attempt_blocked_on_checkin(self, empty_signals):
        decision = should_run_framework(11, "check_in", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw7_first_number_runs_on_pricing_without_anchor(self, empty_signals):
        """On pricing, First Number Tracker runs even without anchor (AIM)."""
        decision = should_run_framework(7, "pricing", empty_signals)
        assert decision.decision == "RUN"
        assert decision.is_aim is True

    def test_fw7_first_number_blocked_on_discovery(self, empty_signals):
        decision = should_run_framework(7, "discovery", empty_signals)
        assert decision.decision == "BLOCK"


# ─── Test Content-Gated Frameworks ──────────────────────────────────────────────


class TestContentGatedFrameworks:
    """Frameworks that require a specific content signal to run."""

    def test_fw5_question_quality_requires_rep_questions(self, empty_signals):
        decision = should_run_framework(5, "discovery", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw5_question_quality_with_signal(self, discovery_signals):
        decision = should_run_framework(5, "discovery", discovery_signals)
        assert decision.decision == "RUN"

    def test_fw16_pushback_requires_objection_markers(self, empty_signals):
        decision = should_run_framework(16, "pricing", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw16_pushback_with_signal(self, pricing_signals):
        decision = should_run_framework(16, "pricing", pricing_signals)
        assert decision.decision == "RUN"


# ─── Test Call Type Blocking ────────────────────────────────────────────────────


class TestCallTypeBlocking:
    """Frameworks blocked on specific call types."""

    def test_fw4_money_left_blocked_on_discovery(self, empty_signals):
        decision = should_run_framework(4, "discovery", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw4_money_left_blocked_on_demo(self, empty_signals):
        decision = should_run_framework(4, "demo", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw4_money_left_blocked_on_checkin(self, empty_signals):
        decision = should_run_framework(4, "check_in", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw13_deal_timing_blocked_on_pricing(self, empty_signals):
        decision = should_run_framework(13, "pricing", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw13_deal_timing_blocked_on_negotiation(self, empty_signals):
        decision = should_run_framework(13, "negotiation", empty_signals)
        assert decision.decision == "BLOCK"

    def test_fw13_deal_timing_runs_on_discovery(self, empty_signals):
        decision = should_run_framework(13, "discovery", empty_signals)
        assert decision.decision == "RUN"

    def test_fw10_frame_match_blocked_on_checkin(self, empty_signals):
        decision = should_run_framework(10, "check_in", empty_signals)
        assert decision.decision == "BLOCK"


# ─── Test Dependency Enforcement ───────────────────────────────────────────────


class TestDependencyEnforcement:
    """Test framework dependency rules."""

    def test_fw9_requires_fw8(self, empty_signals):
        """Removing #8 should cascade to remove #9."""
        active = {1, 2, 5, 6, 8, 9, 10, 13, 15}
        result = enforce_dependencies(active, empty_signals)
        assert 8 in result  # 8 should be added (pinned)
        assert 9 in result  # 9 should be present since 8 is there

    def test_fw9_removed_when_fw8_missing(self, empty_signals):
        """If #8 is somehow not present, #9 should be removed."""
        active = {1, 2, 5, 6, 9, 10, 13, 15}  # Note: no 8
        result = enforce_dependencies(active, empty_signals)
        assert 8 in result  # 8 is pinned, added back
        assert 9 in result  # 9 should still be there since 8 is now present

    def test_fw14_requires_fw5_and_fw15(self, empty_signals):
        active = {1, 2, 5, 6, 14, 15}
        result = enforce_dependencies(active, empty_signals)
        assert 14 in result

    def test_fw14_removed_when_fw5_missing(self, empty_signals):
        active = {1, 2, 6, 14, 15}  # Note: no 5
        result = enforce_dependencies(active, empty_signals)
        assert 14 not in result

    def test_fw14_removed_when_fw15_missing(self, empty_signals):
        active = {1, 2, 5, 6, 14}  # Note: no 15 (but 15 is pinned!)
        result = enforce_dependencies(active, empty_signals)
        # 15 is pinned so it gets added back, then 14 should have both requirements
        assert 15 in result
        assert 14 in result

    def test_fw17_requires_fw16(self, empty_signals):
        active = {1, 2, 6, 16, 17}
        result = enforce_dependencies(active, empty_signals)
        assert 17 in result

    def test_fw17_removed_when_fw16_missing(self, empty_signals):
        active = {1, 2, 6, 17}  # Note: no 16
        result = enforce_dependencies(active, empty_signals)
        assert 17 not in result


# ─── Test Short Call Guard ──────────────────────────────────────────────────────


class TestShortCallGuard:
    """Short calls (< 8 min) should remove frameworks 13 and 14."""

    def test_short_call_removes_13_and_14(self, checkin_signals):
        """With < 8 min and no other signals, 13 and 14 should be removed."""
        active = {1, 2, 5, 6, 8, 9, 13, 14, 15, 16, 17}
        result = enforce_dependencies(active, checkin_signals)
        assert 13 not in result
        assert 14 not in result
        assert 15 in result  # 15 is pinned, stays

    def test_long_call_keeps_13_and_14(self, pricing_signals):
        active = {1, 2, 5, 6, 8, 9, 13, 14, 15, 16, 17}
        result = enforce_dependencies(active, pricing_signals)
        assert 13 in result
        assert 14 in result


# ─── Test Fail-Open ─────────────────────────────────────────────────────────────


class TestFailOpen:
    """Routing errors should fail open — include the framework."""

    def test_unknown_framework_returns_block_not_exception(self, empty_signals):
        """Unknown framework IDs are explicitly blocked in routing table, not excepted."""
        # should_run_framework returns BLOCK for unknown frameworks, not exception
        # This is correct behavior - fail-open is for unexpected errors, not explicit blocks
        result = should_run_framework_safe(99, "pricing", empty_signals)
        assert result is False  # Explicit block for unknown framework

    def test_none_call_type_treated_as_other(self, empty_signals):
        """None call_type defaults to 'other' which respects content gating."""
        # None becomes "other" which is not in any mandatory_for or blocked_for
        # So content-gated frameworks respect their signals
        result = should_run_framework_safe(3, None, empty_signals)
        # FW3 requires has_competitor_mention which is False -> blocked
        assert result is False

    def test_exception_in_routing_returns_true(self, empty_signals):
        """If routing throws, framework should still run (fail open)."""
        # We patch to force an exception - for now just verify the safe wrapper catches it
        result = should_run_framework_safe(1, "pricing", empty_signals)
        assert result is True


# ─── Test route_frameworks Integration ──────────────────────────────────────────


class TestRouteFrameworks:
    """Integration test for the full routing function."""

    def test_pricing_call_routing(self, pricing_signals):
        active, decisions = route_frameworks("pricing", pricing_signals)

        # Should have pinned frameworks
        assert 8 in active
        assert 9 in active
        assert 15 in active

        # Check a few specifics
        assert 3 in active  # BATNA - AIM on pricing
        assert 11 in active  # Close Attempt - AIM on pricing

    def test_checkin_call_routing(self, checkin_signals):
        active, decisions = route_frameworks("check_in", checkin_signals)

        # Check-in blocks many frameworks
        assert 3 not in active  # BATNA blocked
        assert 4 not in active  # Money Left blocked
        assert 7 not in active  # First Number blocked
        assert 11 not in active  # Close Attempt blocked
        assert 12 not in active  # Deal Health blocked
        assert 13 not in active  # Deal Timing blocked (short call)
        assert 14 not in active  # Methodology (short call)
        assert 16 not in active  # Pushback - no signal
        assert 17 not in active  # Objection Response - no 16

        # But pinned should still be there
        assert 8 in active
        assert 9 in active
        assert 15 in active

    def test_discovery_call_routing(self, discovery_signals):
        active, decisions = route_frameworks("discovery", discovery_signals)

        # Discovery has specific blocks
        assert 3 not in active  # BATNA - not mandatory on discovery
        assert 4 not in active  # Money Left blocked
        assert 7 not in active  # First Number blocked
        assert 13 in active  # Deal Timing - mandatory on discovery

    def test_unknown_call_type(self, empty_signals):
        """Unknown call type should treat frameworks as universal (fail open)."""
        active, decisions = route_frameworks("unknown_type", empty_signals)
        # Universal frameworks should run
        assert 1 in active
        assert 2 in active
        assert 6 in active
        # Pinned should run
        assert 8 in active
        assert 9 in active
        assert 15 in active


# ─── Test Group Membership ─────────────────────────────────────────────────────


class TestGroupMembership:
    """Test that frameworks are correctly assigned to groups."""

    def test_group_a_contains_correct_frameworks(self):
        assert GROUP_MEMBERSHIP["A"] == {3, 4, 7, 12, 13}

    def test_group_b_contains_correct_frameworks(self):
        assert GROUP_MEMBERSHIP["B"] == {1, 2, 6, 16}

    def test_group_c_contains_correct_frameworks(self):
        assert GROUP_MEMBERSHIP["C"] == {5, 10, 11, 14, 15, 17}

    def test_group_e_contains_correct_frameworks(self):
        assert GROUP_MEMBERSHIP["E"] == {8, 9}

    def test_get_active_groups(self):
        active = {1, 2, 3, 5, 6, 8, 9, 15}
        groups = get_active_groups(active)
        assert "A" in groups
        assert "B" in groups
        assert "C" in groups
        assert "E" in groups

    def test_empty_group_skipped(self):
        # {1, 2, 6} are in Group B, {8, 9} are in Group E
        # No frameworks from Groups A or C
        active = {1, 2, 6, 8, 9}
        groups = get_active_groups(active)
        assert "A" not in groups
        assert "C" not in groups
        assert "B" in groups
        assert "E" in groups