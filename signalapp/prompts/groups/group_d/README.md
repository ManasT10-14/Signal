# Group D — Deal Health (Phase 2 Scaffolded)

## Status: Phase 2 — Not Yet Implemented

This directory is reserved for **Deal Health** frameworks that operate **across multiple calls in a deal**, not on single-call analysis. These composite frameworks aggregate behavioral signals from multiple Phase 1 framework outputs to produce deal-level intelligence.

## Planned Frameworks

| # | Framework | Description | Dependencies |
|---|-----------|-------------|--------------|
| #30 | Buying Signal Strength | Tracks commitment trajectory, engagement decline, and readiness signals across deal lifecycle | Aggregates #2 (Commitment Quality), #6 (Commitment Thermometer), #13 (Deal Timing) |
| #31 | Negotiation Power Index | Composite power dynamics score based on BATNA strength, question quality, and framing alignment | Aggregates #3 (BATNA), #5 (Question Quality), #10 (Frame Match) |

## Architecture Note

Group D frameworks run at the **deal level** after multiple calls have been analyzed. They require:
- Longitudinal data from 3+ calls in a deal
- Framework outputs from each call's Phase 1 analysis
- Deal-level state management (Phase 2 LangGraph deal workflow)

## When to Implement

Phase 2 of the Signal roadmap, after:
- Phase 1 core pipeline is production-stable
- Deal-level workflow is designed
- Longitudinal storage and aggregation is implemented

## Files

- `__init__.py` — Package marker with Phase 2 status note
- `README.md` — This file
