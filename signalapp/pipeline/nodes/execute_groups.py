"""
Framework group execution node — fans out to Pass 2 group LLM calls in parallel.

Each group (A/B/C/E) runs concurrently. Within each group, frameworks run concurrently.
All results are collected into framework_results dict keyed by fw_id.
"""
from __future__ import annotations

import asyncio
import logging
import os
from signalapp.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

# Mapping: fw_id (int) → (group_id, prompt_module_path, output_class_name)
# prompt_module_path: dotted path to the module
# output_class_name: Pydantic output model class name
FW_PROMPT_MAP: dict[int, tuple[str, str, str]] = {
    # Group A — Negotiation Intelligence
    3: ("A", "signalapp.prompts.groups.group_a.batna_detection_v1", "BatnaDetectionOutput"),
    4: ("A", "signalapp.prompts.groups.group_a.money_left_on_table_v1", "MoneyLeftOnTableOutput"),
    7: ("A", "signalapp.prompts.groups.group_a.first_number_tracker_v1", "FirstNumberTrackerOutput"),
    12: ("A", "signalapp.prompts.groups.group_a.deal_health_v1", "DealHealthOutput"),
    13: ("A", "signalapp.prompts.groups.group_a.deal_timing_v1", "DealTimingOutput"),
    # Group B — Pragmatic Intelligence
    1: ("B", "signalapp.prompts.groups.group_b.unanswered_questions_v1", "UnansweredQuestionsOutput"),
    2: ("B", "signalapp.prompts.groups.group_b.commitment_quality_v1", "CommitmentQualityOutput"),
    6: ("B", "signalapp.prompts.groups.group_b.commitment_thermometer_v1", "CommitmentThermometerOutput"),
    16: ("B", "signalapp.prompts.groups.group_b.pushback_classification_v1", "PushbackClassificationOutput"),
    # Group C — Strategic Clarity
    5: ("C", "signalapp.prompts.groups.group_c.question_quality_v1", "QuestionQualityOutput"),
    10: ("C", "signalapp.prompts.groups.group_c.frame_match_v1", "FrameMatchOutput"),
    11: ("C", "signalapp.prompts.groups.group_c.close_attempt_v1", "CloseAttemptOutput"),
    14: ("C", "signalapp.prompts.groups.group_c.methodology_v1", "MethodologyComplianceOutput"),
    15: ("C", "signalapp.prompts.groups.group_c.call_structure_v1", "CallStructureOutput"),
    17: ("C", "signalapp.prompts.groups.group_c.objection_response_v1", "ObjectionResponseOutput"),
    # Group E — Emotional Resonance
    8: ("E", "signalapp.prompts.groups.group_e.emotional_turning_points_v1", "EmotionTriggerOutput"),
    9: ("E", "signalapp.prompts.groups.group_e.emotional_turning_points_v1", "EmotionTriggerOutput"),
}


# Group → LLM config key in AppConfig
GROUP_LLM_CONFIG_KEY: dict[str, str] = {
    "A": "llm_group_a",
    "B": "llm_group_b",
    "C": "llm_group_c",
    "E": "llm_group_e",
}


def _check_llm_available() -> bool:
    """Check if LLM credentials are configured."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return bool(gemini_key or gcp_project)


async def execute_groups_node(state: PipelineState) -> dict:
    """
    Execute all active framework groups in parallel.

    Inputs: active_frameworks, pass1_result, transcript_segments
    Outputs: framework_results (fw_id → FrameworkOutput), framework_errors (fw_id → error str)

    Fails gracefully: individual framework errors don't block other frameworks.
    """
    from signalapp.app.config import get_config
    from signalapp.adapters.llm.gemini import GeminiProvider
    from signalapp.adapters.llm.base import LLMConfig
    from signalapp.domain.framework import FrameworkOutput

    # LLM availability guard — fail fast if no credentials
    if not _check_llm_available():
        logger.warning(
            "execute_groups_node: No LLM credentials configured. "
            "Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT environment variable. "
            "Returning stub results."
        )
        active_frameworks = state.get("active_frameworks", [])
        framework_results = {}
        framework_errors = {}
        for fw_id in active_frameworks:
            framework_results[fw_id] = _stub_framework_output(
                fw_id, "LLM credentials not configured"
            ).model_dump()
            framework_errors[fw_id] = "LLM not available"
        return {
            "framework_results": framework_results,
            "framework_errors": framework_errors,
        }

    config = get_config()
    provider = GeminiProvider()

    active_frameworks = state["active_frameworks"]
    pass1_result = state.get("pass1_result") or {}

    if not active_frameworks:
        return {"framework_results": {}, "framework_errors": {}}

    # Format transcript for prompts
    transcript_text = _format_transcript(state["transcript_segments"])
    hedge_data = pass1_result.get("hedge_data", [])
    sentiment_data = pass1_result.get("sentiment_data", [])
    appraisal_data = pass1_result.get("appraisal_data", [])

    # Build tasks for all active frameworks
    tasks = []
    fw_ids = sorted(active_frameworks)

    for fw_id in fw_ids:
        if fw_id not in FW_PROMPT_MAP:
            # Unknown framework — skip gracefully
            continue

        group_id, module_path, output_class_name = FW_PROMPT_MAP[fw_id]

        # Get LLM config for this group
        config_key = GROUP_LLM_CONFIG_KEY.get(group_id, "llm_group_b")
        llm_config_obj = getattr(config, config_key, config.llm_group_b)

        task = _run_framework(
            provider=provider,
            fw_id=fw_id,
            group_id=group_id,
            module_path=module_path,
            output_class_name=output_class_name,
            llm_config=LLMConfig(
                model=llm_config_obj.model,
                temperature=llm_config_obj.temperature,
                max_tokens=llm_config_obj.max_tokens,
                provider="gemini",
            ),
            transcript_text=transcript_text,
            hedge_data=hedge_data,
            sentiment_data=sentiment_data,
            appraisal_data=appraisal_data,
        )
        tasks.append(task)

    # Run all frameworks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect results
    framework_results = {}
    framework_errors = {}

    for fw_id, result in zip(fw_ids, results):
        if isinstance(result, Exception):
            framework_errors[fw_id] = str(result)
        elif result is not None:
            # Serialize FrameworkOutput to dict for TypedDict compatibility
            framework_results[fw_id] = result.model_dump()
        else:
            framework_errors[fw_id] = "No output returned"

    return {
        "framework_results": framework_results,
        "framework_errors": framework_errors,
    }


async def _run_framework(
    provider: GeminiProvider,
    fw_id: int,
    group_id: str,
    module_path: str,
    output_class_name: str,
    llm_config: LLMConfig,
    transcript_text: str,
    hedge_data: list,
    sentiment_data: list,
    appraisal_data: list,
):
    """Run a single framework LLM call and return FrameworkOutput."""
    import importlib
    import json

    # Dynamically load prompt module
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return _stub_framework_output(fw_id, f"Prompt module not found: {module_path}")

    output_class = getattr(module, output_class_name, None)
    if output_class is None:
        return _stub_framework_output(fw_id, f"Output class {output_class_name} not found in {module_path}")

    system_prompt = getattr(module, "SYSTEM_PROMPT", "")
    user_template = getattr(module, "USER_PROMPT", "")

    # Format user prompt with pass1 data
    user_prompt = user_template.format(
        transcript_text=transcript_text,
        pass1_hedge_data=json.dumps(hedge_data, indent=2) if hedge_data else "None",
        pass1_sentiment_data=json.dumps(sentiment_data, indent=2) if sentiment_data else "None",
        pass1_appraisal_data=json.dumps(appraisal_data, indent=2) if appraisal_data else "None",
    )

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    try:
        result = await provider.complete_structured(
            prompt=full_prompt,
            response_model=output_class,
            config=llm_config,
        )

        # Convert to FrameworkOutput
        return _to_framework_output(fw_id, result)

    except Exception as e:
        return _stub_framework_output(fw_id, f"LLM call failed: {str(e)}")


def _to_framework_output(fw_id: int, raw_result) -> FrameworkOutput:
    """Convert a Pydantic output model to a FrameworkOutput."""
    from signalapp.domain.framework import FrameworkOutput as FO, Severity

    # Map severity string to enum
    sev = raw_result.severity if hasattr(raw_result, "severity") else "green"
    try:
        severity_enum = Severity(sev)
    except ValueError:
        severity_enum = Severity.YELLOW

    # Extract score
    score = None
    if hasattr(raw_result, "health_score"):
        score = raw_result.health_score * 100
    elif hasattr(raw_result, "compliance_score"):
        score = raw_result.compliance_score * 100
    elif hasattr(raw_result, "response_score"):
        score = raw_result.response_score * 100
    elif hasattr(raw_result, "alignment_score"):
        score = raw_result.alignment_score * 100
    elif hasattr(raw_result, "structure_score"):
        score = raw_result.structure_score * 100
    elif hasattr(raw_result, "urgency_score"):
        score = raw_result.urgency_score * 100
    elif hasattr(raw_result, "buyer_leverage_score"):
        score = raw_result.buyer_leverage_score * 100

    # Get AIM output if present
    aim_output = None
    is_aim_null = False
    if hasattr(raw_result, "is_aim_null_finding"):
        is_aim_null = raw_result.is_aim_null_finding
    if hasattr(raw_result, "aim_output"):
        aim_output = raw_result.aim_output

    # Build FrameworkOutput
    return FO(
        framework_id=f"FW-{fw_id:02d}",
        framework_name=getattr(raw_result, "headline", f"Framework {fw_id}")[:40],
        score=score,
        severity=severity_enum,
        confidence=getattr(raw_result, "confidence", 0.5),
        headline=getattr(raw_result, "headline", f"Framework {fw_id} result"),
        explanation=getattr(raw_result, "explanation", ""),
        evidence=[],
        coaching_recommendation=getattr(raw_result, "coaching_recommendation", ""),
        raw_analysis=raw_result.model_dump() if hasattr(raw_result, "model_dump") else {},
        is_aim_null_finding=is_aim_null,
        aim_output=aim_output,
    )


def _stub_framework_output(fw_id: int, error: str) -> FrameworkOutput:
    """Return a stub FrameworkOutput when LLM call fails."""
    from signalapp.domain.framework import FrameworkOutput, Severity

    return FrameworkOutput(
        framework_id=f"FW-{fw_id:02d}",
        framework_name=f"Framework {fw_id}",
        score=None,
        severity=Severity.YELLOW,
        confidence=0.0,
        headline=f"Analysis unavailable",
        explanation=f"Analysis could not be completed: {error}",
        evidence=[],
        coaching_recommendation="Unable to generate recommendation.",
        raw_analysis={"error": error},
        is_aim_null_finding=False,
    )


def _format_transcript(segments: list[dict]) -> str:
    """Format serialized TranscriptSegment dicts into LLM input."""
    lines = []
    for seg in segments:
        start_ms = seg.get("start_time_ms", 0)
        mins, secs = divmod(start_ms // 1000, 60)
        timestamp = f"{mins:02d}:{secs:02d}"
        speaker = seg.get("speaker_name", "Unknown")
        role = seg.get("speaker_role", "unknown")
        text = seg.get("text", "")
        lines.append(f"[{timestamp}] {speaker} ({role}): {text}")
    return "\n".join(lines)
