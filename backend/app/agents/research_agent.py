from __future__ import annotations

from typing import Any

from .workflow import ResearchWorkflow, WorkflowState


DISCLAIMER = "Research assistance only; not medical advice or a validated biological conclusion."


def answer_question(
    question: str,
    image_analysis: dict[str, Any] | None = None,
    experiment_analysis: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    state = ResearchWorkflow().run(
        WorkflowState(
            question,
            image_analysis,
            experiment_analysis,
            conversation_history=conversation_history or [],
        )
    )

    return {
        "answer": "\n\n".join(state.sections),
        "tools_used": state.tools_used,
        "sources": [
            {key: source[key] for key in ("id", "title", "url", "section")}
            for source in state.sources
        ],
        "evidence_sufficient": state.evidence_sufficient,
        "workflow_trace": state.trace,
        "disclaimer": DISCLAIMER,
    }
