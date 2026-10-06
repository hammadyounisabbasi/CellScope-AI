from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from backend.app.rag import retrieve


@dataclass
class WorkflowState:
    question: str
    image_analysis: dict[str, Any] | None
    experiment_analysis: dict[str, Any] | None
    requested_nodes: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)


class ResearchWorkflow:
    """Small deterministic state graph for grounded research assistance.

    Nodes mutate explicit state and conditional edges are selected by the
    intent planner. No node can derive measurements from raw prose or pixels;
    quantitative claims come only from structured analysis results.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Callable[[WorkflowState], None]] = {
            "intent_context_analyzer": self._plan,
            "microscopy_analysis_tool": self._image,
            "experiment_analysis_tool": self._experiment,
            "scientific_retrieval_tool": self._retrieval,
            "evidence_interpretation": self._interpret,
            "response_composer": self._compose,
        }

    def run(self, state: WorkflowState) -> WorkflowState:
        queue = ["intent_context_analyzer"]
        while queue:
            node_name = queue.pop(0)
            before = len(state.sections)
            self.nodes[node_name](state)
            state.trace.append(
                {
                    "node": node_name,
                    "status": "completed",
                    "sections_added": len(state.sections) - before,
                }
            )
            if node_name == "intent_context_analyzer":
                queue.extend(state.requested_nodes)
                queue.extend(["evidence_interpretation", "response_composer"])
        return state

    @staticmethod
    def _plan(state: WorkflowState) -> None:
        lowered = state.question.lower()
        general = ("measure", "difference", "result", "finding", "found", "interpret", "next", "summary", "summarize", "explain", "report")
        image_terms = ("image", "cell", "morph", "object", "abnormal", "sample", "segment")
        experiment_terms = ("experiment", "control", "treat", "compare", "stat", "anomal", "sample", "effect")
        retrieval_terms = ("literature", "paper", "source", "evidence", "reference", "method", "bbbc", "otsu", "watershed")
        broad = any(term in lowered for term in general)
        if state.image_analysis and (broad or any(term in lowered for term in image_terms)):
            state.requested_nodes.append("microscopy_analysis_tool")
        if state.experiment_analysis and (broad or any(term in lowered for term in experiment_terms)):
            state.requested_nodes.append("experiment_analysis_tool")
        if any(term in lowered for term in retrieval_terms) or not state.requested_nodes:
            state.requested_nodes.append("scientific_retrieval_tool")

    @staticmethod
    def _image(state: WorkflowState) -> None:
        metrics = (state.image_analysis or {}).get("metrics", {})
        state.tools_used.append("microscopy_image_analysis")
        state.sections.append(
            "MEASURED RESULT\n"
            f"The deterministic pipeline segmented {metrics.get('object_count', 'unknown')} objects. "
            f"Mean area was {metrics.get('mean_area_px', 'unknown')} px², mean circularity was "
            f"{metrics.get('mean_circularity', 'unknown')}, and foreground fraction was "
            f"{metrics.get('foreground_fraction', 'unknown')}.\n"
            "These image-derived measurements do not independently establish cell identity, viability, or disease."
        )

    @staticmethod
    def _experiment(state: WorkflowState) -> None:
        data = state.experiment_analysis or {}
        lines = ["STATISTICAL OBSERVATION"]
        lines.extend(data.get("observations", [])[:5])
        comparisons = data.get("group_comparisons", [])
        if comparisons:
            strongest = max(comparisons, key=lambda item: abs(item.get("cohens_d") or 0))
            lines.append(
                f"The largest standardized difference among tested features was {strongest.get('feature')} "
                f"(Cohen's d={strongest.get('cohens_d')}, unadjusted p={strongest.get('p_value_unadjusted')})."
            )
        lines.append("Associations and anomaly flags require experimental and multiple-testing review; they are not causal findings.")
        state.tools_used.append("experiment_csv_analysis")
        state.sections.append("\n".join(lines))

    @staticmethod
    def _retrieval(state: WorkflowState) -> None:
        state.sources = retrieve(state.question)
        state.tools_used.append("retrieve_scientific_context")
        if state.sources:
            lines = ["RETRIEVED EVIDENCE"]
            lines.extend(f"[{source['id']}] {source['text']}" for source in state.sources)
            state.sections.append("\n".join(lines))
        else:
            state.sections.append("RETRIEVED EVIDENCE\nNo sufficiently relevant source was found in the curated offline knowledge base.")

    @staticmethod
    def _interpret(state: WorkflowState) -> None:
        if state.sections:
            state.sections.append(
                "AI INTERPRETATION\nThe available measurements can prioritize follow-up checks, but they are not "
                "sufficient for a causal or biological conclusion. Confirm segmentation visually, inspect "
                "replicates, and pre-specify an appropriate statistical analysis."
            )

    @staticmethod
    def _compose(state: WorkflowState) -> None:
        if not state.sections:
            state.sections.append(
                "EVIDENCE LIMITATION\nThe available experiment context and local knowledge base do not support "
                "a grounded answer. Upload an analysis result or consult a relevant primary source."
            )

