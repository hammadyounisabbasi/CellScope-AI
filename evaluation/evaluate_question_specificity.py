"""Exercise question-sensitive assistant routing against active sample analyses."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agents import answer_question
from backend.app.analytics import analyze_experiment
from backend.app.vision import analyze_image


IMAGE_QUESTIONS = [
    "Summarize the microscopy analysis results.",
    "How many cells or objects were detected in this image?",
    "What are the main morphological observations in this sample?",
    "Explain the mean cell area.",
    "What does the circularity measurement indicate?",
    "What are the limitations of this analysis?",
    "What should I investigate next?",
    "What research evidence is relevant to these observations?",
]

EXPERIMENT_QUESTIONS = [
    "Compare control and treatment.",
    "Which variable changed most?",
    "Are there outliers?",
    "What is the effect size?",
    "Summarize the experiment.",
]


def _evaluate(question: str, image: dict | None = None, experiment: dict | None = None) -> dict:
    result = answer_question(question, image, experiment)
    return {
        "question": question,
        "intents": result["workflow_trace"][0].get("intents", []),
        "workflow": [step["node"] for step in result["workflow_trace"]],
        "tools_used": result["tools_used"],
        "answer": result["answer"],
    }


def run() -> dict:
    image = analyze_image(
        (ROOT / "data" / "sample" / "synthetic_cells.png").read_bytes(),
        "synthetic_cells.png",
    )
    experiment = analyze_experiment(
        (ROOT / "data" / "sample" / "experiment.csv").read_bytes(),
        "experiment.csv",
    )
    image_results = [_evaluate(question, image=image) for question in IMAGE_QUESTIONS]
    experiment_results = [
        _evaluate(question, experiment=experiment) for question in EXPERIMENT_QUESTIONS
    ]
    direct_count = image_results[1]
    evidence = image_results[-1]
    checks = {
        "all_image_answers_distinct": len({item["answer"] for item in image_results}) == len(image_results),
        "all_experiment_answers_distinct": len({item["answer"] for item in experiment_results}) == len(experiment_results),
        "direct_count_skips_interpretation": "evidence_interpretation" not in direct_count["workflow"],
        "evidence_question_uses_retrieval": "scientific_retrieval_tool" in evidence["workflow"],
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Question-specific routing against active deterministic sample analyses",
        "checks": checks,
        "passed": all(checks.values()),
        "image_questions": image_results,
        "experiment_questions": experiment_results,
    }


if __name__ == "__main__":
    results = run()
    target = ROOT / "evaluation" / "question_specificity_results.json"
    target.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
