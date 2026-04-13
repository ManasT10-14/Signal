"""
Signal — Behavioral Sales Intelligence
======================================
Dark-themed Streamlit UI. 60/40 Call Review split.
4-tab right panel (Insights, Stats, Summary, Frameworks).
Single-query dashboard for fast load times.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, date

import streamlit as st

# ── Backend config ──────────────────────────────────────────────────────────────
import os
BACKEND_URL = os.environ.get("SIGNAL_BACKEND_URL", "http://localhost:8000")

# ── Dark Theme Palette ─────────────────────────────────────────────────────────
BG_PRIMARY = "#0F1117"       # main background
BG_CARD = "#1A1D27"          # card background
BG_ELEVATED = "#232731"      # elevated surfaces
BG_INPUT = "#2A2E3A"         # input fields
BORDER = "#2E3340"           # borders
TEXT_PRIMARY = "#E8EAED"     # primary text
TEXT_SECONDARY = "#9AA0AC"   # secondary text
TEXT_MUTED = "#6B7280"       # muted text
ACCENT = "#14B8A6"           # teal primary
ACCENT_DARK = "#0F766E"      # teal dark
ACCENT_GLOW = "rgba(20,184,166,0.15)"
RED = "#EF4444"
ORANGE = "#F97316"
YELLOW = "#EAB308"
GREEN = "#22C55E"

SEV_COLORS = {
    "red":    (RED,    "#3B1C1C"),
    "orange": (ORANGE, "#3B2A1C"),
    "yellow": (YELLOW, "#3B351C"),
    "green":  (GREEN,  "#1C3B2A"),
}

CALL_TYPES = ["discovery", "demo", "pricing", "negotiation", "close", "check_in", "other"]
CALL_TYPE_DESC = {
    "discovery": "Initial exploratory conversation",
    "demo": "Product demonstration",
    "pricing": "Pricing and packaging discussion",
    "negotiation": "Active deal negotiation",
    "close": "Closing conversation",
    "check_in": "Post-sale check-in",
    "other": "Other call type",
}

# Framework group labels
FW_GROUPS = {
    "A": ("Negotiation Intelligence", ["BATNA Detection", "Money Left on Table", "First Number Tracker", "Deal Health at Close", "Deal Timing Intelligence"]),
    "B": ("Pragmatic Intelligence", ["Unanswered Questions", "Commitment Quality", "Commitment Thermometer", "Pushback Classification"]),
    "C": ("Strategic Clarity", ["Question Quality", "Frame Match Score", "Close Attempt Analysis", "Methodology Compliance", "Call Structure Analysis", "Objection Response Score"]),
    "F": ("NEPQ Methodology", ["NEPQ Methodology Analysis"]),
    "E": ("Emotional Resonance", ["Emotional Turning Points", "Emotional Trigger Analysis"]),
}
FW_NAME_TO_GROUP = {}
for gid, (_, names) in FW_GROUPS.items():
    for name in names:
        FW_NAME_TO_GROUP[name] = gid


# ── API helpers ────────────────────────────────────────────────────────────────

def api_get(path: str, timeout: float = 10.0):
    import requests
    try:
        return requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
    except Exception as e:
        return type("R", (), {"status_code": 0, "text": str(e), "json": lambda: {}})()


def api_post(path: str, json: dict, timeout: float = 120.0):
    import requests
    try:
        return requests.post(f"{BACKEND_URL}{path}", json=json, timeout=timeout)
    except Exception as e:
        return type("R", (), {"status_code": 0, "text": str(e), "json": lambda: {}})()


def backend_online() -> bool:
    return api_get("/health", timeout=3).status_code == 200


def fetch_all_calls():
    r = api_get("/api/v1/calls/", timeout=10)
    return r.json().get("calls", []) if r.status_code == 200 else []


def fetch_dashboard_summary():
    """Single-query dashboard data — no N+1."""
    r = api_get("/api/v1/insights/dashboard-summary", timeout=15)
    return r.json() if r.status_code == 200 else {}


def fetch_coaching_meta(call_id: str) -> dict:
    """Fetch coaching metadata: grade, arc, assessment, stats."""
    r = api_get(f"/api/v1/calls/{call_id}/coaching-meta", timeout=10)
    return r.json() if r.status_code == 200 else {}


def fetch_insights(call_id: str):
    r = api_get(f"/api/v1/insights/call/{call_id}", timeout=10)
    return r.json() if r.status_code == 200 else None


def fetch_metrics(call_id: str):
    r = api_get(f"/api/v1/calls/{call_id}/metrics", timeout=10)
    return r.json().get("metrics", {}) if r.status_code == 200 else {}


def fetch_transcript(call_id: str) -> list[dict]:
    r = api_get(f"/api/v1/calls/{call_id}/transcript", timeout=10)
    return r.json() if r.status_code == 200 else []


# ── Page Config & CSS ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Signal — Behavioral Intelligence",
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html(f"""
<style>
/* ── Dark Theme ── */
:root {{
    --bg: {BG_PRIMARY}; --card: {BG_CARD}; --elevated: {BG_ELEVATED};
    --border: {BORDER}; --text: {TEXT_PRIMARY}; --text-2: {TEXT_SECONDARY}; --text-m: {TEXT_MUTED};
    --accent: {ACCENT}; --accent-dark: {ACCENT_DARK};
    --red: {RED}; --orange: {ORANGE}; --yellow: {YELLOW}; --green: {GREEN};
}}
.stApp {{ background: {BG_PRIMARY} !important; color: {TEXT_PRIMARY}; }}
[data-testid="stAppViewContainer"] {{ background: {BG_PRIMARY} !important; }}
[data-testid="stHeader"] {{ background: {BG_PRIMARY} !important; }}
.stMarkdownContent {{ color: {TEXT_PRIMARY}; }}
h1, h2, h3, h4, h5, h6 {{ color: {TEXT_PRIMARY} !important; }}
p, li, span, div {{ color: {TEXT_PRIMARY}; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {BG_CARD} !important; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{ color: {TEXT_SECONDARY}; }}

/* Inputs */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
.stSelectbox > div > div {{ background: {BG_INPUT} !important; color: {TEXT_PRIMARY} !important; border-color: {BORDER} !important; }}
label {{ color: {TEXT_SECONDARY} !important; }}

/* Cards */
.dark-card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 20px; }}
.dark-card:hover {{ border-color: {ACCENT}; transition: border-color 0.2s; }}

/* Stat card */
.stat-card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 18px 20px; }}
.stat-val {{ font-size: 26px; font-weight: 700; line-height: 1.1; }}
.stat-label {{ font-size: 12px; color: {TEXT_MUTED}; margin-top: 4px; }}

/* Insight cards */
.insight-card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 16px 18px; margin-bottom: 10px; border-left: 4px solid {BORDER}; }}
.insight-card:hover {{ border-color: {ACCENT}; }}
.insight-card.red    {{ border-left-color: {RED}; }}
.insight-card.orange {{ border-left-color: {ORANGE}; }}
.insight-card.yellow {{ border-left-color: {YELLOW}; }}
.insight-card.green  {{ border-left-color: {GREEN}; }}

/* Severity badges */
.sev-badge {{ display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }}
.sev-badge.red {{ background: #5C1E1E; color: #FCA5A5; }}
.sev-badge.orange {{ background: #5C3A1E; color: #FDBA74; }}
.sev-badge.yellow {{ background: #5C4E1E; color: #FDE047; }}
.sev-badge.green {{ background: #1E5C3A; color: #86EFAC; }}

/* Call type badges */
.ct-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: capitalize; }}
.ct-badge.discovery {{ background: #312E81; color: #C4B5FD; }}
.ct-badge.demo {{ background: #1E3A5F; color: #93C5FD; }}
.ct-badge.pricing {{ background: #5C4E1E; color: #FDE047; }}
.ct-badge.negotiation {{ background: #5C3A1E; color: #FDBA74; }}
.ct-badge.close {{ background: #1E5C3A; color: #86EFAC; }}
.ct-badge.check_in {{ background: {BG_ELEVATED}; color: {TEXT_SECONDARY}; }}

/* Transcript — REP = blue tint, BUYER = amber tint */
.transcript-seg {{ padding: 8px 12px; border-radius: 6px; margin-bottom: 4px; font-size: 13px; line-height: 1.6; }}
.transcript-seg.rep {{ background: rgba(59,130,246,0.12); border-left: 3px solid #3B82F6; }}
.transcript-seg.buyer {{ background: rgba(245,158,11,0.12); border-left: 3px solid #F59E0B; }}
.transcript-seg.unknown {{ background: {BG_ELEVATED}; border-left: 3px solid {BORDER}; }}
.transcript-seg .ts {{ color: {TEXT_MUTED}; font-size: 11px; margin-right: 8px; font-family: 'JetBrains Mono', monospace; }}
.transcript-seg .speaker {{ font-weight: 600; margin-right: 6px; }}
.transcript-seg.rep .speaker {{ color: #60A5FA; }}
.transcript-seg.buyer .speaker {{ color: #FBBF24; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ background: {BG_CARD}; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ color: {TEXT_SECONDARY} !important; font-weight: 600; font-size: 13px; }}
.stTabs [aria-selected="true"] {{ border-bottom: 2px solid {ACCENT} !important; color: {ACCENT} !important; }}

/* Evidence quote */
.evidence-quote {{ background: {BG_ELEVATED}; border-left: 2px solid {ACCENT}; padding: 6px 10px; font-size: 12px; color: {TEXT_SECONDARY}; border-radius: 0 6px 6px 0; font-style: italic; margin: 4px 0; }}

/* Coaching box */
.coaching-box {{ background: rgba(20,184,166,0.08); border: 1px solid rgba(20,184,166,0.25); border-radius: 8px; padding: 12px 14px; font-size: 13px; color: {TEXT_PRIMARY}; }}

/* Loading */
@keyframes pulse-dot {{ 0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }} 40% {{ transform: scale(1); opacity: 1; }} }}

/* Buttons */
.stButton > button[kind="primary"] {{ background: linear-gradient(135deg, {ACCENT}, {ACCENT_DARK}) !important; color: white !important; border: none !important; border-radius: 8px; font-weight: 600; }}
.stButton > button[kind="primary"]:hover {{ box-shadow: 0 0 20px {ACCENT_GLOW}; }}
.stButton > button[kind="secondary"] {{ background: {BG_ELEVATED} !important; color: {TEXT_PRIMARY} !important; border: 1px solid {BORDER} !important; border-radius: 8px; }}

/* Progress bar */
.stProgress > div > div > div > div {{ background: linear-gradient(90deg, {ACCENT}, {ACCENT_DARK}); }}

/* Expander */
[data-testid="stExpander"] {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
[data-testid="stExpander"] summary {{ color: {TEXT_PRIMARY} !important; }}

/* Alert overrides — each type gets a subtle tinted background */
[data-testid="stAlert"] {{ color: {TEXT_PRIMARY} !important; }}
[data-testid="stAlert"] p {{ color: {TEXT_PRIMARY} !important; }}
[data-testid="stAlert"][data-baseweb*="notification"] {{ background: {BG_ELEVATED} !important; border: 1px solid {BORDER} !important; }}
div[data-testid="stAlert"] {{ background: {BG_ELEVATED} !important; border: 1px solid {BORDER} !important; }}
/* Info alert */
.stAlert {{ background: {BG_ELEVATED} !important; border: 1px solid {BORDER} !important; }}
.stAlert p, .stAlert span, .stAlert div {{ color: {TEXT_PRIMARY} !important; }}

/* Caption */
[data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}
[data-testid="stCaptionContainer"] p {{ color: {TEXT_MUTED} !important; }}
.stCaption {{ color: {TEXT_MUTED} !important; }}

/* Markdown text */
.stMarkdown p {{ color: {TEXT_PRIMARY} !important; }}
.stMarkdown li {{ color: {TEXT_PRIMARY} !important; }}
.stMarkdown strong {{ color: {TEXT_PRIMARY} !important; }}
.stMarkdown code {{ background: {BG_ELEVATED} !important; color: {ACCENT} !important; }}

/* Selectbox dropdown */
[data-baseweb="select"] {{ background: {BG_INPUT} !important; }}
[data-baseweb="select"] * {{ color: {TEXT_PRIMARY} !important; }}
[data-baseweb="popover"] {{ background: {BG_CARD} !important; }}
[data-baseweb="menu"] {{ background: {BG_CARD} !important; }}
[data-baseweb="menu"] li {{ color: {TEXT_PRIMARY} !important; }}
[data-baseweb="menu"] li:hover {{ background: {BG_ELEVATED} !important; }}

/* Date input */
[data-testid="stDateInput"] input {{ background: {BG_INPUT} !important; color: {TEXT_PRIMARY} !important; border-color: {BORDER} !important; }}

/* Column containers — prevent white gaps */
[data-testid="stHorizontalBlock"] {{ background: transparent !important; }}
[data-testid="column"] {{ background: transparent !important; }}

/* Divider */
hr {{ border-color: {BORDER} !important; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: {BG_PRIMARY}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}

/* ── Coaching-specific styles ── */

/* Grade badge */
.grade-badge {{ display: inline-flex; align-items: center; justify-content: center;
    width: 48px; height: 48px; border-radius: 12px; font-size: 24px; font-weight: 800;
    letter-spacing: -1px; }}
.grade-badge.grade-a {{ background: linear-gradient(135deg, #065F46, #047857); color: #6EE7B7; }}
.grade-badge.grade-b {{ background: linear-gradient(135deg, #1E3A5F, #1D4ED8); color: #93C5FD; }}
.grade-badge.grade-c {{ background: linear-gradient(135deg, #5C4E1E, #CA8A04); color: #FDE047; }}
.grade-badge.grade-d {{ background: linear-gradient(135deg, #5C3A1E, #EA580C); color: #FDBA74; }}
.grade-badge.grade-f {{ background: linear-gradient(135deg, #5C1E1E, #DC2626); color: #FCA5A5; }}

/* Coaching category pills */
.coach-cat {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-right: 4px; }}
.coach-cat.questioning {{ background: #312E81; color: #C4B5FD; }}
.coach-cat.objection_handling {{ background: #5C3A1E; color: #FDBA74; }}
.coach-cat.rapport {{ background: #065F46; color: #6EE7B7; }}
.coach-cat.closing {{ background: #5C1E1E; color: #FCA5A5; }}
.coach-cat.value_selling {{ background: #1E3A5F; color: #93C5FD; }}
.coach-cat.pacing {{ background: #4A1D5C; color: #D8B4FE; }}
.coach-cat.active_listening {{ background: #1E5C4A; color: #5EEAD4; }}
.coach-cat.commitment {{ background: #5C4E1E; color: #FDE047; }}

/* Deal impact bar */
.impact-bar {{ display: flex; align-items: center; gap: 6px; margin: 4px 0; }}
.impact-bar .bar {{ flex: 1; height: 6px; background: {BG_ELEVATED}; border-radius: 3px; overflow: hidden; }}
.impact-bar .fill {{ height: 100%; border-radius: 3px; transition: width 0.3s ease; }}

/* Alternative exchange */
.alt-exchange {{ background: {BG_ELEVATED}; border: 1px solid {BORDER}; border-radius: 10px; padding: 12px 16px; margin: 8px 0; }}
.alt-turn {{ padding: 6px 0; display: flex; gap: 8px; align-items: flex-start; }}
.alt-turn .role {{ font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; white-space: nowrap; margin-top: 2px; }}
.alt-turn .role.rep-role {{ background: rgba(59,130,246,0.2); color: #60A5FA; }}
.alt-turn .role.buyer-role {{ background: rgba(245,158,11,0.2); color: #FBBF24; }}
.alt-turn .text {{ font-size: 13px; color: {TEXT_PRIMARY}; font-style: italic; line-height: 1.5; }}

/* Turning point badge */
.turning-point {{ position: relative; }}
.turning-point::before {{ content: "TURNING POINT"; position: absolute; top: -10px; right: 12px;
    background: linear-gradient(135deg, #DC2626, #EA580C); color: white;
    font-size: 9px; font-weight: 800; padding: 2px 8px; border-radius: 4px;
    letter-spacing: 1px; z-index: 10; }}

/* Win celebration */
.win-badge {{ display: inline-flex; align-items: center; gap: 4px; background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.3); border-radius: 6px; padding: 2px 8px;
    font-size: 11px; font-weight: 600; color: {GREEN}; }}

/* Buyer thinking callout */
.buyer-think {{ background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.25);
    border-radius: 8px; padding: 10px 14px; margin: 6px 0; font-size: 13px; }}
.buyer-think .label {{ font-size: 10px; font-weight: 700; color: #A78BFA; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 4px; }}

/* Momentum indicators */
.momentum {{ display: inline-flex; align-items: center; gap: 3px; font-size: 10px; font-weight: 600; }}
.momentum.gaining {{ color: {GREEN}; }}
.momentum.losing {{ color: {RED}; }}
.momentum.neutral {{ color: {TEXT_MUTED}; }}

/* Coaching meta header */
.coaching-header {{ display: grid; grid-template-columns: auto 1fr 1fr 1fr; gap: 16px;
    background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 16px 20px; margin-bottom: 16px; align-items: center; }}

/* ── Mobile Responsive ── */
@media (max-width: 768px) {{
    /* Coaching header: stack vertically on mobile */
    .coaching-header {{
        grid-template-columns: 1fr !important;
        gap: 12px !important;
        padding: 14px 16px !important;
        text-align: center;
    }}
    .coaching-header > div:first-child {{
        display: flex; align-items: center; gap: 12px; justify-content: center;
    }}

    /* Grade badge smaller on mobile */
    .grade-badge {{ width: 40px !important; height: 40px !important; font-size: 20px !important; border-radius: 10px !important; }}

    /* Transcript segments: smaller text, tighter padding */
    .transcript-seg {{ padding: 6px 10px !important; font-size: 12px !important; line-height: 1.5 !important; }}
    .transcript-seg .ts {{ font-size: 10px !important; margin-right: 4px !important; }}
    .transcript-seg .speaker {{ font-size: 12px !important; margin-right: 4px !important; }}

    /* Coaching category pills: smaller */
    .coach-cat {{ font-size: 9px !important; padding: 1px 6px !important; }}

    /* Alternative exchange: tighter */
    .alt-exchange {{ padding: 8px 12px !important; }}
    .alt-turn .role {{ font-size: 9px !important; padding: 1px 4px !important; }}
    .alt-turn .text {{ font-size: 12px !important; }}

    /* Buyer thinking callout: tighter */
    .buyer-think {{ padding: 8px 10px !important; }}

    /* Deal impact bar: stack label */
    .impact-bar {{ flex-wrap: wrap !important; }}

    /* Turning point badge: adjust position */
    .turning-point::before {{ font-size: 8px !important; right: 4px !important; top: -8px !important; padding: 1px 6px !important; }}

    /* Evidence quote: tighter */
    .evidence-quote {{ font-size: 11px !important; padding: 4px 8px !important; }}

    /* Stat cards: word wrap */
    .stat-card {{ padding: 12px 14px !important; }}
    .stat-card div:first-child {{ font-size: 16px !important; }}

    /* Insight cards: tighter */
    .insight-card {{ padding: 12px 14px !important; }}

    /* Coaching box: tighter */
    .coaching-box {{ padding: 10px 12px !important; font-size: 12px !important; }}

    /* Win badge: smaller */
    .win-badge {{ font-size: 10px !important; padding: 1px 6px !important; }}

    /* Dashboard stat cards: 2x2 grid */
    .stat-grid {{ grid-template-columns: repeat(2, 1fr) !important; gap: 8px !important; }}
    .stat-grid > div {{ padding: 14px !important; }}
    .stat-grid > div > div:nth-child(2) {{ font-size: 24px !important; }}
}}

@media (max-width: 480px) {{
    /* Extra small screens */
    .coaching-header {{ padding: 10px 12px !important; gap: 10px !important; }}
    .grade-badge {{ width: 36px !important; height: 36px !important; font-size: 18px !important; }}
    .transcript-seg {{ font-size: 11px !important; padding: 5px 8px !important; }}
    .alt-exchange {{ padding: 6px 8px !important; margin: 4px 0 !important; }}
    .alt-turn {{ gap: 6px !important; }}
    .alt-turn .text {{ font-size: 11px !important; }}
}}
</style>
""")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escape HTML and dollar signs for safe rendering in st.html() contexts."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("$", "&#36;")


def _esc_md(text: str) -> str:
    """Escape dollar signs for Streamlit markdown (prevents LaTeX rendering)."""
    return text.replace("$", "\\$")


def _format_coaching_text(text: str) -> str:
    """Format coaching recommendation with bold section headers and escaped dollars."""
    formatted = text
    for keyword in ["DIAGNOSIS:", "CHAIN:", "MOMENT:", "FIX:", "IMPACT:"]:
        formatted = formatted.replace(keyword, f"\n**{keyword}**")
    return _esc_md(formatted)


def sev_color(sev: str) -> tuple:
    return SEV_COLORS.get(sev.lower(), (TEXT_MUTED, BG_ELEVATED))


def sev_dot(sev: str) -> str:
    color, _ = sev_color(sev)
    return f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color}" title="{sev.upper()}"></span>'


def _detect_format(text: str) -> str:
    import re
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()][:5]
    for line in lines:
        if re.match(r"\[\d+:\d+\]", line):  return "Signal format"
        if re.match(r"\d{2}:\d{2}:\d{2}\s+\w+", line):  return "Zoom format"
        if re.match(r".+\s+\[\d{2}:\d{2}:\d{2}\]", line):  return "Gong format"
        if re.match(r".+\s+\d{2}:\d{2}", line):  return "Otter format"
    for line in lines:
        if ":" in line:  return "Speaker: text"
    return "Plain text"


def _fw_group_for(fw_name: str) -> str:
    """Match framework name to group, using fuzzy substring matching."""
    # Exact match first
    g = FW_NAME_TO_GROUP.get(fw_name)
    if g:
        return g
    # Fuzzy: check if any known name is a substring of fw_name or vice versa
    fw_lower = fw_name.lower()
    for known_name, group_id in FW_NAME_TO_GROUP.items():
        if known_name.lower() in fw_lower or fw_lower in known_name.lower():
            return group_id
    # Keyword fallback
    kw_map = {
        "A": ["batna", "money left", "first number", "deal health", "deal timing", "negotiat"],
        "B": ["unanswered", "commitment", "thermometer", "pushback"],
        "C": ["question quality", "frame match", "close attempt", "methodology", "call structure", "objection"],
        "E": ["emotion", "turning point", "trigger"],
    }
    for group_id, keywords in kw_map.items():
        if any(kw in fw_lower for kw in keywords):
            return group_id
    return "Other"


SAMPLE_TRANSCRIPT = """[00:00] Alex (rep): Thanks for joining today, Jordan. I wanted to walk through the pricing proposal we discussed last week.
[00:15] Jordan (buyer): Sure, happy to dig in. We've been evaluating a few options including Competitor X.
[00:30] Alex (rep): Great. So our enterprise plan is $45,000 annually. That includes full platform access and priority support.
[00:52] Jordan (buyer): That's higher than we expected. Competitor X quoted us around $30,000 for similar features.
[01:15] Alex (rep): I understand the concern. Our platform includes advanced behavioral analytics that Competitor X doesn't offer. Can I walk you through the ROI model?
[01:35] Jordan (buyer): Sure, but I need to be upfront — our budget is capped at $38,000.
[01:50] Alex (rep): I appreciate the transparency. Let me see what I can do. If we go with annual billing, I could bring it down to $40,000.
[02:10] Jordan (buyer): That's still above budget. What about a phased rollout? Maybe start with fewer seats?
[02:30] Alex (rep): We could do a pilot with 50 seats at $32,000, then expand after Q2 results.
[02:48] Jordan (buyer): That sounds more workable. I'd need to get approval from our VP, but I think we can move forward with the pilot.
[03:05] Alex (rep): Excellent. What's the timeline for getting that approval?
[03:15] Jordan (buyer): Probably by end of next week. I'll loop in my procurement team.
[03:30] Alex (rep): Perfect. I'll send over a pilot agreement draft today. Anything else you need from our side?
[03:45] Jordan (buyer): Just make sure the implementation timeline is realistic. We've been burned before with long onboarding.
[04:00] Alex (rep): Absolutely. Our standard pilot onboarding is 2 weeks. I'll include that in the proposal.
[04:15] Jordan (buyer): Sounds good. Let's plan to reconnect next Wednesday to finalize."""


# ═══════════════════════════════════════════════════════════════════════════════
# PAGES
# ═══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    calls = fetch_all_calls()
    ready_calls = [c for c in calls if c.get("processing_status") == "ready"]
    processing_calls = [c for c in calls if c.get("processing_status") == "processing"]

    if not calls:
        st.html(f"""
        <div style="text-align:center;padding:80px 20px">
            <div style="font-size:56px;margin-bottom:16px">🔊</div>
            <div style="font-size:24px;font-weight:700;color:{TEXT_PRIMARY};margin-bottom:8px">Welcome to Signal</div>
            <div style="font-size:14px;color:{TEXT_SECONDARY};max-width:440px;margin:0 auto 32px;line-height:1.6">
                Post-call behavioral intelligence for sales teams.
                Analyze transcripts to surface coaching insights, detect negotiation patterns,
                and improve rep performance with 17 behavioral frameworks.
            </div>
            <div style="display:flex;gap:16px;justify-content:center;margin-bottom:24px">
                <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:12px 20px;text-align:center">
                    <div style="font-size:24px;margin-bottom:4px">📋</div>
                    <div style="font-size:12px;color:{TEXT_MUTED}">Paste a transcript</div>
                </div>
                <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:12px 20px;text-align:center">
                    <div style="font-size:24px;margin-bottom:4px">🧠</div>
                    <div style="font-size:12px;color:{TEXT_MUTED}">17 AI frameworks analyze</div>
                </div>
                <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:12px 20px;text-align:center">
                    <div style="font-size:24px;margin-bottom:4px">💡</div>
                    <div style="font-size:12px;color:{TEXT_MUTED}">Get coaching insights</div>
                </div>
            </div>
        </div>
        """)
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("🚀 Analyze Your First Call", type="primary"):
                st.session_state["view"] = "submit"
                st.rerun()
        with c2:
            if st.button("📋 Try Sample Transcript"):
                st.session_state["view"] = "submit"
                st.session_state["_load_sample"] = True
                st.rerun()
        return

    # ── Single-query dashboard summary ──
    dash = fetch_dashboard_summary()
    avg_conf = f"{dash.get('avg_confidence', 0) * 100:.0f}%" if dash.get("avg_confidence") else "—"
    top_theme = dash.get("top_coaching_theme", "—") or "—"
    if len(top_theme) > 25:
        top_theme = top_theme[:23] + "..."

    from datetime import timedelta
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    calls_this_week = sum(1 for c in calls if (c.get("created_at") or "") >= week_ago)

    # ── Stat Cards Row ──
    st.html(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px" class="stat-grid">
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;padding:20px">
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:{TEXT_MUTED};margin-bottom:8px">Total Calls</div>
            <div style="font-size:32px;font-weight:800;color:{TEXT_PRIMARY};line-height:1">{len(calls)}</div>
            <div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px">{len(ready_calls)} analyzed · {len(processing_calls)} processing</div>
        </div>
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;padding:20px">
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:{TEXT_MUTED};margin-bottom:8px">This Week</div>
            <div style="font-size:32px;font-weight:800;color:{ACCENT};line-height:1">{calls_this_week}</div>
            <div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px">calls submitted</div>
        </div>
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;padding:20px">
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:{TEXT_MUTED};margin-bottom:8px">Avg Confidence</div>
            <div style="font-size:32px;font-weight:800;color:{ACCENT};line-height:1">{avg_conf}</div>
            <div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px">across all insights</div>
        </div>
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;padding:20px">
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;color:{TEXT_MUTED};margin-bottom:8px">Top Coaching Theme</div>
            <div style="font-size:16px;font-weight:700;color:{ORANGE};line-height:1.2;margin-top:4px">{top_theme}</div>
            <div style="font-size:12px;color:{TEXT_MUTED};margin-top:4px">most frequent issue</div>
        </div>
    </div>
    """)

    # ── Two-column layout: Attention + Rep Overview ──
    col_left, col_right = st.columns([3, 2])

    with col_left:
        # Calls Needing Attention
        st.html(f"""
        <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{TEXT_MUTED};margin-bottom:12px;display:flex;align-items:center;gap:8px">
            <span style="width:6px;height:6px;border-radius:50%;background:{RED}"></span>
            Calls Needing Attention
        </div>
        """)

        attention = dash.get("attention_calls", [])
        if attention:
            for item in attention[:5]:
                sev = item.get("severity", "yellow")
                color, _ = sev_color(sev)
                deal = item.get("deal_name") or item.get("rep_name", "Unknown")
                headline = item.get("headline", "")
                fw = item.get("framework_name", "")

                st.html(f"""
                <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;margin-bottom:8px;border-left:3px solid {color}">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div style="flex:1">
                            <div style="font-size:14px;font-weight:600;color:{TEXT_PRIMARY};margin-bottom:3px">{deal}</div>
                            <div style="font-size:12px;color:{TEXT_SECONDARY};margin-bottom:6px">{headline}</div>
                            <div style="display:flex;gap:8px;align-items:center">
                                <span class="sev-badge {sev}" style="font-size:9px">{sev.upper()}</span>
                                <span style="font-size:11px;color:{TEXT_MUTED}">{item.get('rep_name','')} · {item.get('call_type','').title()}</span>
                            </div>
                        </div>
                    </div>
                </div>
                """)

                if st.button(f"Review →", key=f"attn_{item['call_id']}", type="secondary"):
                    st.session_state["view_call_id"] = item["call_id"]
                    st.session_state["view"] = "call_review"
                    st.rerun()
        else:
            st.html(f"""
            <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:24px;text-align:center">
                <div style="font-size:28px;margin-bottom:8px">✅</div>
                <div style="font-size:14px;color:{TEXT_SECONDARY}">No urgent issues detected</div>
                <div style="font-size:12px;color:{TEXT_MUTED}">All analyzed calls look healthy</div>
            </div>
            """)

    with col_right:
        # Rep Overview
        st.html(f"""
        <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{TEXT_MUTED};margin-bottom:12px;display:flex;align-items:center;gap:8px">
            <span style="width:6px;height:6px;border-radius:50%;background:{ACCENT}"></span>
            Rep Overview
        </div>
        """)

        rep_data = {}
        for c in calls:
            rep = c.get("rep_name", "Unknown")
            rep_data.setdefault(rep, {"total": 0, "ready": 0})
            rep_data[rep]["total"] += 1
            if c.get("processing_status") == "ready":
                rep_data[rep]["ready"] += 1

        if rep_data:
            # Table header
            st.html(f"""
            <div style="display:grid;grid-template-columns:1fr 60px 70px;gap:8px;padding:6px 12px;border-bottom:1px solid {BORDER};margin-bottom:4px">
                <div style="font-size:11px;font-weight:700;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:0.5px">Rep</div>
                <div style="font-size:11px;font-weight:700;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:0.5px;text-align:center">Calls</div>
                <div style="font-size:11px;font-weight:700;color:{TEXT_MUTED};text-transform:uppercase;letter-spacing:0.5px;text-align:center">Analyzed</div>
            </div>
            """)
            for rep, data in sorted(rep_data.items(), key=lambda x: x[1]["total"], reverse=True):
                pct = f"{data['ready']/data['total']*100:.0f}%" if data["total"] > 0 else "—"
                st.html(f"""
                <div style="display:grid;grid-template-columns:1fr 60px 70px;gap:8px;padding:8px 12px;border-radius:6px" onmouseover="this.style.background='{BG_ELEVATED}'" onmouseout="this.style.background='transparent'">
                    <div style="font-size:13px;font-weight:500;color:{TEXT_PRIMARY}">{rep}</div>
                    <div style="font-size:13px;color:{TEXT_SECONDARY};text-align:center">{data['total']}</div>
                    <div style="font-size:13px;text-align:center">
                        <span style="color:{ACCENT};font-weight:600">{data['ready']}</span>
                        <span style="color:{TEXT_MUTED};font-size:11px"> ({pct})</span>
                    </div>
                </div>
                """)
        else:
            st.caption("No reps found.")

    # ── Recent Calls ──
    st.html(f"""
    <div style="margin-top:24px;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{TEXT_MUTED};margin-bottom:12px;display:flex;align-items:center;gap:8px">
        <span style="width:6px;height:6px;border-radius:50%;background:{TEXT_MUTED}"></span>
        Recent Calls
    </div>
    """)

    sorted_calls = sorted(calls, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
    for c in sorted_calls:
        status = c.get("processing_status", "unknown")
        ct = c.get("call_type", "other")
        d = (c.get("call_date") or c.get("created_at") or "")[:10]
        deal = c.get("deal_name") or c.get("rep_name", "Unknown")
        status_color = {
            "ready": GREEN, "processing": YELLOW, "failed": RED
        }.get(status, TEXT_MUTED)
        status_label = status.upper()

        st.html(f"""
        <div class="call-row" style="display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 14px;border-radius:8px;margin-bottom:2px;border-bottom:1px solid {BORDER}" onmouseover="this.style.background='{BG_ELEVATED}'" onmouseout="this.style.background='transparent'">
            <div>
                <div style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY}">{deal}</div>
                <div style="font-size:11px;color:{TEXT_MUTED}">{c.get('rep_name', '')} · {ct}</div>
            </div>
            <div style="text-align:center">
                <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;background:{status_color}22;color:{status_color}">{status_label}</span>
            </div>
            <div style="font-size:12px;color:{TEXT_MUTED};text-align:right;white-space:nowrap">{d if d else '—'}</div>
        </div>
        """)

        if st.button("View →", key=f"v_{c['id']}", type="secondary"):
            st.session_state["view_call_id"] = c["id"]
            st.session_state["view"] = "call_review"
            st.rerun()


def page_calls_list():
    st.markdown("### All Calls")
    calls = fetch_all_calls()

    c1, c2, c3 = st.columns([2, 2, 1])
    filter_rep = c1.text_input("Filter by rep", "")
    filter_type = c2.selectbox("Call type", ["All"] + CALL_TYPES, index=0)
    filter_status = c3.selectbox("Status", ["All", "ready", "processing", "failed"], index=0)

    filtered = calls
    if filter_rep:
        filtered = [c for c in filtered if filter_rep.lower() in c.get("rep_name", "").lower()]
    if filter_type != "All":
        filtered = [c for c in filtered if c.get("call_type", "") == filter_type.lower()]
    if filter_status != "All":
        filtered = [c for c in filtered if c.get("processing_status", "") == filter_status]

    st.caption(f"Showing {len(filtered)} of {len(calls)} calls")

    if not filtered:
        st.info("No calls match your filters.")
        return

    for c in sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True):
        status = c.get("processing_status", "unknown")
        ct = c.get("call_type", "other")
        dot = {"ready": "🟢", "processing": "🟡", "failed": "🔴"}.get(status, "⚪")
        row = st.columns([4, 1, 1, 1, 1])
        with row[0]:
            st.markdown(f"**{c.get('deal_name') or c.get('rep_name', 'Unknown Call')}**")
            st.caption(f"Rep: {c.get('rep_name', '—')}")
        with row[1]:
            st.html(f'<span class="ct-badge {ct.lower()}">{ct}</span>')
        with row[2]:
            st.markdown(f"{dot} {status}")
        with row[3]:
            d = c.get("call_date") or c.get("created_at") or ""
            st.caption(d[:10] if d else "—")
        with row[4]:
            if st.button("Open", key=f"o_{c['id']}", type="secondary"):
                st.session_state["view_call_id"] = c["id"]
                st.session_state["view"] = "call_review"
                st.rerun()
        st.markdown("---")


def page_submit():
    st.markdown("### Analyze a Call")
    tab_paste, tab_audio = st.tabs(["📋 Paste Transcript", "📁 Upload Audio"])

    with tab_paste:
        transcript_text = st.text_area(
            "Paste your transcript",
            height=260,
            placeholder="[00:00] Alex (rep): Thanks for joining today!\n[00:15] Jordan (buyer): Happy to be here...",
            key="transcript_input",
            value=SAMPLE_TRANSCRIPT if st.session_state.get("_load_sample") else "",
        )
        if st.session_state.get("_load_sample"):
            st.session_state.pop("_load_sample", None)

        if transcript_text and len(transcript_text.strip()) > 10:
            fmt = _detect_format(transcript_text)
            seg_count = len([l for l in transcript_text.strip().split("\n") if l.strip()])
            st.caption(f"Detected: **{fmt}** · {seg_count} lines · {transcript_text.count('?')} questions")

        c1, c2, c3 = st.columns(3)
        with c1:
            rep_name = st.text_input("Rep Name", placeholder="e.g. Alex")
        with c2:
            call_type = st.selectbox("Call Type", CALL_TYPES, index=0)
            st.caption(CALL_TYPE_DESC.get(call_type, ""))
        with c3:
            deal_name = st.text_input("Deal Name (optional)", placeholder="e.g. Acme Corp Q2")

        call_date = st.date_input("Call Date", value=date.today())

        st.markdown("")
        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            if transcript_text.strip():
                _do_submit(transcript_text, rep_name or "Unknown", call_type, deal_name, str(call_date) if call_date else None)
            else:
                st.error("Please paste a transcript first.")

    with tab_audio:
        st.warning("Audio upload requires ASR (disabled in transcript-only mode). Use Paste Transcript instead.")


def _do_submit(transcript_text, rep_name, call_type, deal_name, call_date=None):
    if st.session_state.get("_submitting"):
        return
    st.session_state["_submitting"] = True
    try:
        with st.spinner("Submitting to analysis pipeline..."):
            resp = api_post("/api/v1/calls/paste-transcript", json={
                "rep_name": rep_name, "call_type": call_type,
                "deal_name": deal_name or None, "transcript_text": transcript_text,
                "call_date": call_date,
            }, timeout=30)
    finally:
        st.session_state["_submitting"] = False

    if resp.status_code not in (200, 201):
        st.error(f"Backend error {resp.status_code}: {resp.text}")
        return

    call_id = resp.json().get("call_id")
    if call_id:
        st.session_state["view_call_id"] = call_id
        st.session_state["view"] = "call_review"
        st.session_state["_polling"] = True
        st.rerun()


# ── Call Review Page ──────────────────────────────────────────────────────────

def page_call_review():
    call_id = st.session_state.get("view_call_id")
    if not call_id:
        st.warning("No call selected.")
        if st.button("← Back"):
            st.session_state["view"] = "dashboard"
            st.rerun()
        return

    r = api_get(f"/api/v1/calls/{call_id}", timeout=10)
    if r.status_code != 200:
        st.error(f"Could not load call: {r.text}")
        return

    call = r.json()
    status = call.get("processing_status", "unknown")

    # Header
    h1, h2, h3 = st.columns([1, 5, 2])
    with h1:
        if st.button("← Back", type="secondary"):
            st.session_state["view"] = "dashboard"
            st.session_state["_polling"] = False
            st.rerun()
    with h2:
        deal = call.get("deal_name") or f"{call.get('rep_name', '')} — {call.get('call_type', '').title()}"
        ct = call.get("call_type", "other")
        d = (call.get("call_date") or call.get("created_at") or "")[:10]
        st.markdown(f"### {deal}")
        st.caption(f"**Rep:** {call.get('rep_name', '—')} · **Type:** `{ct}` · **Date:** {d}")
    with h3:
        dot = {"ready": "🟢", "processing": "🟡", "failed": "🔴"}.get(status, "⚪")
        st.markdown(f"<div style='text-align:right'>{dot} <b>{status.upper()}</b></div>", unsafe_allow_html=True)
        if status == "ready":
            if st.button("🔄 Re-analyze", type="secondary"):
                api_post(f"/api/v1/calls/{call_id}/reanalyze", json={})
                st.session_state["_polling"] = True
                st.rerun()

    # Processing state
    if status == "processing":
        _render_processing(call_id)
        if st.session_state.get("_polling"):
            cr = api_get(f"/api/v1/calls/{call_id}", timeout=10)
            if cr.status_code == 200 and cr.json().get("processing_status") in ("ready", "failed"):
                st.session_state["_polling"] = False
                st.rerun()
                return
            time.sleep(5)
            st.rerun()
        return

    if status == "failed":
        st.error("Analysis failed. Check backend logs.")
        if st.button("🔄 Retry"):
            api_post(f"/api/v1/calls/{call_id}/reanalyze", json={})
            st.session_state["_polling"] = True
            st.rerun()
        return

    # Fetch data
    insights_data = fetch_insights(call_id) or {}
    insights = insights_data.get("insights") or []
    summary = insights_data.get("summary") or {}
    metrics = fetch_metrics(call_id)
    segments = fetch_transcript(call_id)
    coaching_meta = fetch_coaching_meta(call_id)

    # One-line summary
    headline = summary.get("headline") if summary else None
    if headline:
        st.markdown(f"**{headline}**")

    # Coaching meta header — grade, arc, skills
    if coaching_meta.get("available"):
        _render_coaching_header(coaching_meta)

    # 60/40 split
    col_left, col_right = st.columns([3, 2])

    with col_left:
        _render_transcript(segments, call_id)

    with col_right:
        t_ins, t_stats, t_sum, t_fw = st.tabs(["💡 Insights", "📊 Call Stats", "📝 Summary", "🔬 Frameworks"])
        with t_ins:
            _render_insights(insights)
        with t_stats:
            _render_stats(metrics, summary)
        with t_sum:
            _render_summary(summary, insights)
        with t_fw:
            _render_frameworks(insights)


def _render_processing(call_id):
    st.html(f"""
    <div style="text-align:center;padding:30px 20px">
        <div style="font-size:40px;margin-bottom:8px">🔊</div>
        <div style="font-size:18px;font-weight:700;color:{TEXT_PRIMARY};margin-bottom:4px">Analyzing your call</div>
        <div style="font-size:13px;color:{TEXT_SECONDARY};margin-bottom:20px">Running behavioral intelligence pipeline</div>
        <div style="display:flex;align-items:center;justify-content:center;gap:6px">
            <div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};animation:pulse-dot 1.2s ease-in-out infinite"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};animation:pulse-dot 1.2s ease-in-out infinite;animation-delay:.2s"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};animation:pulse-dot 1.2s ease-in-out infinite;animation-delay:.4s"></div>
        </div>
    </div>
    """)
    steps = ["Parsing transcript", "Pass 1 extraction", "Framework routing",
             "Running 17 frameworks", "Verifying results", "Generating summary"]
    for i, step in enumerate(steps):
        icon = "✅" if i < 1 else "⏳" if i == 1 else "⬜"
        st.markdown(f"{icon} {step}")
    st.caption(f"Call ID: `{call_id}` · Typically 1-3 minutes")


def _render_coaching_header(meta: dict):
    """Render the coaching performance header with grade, arc, skills."""
    grade = meta.get("rep_grade", "?")
    assessment = meta.get("overall_assessment", "")
    arc = meta.get("conversation_arc", "")
    strongest = meta.get("strongest_skill", "")
    growth = meta.get("biggest_growth_area", "")
    n_coaching = meta.get("total_coaching_moments", 0)
    n_signals = meta.get("total_signal_moments", 0)
    n_wins = meta.get("total_wins", 0)

    grade_class = f"grade-{grade.lower()}" if grade else "grade-c"

    st.html(f"""
    <div class="coaching-header">
        <div style="text-align:center;min-width:56px">
            <div class="grade-badge {grade_class}">{grade}</div>
            <div style="font-size:10px;color:{TEXT_MUTED};margin-top:4px;font-weight:600">REP GRADE</div>
        </div>
        <div style="min-width:0">
            <div style="font-size:12px;color:{TEXT_SECONDARY};line-height:1.5">{_esc(assessment)}</div>
            {f'<div style="font-size:11px;color:{TEXT_MUTED};margin-top:4px;font-style:italic">{_esc(arc)}</div>' if arc else ''}
        </div>
        <div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:6px">
                <div><div style="font-size:10px;color:{TEXT_MUTED};font-weight:600">STRONGEST</div><div style="font-size:12px;color:{GREEN};font-weight:600">{_esc(strongest)}</div></div>
                <div><div style="font-size:10px;color:{TEXT_MUTED};font-weight:600">FOCUS AREA</div><div style="font-size:12px;color:{ORANGE};font-weight:600">{_esc(growth)}</div></div>
            </div>
        </div>
        <div style="display:flex;gap:16px;justify-content:center;flex-wrap:wrap">
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:800;color:{ACCENT}">{n_coaching}</div>
                <div style="font-size:10px;color:{TEXT_MUTED}">Coaching</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:800;color:{YELLOW}">{n_signals}</div>
                <div style="font-size:10px;color:{TEXT_MUTED}">Signals</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:800;color:{GREEN}">{n_wins}</div>
                <div style="font-size:10px;color:{TEXT_MUTED}">Wins</div>
            </div>
        </div>
    </div>
    """)


def _render_transcript(segments, call_id):
    st.markdown("#### Transcript")

    # Enhanced legend
    st.html(f"""
    <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px;font-size:11px;color:{TEXT_SECONDARY}">
        <span><span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:rgba(59,130,246,0.25);border-left:3px solid #3B82F6;margin-right:4px"></span> Rep</span>
        <span><span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:rgba(245,158,11,0.25);border-left:3px solid #F59E0B;margin-right:4px"></span> Buyer</span>
        <span style="color:{ACCENT}">💡 Coaching</span>
        <span style="color:{YELLOW}">⚡ Signal</span>
        <span style="color:{GREEN}">🌟 Win</span>
        <span style="color:{RED}">🔥 Turning Point</span>
    </div>
    """)

    search = st.text_input("Search transcript", "", key="tsearch", placeholder="Search...")

    if not segments:
        st.info("Transcript segments not available.")
        return

    filtered = segments
    if search:
        filtered = [s for s in segments if search.lower() in s.get("text", "").lower()]
        st.caption(f"{len(filtered)} matches")
    else:
        coached = sum(1 for s in segments if s.get("coaching"))
        wins = sum(1 for s in segments if (s.get("coaching") or {}).get("type") == "win")
        parts = [f"{len(segments)} segments"]
        if coached:
            parts.append(f"{coached} annotated")
        if wins:
            parts.append(f"{wins} wins")
        st.caption(" · ".join(parts))

    for seg in filtered:
        role = seg.get("role", "unknown")
        start_ms = seg.get("start_ms", 0)
        m, s = divmod(start_ms // 1000, 60)
        spk = seg.get("speaker", "?")
        text = seg.get("text", "")
        coaching = seg.get("coaching")
        seg_idx = seg.get("index", 0)

        if search and search.lower() in text.lower():
            import re
            text = re.sub(f"({re.escape(search)})", r'<mark style="background:#5C4E1E;color:#FDE047;padding:1px 2px;border-radius:2px">\1</mark>', text, flags=re.IGNORECASE)

        role_class = "rep" if role == "rep" else "buyer" if role == "buyer" else "unknown"

        if coaching:
            _render_coached_segment(seg_idx, m, s, spk, text, role_class, coaching)
        else:
            st.html(f'<div class="transcript-seg {role_class}"><span class="ts">[{m:02d}:{s:02d}]</span><span class="speaker">{spk}:</span> {text}</div>')


def _render_coached_segment(seg_idx, m, s, spk, text, role_class, coaching):
    """Render a single segment with rich coaching annotation."""
    c_type = coaching.get("type", "coaching")
    sev = coaching.get("severity", "yellow")
    momentum = coaching.get("momentum", "neutral")
    category = coaching.get("coaching_category", "")
    impact = coaching.get("deal_impact_score", 5)
    impact_text = coaching.get("deal_impact_explanation", "")
    fw = coaching.get("framework_source", "")

    # Icons and colors per type
    type_config = {
        "coaching":      {"icon": "💡", "label": "COACHING",       "border_color": ACCENT},
        "signal":        {"icon": "⚡", "label": "BUYER SIGNAL",   "border_color": YELLOW},
        "win":           {"icon": "🌟", "label": "GREAT MOVE",     "border_color": GREEN},
        "turning_point": {"icon": "🔥", "label": "TURNING POINT",  "border_color": RED},
    }
    tc = type_config.get(c_type, type_config["coaching"])
    sev_color_val = {"red": RED, "orange": ORANGE, "yellow": YELLOW, "green": GREEN}.get(sev, YELLOW)

    # Momentum arrow
    mom_html = ""
    if momentum == "gaining":
        mom_html = f'<span class="momentum gaining">&#9650; Gaining</span>'
    elif momentum == "losing":
        mom_html = f'<span class="momentum losing">&#9660; Losing</span>'

    # Category pill
    cat_html = f'<span class="coach-cat {category}">{category.replace("_", " ")}</span>' if category else ""

    # Turning point gets special wrapper
    tp_class = " turning-point" if c_type == "turning_point" else ""

    st.html(f'''<div class="transcript-seg {role_class}{tp_class}" style="border-right:3px solid {tc["border_color"]}">
        <span class="ts">[{m:02d}:{s:02d}]</span>
        <span class="speaker">{spk}:</span> {text}
        <span style="display:inline-flex;align-items:center;gap:4px;margin-left:6px;white-space:nowrap;vertical-align:middle">
            {mom_html}<span style="font-size:14px">{tc["icon"]}</span>
        </span>
    </div>''')

    # Expandable coaching card
    with st.expander(f'{tc["icon"]} {tc["label"]} — [{m:02d}:{s:02d}]', expanded=False):
        # Header: category + impact + source
        header_parts = []
        if cat_html:
            header_parts.append(cat_html)
        if fw:
            header_parts.append(f'<span style="font-size:10px;color:{TEXT_MUTED}">via {fw}</span>')
        if header_parts:
            st.html(f'<div style="margin-bottom:8px">{"".join(header_parts)}</div>')

        # Deal impact bar
        if impact > 0:
            impact_color = GREEN if impact <= 3 else (YELLOW if impact <= 5 else (ORANGE if impact <= 7 else RED))
            pct = impact * 10
            st.html(f'''<div class="impact-bar">
                <span style="font-size:10px;font-weight:700;color:{TEXT_MUTED};width:70px">DEAL IMPACT</span>
                <div class="bar"><div class="fill" style="width:{pct}%;background:{impact_color}"></div></div>
                <span style="font-size:13px;font-weight:800;color:{impact_color}">{impact}/10</span>
            </div>''')
            if impact_text:
                st.html(f'<div style="font-size:11px;color:{TEXT_SECONDARY};margin-bottom:8px;font-style:italic">{_esc(impact_text)}</div>')

        # ── Type-specific content ──
        if c_type == "turning_point":
            # Positive turning point (green) uses win content; negative uses coaching
            if sev == "green":
                _render_win_content(coaching)
            else:
                _render_coaching_content(coaching)
        elif c_type == "coaching":
            _render_coaching_content(coaching)
        elif c_type == "signal":
            _render_signal_content(coaching)
        elif c_type == "win":
            _render_win_content(coaching)

        # Related segments
        related = coaching.get("related_segments") or []
        if related:
            links = ", ".join(f"seg {r}" for r in related)
            st.caption(f"Connected to: {links}")


def _render_coaching_content(coaching):
    """Render coaching/turning_point annotation content."""
    alt = coaching.get("what_to_say_instead", "")
    why = coaching.get("why", "")
    exchange = coaching.get("alternative_exchange") or []

    # "Instead, try" box
    if alt:
        st.html(f'''<div style="background:rgba(20,184,166,0.1);border:1px solid rgba(20,184,166,0.3);
            border-radius:8px;padding:12px 16px;margin-bottom:8px">
            <div style="font-size:10px;font-weight:700;color:{ACCENT};text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Instead, try</div>
            <div style="color:{TEXT_PRIMARY};font-size:14px;font-style:italic;line-height:1.5">"{_esc(alt)}"</div>
        </div>''')

    # Why
    if why:
        st.markdown(f"**Why:** {why}")

    # Alternative exchange — mini script
    if exchange:
        turns_html = ""
        for turn in exchange:
            speaker = turn.get("speaker", "")
            turn_text = turn.get("text", "")
            role_cls = "rep-role" if speaker.lower() == "rep" else "buyer-role"
            turns_html += f'''<div class="alt-turn">
                <span class="role {role_cls}">{speaker}</span>
                <span class="text">"{_esc(turn_text)}"</span>
            </div>'''
        st.html(f'''<div class="alt-exchange">
            <div style="font-size:10px;font-weight:700;color:{ACCENT};text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">How it should have gone</div>
            {turns_html}
        </div>''')


def _render_signal_content(coaching):
    """Render buyer signal annotation content."""
    signal = coaching.get("signal_detected", "")
    missed = coaching.get("missed_opportunity", "")
    buyer_thinking = coaching.get("buyer_thinking", "")
    exchange = coaching.get("alternative_exchange") or []

    # Signal detected
    if signal:
        st.html(f'''<div style="background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.25);
            border-radius:8px;padding:10px 14px;margin-bottom:8px">
            <div style="font-size:10px;font-weight:700;color:{YELLOW};text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Signal Detected</div>
            <div style="font-size:13px;color:{TEXT_PRIMARY};line-height:1.5">{_esc(signal)}</div>
        </div>''')

    # Buyer psychology decoder
    if buyer_thinking:
        st.html(f'''<div class="buyer-think">
            <div class="label">What the buyer was actually thinking</div>
            <div style="color:{TEXT_PRIMARY};font-size:13px;line-height:1.5;font-style:italic">"{_esc(buyer_thinking)}"</div>
        </div>''')

    # Missed opportunity
    if missed:
        st.markdown(f"**Missed opportunity:** {missed}")

    # Alternative exchange
    if exchange:
        turns_html = ""
        for turn in exchange:
            speaker = turn.get("speaker", "")
            turn_text = turn.get("text", "")
            role_cls = "rep-role" if speaker.lower() == "rep" else "buyer-role"
            turns_html += f'''<div class="alt-turn">
                <span class="role {role_cls}">{speaker}</span>
                <span class="text">"{_esc(turn_text)}"</span>
            </div>'''
        st.html(f'''<div class="alt-exchange">
            <div style="font-size:10px;font-weight:700;color:{YELLOW};text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">What should have happened next</div>
            {turns_html}
        </div>''')


def _render_win_content(coaching):
    """Render win celebration annotation content."""
    great = coaching.get("what_was_great", "")
    why_worked = coaching.get("why_it_worked", "")

    if great:
        st.html(f'''<div style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);
            border-radius:8px;padding:12px 16px;margin-bottom:8px">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                <span class="win-badge">GREAT MOVE</span>
            </div>
            <div style="color:{TEXT_PRIMARY};font-size:13px;line-height:1.5">{_esc(great)}</div>
        </div>''')

    if why_worked:
        st.html(f'''<div style="font-size:12px;color:{TEXT_SECONDARY};line-height:1.5;margin-top:4px">
            <strong style="color:{GREEN}">Why it worked:</strong> {_esc(why_worked)}
        </div>''')


def _render_insights(insights):
    # Filter out stubs
    insights = [i for i in insights if i.get("headline") != "Analysis unavailable" and i.get("confidence", 0) > 0]
    st.markdown("### Top Insights")
    if not insights:
        st.info("No insights generated.")
        return

    top = [i for i in insights if i.get("is_top_insight")]
    if not top:
        top = insights[:5]

    st.caption(f"Showing {len(top)} top · {len(insights)} total")

    for idx, ins in enumerate(top, 1):
        sev = ins.get("severity", "yellow").lower()
        color, _ = sev_color(sev)
        score = int(ins.get("confidence", 0.5) * 100)
        headline = ins.get("headline", "No headline")
        explanation = ins.get("explanation", "")
        coaching = ins.get("coaching_recommendation", "")
        fw_name = ins.get("framework_name", "Framework")
        evidence = ins.get("evidence") or []
        iid = ins.get("id", "")

        with st.container():
            hl, hr = st.columns([5, 1])
            with hl:
                st.html(f'{sev_dot(sev)} <span style="font-size:11px;color:{TEXT_MUTED};font-weight:600">{fw_name}</span> <span class="sev-badge {sev}">{sev.upper()}</span>')
                st.markdown(f"**{idx}. {headline}**")
            with hr:
                st.html(f'<div style="text-align:right;font-size:22px;font-weight:800;color:{color}">{score}<span style="font-size:11px;color:{TEXT_MUTED}">%</span></div>')

            # Full explanation — no truncation
            st.markdown(f"<div style='font-size:13px;color:{TEXT_SECONDARY};line-height:1.6'>{_esc(explanation)}</div>", unsafe_allow_html=True)

            # Evidence quotes with verification badges
            shown_ev = 0
            for ev in evidence:
                if shown_ev >= 5:
                    break
                q = ev.get("quote", "") or ev.get("text_excerpt", "")
                if not q or not q.strip():
                    continue
                ts = ev.get("timestamp", 0) or ev.get("start_time_ms", 0)
                verified = ev.get("quote_verified", False)
                match_score = ev.get("quote_match_score", 0.0)
                spk = ev.get("speaker", "")
                badge = ""
                if verified:
                    badge = f' <span style="color:{GREEN};font-size:10px;font-weight:600">VERIFIED</span>'
                elif match_score > 0:
                    badge = f' <span style="color:{YELLOW};font-size:10px">~{int(match_score*100)}%</span>'
                spk_label = f' <span style="color:{TEXT_MUTED};font-size:10px">{_esc(spk)}</span>' if spk else ""
                st.html(f'<div class="evidence-quote">[{ts//60000:02d}:{(ts%60000)//1000:02d}]{spk_label} "{_esc(q[:200])}"{badge}</div>')
                shown_ev += 1

            # Full coaching — NO truncation, displayed in expandable section
            if coaching and "Unable to generate" not in coaching:
                # Show first 200 chars as preview, full text in expander
                preview = coaching[:200].rstrip()
                if len(coaching) > 200:
                    st.html(f'<div class="coaching-box" style="margin-top:8px"><strong style="color:{ACCENT}">Coaching:</strong> {_esc(preview)}...</div>')
                    with st.expander("Read full coaching recommendation"):
                        formatted = _format_coaching_text(coaching)
                        st.markdown(formatted)
                else:
                    st.html(f'<div class="coaching-box" style="margin-top:8px"><strong style="color:{ACCENT}">Coaching:</strong> {coaching}</div>')

            fb1, fb2, _ = st.columns([1, 1, 6])
            with fb1:
                st.button("👍", key=f"u_{iid}_{idx}", help="Helpful",
                          on_click=lambda iid=iid: api_post(f"/api/v1/insights/{iid}/feedback", json={"feedback": "positive"}))
            with fb2:
                st.button("👎", key=f"d_{iid}_{idx}", help="Needs work",
                          on_click=lambda iid=iid: api_post(f"/api/v1/insights/{iid}/feedback", json={"feedback": "negative"}))
            st.markdown("---")

    remaining = [i for i in insights if not i.get("is_top_insight")]
    if remaining:
        with st.expander(f"All Framework Results ({len(remaining)} more)"):
            for ins in remaining:
                sev = ins.get("severity", "yellow").lower()
                color, _ = sev_color(sev)
                score = int(ins.get("confidence", 0) * 100)
                headline = ins.get("headline", "")
                coaching_r = ins.get("coaching_recommendation", "")
                st.html(f'{sev_dot(sev)} <b>{ins.get("framework_name","")}</b> — {score}%')
                st.caption(headline)
                if coaching_r and "Unable to generate" not in coaching_r:
                    with st.expander(f"Coaching for {ins.get('framework_name', '')}"):
                        st.markdown(_esc_md(coaching_r))


def _render_stats(metrics, summary):
    st.markdown("### Call Stats")
    if not metrics:
        st.info("Base metrics not yet available. They are computed during analysis.")
        # Still show severity if summary exists
        if summary and summary.get("severity_breakdown"):
            _render_severity_bars(summary)
        return

    # Talk ratio donut
    rep_r = metrics.get("rep_talk_ratio", 0)
    buyer_r = metrics.get("buyer_talk_ratio", 0)
    rep_deg = int(rep_r * 360)
    st.markdown("**Talk Ratio**")
    st.html(f"""
    <div style="display:flex;align-items:center;gap:20px;margin:8px 0 16px">
        <div style="width:72px;height:72px;border-radius:50%;
            background:conic-gradient(#3B82F6 0deg {rep_deg}deg, #F59E0B {rep_deg}deg 360deg);
            display:flex;align-items:center;justify-content:center">
            <div style="width:44px;height:44px;border-radius:50%;background:{BG_CARD};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:{TEXT_PRIMARY}">
                {rep_r:.0%}
            </div>
        </div>
        <div style="font-size:13px">
            <div><span style="color:#60A5FA;font-weight:700">■</span> Rep: {rep_r:.0%}</div>
            <div><span style="color:#FBBF24;font-weight:700">■</span> Buyer: {buyer_r:.0%}</div>
        </div>
    </div>
    """)

    # 2-column grid
    c1, c2 = st.columns(2)
    est = " (est.)" if metrics.get("wpm_estimated") else ""
    metric_pairs = [
        (c1, f"{metrics.get('rep_questions',0)} / {metrics.get('buyer_questions',0)}", "Questions (Rep / Buyer)"),
        (c2, f"{metrics.get('rep_filler_rate_per_min',0)} / {metrics.get('buyer_filler_rate_per_min',0)}", "Filler Words/Min"),
        (c1, f"{metrics.get('rep_wpm',0)} / {metrics.get('buyer_wpm',0)}", f"Words/Min{est} (Rep / Buyer)"),
        (c2, str(metrics.get('interruption_count', 0)), "Interruptions"),
        (c1, f"{metrics.get('rep_longest_monologue_seconds',0)}s", "Longest Rep Monologue"),
        (c2, f"{metrics.get('rep_avg_response_latency_seconds',0)}s / {metrics.get('buyer_avg_response_latency_seconds',0)}s", "Response Latency"),
        (c1, f"{metrics.get('silence_percentage',0)}%", "Silence"),
        (c2, f"{metrics.get('longest_silence_seconds',0)}s", "Longest Silence"),
    ]
    for col, val, label in metric_pairs:
        with col:
            st.html(f'<div class="stat-card" style="margin-bottom:8px"><div style="font-size:18px;font-weight:700;color:{TEXT_PRIMARY}">{val}</div><div class="stat-label">{label}</div></div>')

    st.markdown("---")
    if summary:
        _render_severity_bars(summary)


def _render_severity_bars(summary):
    st.markdown("**Severity Breakdown**")
    sev_counts = summary.get("severity_breakdown") or {}
    total = sum(sev_counts.values()) or 1
    for sev_key, label in [("red", "Critical"), ("orange", "Warning"), ("yellow", "Note"), ("green", "Positive")]:
        count = sev_counts.get(sev_key, 0)
        color, _ = sev_color(sev_key)
        st.html(f'{sev_dot(sev_key)} <b style="color:{color}">{label}</b>: {count}')
        st.progress(count / total)


def _render_summary(summary, insights):
    st.markdown("### Call Summary")
    if not summary:
        st.info("Summary not available yet.")
        return

    # Recap
    recap = summary.get("recap") or summary.get("ai_summary_text") or ""
    if recap:
        st.markdown("**RECAP**")
        st.info(recap)

    # Key decisions
    decisions = summary.get("key_decisions") or []
    if decisions:
        st.markdown("**KEY DECISIONS**")
        for d in decisions:
            st.markdown(f"- {d}")

    # Action items
    rep_actions = summary.get("action_items_rep") or []
    buyer_actions = summary.get("action_items_buyer") or []
    if rep_actions or buyer_actions:
        st.markdown("**ACTION ITEMS**")
        for a in rep_actions:
            st.markdown(f"- Rep: {a}")
        for a in buyer_actions:
            st.markdown(f"- Buyer: {a}")

    # Open questions
    open_q = summary.get("open_questions") or []
    if open_q:
        st.markdown("**OPEN QUESTIONS**")
        for q in open_q:
            st.markdown(f"- {q}")

    # Deal assessment
    assessment = summary.get("deal_assessment") or ""
    if assessment:
        st.markdown("**DEAL ASSESSMENT**")
        sev = summary.get("severity_breakdown") or {}
        if sev.get("red", 0) >= 2:
            st.error(assessment)
        elif sev.get("red", 0) >= 1 or sev.get("orange", 0) >= 2:
            st.warning(assessment)
        else:
            st.success(assessment)

    # Coaching focus
    focus = summary.get("coaching_focus") or ""
    if focus:
        st.markdown("**COACHING FOCUS**")
        st.html(f'<div class="coaching-box">{focus}</div>')

    # Key themes
    themes = summary.get("key_themes") or []
    if themes:
        st.markdown("---")
        st.markdown("**Key Themes**")
        for t in themes:
            st.markdown(f"- {t}")

    # Key concerns from insights
    red_orange = [i for i in insights if i.get("severity", "").lower() in ("red", "orange")]
    if red_orange:
        st.markdown("---")
        st.markdown("**Key Concerns**")
        for ins in red_orange[:3]:
            sev = ins.get("severity", "yellow").lower()
            st.html(f'{sev_dot(sev)} <b>{ins.get("framework_name","")}</b>: {ins.get("headline","")}')


def _render_frameworks(insights):
    # Filter out stubs
    insights = [i for i in insights if i.get("headline") != "Analysis unavailable" and i.get("confidence", 0) > 0]
    st.markdown("### Framework Results")
    if not insights:
        st.info("No framework results available.")
        return

    # Group using fuzzy matching
    grouped = {"A": [], "B": [], "C": [], "E": [], "Other": []}
    for ins in insights:
        fw_name = ins.get("framework_name", "")
        # Use prompt_group from API if available, else fuzzy match
        group = ins.get("prompt_group") or _fw_group_for(fw_name)
        grouped.setdefault(group, []).append(ins)

    for gid in ["A", "B", "C", "E", "F"]:
        items = grouped.get(gid, [])
        group_label = FW_GROUPS.get(gid, (f"Group {gid}", []))[0]

        with st.expander(f"Group {gid}: {group_label} — {len(items)} result{'s' if len(items) != 1 else ''}", expanded=bool(items)):
            if not items:
                st.caption("No active frameworks in this group for this call type.")
            for ins in items:
                sev = ins.get("severity", "yellow").lower()
                color, _ = sev_color(sev)
                score = int(ins.get("confidence", 0) * 100)
                explanation = ins.get("explanation", "")
                coaching_fw = ins.get("coaching_recommendation", "")
                st.html(f"""
                <div style="padding:10px 14px;border-left:3px solid {color};margin-bottom:10px;border-radius:0 6px 6px 0;background:{BG_ELEVATED}">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        {sev_dot(sev)}
                        <span style="font-weight:700;font-size:13px;color:{TEXT_PRIMARY}">{ins.get('framework_name','')}</span>
                        <span class="sev-badge {sev}" style="font-size:9px">{sev.upper()}</span>
                        <span style="font-size:11px;color:{TEXT_MUTED}">{score}%</span>
                    </div>
                    <div style="font-size:13px;font-weight:600;color:{TEXT_PRIMARY}">{ins.get('headline','')}</div>
                    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:4px;line-height:1.5">{_esc(explanation)}</div>
                </div>
                """)
                if coaching_fw and "Unable to generate" not in coaching_fw:
                    with st.expander(f"Coaching: {ins.get('framework_name', '')}"):
                        formatted = _format_coaching_text(coaching_fw)
                        st.markdown(formatted)

    # Other/ungrouped
    other = grouped.get("Other", [])
    if other:
        with st.expander(f"Other — {len(other)} results"):
            for ins in other:
                st.markdown(f"- **{ins.get('framework_name','')}**: {ins.get('headline','')[:80]}")


# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════

# Top bar
st.html(f"""
<div style="display:flex;align-items:center;padding:12px 24px;background:{BG_CARD};border-bottom:1px solid {BORDER}">
    <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:22px">🔊</span>
        <span style="font-size:17px;font-weight:800;color:{ACCENT};letter-spacing:-0.5px">Signal</span>
        <span style="font-size:10px;background:{ACCENT};color:white;padding:2px 6px;border-radius:8px;font-weight:700">BETA</span>
    </div>
</div>
""")

# Sidebar
with st.sidebar:
    st.html(f"""
    <div style="padding:20px 16px 10px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px">
            <span style="font-size:24px">🔊</span>
            <div>
                <div style="font-size:16px;font-weight:800;color:{TEXT_PRIMARY};line-height:1">Signal</div>
                <div style="font-size:10px;color:{TEXT_MUTED};letter-spacing:0.5px">BEHAVIORAL INTELLIGENCE</div>
            </div>
        </div>
    </div>
    """)

    for label, key in [("📊 Dashboard", "dashboard"), ("📞 All Calls", "calls"), ("🚀 Analyze", "submit")]:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state["view"] = key
            if key in ("dashboard", "calls"):
                st.session_state.pop("view_call_id", None)
            st.rerun()

    st.markdown("---")
    if backend_online():
        st.success("Backend online")
    else:
        st.error("Backend offline")

    st.html(f"""
    <div style="margin-top:16px;padding:12px;background:{BG_ELEVATED};border-radius:8px;border:1px solid {BORDER}">
        <div style="font-size:11px;color:{TEXT_MUTED};line-height:1.7">
            <strong style="color:{TEXT_PRIMARY}">Signal v0.2.0</strong><br>
            Backend: FastAPI · Pipeline: LangGraph<br>
            Intelligence: 17 frameworks · 7-gate verify<br>
            LLM: Vertex AI / Gemini 2.5 Flash
        </div>
    </div>
    """)

# Route
view = st.session_state.get("view", "dashboard")
{"dashboard": page_dashboard, "calls": page_calls_list, "submit": page_submit, "call_review": page_call_review}.get(view, page_dashboard)()
