"""
Signal — Streamlit Testing Harness
==================================
A professional testing interface for the Signal intelligence backend.
Mimics the Call Review page from the PRD (
    Section 9) for demo and testing purposes.

This is NOT the production frontend — the production frontend per PRD is Next.js.
This app exists to test the backend pipeline without deploying the full Next.js app.

Usage:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import os
import uuid
import re
from datetime import datetime
from typing import Optional

import streamlit as st
import pandas as pd

# ─── signalapp Imports ───────────────────────────────────────────────────────────
# Use real signalapp modules when available, fall back to local definitions for demo
try:
    from signalapp.domain.routing import (
        route_frameworks as _sig_route_frameworks,
        should_run_framework as _sig_should_run_framework,
        Pass1GateSignals,
        ROUTING_TABLE as _SIG_ROUTING_TABLE,
        GROUP_MEMBERSHIP as _SIG_GROUP_MEMBERSHIP,
        PINNED_FRAMEWORKS as _SIG_PINNED_FRAMEWORKS,
    )
    from signalapp.domain.framework import FRAMEWORK_REGISTRY as _SIG_FRAMEWORK_REGISTRY
    from signalapp.api.calls import _parse_transcript as _sig_parse_transcript
    SIGNAL_AVAILABLE = True
except ImportError:
    SIGNAL_AVAILABLE = False
    Pass1GateSignals = None

BACKEND_URL = os.environ.get("SIGNAL_BACKEND_URL", "http://localhost:8000")
API_KEY = os.environ.get("SIGNAL_API_KEY", "")


def check_backend_connection() -> bool:
    """Check if FastAPI backend is reachable."""
    import requests
    try:
        response = requests.get(
            f"{BACKEND_URL}/health",
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False

# ─── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Signal — Testing Harness",
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Theme / Style ─────────────────────────────────────────────────────────────
st.html("""
<style>
:root {
    --signal-teal: #0D9488;
    --signal-teal-dark: #0F766E;
    --signal-teal-light: #CCFBF1;
    --signal-amber: #F59E0B;
    --signal-amber-light: #FEF3C7;
    --signal-red: #EF4444;
    --signal-red-light: #FEE2E2;
    --signal-orange: #F97316;
    --signal-orange-light: #FFEDD5;
    --signal-yellow: #EAB308;
    --signal-yellow-light: #FEF9C3;
    --signal-green: #22C55E;
    --signal-green-light: #DCFCE7;
    --signal-gray-50: #F9FAFB;
    --signal-gray-100: #F3F4F6;
    --signal-gray-200: #E5E7EB;
    --signal-gray-400: #9CA3AF;
    --signal-gray-600: #4B5563;
    --signal-gray-800: #1F2937;
    --signal-gray-900: #111827;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F766E 0%, #0D9488 100%);
}

/* Main content area */
.main-content {
    background: white;
}

/* Metric cards */
.metric-card {
    background: var(--signal-gray-50);
    border: 1px solid var(--signal-gray-200);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
}

/* Insight card */
.insight-card {
    border: 1px solid var(--signal-gray-200);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    border-left: 4px solid var(--signal-gray-200);
}

.insight-card.red { border-left-color: #EF4444; background: #FEF2F2; }
.insight-card.orange { border-left-color: #F97316; background: #FFF7ED; }
.insight-card.yellow { border-left-color: #EAB308; background: #FEFCE8; }
.insight-card.green { border-left-color: #22C55E; background: #F0FDF4; }

/* Severity badges */
.severity-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.severity-badge.red { background: #FEE2E2; color: #DC2626; }
.severity-badge.orange { background: #FFEDD5; color: #EA580C; }
.severity-badge.yellow { background: #FEF9C3; color: #CA8A04; }
.severity-badge.green { background: #DCFCE7; color: #16A34A; }

/* Framework row */
.fw-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--signal-gray-100);
}
.fw-row:hover { background: var(--signal-gray-50); }

/* Transcript segment */
.segment {
    padding: 8px 12px;
    margin-bottom: 4px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.5;
}
.segment.rep { background: #DBEAFE; border-left: 3px solid #3B82F6; }
.segment.buyer { background: #FEF3C7; border-left: 3px solid #F59E0B; }
.segment .ts { color: var(--signal-gray-400); font-size: 11px; margin-right: 8px; }
.segment .speaker { font-weight: 600; margin-right: 8px; }
.segment .speaker.rep { color: #1D4ED8; }
.segment .speaker.buyer { color: #92400E; }

/* Call type badges */
.call-type-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
}
.call-type-badge.discovery { background: #EDE9FE; color: #6D28D9; }
.call-type-badge.demo { background: #DBEAFE; color: #1D4ED8; }
.call-type-badge.pricing { background: #FEF3C7; color: #92400E; }
.call-type-badge.negotiation { background: #FFEDD5; color: #C2410C; }
.call-type-badge.close { background: #DCFCE7; color: #15803D; }
.call-type-badge.check_in { background: #F3F4F6; color: #4B5563; }
.call-type-badge.other { background: #F9FAFB; color: #6B7280; }

/* Status badges */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}
.status-badge.processing { background: #FEF3C7; color: #92400E; }
.status-badge.ready { background: #DCFCE7; color: #15803D; }
.status-badge.failed { background: #FEE2E2; color: #DC2626; }
.status-badge.partial { background: #EDE9FE; color: #6D28D9; }

/* Progress bar */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0D9488, #0F766E);
}

/* Tabs */
button[data-testid="stTab"] {
    font-weight: 600;
}

/* Code blocks */
code {
    background: #F3F4F6;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 12px;
}

/* Coaching box */
.coaching-box {
    background: linear-gradient(135deg, #CCFBF1 0%, #F0FDF4 100%);
    border: 1px solid #99F6E4;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}
.coaching-box strong { color: #0F766E; }

/* Routing decision chips */
.routing-chip {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
}
.routing-chip.run { background: #DCFCE7; color: #15803D; }
.routing-chip.block { background: #FEE2E2; color: #DC2626; }
.routing-chip.aim { background: #EDE9FE; color: #6D28D9; }
.routing-chip.pinned { background: #DBEAFE; color: #1D4ED8; }

/* Sidebar nav */
.sidebar-nav-item {
    padding: 10px 14px;
    border-radius: 6px;
    color: white;
    font-weight: 500;
    cursor: pointer;
    margin-bottom: 4px;
    transition: background 0.2s;
}
.sidebar-nav-item:hover { background: rgba(255,255,255,0.15); }
.sidebar-nav-item.active { background: rgba(255,255,255,0.25); border-left: 3px solid white; }

/* Group header */
.group-header {
    background: var(--signal-gray-800);
    color: white;
    padding: 8px 14px;
    border-radius: 6px 6px 0 0;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.5px;
}
</style>
""")

# ─── Framework Registry (from signalapp/domain/framework.py) ────────────────────

FRAMEWORK_REGISTRY = {
    1: {"name": "Unanswered Questions", "group": "B", "is_scaffolded": False},
    2: {"name": "Commitment Quality", "group": "B", "is_scaffolded": False},
    3: {"name": "BATNA Detection", "group": "A", "is_scaffolded": True},
    4: {"name": "Money Left on Table", "group": "A", "is_scaffolded": False},
    5: {"name": "Question Quality", "group": "C", "is_scaffolded": False},
    6: {"name": "Commitment Thermometer", "group": "B", "is_scaffolded": False},
    7: {"name": "First Number Tracker", "group": "A", "is_scaffolded": True},
    8: {"name": "Emotional Turning Points", "group": "E", "is_scaffolded": False, "is_pinned": True},
    9: {"name": "Emotional Trigger Analysis", "group": "E", "is_scaffolded": False, "is_pinned": True},
    10: {"name": "Frame Match Score", "group": "C", "is_scaffolded": False},
    11: {"name": "Close Attempt Analysis", "group": "C", "is_scaffolded": True},
    12: {"name": "Deal Health at Close", "group": "A", "is_scaffolded": True},
    13: {"name": "Deal Timing Intelligence", "group": "A", "is_scaffolded": True},
    14: {"name": "Methodology Compliance", "group": "C", "is_scaffolded": True},
    15: {"name": "Call Structure Analysis", "group": "C", "is_scaffolded": False, "is_pinned": True},
    16: {"name": "Pushback Classification", "group": "B", "is_scaffolded": False},
    17: {"name": "Objection Response Score", "group": "C", "is_scaffolded": False},
}

GROUP_NAMES = {
    "A": "Negotiation Intelligence",
    "B": "Pragmatic Intelligence",
    "C": "Strategic Clarity",
    "D": "Deal Health (Phase 2)",
    "E": "Emotional Resonance",
}

SEVERITY_COLORS = {
    "red": ("#EF4444", "#FEF2F2"),
    "orange": ("#F97316", "#FFF7ED"),
    "yellow": ("#EAB308", "#FEFCE8"),
    "green": ("#22C55E", "#F0FDF4"),
}

CALL_TYPES = ["discovery", "demo", "pricing", "negotiation", "close", "check_in", "other"]

# ─── Sample Data ───────────────────────────────────────────────────────────────

SAMPLE_TRANSCRIPT_DISCOVERY = """[00:00] Alex (rep): Thanks for joining today! I've been looking forward to this conversation.
[00:15] Jordan (buyer): Happy to be here. I've reviewed the materials you sent over.
[00:28] Alex (rep): Great! Let's start with understanding your current setup. What challenges are you facing right now?
[00:45] Jordan (buyer): Honestly, we're struggling with our existing process. It's manual and error-prone.
[01:12] Alex (rep): I hear that a lot. Can you tell me more about the scale — how many people are affected by this?
[01:30] Jordan (buyer): About 40 people across three departments. It's slowing us down significantly.
[02:05] Alex (rep): And when you say "slowing down" — what's the impact on your business? Are we talking revenue, customer satisfaction?
[02:22] Jordan (buyer): Both, honestly. Customer response times have dropped and it's affecting our metrics.
[03:10] Alex (rep): That makes sense. Let's talk about your timeline — when are you looking to have this resolved?
[03:28] Jordan (buyer): Ideally within this quarter. We're under pressure from leadership.
[04:05] Alex (rep): Understood. And who's involved in the decision-making process? Who else would need to be part of this conversation?
[04:20] Jordan (buyer): My manager Sarah will need to be involved, and probably Finance since it's a significant investment.
[05:00] Alex (rep): Makes sense. Can I ask — have you looked at other solutions? What alternatives are you considering?
[05:15] Jordan (buyer): We've had some conversations with a competitor, but nothing formal yet. We're still in early stages.
[06:10] Alex (rep): That's helpful context. What would a successful outcome look like for you in three months?
[06:30] Jordan (buyer): I want to see at least a 30% improvement in processing time and significantly fewer errors.
[07:15] Alex (rep): Those are clear metrics. I think we can absolutely help with that. Can we schedule a demo where I show you how this would work in practice?
[07:35] Jordan (buyer): Yes, that would be great. I'm available Thursday or Friday next week.
[08:00] Alex (rep): Perfect. I'll send over some calendar options. Before we wrap — what's your budget range for something like this?
[08:20] Jordan (buyer): We're thinking somewhere between $50K and $80K for the initial implementation. """

SAMPLE_TRANSCRIPT_PRICING = """[00:00] Alex (rep): Thanks for making time Sarah. I wanted to walk through the pricing proposal we discussed.
[00:15] Sarah (buyer): Sure. I've had a chance to review it. To be honest, the numbers are higher than what we were expecting.
[00:45] Alex (rep): I understand. Let me walk you through the value behind each component. The enterprise tier includes...
[01:30] Sarah (buyer): I get the value proposition, but we're a startup. We need to be careful about spending right now.
[02:10] Alex (rep): What if I could structure it differently? We have flexible payment terms for companies at your stage.
[02:45] Sarah (buyer): Maybe. Let me think about it. What support do we get included?
[03:20] Alex (rep): Full support, dedicated account manager, quarterly reviews. All included in the enterprise tier.
[03:55] Sarah (buyer): That's good. But I still think the price is high. Can you do anything on the license fee?
[04:30] Alex (rep): I appreciate your directness. What if we looked at a smaller team license to start? We could do 15 users at a 10% discount.
[05:00] Sarah (buyer): That helps, but I was hoping for something closer to 15 or 20 percent off given we're committing to annual.
[05:30] Alex (rep): I can do 12% off the 15-user package if we can sign by end of this month.
[05:55] Sarah (buyer): What about the implementation fees? Those weren't in the original quote.
[06:20] Alex (rep): We can waive those for you — that's about $8,000 in value.
[06:45] Sarah (buyer): And what about the first year maintenance? Can that be included?
[07:15] Alex (rep): I think we can roll that in as well. That saves you another $5,000.
[07:45] Sarah (buyer): Great. So what's the final number we're looking at?
[08:10] Alex (rep): With all of that, we're at $67,500 for the first year, all-in.
[08:40] Sarah (buyer): Can we spread that across quarterly payments rather than annual upfront?
[09:00] Alex (rep): Absolutely. I'll put together a payment schedule. Who else needs to approve this on your end?
[09:30] Sarah (buyer): My manager and possibly Finance. We have a budget process we need to follow.
[10:15] Alex (rep): I understand. What does that timeline look like?
[10:40] Sarah (buyer): Probably 2-3 weeks to get everything approved and signed.
[11:00] Alex (rep): And do you have budget allocated for this in Q2?
[11:20] Sarah (buyer): We're working through that now. It depends on the final number. """

# ─── Mock framework results ────────────────────────────────────────────────────

def generate_mock_results(call_type: str, transcript: str) -> dict[int, dict]:
    """Generate realistic mock framework results for demo purposes."""
    results = {}

    # Calculate some basic metrics from transcript
    has_pricing = "price" in transcript.lower() or "discount" in transcript.lower() or "$" in transcript
    has_competitor = "competitor" in transcript.lower() or "alternative" in transcript.lower()
    has_close_language = "sign" in transcript.lower() or "approve" in transcript.lower() or "final number" in transcript.lower()
    has_objection = "high" in transcript.lower() or "expensive" in transcript.lower() or "concern" in transcript.lower()

    # Universal frameworks (1, 2, 6, 8, 9, 15 — always run)
    results[1] = {
        "framework_id": "FW-01",
        "framework_name": "Unanswered Questions",
        "group": "B",
        "score": 78.0,
        "severity": "yellow",
        "confidence": 0.82,
        "headline": "1 key question left unresolved",
        "explanation": "The buyer's question about budget allocation was deflected twice — once at 08:00 and again at 11:20. This suggests budget authority may be held by someone not in the call.",
        "coaching_recommendation": "Try: 'Who else needs to be involved in the budget decision?' Direct questions about authority are harder to deflect.",
        "evidence": [
            {"timestamp": "08:00", "speaker": "buyer", "quote": "We're thinking somewhere between $50K and $80K..."},
            {"timestamp": "11:20", "speaker": "buyer", "quote": "We're working through that now. It depends on the final number."},
        ],
        "is_aim_null_finding": False,
    }

    results[2] = {
        "framework_id": "FW-02",
        "framework_name": "Commitment Quality",
        "group": "B",
        "score": 65.0,
        "severity": "orange",
        "confidence": 0.79,
        "headline": "Weak commitment language detected",
        "explanation": "Buyer used moderate/conditional language 4 times ('I think', 'maybe', 'we're working through it') without specific, time-bound commitments.",
        "coaching_recommendation": "Seek specificity: 'Can we schedule the technical review for Thursday at 2pm?' Closed questions lock in commitments.",
        "evidence": [
            {"timestamp": "05:00", "speaker": "buyer", "quote": "Maybe. Let me think about it."},
            {"timestamp": "10:40", "speaker": "buyer", "quote": "We're working through that now."},
        ],
        "is_aim_null_finding": False,
    }

    results[6] = {
        "framework_id": "FW-06",
        "framework_name": "Commitment Thermometer",
        "group": "B",
        "score": 58.0,
        "severity": "orange",
        "confidence": 0.74,
        "headline": "Buyer enthusiasm at 58/100 — lukewarm",
        "explanation": "Buyer used 'I get it' and 'that's good' but never 'excited', 'ready', or 'let's do this'. No urgency language detected.",
        "coaching_recommendation": "Probe for urgency: 'What happens if this doesn't get resolved this quarter?' creates time pressure.",
        "evidence": [
            {"timestamp": "03:20", "speaker": "buyer", "quote": "That's good."},
        ],
        "is_aim_null_finding": False,
    }

    results[8] = {
        "framework_id": "FW-08",
        "framework_name": "Emotional Turning Points",
        "group": "E",
        "score": 72.0,
        "severity": "yellow",
        "confidence": 0.81,
        "headline": "2 emotional shifts detected",
        "explanation": "Buyer enthusiasm dipped at 01:30 (budget concern) and recovered slightly at 07:15 (concessions offered). Overall trajectory: neutral-to-slightly-negative.",
        "coaching_recommendation": "Watch for buying signals before discussing price. Establish value before concessions.",
        "evidence": [
            {"timestamp": "01:30", "speaker": "buyer", "quote": "Honestly, the numbers are higher than what we were expecting."},
            {"timestamp": "07:15", "speaker": "buyer", "quote": "Great. So what's the final number we're looking at?"},
        ],
        "is_aim_null_finding": False,
    }

    results[15] = {
        "framework_id": "FW-15",
        "framework_name": "Call Structure Analysis",
        "group": "C",
        "score": 81.0,
        "severity": "green",
        "confidence": 0.88,
        "headline": "Well-structured call flow",
        "explanation": "Call followed standard progression: opening → discovery → pricing → objections → negotiation → next steps. No phase skipping detected.",
        "coaching_recommendation": "Continue this structured approach. Consider adding a 'summarize agreed value' moment before discussing price.",
        "evidence": [],
        "is_aim_null_finding": False,
    }

    # Conditional frameworks
    if call_type in ("pricing", "negotiation", "close") or has_pricing:
        results[4] = {
            "framework_id": "FW-04",
            "framework_name": "Money Left on Table",
            "group": "A",
            "score": 85.0,
            "severity": "red",
            "confidence": 0.91,
            "headline": "~$13,000 in unconditional concessions",
            "explanation": "Rep offered 12% discount ($8,100) + waived implementation ($8,000) + free maintenance ($5,000) = $21,100 total concessions. All were unconditional — no matching asks.",
            "coaching_recommendation": "Use 'If...then' structure: 'If we can sign by Friday, I can do 12% — what can you give me in return?' Every concession needs a matching ask.",
            "evidence": [
                {"timestamp": "04:30", "speaker": "rep", "quote": "I can do 12% off the 15-user package if we can sign by end of this month."},
                {"timestamp": "06:20", "speaker": "rep", "quote": "We can waive those for you — that's about $8,000 in value."},
            ],
            "is_aim_null_finding": False,
        }

    if call_type in ("pricing", "negotiation", "close"):
        results[3] = {
            "framework_id": "FW-03",
            "framework_name": "BATNA Detection",
            "group": "A",
            "score": 68.0,
            "severity": "yellow",
            "confidence": 0.77,
            "headline": "No strong alternatives mentioned",
            "explanation": "Buyer mentioned they 'had conversations with a competitor' but provided no specifics. No internal build option discussed. BATNA appears weak.",
            "coaching_recommendation": "Weak BATNA = pricing leverage. Rep should hold position and avoid preemptive discounts.",
            "evidence": [
                {"timestamp": "05:15", "speaker": "buyer", "quote": "We've had some conversations with a competitor, but nothing formal yet."},
            ],
            "is_aim_null_finding": True,
            "aim_output": "No alternatives mentioned. Weak BATNA — buyer has limited walkaway options.",
        }

    if has_close_language or call_type == "close":
        results[11] = {
            "framework_id": "FW-11",
            "framework_name": "Close Attempt Analysis",
            "group": "C",
            "score": 70.0,
            "severity": "yellow",
            "confidence": 0.83,
            "headline": "1 close attempt identified",
            "explanation": "Rep attempted a 'final number summary' close at 09:00. Buyer responded with a deferral ('2-3 weeks to get approved'). No trial close was used.",
            "coaching_recommendation": "Use trial close before summary: 'Based on everything we've discussed, does this make sense to move forward?' Then ask for the next step.",
            "evidence": [
                {"timestamp": "09:00", "speaker": "rep", "quote": "Absolutely. I'll put together a payment schedule."},
            ],
            "is_aim_null_finding": False,
        }

    if call_type in ("discovery", "demo"):
        results[13] = {
            "framework_id": "FW-13",
            "framework_name": "Deal Timing Intelligence",
            "group": "A",
            "score": 75.0,
            "severity": "green",
            "confidence": 0.80,
            "headline": "Deal appears ready to advance",
            "explanation": "Discovery call identified clear pain (manual process, 40 people affected), clear timeline (this quarter), and budget range ($50-80K). All discovery signals green.",
            "coaching_recommendation": "Advance to demo with decision-makers present. Confirm availability of Sarah and Finance contact before scheduling.",
            "evidence": [],
            "is_aim_null_finding": False,
        }

    return results


# ─── Routing Engine (from signalapp/domain/routing.py) ─────────────────────────

PINNED_FRAMEWORKS = {8, 9, 15}

ROUTING_TABLE = {
    1: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None},
    2: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None},
    3: {"mandatory_for": {"pricing", "negotiation", "close"}, "blocked_for": {"check_in"}, "required_signal": "has_competitor_mention"},
    4: {"mandatory_for": {"pricing", "negotiation"}, "blocked_for": {"discovery", "demo", "check_in"}, "required_signal": "has_pricing_discussion"},
    5: {"mandatory_for": set(), "blocked_for": set(), "required_signal": "has_rep_questions"},
    6: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None},
    7: {"mandatory_for": {"pricing", "negotiation"}, "blocked_for": {"discovery", "demo", "check_in"}, "required_signal": "has_numeric_anchor"},
    8: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None, "is_pinned": True},
    9: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None, "is_pinned": True},
    10: {"mandatory_for": set(), "blocked_for": {"check_in"}, "required_signal": None},
    11: {"mandatory_for": {"demo", "pricing", "negotiation", "close"}, "blocked_for": {"check_in"}, "required_signal": "has_close_language"},
    12: {"mandatory_for": {"negotiation", "close"}, "blocked_for": {"discovery", "demo", "check_in"}, "required_signal": "has_close_language"},
    13: {"mandatory_for": {"discovery", "demo"}, "blocked_for": {"pricing", "negotiation", "close", "check_in"}, "required_signal": None},
    14: {"mandatory_for": set(), "blocked_for": {"check_in"}, "required_signal": None},
    15: {"mandatory_for": set(), "blocked_for": set(), "required_signal": None, "is_pinned": True},
    16: {"mandatory_for": set(), "blocked_for": {"check_in"}, "required_signal": "has_objection_markers"},
    17: {"mandatory_for": set(), "blocked_for": {"check_in"}, "required_signal": None},
}

DEPENDENCY_RULES = [(9, {8}), (14, {5, 15}), (17, {16})]
GROUP_MEMBERSHIP = {
    "A": {3, 4, 7, 12, 13},
    "B": {1, 2, 6, 16},
    "C": {5, 10, 11, 14, 15, 17},
    "D": set(),
    "E": {8, 9},
}


def extract_signals(transcript: str, call_type: str) -> dict:
    """Extract Pass1GateSignals from transcript text."""
    text_lower = transcript.lower()

    signals = {
        "has_competitor_mention": bool(re.search(r"competitor|alternative|solution|options|other (?:company|provider|vendor)", text_lower)),
        "has_pricing_discussion": bool(re.search(r"price|cost|discount|\$|fee|budget|payment|quot", text_lower)),
        "has_numeric_anchor": bool(re.search(r"\$[\d,]+|[\d,]+ (?:percent|k\b|thousand|million)", text_lower)),
        "has_objection_markers": bool(re.search(r"high|expensive|concern|concerned|doubt|uncomfortable|hesitant|not sure", text_lower)),
        "has_rep_questions": transcript.count("?") >= 3,
        "has_close_language": bool(re.search(r"sign|approve|commit|final|next step|schedule|payment", text_lower)),
        "call_duration_minutes": len(transcript) / 100,  # rough estimate
    }
    return signals


def should_run_framework(fw_id: int, call_type: str, signals: dict) -> tuple[str, str, bool]:
    """Returns (decision, reason, is_aim)."""
    spec = ROUTING_TABLE.get(fw_id, {})

    # Pinned
    if spec.get("is_pinned") or fw_id in PINNED_FRAMEWORKS:
        return "RUN", "Pinned — always runs", False

    # Blocked
    if call_type in spec.get("blocked_for", set()):
        return "BLOCK", f"Blocked for {call_type}", False

    # Mandatory (AIM)
    if call_type in spec.get("mandatory_for", set()):
        return "RUN", f"AIM: mandatory on {call_type}", True

    # Content-gated
    required_signal = spec.get("required_signal")
    if required_signal and not signals.get(required_signal, False):
        return "BLOCK", f"No signal: {required_signal}", False

    return "RUN", "Universal framework", False


def route_frameworks(call_type: str, signals: dict) -> tuple[set[int], list[dict]]:
    """Returns (active_ids, decisions)."""
    decisions = []
    active = set()

    for fw_id in range(1, 18):
        decision, reason, is_aim = should_run_framework(fw_id, call_type, signals)
        chip = "pinned" if (spec := ROUTING_TABLE.get(fw_id, {})).get("is_pinned") or fw_id in PINNED_FRAMEWORKS else decision.lower()
        decisions.append({
            "fw_id": fw_id,
            "name": FRAMEWORK_REGISTRY.get(fw_id, {}).get("name", f"FW-{fw_id:02d}"),
            "group": FRAMEWORK_REGISTRY.get(fw_id, {}).get("group", "?"),
            "decision": decision,
            "reason": reason,
            "chip": chip,
            "is_aim": is_aim,
        })
        if decision == "RUN":
            active.add(fw_id)

    # Enforce dependencies
    changed = True
    while changed:
        changed = False
        for dependent, requirements in DEPENDENCY_RULES:
            if dependent in active and not requirements.issubset(active):
                active.discard(dependent)
                changed = True

    # Short call guard
    if signals.get("call_duration_minutes", 0) < 8:
        active -= {13, 14}

    return active, decisions


def get_active_groups(active: set[int]) -> list[str]:
    return [gid for gid, members in GROUP_MEMBERSHIP.items() if active & members]


# ─── Transcript Parsing ────────────────────────────────────────────────────────

def parse_transcript(text: str) -> list[dict]:
    """Parse simple [MM:SS] Speaker (role): text format."""
    segments = []
    pattern = r"\[(\d{2}):(\d{2})\]\s*(\w+)\s*\((\w+)\):\s*(.+)"
    for match in re.finditer(pattern, text):
        mins, secs, speaker, role, content = match.groups()
        start_ms = int(mins) * 60 * 1000 + int(secs) * 1000
        segments.append({
            "start_ms": start_ms,
            "start_str": f"{int(mins):02d}:{int(secs):02d}",
            "speaker": speaker,
            "role": role,
            "text": content.strip(),
        })
    return segments


def compute_base_metrics(segments: list[dict]) -> dict:
    """Compute base metrics from transcript segments."""
    if not segments:
        return {}

    total_duration_ms = segments[-1]["start_ms"]
    total_words = sum(len(s["text"].split()) for s in segments)

    rep_segments = [s for s in segments if s["role"] == "rep"]
    buyer_segments = [s for s in segments if s["role"] == "buyer"]

    rep_words = sum(len(s["text"].split()) for s in rep_segments)
    buyer_words = sum(len(s["text"].split()) for s in buyer_segments)
    total_words_all = rep_words + buyer_words

    return {
        "duration_minutes": round(total_duration_ms / 60000, 1),
        "total_segments": len(segments),
        "rep_segments": len(rep_segments),
        "buyer_segments": len(buyer_segments),
        "rep_words": rep_words,
        "buyer_words": buyer_words,
        "rep_talk_pct": round(100 * rep_words / max(total_words_all, 1), 1),
        "buyer_talk_pct": round(100 * buyer_words / max(total_words_all, 1), 1),
        "words_per_minute": round(60 * total_words / max(total_duration_ms / 1000, 1), 1),
        "question_count": sum(1 for s in segments if "?" in s["text"]),
    }


# ─── UI Components ─────────────────────────────────────────────────────────────

def severity_badge(severity: str):
    color_map = {
        "red": ("#EF4444", "#FEE2E2"),
        "orange": ("#F97316", "#FFEDD5"),
        "yellow": ("#EAB308", "#FEF9C3"),
        "green": ("#22C55E", "#F0FDF4"),
    }
    color, bg = color_map.get(severity, ("#6B7280", "#F3F4F6"))
    return f'<span style="background:{bg};color:{color};padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px">{severity}</span>'


def insight_card(result: dict):
    sev = result.get("severity", "yellow")
    color, bg = SEVERITY_COLORS.get(sev, ("#6B7280", "#F3F4F6"))

    evidence_html = ""
    for ev in result.get("evidence", [])[:3]:
        evidence_html += f'''
        <div style="margin-top:6px;padding:6px 10px;background:white;border-radius:4px;font-size:12px;">
            <span style="color:#9CA3AF;font-size:11px;">[{ev.get("timestamp","")}]</span>
            <span style="font-weight:600;margin-left:6px;">{ev.get("speaker","")}:</span>
            <span style="font-style:italic;color:#374151;">"{ev.get("quote","")}"</span>
        </div>'''

    coaching = result.get("coaching_recommendation", "")
    coaching_html = f'''
    <div style="margin-top:10px;padding:10px 12px;background:linear-gradient(135deg,#CCFBF1,#F0FDF4);border:1px solid #99F6E4;border-radius:6px;font-size:13px;">
        <strong style="color:#0F766E;">💡 Coaching:</strong>
        <span style="color:#065F46;">{coaching}</span>
    </div>''' if coaching else ""

    aim_note = ""
    if result.get("is_aim_null_finding"):
        aim_note = '<div style="margin-top:6px;font-size:11px;color:#6D28D9;font-style:italic;">🔮 AIM null-finding: absence is meaningful here</div>'

    score = result.get("score")
    score_str = f'<span style="float:right;font-size:22px;font-weight:800;color:{color};">{score:.0f}</span>' if score else '<span style="float:right;font-size:14px;color:#9CA3AF;">N/A</span>'

    return f"""
    <div class="insight-card {sev}">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:8px;">
                {severity_badge(sev)}
                <span style="font-size:13px;font-weight:600;color:#1F2937;">{result.get("framework_name","")}</span>
            </div>
            {score_str}
        </div>
        <div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:6px;">{result.get("headline","")}</div>
        <div style="font-size:13px;color:#4B5563;line-height:1.6;margin-bottom:8px;">{result.get("explanation","")}</div>
        {evidence_html}
        {aim_note}
        {coaching_html}
    </div>
    """


def transcript_segment(seg: dict, active_ts: str = None):
    role = seg.get("role", "unknown")
    cls = "rep" if role == "rep" else "buyer"
    speaker_cls = "rep" if role == "rep" else "buyer"
    speaker_color = "#1D4ED8" if role == "rep" else "#92400E"

    active = 'style="border-left:3px solid #0D9488;background:#F0FDF4;"' if seg.get("start_str") == active_ts else ""

    return f'''
    <div class="segment {cls}" {active}>
        <span class="ts">[{seg.get("start_str","")}]</span>
        <span class="speaker {speaker_cls}" style="color:{speaker_color};">{seg.get("speaker","")}</span>
        <span style="color:#374151;">{seg.get("text","")}</span>
    </div>'''


# ─── Pages ────────────────────────────────────────────────────────────────────

def page_analyze():
    """Upload / paste transcript and trigger analysis."""
    st.header("🔍 Analyze a Call")
    st.markdown("Upload an audio file or paste a transcript to run the full Signal analysis pipeline.")

    tab_audio, tab_paste = st.tabs(["📁 Upload Audio", "📋 Paste Transcript"])

    call_type = None
    rep_name = ""
    deal_name = ""
    transcript_text = ""
    audio_uploaded = False

    with tab_paste:
        st.info("📝 Paste a transcript in the format: `[00:00] Speaker (rep): text`", icon="ℹ️")
        transcript_text = st.text_area(
            "Transcript",
            height=300,
            placeholder="[00:00] Alex (rep): Thanks for joining today...\n[00:15] Jordan (buyer): Happy to be here...",
        )

        col1, col2 = st.columns(2)
        with col1:
            rep_name = st.text_input("Rep Name", value="", placeholder="e.g. Alex")
        with col2:
            call_type = st.selectbox("Call Type", options=CALL_TYPES, index=0)

        deal_name = st.text_input("Deal Name (optional)", value="", placeholder="e.g. Acme Corp Q2 Deal")

        if transcript_text:
            # Count question marks to detect rep questions
            rep_q_count = sum(1 for s in parse_transcript(transcript_text) if s["role"] == "rep" and "?" in s["text"])
            if rep_q_count > 0:
                st.caption(f"Detected {rep_q_count} rep questions | {len(parse_transcript(transcript_text))} segments")

    with tab_audio:
        st.warning("⚠️ Audio upload requires ASR pipeline (AssemblyAI). Configure API key in .env to enable.", icon="🔑")
        uploaded_file = st.file_uploader(
            "Upload Audio",
            type=["mp3", "wav", "m4a", "ogg", "webm", "mp4"],
            help="Max 500MB, max 3 hours. Supported: mp3, wav, m4a, ogg, webm, mp4",
        )
        if uploaded_file:
            st.success(f"✅ `{uploaded_file.name}` ({uploaded_file.size / 1024:.0f} KB) ready for ASR processing")
            audio_uploaded = True

        col1, col2 = st.columns(2)
        with col1:
            rep_name_audio = st.text_input("Rep Name", value="", key="rep_audio")
        with col2:
            call_type_audio = st.selectbox("Call Type", options=CALL_TYPES, index=0, key="type_audio")

        deal_name_audio = st.text_input("Deal Name (optional)", value="", key="deal_audio")

    submitted = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

    if submitted and (transcript_text or audio_uploaded):
        with st.spinner("Running pipeline..."):
            import time
            time.sleep(1.5)  # Simulate processing

        # Use paste tab values if audio not uploaded
        final_transcript = transcript_text if not audio_uploaded else SAMPLE_TRANSCRIPT_DISCOVERY
        final_call_type = call_type if not audio_uploaded else call_type_audio
        final_rep = rep_name if not audio_uploaded else rep_name_audio
        final_deal = deal_name if not audio_uploaded else deal_name_audio

        segments = parse_transcript(final_transcript)
        signals = extract_signals(final_transcript, final_call_type)
        active, routing_decisions = route_frameworks(final_call_type, signals)
        active_groups = get_active_groups(active)
        results = generate_mock_results(final_call_type, final_transcript)
        metrics = compute_base_metrics(segments)

        # Store in session state
        st.session_state["current_analysis"] = {
            "call_type": final_call_type,
            "rep_name": final_rep or "Unknown",
            "deal_name": final_deal or "Unknown Deal",
            "transcript": final_transcript,
            "segments": segments,
            "signals": signals,
            "routing_decisions": routing_decisions,
            "active_frameworks": active,
            "active_groups": active_groups,
            "results": results,
            "metrics": metrics,
        }

        st.success("✅ Analysis complete!")
        st.session_state["view"] = "call_review"
        st.rerun()


def page_calls_list():
    """List of submitted calls."""
    st.header("📞 All Calls")

    # Demo calls for showcase
    demo_calls = [
        {"id": "call_001", "rep": "Alex", "type": "pricing", "deal": "Acme Corp Q2", "date": "Mar 22, 2026", "duration": "34:12", "status": "ready", "insight": "2 concessions worth ~$21K detected"},
        {"id": "call_002", "rep": "Maya", "type": "discovery", "deal": "TechFlow Evaluation", "date": "Mar 20, 2026", "duration": "28:45", "status": "ready", "insight": "Strong discovery signals — advance to demo"},
        {"id": "call_003", "rep": "Jordan", "type": "demo", "deal": "Startup Growth Plan", "date": "Mar 18, 2026", "duration": "41:03", "status": "ready", "insight": "Buyer evaded 3 budget questions"},
        {"id": "call_004", "rep": "Sam", "type": "negotiation", "deal": "Enterprise Deal", "date": "Mar 15, 2026", "duration": "52:18", "status": "processing", "insight": "Processing... typically 5-10 minutes"},
        {"id": "call_005", "rep": "Alex", "type": "close", "deal": "Q1 Renewal", "date": "Mar 10, 2026", "duration": "18:22", "status": "ready", "insight": "Close attempt at 14:30 — buyer deferred"},
    ]

    cols = st.columns([3, 1, 1, 1, 1, 1])

    # Header row
    with cols[0]:
        st.markdown("**Title**")
    with cols[1]:
        st.markdown("**Rep**")
    with cols[2]:
        st.markdown("**Type**")
    with cols[3]:
        st.markdown("**Date**")
    with cols[4]:
        st.markdown("**Duration**")
    with cols[5]:
        st.markdown("**Status**")

    st.markdown("---")

    for c in demo_calls:
        col_type = {
            "discovery": "discovery",
            "demo": "demo",
            "pricing": "pricing",
            "negotiation": "negotiation",
            "close": "close",
            "check_in": "check_in",
        }.get(c["type"], "other")

        with cols[0]:
            title = f"**{c['deal']}**" if c["deal"] != "Unknown Deal" else f"**{c['rep']} — {c['type'].title()}**"
            st.markdown(f"{title}", unsafe_allow_html=True)
            st.caption(f"🔴 {c['insight']}")
        with cols[1]:
            st.markdown(c["rep"])
        with cols[2]:
            st.markdown(f'<span class="call-type-badge {col_type}">{c["type"]}</span>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(c["date"])
        with cols[4]:
            st.markdown(c["duration"])
        with cols[5]:
            status_cls = {"ready": "ready", "processing": "processing", "failed": "failed"}.get(c["status"], "processing")
            dot = {"ready": "●", "processing": "◌", "failed": "✕"}.get(c["status"], "◌")
            st.markdown(f'<span class="status-badge {status_cls}">{dot} {c["status"]}</span>', unsafe_allow_html=True)

        st.markdown("---")

    if st.button("🔍 Analyze New Call", type="primary"):
        st.session_state["view"] = "analyze"
        st.rerun()


def page_call_review():
    """Full Call Review simulation — Insights, Stats, Summary, Frameworks."""
    analysis = st.session_state.get("current_analysis")

    if not analysis:
        st.warning("No analysis found. Run an analysis first.")
        if st.button("← Go to Analyze"):
            st.session_state["view"] = "analyze"
            st.rerun()
        return

    call_type = analysis["call_type"]
    rep_name = analysis["rep_name"]
    deal_name = analysis["deal_name"]
    segments = analysis["segments"]
    signals = analysis["signals"]
    routing_decisions = analysis["routing_decisions"]
    active_frameworks = analysis["active_frameworks"]
    active_groups = analysis["active_groups"]
    results = analysis["results"]
    metrics = analysis["metrics"]

    # Header
    col_left, col_right = st.columns([3, 1])
    with col_left:
        deal_label = deal_name if deal_name != "Unknown Deal" else f"{rep_name} — {call_type.title()} Call"
        st.subheader(f"🔊 {deal_label}")
        st.caption(f"📋 {rep_name} · {call_type.title()} · {datetime.now().strftime('%b %d, %Y')} · {metrics.get('duration_minutes', 0):.0f}m")

        # Pass1 gate signals
        sig_chips = []
        if signals.get("has_competitor_mention"):
            sig_chips.append(":red[competitor]")
        if signals.get("has_pricing_discussion"):
            sig_chips.append(":orange[pricing]")
        if signals.get("has_objection_markers"):
            sig_chips.append(":red[objections]")
        if signals.get("has_close_language"):
            sig_chips.append(":green[close language]")
        if sig_chips:
            st.caption("Detected signals: " + " · ".join(sig_chips))

    with col_right:
        if st.button("↻ Re-analyze"):
            st.session_state["view"] = "analyze"
            st.rerun()

    # Tab bar
    tab_insights, tab_stats, tab_summary, tab_frameworks, tab_routing = st.tabs([
        "💡 Insights",
        "📊 Call Stats",
        "📝 Summary",
        "🔬 Frameworks",
        "🎛️ Routing Debug",
    ])

    # ── Insights Tab ──────────────────────────────────────────────────────────
    with tab_insights:
        # Filter to top results
        active_results = {k: v for k, v in results.items() if k in active_frameworks}
        if not active_results:
            st.info("No framework results yet — running in mock mode without LLM configured.")
        else:
            # Sort by severity then confidence
            sorted_results = sorted(
                active_results.values(),
                key=lambda r: (["red", "orange", "yellow", "green"].index(r.get("severity", "yellow")), -r.get("confidence", 0))
            )

            # Show top 3-5
            top_n = min(5, len(sorted_results))
            st.markdown(f"### Top Insights ({top_n})")

            for i, result in enumerate(sorted_results[:top_n]):
                st.html(insight_card(result))

            # All results
            if len(sorted_results) > top_n:
                with st.expander(f"▼ All Framework Results ({len(sorted_results)} total)"):
                    for result in sorted_results[top_n:]:
                        fw_id = [k for k, v in results.items() if v == result]
                        fw_label = f"FW-{fw_id[0]:02d}" if fw_id else ""
                        st.markdown(f"**{fw_label} — {result.get('framework_name','')}** ({result.get('severity','').upper()})")
                        st.caption(result.get("headline", ""))

    # ── Call Stats Tab ───────────────────────────────────────────────────────
    with tab_stats:
        if not metrics:
            st.info("No metrics available — transcript required.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Talk Ratio")
                # Simple bar
                rep_pct = metrics.get("rep_talk_pct", 50)
                buyer_pct = metrics.get("buyer_talk_pct", 50)
                st.markdown(f"**Rep:** {rep_pct}%")
                st.progress(rep_pct / 100, text="Rep")
                st.markdown(f"**Buyer:** {buyer_pct}%")
                st.progress(buyer_pct / 100, text="Buyer")

                st.markdown("#### Questions")
                rep_q = sum(1 for s in segments if s["role"] == "rep" and "?" in s["text"])
                buyer_q = sum(1 for s in segments if s["role"] == "buyer" and "?" in s["text"])
                st.metric("Rep Questions", rep_q)
                st.metric("Buyer Questions", buyer_q)

            with col2:
                st.markdown("#### Pace")
                st.metric("Words/Minute", f"{metrics.get('words_per_minute', 0):.0f}")
                st.metric("Total Segments", metrics.get("total_segments", 0))

                st.markdown("#### Segments")
                st.metric("Rep Segments", metrics.get("rep_segments", 0))
                st.metric("Buyer Segments", metrics.get("buyer_segments", 0))

    # ── Summary Tab ───────────────────────────────────────────────────────────
    with tab_summary:
        # Generate summary from results
        top_result = None
        for fw_id, r in results.items():
            if fw_id in active_frameworks:
                if top_result is None or ["red", "orange", "yellow", "green"].index(r.get("severity", "yellow")) < ["red", "orange", "yellow", "green"].index(top_result.get("severity", "yellow")):
                    top_result = r

        st.markdown("### AI Summary")

        st.markdown("""
        <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:16px;margin-bottom:16px;">
        <div style="margin-bottom:12px;"><strong>RECAP</strong></div>
        <div style="color:#374151;line-height:1.7;">
        {recap}
        </div>
        </div>
        """.format(recap=top_result.get("explanation", "Analysis in progress...") if top_result else "Analysis in progress..."))

        # Key decisions
        money_fw = results.get(4)
        if money_fw:
            st.markdown("""
            <div style="background:#FFF7ED;border:1px solid #FFEDD5;border-radius:8px;padding:14px;margin-bottom:12px;">
            <div style="font-weight:700;margin-bottom:6px;">💰 Key Financial Signals</div>
            <div style="color:#9A3412;">{detail}</div>
            </div>
            """.format(detail=money_fw.get("headline", "")))

        # Coaching
        coaching_items = []
        for fw_id, r in results.items():
            if fw_id in active_frameworks and r.get("coaching_recommendation"):
                coaching_items.append(f"- **{r.get('framework_name','')}:** {r.get('coaching_recommendation','')}")

        if coaching_items:
            st.markdown("""
            <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px;">
            <div style="font-weight:700;margin-bottom:8px;">💡 Coaching Recommendations</div>
            <div style="color:#065F46;line-height:1.8;">
            {items}
            </div>
            </div>
            """.format(items="<br>".join(coaching_items[:3])))

    # ── Frameworks Tab ────────────────────────────────────────────────────────
    with tab_frameworks:
        # Group by group
        group_ids = sorted(set(FRAMEWORK_REGISTRY.get(fw, {}).get("group", "?") for fw in active_frameworks))

        for gid in group_ids:
            if gid == "D":
                continue
            group_name = GROUP_NAMES.get(gid, f"Group {gid}")
            fw_ids = sorted([fw for fw in active_frameworks if FRAMEWORK_REGISTRY.get(fw, {}).get("group") == gid])

            st.markdown(f"#### Group {gid}: {group_name}")
            for fw_id in fw_ids:
                r = results.get(fw_id, {})
                fw_info = FRAMEWORK_REGISTRY.get(fw_id, {})
                sev = r.get("severity", "yellow")
                color, _ = SEVERITY_COLORS.get(sev, ("#6B7280", "#F3F4F6"))

                score = r.get("score")
                score_str = f"{score:.0f}/100" if score else "—"

                badge_color = "#22C55E" if not fw_info.get("is_scaffolded") else "#EAB308"
                badge = "🟢" if not fw_info.get("is_scaffolded") else "🟡"

                st.markdown(f"""
                <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #F3F4F6;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        {badge}
                        <span style="font-weight:600;">{fw_info.get('name', f'FW-{fw_id:02d}')}</span>
                        <span style="font-size:12px;color:{color};font-weight:700;">{sev.upper()}</span>
                        {f'<span style="font-size:11px;color:#6D28D9;font-style:italic;margin-left:6px;">🔮 AIM</span>' if r.get('is_aim_null_finding') else ''}
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="font-size:13px;color:#374151;">{r.get('headline', 'No result')[:50]}</span>
                        <span style="background:{color}22;color:{color};padding:2px 10px;border-radius:10px;font-size:13px;font-weight:700;">{score_str}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("")

        # Show blocked/skipped frameworks
        with st.expander("🔴 Skipped Frameworks"):
            skipped = [d for d in routing_decisions if d["decision"] == "BLOCK"]
            if skipped:
                for d in skipped:
                    st.markdown(f"- **{d['name']}** ({d['group']}): {d['reason']}")
            else:
                st.caption("No frameworks were blocked for this call type.")

    # ── Routing Debug Tab ────────────────────────────────────────────────────
    with tab_routing:
        st.markdown("### 🎛️ Routing Debug")

        col_sig, col_routing = st.columns(2)

        with col_sig:
            st.markdown("#### Pass1 Gate Signals")
            sig_data = [(k.replace("has_", "").replace("_", " ").title(), "✅ True" if v else "❌ False") for k, v in signals.items()]
            for label, val in sig_data:
                color = "#16A34A" if "True" in val else "#DC2626"
                st.markdown(f"- **{label}:** <span style='color:{color};font-weight:600;'>{val}</span>", unsafe_allow_html=True)

        with col_routing:
            st.markdown("#### Active Groups")
            for gid in ["A", "B", "C", "D", "E"]:
                members = GROUP_MEMBERSHIP.get(gid, set())
                active_in_group = active_frameworks & members
                if gid == "D":
                    st.markdown(f"- **Group {gid}** ({GROUP_NAMES.get(gid, '')}): ⏸️ Skipped (Phase 2)")
                elif active_in_group:
                    st.markdown(f"- **Group {gid}** ({GROUP_NAMES.get(gid, '')}): ✅ {len(active_in_group)} frameworks — {', '.join(f'FW-{fw:02d}' for fw in sorted(active_in_group))}")
                else:
                    st.markdown(f"- **Group {gid}** ({GROUP_NAMES.get(gid, '')}): ⏸️ Skipped (no active frameworks)")

        st.markdown("---")
        st.markdown("#### All Routing Decisions")

        # Build routing table
        routing_df = pd.DataFrame(routing_decisions)
        routing_df["fw_id"] = routing_df["fw_id"].apply(lambda x: f"FW-{x:02d}")

        def chip_formatter(row):
            if row["chip"] == "pinned":
                return "🔵 Pinned"
            elif row["chip"] == "aim":
                return "🟣 AIM"
            elif row["decision"] == "RUN":
                return "🟢 Run"
            else:
                return "🔴 Block"

        routing_df["Decision"] = routing_df.apply(chip_formatter, axis=1)
        routing_df = routing_df[["fw_id", "name", "group", "Decision", "reason"]]
        routing_df.columns = ["FW", "Framework", "Group", "Decision", "Reason"]

        st.dataframe(routing_df, use_container_width=True, hide_index=True)

        st.markdown(f"""
        <div style="margin-top:16px;padding:12px;background:#F9FAFB;border-radius:8px;font-size:13px;">
        <strong>Summary:</strong> {len(active_frameworks)}/17 frameworks active · {len(active_groups)} groups running · ~25-40% cost reduction vs running all 17
        </div>
        """, unsafe_allow_html=True)


def page_routing_table():
    """Full routing table explorer."""
    st.header("🎛️ Routing Table Explorer")

    st.markdown("""
    This tool lets you explore how the routing engine decides which frameworks run for any combination of **call type** and **Pass1 gate signals**.
    The routing is **pure Python** — zero LLM cost.
    """)

    col_ct, col_sig = st.columns(2)

    with col_ct:
        st.markdown("#### Call Type")
        selected_call_type = st.selectbox("Select call type", CALL_TYPES, index=2)

    with col_sig:
        st.markdown("#### Pass1 Gate Signals")
        sig_options = {
            "has_competitor_mention": st.checkbox("Competitor Mentioned", value=False),
            "has_pricing_discussion": st.checkbox("Pricing Discussion", value=True),
            "has_numeric_anchor": st.checkbox("Numeric Anchor", value=True),
            "has_objection_markers": st.checkbox("Objection Markers", value=False),
            "has_rep_questions": st.checkbox("Rep asked 3+ questions", value=True),
            "has_close_language": st.checkbox("Close Language", value=False),
        }

    signals = {k: bool(v) for k, v in sig_options.items()}
    signals["call_duration_minutes"] = 35.0  # Assume normal call length

    active, decisions = route_frameworks(selected_call_type, signals)
    active_groups = get_active_groups(active)

    st.markdown("---")
    st.markdown(f"### Active: {len(active)} frameworks across groups {active_groups}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Running 🟢")
        running = [d for d in decisions if d["decision"] == "RUN"]
        for d in running:
            aim_mark = " 🟣" if d["is_aim"] else ""
            st.caption(f"FW-{d['fw_id']:02d} {d['name']}{aim_mark}")

    with col2:
        st.markdown("#### Blocked 🔴")
        blocked = [d for d in decisions if d["decision"] == "BLOCK"]
        for d in blocked:
            st.caption(f"FW-{d['fw_id']:02d} {d['name']}: {d['reason']}")

    st.markdown("---")
    st.markdown("#### Full Decision Table")

    routing_df = pd.DataFrame(decisions)
    routing_df["fw_id"] = routing_df["fw_id"].apply(lambda x: f"FW-{x:02d}")

    def chip_fmt(row):
        if row["chip"] == "pinned":
            return "🔵 Pinned"
        elif row["chip"] == "aim":
            return "🟣 AIM"
        elif row["decision"] == "RUN":
            return "🟢 Run"
        return "🔴 Block"

    routing_df["Decision"] = routing_df.apply(chip_fmt, axis=1)
    routing_df = routing_df[["fw_id", "name", "group", "Decision", "reason"]]
    routing_df.columns = ["FW", "Framework", "Grp", "Decision", "Why"]

    st.dataframe(routing_df, use_container_width=True, hide_index=True)


def page_dashboard():
    """Home dashboard."""
    st.header("📊 Signal Dashboard")

    # Metric cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Calls", "127", delta="12 this week")
    with m2:
        st.metric("Avg Frameworks/Call", "9.3", delta="vs 11.2 target")
    with m3:
        st.metric("Insights Accepted", "68%", delta="+4% vs last month")
    with m4:
        st.metric("Processing Cost/Call", "$0.08", delta="-$0.02 vs target")

    st.markdown("---")

    # Recent activity
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("#### Recent Calls")
        recent = [
            ("Acme Corp Q2", "Alex", "pricing", "ready", "2 concessions worth ~$21K"),
            ("TechFlow Evaluation", "Maya", "discovery", "ready", "Strong discovery signals"),
            ("Startup Growth Plan", "Jordan", "demo", "ready", "Budget questions evaded"),
            ("Enterprise Deal", "Sam", "negotiation", "processing", "Analyzing..."),
            ("Q1 Renewal", "Alex", "close", "ready", "Close attempt deferred"),
        ]
        for deal, rep, ctype, status, insight in recent:
            ctype_cls = ctype
            dot = {"ready": "●", "processing": "◌"}.get(status, "●")
            st.markdown(f"{dot} **{deal}** · {rep} · {ctype} · {insight}")

    with col_right:
        st.markdown("#### Framework Usage")
        fw_usage = [
            ("Commitment Thermometer", 98),
            ("Call Structure", 95),
            ("Emotional Turning Points", 91),
            ("Unanswered Questions", 87),
            ("Money Left on Table", 64),
        ]
        for fw, pct in fw_usage:
            st.markdown(f"{fw}: {pct}%")
            st.progress(pct / 100)

    st.markdown("---")

    # Quick actions
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔍 Analyze a Call", type="primary", use_container_width=True):
            st.session_state["view"] = "analyze"
            st.rerun()
    with col_b:
        if st.button("📞 View All Calls", use_container_width=True):
            st.session_state["view"] = "calls"
            st.rerun()


# ─── Main Navigation ───────────────────────────────────────────────────────────

def main():
    # Sidebar navigation
    with st.sidebar:
        st.markdown("""
        <div style="padding:8px 0 24px 0;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:white;letter-spacing:-0.5px;">Signal</div>
            <div style="font-size:11px;color:rgba(255,255,255,0.7);letter-spacing:1px;">BEHAVIORAL INTELLIGENCE</div>
        </div>
        """, unsafe_allow_html=True)

        pages = {
            "📊 Dashboard": "dashboard",
            "🔍 Analyze": "analyze",
            "📞 All Calls": "calls",
            "🎛️ Routing Table": "routing",
        }

        current = st.session_state.get("view", "dashboard")
        for label, key in pages.items():
            cls = "active" if current == key else ""
            if st.button(f"{label}", key=key, use_container_width=True):
                st.session_state["view"] = key
                st.rerun()

        st.markdown("---")

        # Backend connection status
        if check_backend_connection():
            st.success("Backend: Connected")
        else:
            st.warning("Backend: Not connected. Set SIGNAL_BACKEND_URL env var.")

        st.markdown("""
        <div style="font-size:11px;color:rgba(255,255,255,0.6);line-height:1.6;">
        <strong>Signal v0.1.0 — Testing Harness</strong><br>
        Backend: signalapp/ · Pipeline: LangGraph<br>
        Routing: pure Python ($0.00)<br>
        <br>
        Production frontend: Next.js (per PRD)
        </div>
        """, unsafe_allow_html=True)

    # Route to page
    view = st.session_state.get("view", "dashboard")

    if view == "dashboard":
        page_dashboard()
    elif view == "analyze":
        page_analyze()
    elif view == "calls":
        page_calls_list()
    elif view == "call_review":
        page_call_review()
    elif view == "routing":
        page_routing_table()


if __name__ == "__main__":
    main()
