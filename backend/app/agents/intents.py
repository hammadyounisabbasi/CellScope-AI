from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MICROSCOPY_SUMMARY = "MICROSCOPY_SUMMARY"
OBJECT_COUNT = "OBJECT_COUNT"
MORPHOLOGY = "MORPHOLOGY"
AREA_ANALYSIS = "AREA_ANALYSIS"
CIRCULARITY_ANALYSIS = "CIRCULARITY_ANALYSIS"
FOREGROUND_COVERAGE = "FOREGROUND_COVERAGE"
QUALITY_OR_FOCUS = "QUALITY_OR_FOCUS"
SEGMENTATION_EXPLANATION = "SEGMENTATION_EXPLANATION"
LIMITATIONS = "LIMITATIONS"
FOLLOW_UP = "FOLLOW_UP"
GENERAL_IMAGE_QUESTION = "GENERAL_IMAGE_QUESTION"

EXPERIMENT_SUMMARY = "EXPERIMENT_SUMMARY"
GROUP_COMPARISON = "GROUP_COMPARISON"
STRONGEST_CHANGE = "STRONGEST_CHANGE"
EFFECT_SIZE = "EFFECT_SIZE"
OUTLIERS = "OUTLIERS"
CORRELATIONS = "CORRELATIONS"
MISSING_DATA = "MISSING_DATA"
GENERAL_EXPERIMENT_QUESTION = "GENERAL_EXPERIMENT_QUESTION"
SCIENTIFIC_EVIDENCE = "SCIENTIFIC_EVIDENCE"


IMAGE_INTENTS = {
    MICROSCOPY_SUMMARY,
    OBJECT_COUNT,
    MORPHOLOGY,
    AREA_ANALYSIS,
    CIRCULARITY_ANALYSIS,
    FOREGROUND_COVERAGE,
    QUALITY_OR_FOCUS,
    SEGMENTATION_EXPLANATION,
    GENERAL_IMAGE_QUESTION,
}
EXPERIMENT_INTENTS = {
    EXPERIMENT_SUMMARY,
    GROUP_COMPARISON,
    STRONGEST_CHANGE,
    EFFECT_SIZE,
    OUTLIERS,
    CORRELATIONS,
    MISSING_DATA,
    GENERAL_EXPERIMENT_QUESTION,
}


@dataclass(frozen=True)
class IntentSpec:
    name: str
    domain: str
    patterns: tuple[str, ...]
    prototypes: tuple[str, ...]


SPECS = (
    IntentSpec(MICROSCOPY_SUMMARY, "image", (r"\bsummar", r"\boverview\b", r"short conclusion", r"key image results?"), ("give a concise microscopy overview", "tell me the main image results", "explain this image simply")),
    IntentSpec(OBJECT_COUNT, "image", (r"\bhow many\b", r"\bnumber of\b.*\b(cell|object|region)", r"\b(cell|object|region) count\b", r"\bcount\b.*\b(cell|object|region)"), ("how many segmented objects are present", "tell me the cell count", "quantity of detected regions")),
    IntentSpec(MORPHOLOGY, "image", (r"morpholog", r"\bshape\b", r"\bround(?:ed)?\b", r"\birregular\b", r"\belongat"), ("describe the object morphology", "what shape are they", "are the regions rounded or irregular")),
    IntentSpec(AREA_ANALYSIS, "image", (r"\b(mean|average|median|typical)?\s*(cell|object)?\s*area\b", r"\bsize distribution\b", r"\b(typical|average|mean|median)?\s*(segmented|cell|object|region)?\s*size\b", r"\bhow (large|small)\b"), ("explain the mean area", "what is the typical object size", "describe the area distribution")),
    IntentSpec(CIRCULARITY_ANALYSIS, "image", (r"circular", r"\broundness\b"), ("what does the circularity value mean", "interpret the roundness measurement", "are these mostly circular")),
    IntentSpec(FOREGROUND_COVERAGE, "image", (r"foreground", r"\bcoverage\b", r"\bconfluen", r"\bdens(?:e|ity)\b", r"occupied.*image"), ("how much of the image is occupied", "does this field look dense", "explain foreground coverage")),
    IntentSpec(QUALITY_OR_FOCUS, "image", (r"\bfocus\b", r"\bblur", r"image quality", r"segmentation reliable", r"\breliab"), ("is the image in focus", "can I trust this segmentation", "assess image quality")),
    IntentSpec(SEGMENTATION_EXPLANATION, "image", (r"\bsegmentation\b", r"\bsegmenting\b", r"how.*segmented", r"\bthreshold", r"\botsu\b", r"\bwatershed\b", r"how (?:did|does|were).*detect", r"how.*algorithm.*detect"), ("how were objects segmented", "explain the image analysis method", "how did the algorithm find regions")),
    IntentSpec(EXPERIMENT_SUMMARY, "experiment", (r"summar.*(?:experiment|dataset|table)", r"(?:experiment|dataset|table).*overview", r"overview.*(?:experiment|dataset|table)", r"short conclusion", r"key experiment results?"), ("summarize the experiment table", "give the main statistical results", "explain the experiment simply")),
    IntentSpec(GROUP_COMPARISON, "experiment", (r"\bcompar", r"\bcontrast", r"control.*treat", r"treat.*control", r"between.*groups?", r"treatment group", r"differ.*baseline"), ("compare control and treatment", "how do the groups differ", "tell me about the treatment group")),
    IntentSpec(STRONGEST_CHANGE, "experiment", (r"changed? (the )?most", r"biggest difference", r"largest (change|difference)", r"strongest (shift|change|difference)", r"moved? (the )?(furthest|most)", r"which (variable|measurement|result|readout).*matters?", r"pay attention"), ("which variable changed the most", "what is the largest group difference", "which result should I focus on")),
    IntentSpec(EFFECT_SIZE, "experiment", (r"effect sizes?", r"cohen'?s?\s*d", r"standardi[sz]ed (difference|magnitude)s?"), ("what are the effect sizes", "explain Cohen d", "how large is the treatment effect")),
    IntentSpec(OUTLIERS, "experiment", (r"\boutliers?\b", r"\banomal", r"\bunusual\b", r"\bsuspicious\b", r"odd (samples?|records?|rows?)"), ("which samples look unusual", "are there anomalous rows", "show candidate outliers")),
    IntentSpec(CORRELATIONS, "experiment", (r"\bcorrelat", r"\brelationship between", r"move together"), ("which variables are correlated", "describe the strongest associations", "what measurements move together")),
    IntentSpec(MISSING_DATA, "experiment", (r"missing (data|values?)", r"\bnulls?\b", r"incomplete (rows?|columns?)"), ("are any values missing", "show incomplete columns", "how much data is absent")),
)


LIMITATION_PATTERNS = (
    r"\blimit(?:ation)?s?\b",
    r"what (?:can|could).*wrong",
    r"why might.*(?:count|result).*wrong",
    r"what.*(?:cannot|can't|can not).*conclud",
    r"\btrust\b",
    r"\bfail(?:ure|s|ed)?\b",
)
FOLLOW_UP_PATTERNS = (
    r"what.*(?:next|check|investigate|follow up)",
    r"next steps?",
    r"(?:suggest|recommend).*next",
    r"validation (?:step|check)",
    r"perform.*validation",
    r"validation.*(?:perform|after|next)",
    r"recommend.*(?:check|analysis)",
)
EVIDENCE_PATTERNS = (
    r"research evidence",
    r"\bevidence\b",
    r"\b(?:literature|papers?|sources?|references?|citations?)\b",
    r"what evidence supports",
)
CLINICAL_PATTERNS = (
    r"\bhealthy\b",
    r"\bviab",
    r"\bdisease\b",
    r"\bdiagnos",
    r"\bmalignan",
    r"which cancer",
)


def normalize_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("_", "-")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%.'?-]+", " ", normalized)).strip()


@lru_cache
def _semantic_index() -> tuple[TfidfVectorizer, Any, list[str]]:
    labels: list[str] = []
    texts: list[str] = []
    for spec in SPECS:
        for prototype in spec.prototypes:
            labels.append(spec.name)
            texts.append(prototype)
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    return vectorizer, vectorizer.fit_transform(texts), labels


def _matches(question: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, question) for pattern in patterns)


def _last_user_question(history: list[dict[str, str]]) -> str:
    for turn in reversed(history):
        if turn.get("role") == "user" and turn.get("content"):
            return str(turn["content"])
    return ""


def _is_contextual_followup(question: str) -> bool:
    words = question.split()
    return (
        len(words) <= 5
        or bool(re.search(r"\b(their|that|those|these|it|one)\b", question))
        or question.startswith(("why", "what about", "which one", "explain that", "does that", "is that"))
    )


def classify_question(
    question: str,
    has_image: bool,
    has_experiment: bool,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Classify one or more intents using rules plus reproducible char-ngram similarity."""
    current = normalize_question(question)
    previous = normalize_question(_last_user_question(history or []))
    current_has_intent_cue = any(_matches(current, spec.patterns) for spec in SPECS)
    contextual = bool(previous and _is_contextual_followup(current) and not current_has_intent_cue)
    analysis_text = f"{previous} {current}" if contextual else current

    image_explicit = bool(re.search(r"\b(image|microscop|cell|object|foreground|morph|shape|circular|focus|segment)\b", analysis_text))
    experiment_explicit = bool(re.search(r"\b(experiment|table|csv|control|treat|group|variable|sample|outlier|anomal|effect|correlat)\b", analysis_text))

    intents: list[str] = []
    for spec in SPECS:
        if spec.domain == "image" and not has_image:
            continue
        if spec.domain == "experiment" and not has_experiment:
            continue
        if _matches(analysis_text, spec.patterns):
            intents.append(spec.name)

    has_shared_cue = any(
        _matches(current, patterns)
        for patterns in (LIMITATION_PATTERNS, FOLLOW_UP_PATTERNS, EVIDENCE_PATTERNS, CLINICAL_PATTERNS)
    )

    # Similarity supplies a reusable fallback for unseen paraphrases. Explicit
    # rules remain authoritative, especially for multi-part questions.
    if not intents and not has_shared_cue:
        vectorizer, matrix, labels = _semantic_index()
        scores = cosine_similarity(vectorizer.transform([analysis_text]), matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
        for index, score in ranked:
            candidate = labels[index]
            if score < 0.34:
                break
            if candidate in IMAGE_INTENTS and has_image and not experiment_explicit:
                intents.append(candidate)
                break
            if candidate in EXPERIMENT_INTENTS and has_experiment and not image_explicit:
                intents.append(candidate)
                break

    evidence = _matches(current, EVIDENCE_PATTERNS)
    limitations = _matches(analysis_text, LIMITATION_PATTERNS)
    follow_up = _matches(analysis_text, FOLLOW_UP_PATTERNS)
    clinical = _matches(current, CLINICAL_PATTERNS)

    if limitations:
        intents.append(LIMITATIONS)
    if follow_up:
        intents.append(FOLLOW_UP)
    if evidence:
        intents.append(SCIENTIFIC_EVIDENCE)

    if clinical:
        intents = [intent for intent in intents if intent in {LIMITATIONS, SCIENTIFIC_EVIDENCE}]
        if has_image:
            intents.append(GENERAL_IMAGE_QUESTION)
        elif has_experiment:
            intents.append(GENERAL_EXPERIMENT_QUESTION)

    # Resolve shared or underspecified language against explicit and recent context.
    shared_only = not any(intent in IMAGE_INTENTS | EXPERIMENT_INTENTS for intent in intents)
    if shared_only and (limitations or follow_up or evidence):
        prior_image = any(token in previous for token in ("image", "cell", "object", "shape", "area", "circular", "segment"))
        prior_experiment = any(token in previous for token in ("experiment", "control", "treat", "group", "variable", "outlier", "effect"))
        ambiguous_both = has_image and has_experiment and not any(
            (image_explicit, experiment_explicit, prior_image, prior_experiment)
        )
        if has_image and (image_explicit or prior_image or not has_experiment or ambiguous_both):
            intents.append(GENERAL_IMAGE_QUESTION)
        if has_experiment and (experiment_explicit or prior_experiment or not has_image or ambiguous_both):
            intents.append(GENERAL_EXPERIMENT_QUESTION)

    if not intents:
        if has_image and (image_explicit or not has_experiment):
            intents.append(GENERAL_IMAGE_QUESTION)
        elif has_experiment:
            intents.append(GENERAL_EXPERIMENT_QUESTION)

    # A broad results request with both active contexts intentionally covers both.
    if has_image and has_experiment and re.search(r"\b(results?|findings?|measurable differences?)\b", current):
        if not image_explicit and not experiment_explicit:
            intents.extend((MICROSCOPY_SUMMARY, EXPERIMENT_SUMMARY))

    deduplicated = list(dict.fromkeys(intents))
    wants_explanation = bool(
        re.search(
            r"\b(explain|means|indicate|interpret|simple terms?|conclusion|dense|read|reliable)\b|what does|how should",
            current,
        )
    )
    return {
        "intents": deduplicated,
        "contextual_followup": contextual,
        "resolved_question": analysis_text,
        "wants_explanation": wants_explanation,
        "clinical_or_biological_claim": clinical,
    }
