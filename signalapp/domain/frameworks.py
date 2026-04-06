"""Authoritative framework names and descriptions for all 17 Phase 1 frameworks."""

FRAMEWORK_NAMES: dict[int, str] = {
    1: "Unanswered Questions",
    2: "Commitment Quality",
    3: "BATNA Detection",
    4: "Money Left on Table",
    5: "Question Quality",
    6: "Commitment Thermometer",
    7: "First Number Tracker",
    8: "Emotional Turning Points",
    9: "Emotional Trigger Analysis",
    10: "Frame Match Score",
    11: "Close Attempt Analysis",
    12: "Deal Health at Close",
    13: "Deal Timing Intelligence",
    14: "Methodology Compliance",
    15: "Call Structure Analysis",
    16: "Pushback Classification",
    17: "Objection Response Score",
}

FRAMEWORK_DESCRIPTIONS: dict[int, str] = {
    1: "Questions the buyer deflected, evaded, or changed topic to avoid",
    2: "Whether buyer commitments are genuine, face-saving, or deflecting",
    3: "Buyer's alternatives and walkaway strength; bluff probability",
    4: "Unconditional concessions and estimated dollar impact left on the table",
    5: "Rep question types — diagnostic vs. leading vs. rhetorical",
    6: "Scalar implicature accuracy — 'good' ≠ 'excellent' on a 0–100 scale",
    7: "Who anchored first on pricing; anchor relative to target",
    8: "Moments where emotional state shifted significantly",
    9: "Why the emotion shifted — the preceding causative utterance",
    10: "Gain vs. loss framing alignment between rep and buyer",
    11: "Whether rep attempted to close; technique classification",
    12: "Churn risk based on closing moment signals",
    13: "Ripeness assessment — is the deal ready to advance?",
    14: "SPIN/MEDDIC/Challenger adherence score",
    15: "Phase progression — discovery → demo → objections → close",
    16: "Objection vs. concern vs. rejection — each needs different response",
    17: "LAER framework quality per objection handled",
}


def get_framework_name(fw_id: int) -> str:
    """Return the human-readable name for a framework ID."""
    return FRAMEWORK_NAMES.get(fw_id, f"Framework {fw_id}")


def get_framework_description(fw_id: int) -> str:
    """Return the behavioral science description for a framework."""
    return FRAMEWORK_DESCRIPTIONS.get(fw_id, "")
