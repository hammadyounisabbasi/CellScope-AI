from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from backend.app.agents.intents import (
    AREA_ANALYSIS,
    CIRCULARITY_ANALYSIS,
    CORRELATIONS,
    EFFECT_SIZE,
    EXPERIMENT_INTENTS,
    EXPERIMENT_SUMMARY,
    FOLLOW_UP,
    FOREGROUND_COVERAGE,
    GENERAL_EXPERIMENT_QUESTION,
    GENERAL_IMAGE_QUESTION,
    GROUP_COMPARISON,
    IMAGE_INTENTS,
    LIMITATIONS,
    MICROSCOPY_SUMMARY,
    MISSING_DATA,
    MORPHOLOGY,
    OBJECT_COUNT,
    OUTLIERS,
    QUALITY_OR_FOCUS,
    SCIENTIFIC_EVIDENCE,
    SEGMENTATION_EXPLANATION,
    STRONGEST_CHANGE,
    classify_question,
)
from backend.app.rag import retrieve


@dataclass
class WorkflowState:
    question: str
    image_analysis: dict[str, Any] | None
    experiment_analysis: dict[str, Any] | None
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    requested_nodes: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    interpretation_lines: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    resolved_question: str = ""
    wants_explanation: bool = False
    clinical_or_biological_claim: bool = False
    needs_interpretation: bool = False
    evidence_sufficient: bool = False


def _display(value: Any, fallback: str = "not available") -> str:
    return fallback if value is None else str(value)


def _section(heading: str, lines: list[str]) -> str:
    return f"{heading}\n" + "\n".join(line for line in lines if line)


def _strongest(comparisons: list[dict[str, Any]]) -> dict[str, Any] | None:
    usable = [item for item in comparisons if isinstance(item.get("cohens_d"), (int, float))]
    return max(usable, key=lambda item: abs(item["cohens_d"])) if usable else None


class ResearchWorkflow:
    """Deterministic, multi-intent state graph for grounded research answers."""

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
            trace_item: dict[str, Any] = {
                "node": node_name,
                "status": "completed",
                "sections_added": len(state.sections) - before,
            }
            if node_name == "intent_context_analyzer":
                trace_item["intents"] = state.intents
                trace_item["requested_nodes"] = state.requested_nodes
            state.trace.append(trace_item)
            if node_name == "intent_context_analyzer":
                queue.extend(state.requested_nodes)
                if state.needs_interpretation:
                    queue.append("evidence_interpretation")
                queue.append("response_composer")
        return state

    @staticmethod
    def _plan(state: WorkflowState) -> None:
        classification = classify_question(
            state.question,
            has_image=bool(state.image_analysis),
            has_experiment=bool(state.experiment_analysis),
            history=state.conversation_history,
        )
        state.intents = classification["intents"]
        state.resolved_question = classification["resolved_question"]
        state.wants_explanation = classification["wants_explanation"]
        state.clinical_or_biological_claim = classification["clinical_or_biological_claim"]

        if state.image_analysis and any(intent in IMAGE_INTENTS for intent in state.intents):
            state.requested_nodes.append("microscopy_analysis_tool")
        if state.experiment_analysis and any(intent in EXPERIMENT_INTENTS for intent in state.intents):
            state.requested_nodes.append("experiment_analysis_tool")
        if SCIENTIFIC_EVIDENCE in state.intents or not state.requested_nodes:
            state.requested_nodes.append("scientific_retrieval_tool")

        explanatory_intents = {
            MICROSCOPY_SUMMARY,
            AREA_ANALYSIS,
            CIRCULARITY_ANALYSIS,
            FOREGROUND_COVERAGE,
            QUALITY_OR_FOCUS,
            EXPERIMENT_SUMMARY,
            GROUP_COMPARISON,
            STRONGEST_CHANGE,
            EFFECT_SIZE,
            CORRELATIONS,
        }
        state.needs_interpretation = (
            SCIENTIFIC_EVIDENCE in state.intents
            or MICROSCOPY_SUMMARY in state.intents
            or EXPERIMENT_SUMMARY in state.intents
            or (state.wants_explanation and any(intent in explanatory_intents for intent in state.intents))
        )

    @staticmethod
    def _image(state: WorkflowState) -> None:
        data = state.image_analysis or {}
        metrics = data.get("metrics", {})
        intents = set(state.intents) & (IMAGE_INTENTS | {LIMITATIONS, FOLLOW_UP, SCIENTIFIC_EVIDENCE})
        state.tools_used.append("microscopy_image_analysis")

        if state.clinical_or_biological_claim:
            state.sections.append(
                _section(
                    "EVIDENCE LIMITATION",
                    [
                        "The current analysis cannot establish health, viability, disease, or diagnosis.",
                        "It measures segmented-object count, geometry, intensity, foreground coverage, and focus only. Biological or clinical conclusions require validated labels, appropriate assays, and expert review.",
                    ],
                )
            )
            return

        if MICROSCOPY_SUMMARY in intents:
            state.sections.append(
                _section(
                    "MEASURED RESULT",
                    [
                        f"Objects detected: {_display(metrics.get('object_count'))}",
                        f"Mean area: {_display(metrics.get('mean_area_px'))} px^2",
                        f"Mean circularity: {_display(metrics.get('mean_circularity'))}",
                        f"Foreground fraction: {_display(metrics.get('foreground_fraction'))}",
                        f"Focus score: {_display(metrics.get('focus_score'))}",
                    ],
                )
            )
            state.interpretation_lines.append(
                "This is a quantitative summary of segmented regions, not a determination of cell identity or condition. Review the overlay and mask before using the measurements downstream."
            )
            state.evidence_sufficient = True
        else:
            if OBJECT_COUNT in intents:
                state.sections.append(
                    _section(
                        "MEASURED RESULT",
                        [f"{_display(metrics.get('object_count'))} objects were detected in the current microscopy image."],
                    )
                )
                state.evidence_sufficient = True

            if MORPHOLOGY in intents:
                morphology_measurements = [
                    f"Mean area: {_display(metrics.get('mean_area_px'))} px^2",
                    f"Mean perimeter: {_display(metrics.get('mean_perimeter_px'))} px",
                    f"Mean circularity: {_display(metrics.get('mean_circularity'))}",
                    f"Mean eccentricity: {_display(metrics.get('mean_eccentricity'))}",
                ]
                if OBJECT_COUNT not in intents:
                    morphology_measurements.insert(0, f"Objects segmented: {_display(metrics.get('object_count'))}")
                state.sections.append(
                    _section(
                        "MEASURED RESULT",
                        morphology_measurements,
                    )
                )
                circularity = metrics.get("mean_circularity")
                eccentricity = metrics.get("mean_eccentricity")
                observations: list[str] = []
                if isinstance(circularity, (int, float)):
                    shape = "strongly rounded" if circularity >= 0.85 else "moderately rounded" if circularity >= 0.65 else "less circular or more irregular"
                    observations.append(f"The aggregate circularity ({circularity}) indicates {shape} segmented boundaries on average.")
                if isinstance(eccentricity, (int, float)):
                    elongation = "limited elongation" if eccentricity < 0.5 else "moderate elongation" if eccentricity < 0.75 else "pronounced elongation"
                    observations.append(f"The mean eccentricity ({eccentricity}) indicates {elongation} on average.")
                observations.append("These are aggregate region-shape descriptors; they do not identify a biological phenotype.")
                state.sections.append(_section("MORPHOLOGICAL OBSERVATION", observations))
                state.evidence_sufficient = True

            if AREA_ANALYSIS in intents:
                state.sections.append(
                    _section(
                        "MEASURED RESULT",
                        [
                            f"Mean area: {_display(metrics.get('mean_area_px'))} px^2",
                            f"Median area: {_display(metrics.get('median_area_px'))} px^2",
                            f"Area standard deviation: {_display(metrics.get('std_area_px'))} px^2",
                        ],
                    )
                )
                state.interpretation_lines.append(
                    "Area is measured in pixels for each segmented region. It is not a physical cell size until the image has a spatial calibration, and merged or split regions can shift the result."
                )
                state.evidence_sufficient = True

            if CIRCULARITY_ANALYSIS in intents:
                circularity = metrics.get("mean_circularity")
                state.sections.append(_section("MEASURED RESULT", [f"Mean circularity: {_display(circularity)}"]))
                state.interpretation_lines.append(
                    "Circularity approaches 1 for a compact circular boundary and decreases as a region becomes elongated or irregular. It describes segmented shape, not cell health or identity."
                )
                state.evidence_sufficient = True

            if FOREGROUND_COVERAGE in intents:
                foreground = metrics.get("foreground_fraction")
                lines = [f"Foreground fraction: {_display(foreground)}"]
                if isinstance(foreground, (int, float)):
                    lines.append(f"Segmented foreground covers {foreground * 100:.2f}% of the image.")
                if metrics.get("density_per_megapixel") is not None:
                    lines.append(f"Detected-object density: {metrics['density_per_megapixel']} per megapixel.")
                state.sections.append(_section("MEASURED RESULT", lines))
                state.interpretation_lines.append(
                    "Foreground coverage quantifies occupied pixels under this segmentation. Calling the image sparse or dense requires a protocol-specific reference range."
                )
                state.evidence_sufficient = True

            if QUALITY_OR_FOCUS in intents:
                notes = list((data.get("reliability") or {}).get("notes", []))
                state.sections.append(
                    _section(
                        "QUALITY ASSESSMENT",
                        [f"Focus score: {_display(metrics.get('focus_score'))}", *notes],
                    )
                )
                state.interpretation_lines.append(
                    "The focus score is an edge-variance indicator without a universal pass threshold. Reliability should be judged by visually comparing the original, overlay, and mask."
                )
                state.evidence_sufficient = True

            if SEGMENTATION_EXPLANATION in intents:
                state.sections.append(
                    _section(
                        "METHOD",
                        [
                            f"Pipeline: {_display(data.get('method'))}",
                            f"Intensity threshold: {_display(data.get('threshold'))}",
                            "The reported count represents connected regions separated by the segmentation workflow, not independently verified cells.",
                        ],
                    )
                )
                state.evidence_sufficient = True

        if LIMITATIONS in intents:
            notes = list((data.get("reliability") or {}).get("notes", []))
            state.sections.append(
                _section(
                    "LIMITATION",
                    [
                        *notes,
                        "Counts can be affected by low contrast, blur, uneven illumination, scale shift, touching objects, debris, and over- or under-segmentation.",
                        "Pixel measurements alone do not establish cell identity, viability, disease, or mechanism.",
                    ],
                )
            )
            state.evidence_sufficient = True

        if FOLLOW_UP in intents:
            state.sections.append(
                _section(
                    "NEXT INVESTIGATION",
                    [
                        "Inspect false splits and merges in the overlay and mask.",
                        "Compare measurements across independent images acquired with the same settings.",
                        "Add spatial calibration before interpreting pixel area as physical size.",
                    ],
                )
            )
            state.evidence_sufficient = True

        specific = intents & (IMAGE_INTENTS - {GENERAL_IMAGE_QUESTION})
        if GENERAL_IMAGE_QUESTION in intents and not specific and SCIENTIFIC_EVIDENCE not in intents and LIMITATIONS not in intents and FOLLOW_UP not in intents:
            state.sections.append(
                _section(
                    "EVIDENCE LIMITATION",
                    [
                        "That question is not directly answered by the available image measurements.",
                        "Supported measurements include segmented-object count, area, perimeter, circularity, eccentricity, intensity, foreground coverage, and focus. No unsupported biological conclusion was inferred.",
                    ],
                )
            )

        if SCIENTIFIC_EVIDENCE in intents and not state.sections:
            state.sections.append(
                _section(
                    "MEASURED CONTEXT",
                    [
                        f"The active image contains {_display(metrics.get('object_count'))} segmented objects with mean circularity {_display(metrics.get('mean_circularity'))} and foreground fraction {_display(metrics.get('foreground_fraction'))}.",
                    ],
                )
            )

    @staticmethod
    def _experiment(state: WorkflowState) -> None:
        data = state.experiment_analysis or {}
        intents = set(state.intents) & (EXPERIMENT_INTENTS | {LIMITATIONS, FOLLOW_UP, SCIENTIFIC_EVIDENCE})
        comparisons = data.get("group_comparisons", [])
        strongest = _strongest(comparisons)
        state.tools_used.append("experiment_csv_analysis")

        if state.clinical_or_biological_claim:
            state.sections.append(
                _section(
                    "EVIDENCE LIMITATION",
                    ["The table analysis cannot diagnose disease, establish treatment efficacy, or prove a biological mechanism."],
                )
            )
            return

        if EXPERIMENT_SUMMARY in intents:
            group_column = (data.get("schema_summary") or {}).get("group_column")
            state.sections.append(
                _section(
                    "STATISTICAL OBSERVATION",
                    [
                        f"Rows: {_display(data.get('rows'))}; columns: {_display(data.get('columns'))}.",
                        f"Candidate grouping column: {_display(group_column)}.",
                        f"Group comparisons available: {len(comparisons)}.",
                        f"Candidate unusual rows: {len(data.get('anomalies', []))}.",
                    ],
                )
            )
            if strongest:
                state.interpretation_lines.append(
                    f"The largest standardized group difference is for {strongest.get('feature')} (Cohen's d={strongest.get('cohens_d')}); its p-value is unadjusted and the association is not causal."
                )
            state.evidence_sufficient = True

        if GROUP_COMPARISON in intents:
            if comparisons:
                lines = []
                for item in comparisons[:6]:
                    lines.append(
                        f"{item.get('feature')}: {item.get('control_label')} mean={item.get('control_mean')}; "
                        f"{item.get('treatment_label')} mean={item.get('treatment_mean')}; "
                        f"Cohen's d={item.get('cohens_d')}; unadjusted p={item.get('p_value_unadjusted')}."
                    )
                state.sections.append(_section("STATISTICAL OBSERVATION", lines))
                state.interpretation_lines.append("Group differences are exploratory associations and require replicate-aware, multiple-testing-corrected analysis.")
            else:
                state.sections.append(_section("EVIDENCE LIMITATION", ["No valid two-group comparison is available in the active experiment analysis."]))
            state.evidence_sufficient = bool(comparisons)

        if STRONGEST_CHANGE in intents:
            if strongest:
                state.sections.append(
                    _section(
                        "STATISTICAL OBSERVATION",
                        [
                            f"{strongest.get('feature')} has the largest absolute standardized difference (Cohen's d={strongest.get('cohens_d')}).",
                            f"Means: {strongest.get('control_label')}={strongest.get('control_mean')}; {strongest.get('treatment_label')}={strongest.get('treatment_mean')}. Unadjusted p={strongest.get('p_value_unadjusted')}.",
                        ],
                    )
                )
                state.interpretation_lines.append("Largest effect size means largest standardized difference among the tested features, not necessarily the most biologically important result.")
                state.evidence_sufficient = True
            else:
                state.sections.append(_section("EVIDENCE LIMITATION", ["No effect-size comparison is available to rank variables."]))

        if EFFECT_SIZE in intents:
            if comparisons:
                state.sections.append(
                    _section(
                        "STATISTICAL OBSERVATION",
                        [f"{item.get('feature')}: Cohen's d={item.get('cohens_d')}" for item in comparisons[:10]],
                    )
                )
                state.interpretation_lines.append("Cohen's d expresses the mean difference in pooled-standard-deviation units; sign indicates direction, while magnitude is context-dependent.")
                state.evidence_sufficient = True
            else:
                state.sections.append(_section("EVIDENCE LIMITATION", ["No two-group effect sizes were calculated for this table."]))

        if OUTLIERS in intents:
            anomalies = data.get("anomalies", [])
            lines = [f"Isolation Forest flagged {len(anomalies)} candidate unusual rows."]
            lines.extend(f"{item.get('sample')}: anomaly score={item.get('anomaly_score')}" for item in anomalies[:8])
            lines.append("These are review candidates, not confirmed errors or biological abnormalities.")
            state.sections.append(_section("STATISTICAL OBSERVATION", lines))
            state.evidence_sufficient = True

        if CORRELATIONS in intents:
            correlations = data.get("correlations", [])
            if correlations:
                lines = [f"{item.get('left')} vs {item.get('right')}: Spearman rho={item.get('spearman_rho')}" for item in correlations[:8]]
                lines.append("Correlation does not establish causality.")
                state.sections.append(_section("STATISTICAL OBSERVATION", lines))
                state.evidence_sufficient = True
            else:
                state.sections.append(_section("EVIDENCE LIMITATION", ["No correlations at the analysis reporting threshold were available."]))

        if MISSING_DATA in intents:
            missing = (data.get("schema_summary") or {}).get("missing_values", {})
            if missing:
                state.sections.append(_section("DATA QUALITY", [f"{column}: {count} missing values" for column, count in missing.items()]))
            else:
                state.sections.append(_section("DATA QUALITY", ["No missing values were reported in the active table."]))
            state.evidence_sufficient = True

        if LIMITATIONS in intents:
            notes = list((data.get("reliability") or {}).get("notes", []))
            state.sections.append(
                _section(
                    "LIMITATION",
                    [*notes, "Reported p-values are unadjusted for multiple testing, and associations do not establish causality."],
                )
            )
            state.evidence_sufficient = True

        if FOLLOW_UP in intents:
            state.sections.append(
                _section(
                    "NEXT INVESTIGATION",
                    [
                        "Verify the inferred grouping column and inspect candidate unusual rows against source records.",
                        "Use biological replicates and a pre-specified, multiple-testing-aware analysis.",
                        "Check distributions and measurement quality before interpreting group differences.",
                    ],
                )
            )
            state.evidence_sufficient = True

        specific = intents & (EXPERIMENT_INTENTS - {GENERAL_EXPERIMENT_QUESTION})
        if GENERAL_EXPERIMENT_QUESTION in intents and not specific and SCIENTIFIC_EVIDENCE not in intents and LIMITATIONS not in intents and FOLLOW_UP not in intents:
            state.sections.append(
                _section(
                    "EVIDENCE LIMITATION",
                    [
                        "That question is not directly answered by the available table analysis.",
                        "Supported outputs include schema, missingness, group comparisons, effect sizes, correlations, and anomaly candidates.",
                    ],
                )
            )

    @staticmethod
    def _retrieval(state: WorkflowState) -> None:
        query = state.resolved_question or state.question
        if state.image_analysis:
            query += " microscopy segmentation Otsu region properties"
        if state.experiment_analysis:
            query += " experiment statistics Isolation Forest"
        candidates = retrieve(query, limit=5)
        if state.image_analysis and not state.experiment_analysis:
            candidates = [source for source in candidates if source["id"] != "isolation-forest"]
        state.sources = candidates[:3]
        state.tools_used.append("retrieve_scientific_context")
        if state.sources:
            state.sections.append(
                _section(
                    "RETRIEVED EVIDENCE",
                    [f"[{source['id']}] {source['text']}" for source in state.sources],
                )
            )
            state.evidence_sufficient = True
        else:
            state.sections.append(
                _section("RETRIEVED EVIDENCE", ["No sufficiently relevant source was found in the curated offline knowledge base."])
            )

    @staticmethod
    def _interpret(state: WorkflowState) -> None:
        lines = list(dict.fromkeys(state.interpretation_lines))
        if state.sources:
            lines.append(
                "The retrieved sources explain relevant methods or benchmarks; they do not independently validate a biological conclusion for this uploaded sample."
            )
        if lines:
            state.sections.append(_section("AI INTERPRETATION", lines))

    @staticmethod
    def _compose(state: WorkflowState) -> None:
        if not state.sections:
            state.sections.append(
                _section(
                    "EVIDENCE LIMITATION",
                    [
                        "The available context does not support a grounded answer to that question.",
                        "Upload an image or experiment analysis, provide the missing context, or ask for a relevant source.",
                    ],
                )
            )
