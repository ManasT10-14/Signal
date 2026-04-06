"""
LangGraph Pipeline Workflow — the orchestration graph.

ARQ enqueues a job → this workflow executes: Pass 1 → Route → Execute Groups → Verify → Insights.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END, START
from typing import Literal

from signalapp.pipeline.state import PipelineState


def create_pipeline_workflow():
    """
    Create the LangGraph pipeline workflow.

    Nodes:
        pass1_extract: Run Pass 1 infrastructure extraction
        route_frameworks: Decide which frameworks run
        execute_groups: Fan out to Pass 2 groups (A/B/C/E in parallel)
        verify_results: Run 7-gate verification
        generate_insights: Build insight entities
        generate_summary: AI summary generation
        store_results: Persist to DB

    Edges:
        pass1_extract → route_frameworks
        route_frameworks → execute_groups (conditional on active_frameworks)
        execute_groups → verify_results
        verify_results → generate_insights
        generate_insights → generate_summary
        generate_summary → store_results → END
    """
    from signalapp.pipeline.nodes.base_metrics import base_metrics_node
    from signalapp.pipeline.nodes.pass1_extract import pass1_extract_node
    from signalapp.pipeline.nodes.route import route_node
    from signalapp.pipeline.nodes.execute_groups import execute_groups_node
    from signalapp.pipeline.nodes.verify import verify_node
    from signalapp.pipeline.nodes.insights import generate_insights_node
    from signalapp.pipeline.nodes.summary import generate_summary_node
    from signalapp.pipeline.nodes.store import store_results_node

    # Build the graph
    builder = StateGraph(PipelineState)

    # Add nodes
    builder.add_node("base_metrics", base_metrics_node)
    builder.add_node("pass1_extract", pass1_extract_node)
    builder.add_node("route_frameworks", route_node)
    builder.add_node("execute_groups", execute_groups_node)
    builder.add_node("verify_results", verify_node)
    builder.add_node("generate_insights", generate_insights_node)
    builder.add_node("generate_summary", generate_summary_node)
    builder.add_node("store_results", store_results_node)

    # Edges
    builder.add_edge(START, "base_metrics")
    builder.add_edge("base_metrics", "pass1_extract")
    builder.add_edge("pass1_extract", "route_frameworks")
    builder.add_edge("route_frameworks", "execute_groups")
    builder.add_edge("execute_groups", "verify_results")
    builder.add_edge("verify_results", "generate_insights")
    builder.add_edge("generate_insights", "generate_summary")
    builder.add_edge("generate_summary", "store_results")
    builder.add_edge("store_results", END)

    return builder.compile()
