"""
Cost tracking for LLM calls.
Records and aggregates cost data per call and across time periods.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy import select, func

from signalapp.db.repository import get_session
from signalapp.db.models import Call, AnalysisRun, FrameworkResult, Pass1Result


@dataclass
class CallCost:
    """Cost data for a single LLM call."""
    call_id: str
    analysis_run_id: str | None = None
    llm_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    model: str = ""
    prompt_group: str | None = None
    framework_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Token counts
    tokens_input: int = 0
    tokens_output: int = 0

    # Performance
    latency_ms: int = 0


class CostTracker:
    """
    Track and aggregate LLM costs across calls.

    Usage:
        tracker = CostTracker()
        await tracker.record(CallCost(call_id="...", llm_cost_usd=0.05, ...))
        cost = await tracker.get_call_cost(call_id)
        total = await tracker.get_total_cost_period(start, end)
    """

    async def record(self, cost: CallCost) -> None:
        """
        Record a cost entry for a call.

        Note: For MVP, cost data is stored in the existing FrameworkResult/Pass1Result
        records in the DB. This method can be extended to store dedicated cost records.
        """
        # Cost data is already persisted in FrameworkResult.cost_usd and Pass1Result.cost_usd
        # This method provides a programmatic interface for cost tracking
        pass

    async def get_call_cost(self, call_id: str) -> CallCost | None:
        """
        Get total cost for a specific call.

        Sums up all FrameworkResult and Pass1Result costs for the call.
        """
        try:
            call_uuid = uuid.UUID(call_id)
        except ValueError:
            return None

        async for session in get_session():
            # Get all framework results for this call's analysis runs
            result = await session.execute(
                select(func.sum(FrameworkResult.cost_usd))
                .join(AnalysisRun)
                .where(AnalysisRun.call_id == call_uuid)
            )
            framework_cost = result.scalar() or 0.0

            # Get pass1 cost
            result = await session.execute(
                select(func.sum(Pass1Result.cost_usd))
                .join(AnalysisRun)
                .where(AnalysisRun.call_id == call_uuid)
            )
            pass1_cost = result.scalar() or 0.0

            total = framework_cost + pass1_cost

            if total == 0:
                return None

            return CallCost(
                call_id=call_id,
                llm_cost_usd=total,
                total_cost_usd=total,
            )

    async def get_total_cost_period(self, start: datetime, end: datetime) -> float:
        """
        Get total cost across all calls in a time period.

        Args:
            start: Start of time period
            end: End of time period

        Returns:
            Total cost in USD
        """
        async for session in get_session():
            # Sum framework result costs
            result = await session.execute(
                select(func.sum(FrameworkResult.cost_usd))
                .join(AnalysisRun)
                .where(AnalysisRun.started_at >= start)
                .where(AnalysisRun.started_at <= end)
            )
            framework_cost = result.scalar() or 0.0

            # Sum pass1 costs
            result = await session.execute(
                select(func.sum(Pass1Result.cost_usd))
                .join(AnalysisRun)
                .where(AnalysisRun.started_at >= start)
                .where(AnalysisRun.started_at <= end)
            )
            pass1_cost = result.scalar() or 0.0

            return framework_cost + pass1_cost


# Global cost tracker instance
_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker