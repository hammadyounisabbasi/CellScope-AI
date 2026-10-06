from __future__ import annotations

import pytest

from backend.app.agents.research_agent import answer_question


IMAGE = {
    "method": "Max-RGB Otsu + morphology + marker-controlled watershed (v2)",
    "threshold": 0.42,
    "metrics": {
        "object_count": 39,
        "mean_area_px": 2720.667,
        "median_area_px": 2500.0,
        "std_area_px": 410.2,
        "mean_perimeter_px": 201.4,
        "mean_circularity": 0.7703,
        "mean_eccentricity": 0.48,
        "mean_intensity": 0.64,
        "foreground_fraction": 0.117569,
        "density_per_megapixel": 43.2,
        "focus_score": 0.0061,
    },
    "reliability": {
        "level": "moderate",
        "notes": [
            "Counts are segmented objects, not independently verified biological cell identities."
        ],
    },
}

EXPERIMENT = {
    "rows": 60,
    "columns": 5,
    "schema_summary": {
        "group_column": "group",
        "missing_values": {"intensity": 2},
    },
    "group_comparisons": [
        {
            "feature": "cell_area",
            "control_label": "control",
            "treatment_label": "treated",
            "control_mean": 76.3,
            "treatment_mean": 90.9,
            "cohens_d": 1.287,
            "p_value_unadjusted": 0.000023,
        },
        {
            "feature": "circularity",
            "control_label": "control",
            "treatment_label": "treated",
            "control_mean": 0.81,
            "treatment_mean": 0.72,
            "cohens_d": -0.842,
            "p_value_unadjusted": 0.003,
        },
    ],
    "correlations": [{"left": "cell_area", "right": "intensity", "spearman_rho": 0.66}],
    "anomalies": [
        {"sample": "T17", "anomaly_score": -0.12},
        {"sample": "C04", "anomaly_score": -0.08},
    ],
    "observations": ["Detected 3 numeric and 2 categorical columns."],
    "reliability": {
        "level": "moderate",
        "notes": ["Group inference is heuristic and must be checked by a researcher."],
    },
}


def _nodes(result: dict) -> list[str]:
    return [step["node"] for step in result["workflow_trace"]]


def _intents(result: dict) -> list[str]:
    return result["workflow_trace"][0]["intents"]


def test_direct_count_is_short_and_skips_interpretation():
    result = answer_question("How many cells or objects were detected in this image?", IMAGE)
    assert "39 objects were detected" in result["answer"]
    assert "Mean area" not in result["answer"]
    assert "Mean circularity" not in result["answer"]
    assert "METHOD" not in result["answer"]
    assert _nodes(result) == ["intent_context_analyzer", "microscopy_analysis_tool", "response_composer"]


def test_morphology_uses_shape_metrics_and_differs_from_count():
    morphology = answer_question("What are the main morphological observations?", IMAGE)
    count = answer_question("Give me the number of detected regions.", IMAGE)
    assert {"MORPHOLOGY"}.issubset(_intents(morphology))
    assert "Mean perimeter: 201.4 px" in morphology["answer"]
    assert "Mean eccentricity: 0.48" in morphology["answer"]
    assert "MORPHOLOGICAL OBSERVATION" in morphology["answer"]
    assert morphology["answer"] != count["answer"]


def test_summary_is_broad_but_grounded():
    result = answer_question("Summarize the microscopy analysis results.", IMAGE)
    assert "Objects detected: 39" in result["answer"]
    assert "Mean area: 2720.667 px^2" in result["answer"]
    assert "Mean circularity: 0.7703" in result["answer"]
    assert "Foreground fraction: 0.117569" in result["answer"]
    assert "AI INTERPRETATION" in result["answer"]


def test_direct_mean_area_puts_value_first_without_extra_interpretation():
    result = answer_question("What is the mean area?", IMAGE)
    assert result["answer"].startswith("MEASURED RESULT\nMean area: 2720.667 px^2")
    assert "AI INTERPRETATION" not in result["answer"]


def test_limitations_focuses_on_failure_modes():
    result = answer_question("Where can this image analysis fail?", IMAGE)
    assert "LIMITATION" in result["answer"]
    assert "over- or under-segmentation" in result["answer"]
    assert "Mean area" not in result["answer"]
    assert "evidence_interpretation" not in _nodes(result)


def test_research_evidence_routes_retrieval():
    result = answer_question("Which published evidence is relevant to the active observation?", IMAGE)
    assert "scientific_retrieval_tool" in _nodes(result)
    assert "retrieve_scientific_context" in result["tools_used"]
    assert "RETRIEVED EVIDENCE" in result["answer"]
    assert result["sources"]


def test_typo_tolerance_for_morphology():
    result = answer_question("Give a morphological obcervateion of their form", IMAGE)
    assert "MORPHOLOGY" in _intents(result)
    assert "Mean circularity" in result["answer"]


def test_multi_part_image_question_composes_multiple_intents():
    result = answer_question(
        "Count the regions, say whether they are round, and suggest the next validation step.", IMAGE
    )
    assert {"OBJECT_COUNT", "MORPHOLOGY", "FOLLOW_UP"}.issubset(_intents(result))
    assert "39 objects were detected" in result["answer"]
    assert "MORPHOLOGICAL OBSERVATION" in result["answer"]
    assert "NEXT INVESTIGATION" in result["answer"]


def test_short_follow_up_uses_history_without_repeating_prior_metric():
    history = [
        {"role": "user", "content": "How many objects are there?"},
        {"role": "assistant", "content": "39 objects were detected."},
    ]
    result = answer_question("What about their shape?", IMAGE, conversation_history=history)
    assert "MORPHOLOGY" in _intents(result)
    assert "OBJECT_COUNT" not in _intents(result)
    assert "Mean circularity" in result["answer"]


def test_unsupported_clinical_question_refuses_inference():
    result = answer_question("Do these regions show a healthy disease-free sample?", IMAGE)
    assert result["evidence_sufficient"] is False
    assert "cannot establish health, viability, disease, or diagnosis" in result["answer"]
    assert "39" not in result["answer"]


@pytest.mark.parametrize(
    ("question", "expected_intent", "required_text"),
    [
        ("Roughly what portion of the field is occupied?", "FOREGROUND_COVERAGE", "11.76%"),
        ("Would you call this field dense?", "FOREGROUND_COVERAGE", "reference range"),
        ("Tell me the typical segmented size.", "AREA_ANALYSIS", "Median area"),
        ("How should I read the roundness score?", "CIRCULARITY_ANALYSIS", "approaches 1"),
        ("Was this frame blurry or acceptably focused?", "QUALITY_OR_FOCUS", "Focus score"),
        ("How did the software identify separate regions?", "SEGMENTATION_EXPLANATION", "Pipeline:"),
        ("What validation would you perform after this?", "FOLLOW_UP", "NEXT INVESTIGATION"),
        ("Give me a compact overview of the table.", "EXPERIMENT_SUMMARY", "Rows: 60"),
        ("How did the treated cohort differ from baseline?", "GROUP_COMPARISON", "cell_area"),
        ("Which readout moved furthest between groups?", "STRONGEST_CHANGE", "largest absolute"),
        ("List the standardized magnitudes.", "EFFECT_SIZE", "Cohen's d"),
        ("Did the detector flag any odd records?", "OUTLIERS", "T17"),
        ("Which measurements tend to move together?", "CORRELATIONS", "Spearman rho"),
        ("Are any entries absent from the data?", "MISSING_DATA", "intensity: 2"),
    ],
)
def test_unseen_paraphrase_suite(question: str, expected_intent: str, required_text: str):
    image_intents = {
        "FOREGROUND_COVERAGE",
        "AREA_ANALYSIS",
        "CIRCULARITY_ANALYSIS",
        "QUALITY_OR_FOCUS",
        "SEGMENTATION_EXPLANATION",
        "FOLLOW_UP",
    }
    result = answer_question(
        question,
        IMAGE if expected_intent in image_intents else None,
        EXPERIMENT if expected_intent not in image_intents else None,
    )
    assert expected_intent in _intents(result)
    assert required_text in result["answer"]


def test_experiment_questions_produce_distinct_scoped_answers():
    prompts = [
        "Contrast the experimental groups.",
        "Which endpoint has the strongest shift?",
        "Show only the effect sizes.",
        "Which records deserve outlier review?",
        "Summarize this dataset briefly.",
    ]
    results = [answer_question(prompt, experiment_analysis=EXPERIMENT) for prompt in prompts]
    answers = [result["answer"] for result in results]
    assert len(set(answers)) == len(answers)
    assert "T17" not in answers[0]
    assert "T17" in answers[3]


def test_ambiguous_unknown_question_uses_safe_fallback():
    result = answer_question("Is there a hidden story here?", IMAGE)
    assert "EVIDENCE LIMITATION" in result["answer"]
    assert "No unsupported biological conclusion was inferred" in result["answer"]
