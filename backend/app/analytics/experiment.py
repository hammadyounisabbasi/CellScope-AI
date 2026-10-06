from __future__ import annotations

import base64
import io
import uuid
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest

from backend.app.core.errors import AnalysisError, UploadValidationError


CONTROL_TERMS = {"control", "ctrl", "vehicle", "untreated", "mock", "baseline"}


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else round(float(value), 6)
    if pd.isna(value):
        return None
    return value


def _chart_b64(fig: plt.Figure) -> str:
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=120, bbox_inches="tight", facecolor="#0b1220")
    plt.close(fig)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _detect_group_column(frame: pd.DataFrame) -> str | None:
    categorical = [c for c in frame.columns if not pd.api.types.is_numeric_dtype(frame[c])]
    preferred = [c for c in categorical if any(t in c.lower() for t in ("group", "treatment", "condition"))]
    candidates = preferred + [c for c in categorical if c not in preferred]
    return next((c for c in candidates if 2 <= frame[c].nunique(dropna=True) <= 12), None)


def _compare_groups(frame: pd.DataFrame, group_column: str, numeric: list[str]) -> list[dict[str, Any]]:
    groups = [g for g in frame[group_column].dropna().unique()]
    if len(groups) != 2:
        return []
    control = next((g for g in groups if str(g).strip().lower() in CONTROL_TERMS), groups[0])
    treatment = next(g for g in groups if g != control)
    results: list[dict[str, Any]] = []
    for column in numeric[:20]:
        a = frame.loc[frame[group_column] == control, column].dropna().astype(float)
        b = frame.loc[frame[group_column] == treatment, column].dropna().astype(float)
        if len(a) < 2 or len(b) < 2:
            continue
        test = stats.mannwhitneyu(a, b, alternative="two-sided")
        pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / max(len(a) + len(b) - 2, 1))
        effect = (b.mean() - a.mean()) / pooled if pooled > 0 else 0.0
        results.append(
            {
                "feature": column,
                "control_label": str(control),
                "treatment_label": str(treatment),
                "control_n": len(a),
                "treatment_n": len(b),
                "control_mean": a.mean(),
                "treatment_mean": b.mean(),
                "median_difference": b.median() - a.median(),
                "cohens_d": effect,
                "mann_whitney_u": test.statistic,
                "p_value_unadjusted": test.pvalue,
                "note": "Exploratory association; p-value is unadjusted for multiple testing.",
            }
        )
    return _clean_json(results)


def analyze_experiment(content: bytes, filename: str) -> dict[str, Any]:
    if not content:
        raise UploadValidationError("The uploaded CSV is empty.")
    try:
        frame = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise UploadValidationError("The file could not be parsed as a safe CSV.") from exc
    if frame.empty or frame.shape[1] < 1:
        raise AnalysisError("The CSV contains no analyzable rows or columns.")
    if frame.shape[0] > 100_000 or frame.shape[1] > 200:
        raise UploadValidationError("CSV exceeds the 100,000-row or 200-column analysis limit.")

    numeric = frame.select_dtypes(include=np.number).columns.tolist()
    categorical = [c for c in frame.columns if c not in numeric]
    group_column = _detect_group_column(frame)
    missing = {c: int(frame[c].isna().sum()) for c in frame.columns if frame[c].isna().any()}
    identifier_candidates = [
        c for c in frame.columns if c.lower() in {"id", "sample_id", "sample", "well", "filename"}
    ]
    descriptive = (
        frame[numeric].describe(percentiles=[0.25, 0.5, 0.75]).to_dict() if numeric else {}
    )
    comparisons = _compare_groups(frame, group_column, numeric) if group_column else []

    correlations: list[dict[str, Any]] = []
    if len(numeric) >= 2:
        corr = frame[numeric[:25]].corr(method="spearman")
        for i, left in enumerate(corr.columns):
            for right in corr.columns[i + 1 :]:
                value = corr.loc[left, right]
                if pd.notna(value) and abs(value) >= 0.5:
                    correlations.append({"left": left, "right": right, "spearman_rho": value})
        correlations.sort(key=lambda item: abs(item["spearman_rho"]), reverse=True)

    anomalies: list[dict[str, Any]] = []
    usable = frame[numeric].replace([np.inf, -np.inf], np.nan).dropna() if numeric else pd.DataFrame()
    if len(usable) >= 10 and usable.shape[1] >= 1:
        model = IsolationForest(contamination="auto", random_state=42, n_estimators=100)
        scores = model.fit_predict(usable)
        decision = model.decision_function(usable)
        for idx, score in zip(usable.index[scores == -1], decision[scores == -1], strict=True):
            label = str(frame.loc[idx, identifier_candidates[0]]) if identifier_candidates else str(idx)
            anomalies.append({"row_index": int(idx), "sample": label, "anomaly_score": float(score)})
        anomalies.sort(key=lambda item: item["anomaly_score"])
        anomalies = anomalies[:50]

    charts: list[dict[str, str]] = []
    if numeric:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.set_facecolor("#0b1220")
        fig.patch.set_facecolor("#0b1220")
        ax.hist(frame[numeric[0]].dropna(), bins=min(30, max(5, int(np.sqrt(len(frame))))), color="#2dd4bf")
        ax.set_title(f"Distribution: {numeric[0]}", color="white")
        ax.tick_params(colors="white")
        charts.append({"title": f"Distribution of {numeric[0]}", "png_base64": _chart_b64(fig)})
    if group_column and numeric:
        fig, ax = plt.subplots(figsize=(7, 4))
        frame.boxplot(column=numeric[0], by=group_column, ax=ax, grid=False)
        fig.suptitle("")
        ax.set_title(f"{numeric[0]} by {group_column}")
        charts.append({"title": "Group comparison", "png_base64": _chart_b64(fig)})

    observations = [
        f"Detected {len(numeric)} numeric and {len(categorical)} categorical columns.",
        f"Missing values occur in {len(missing)} columns.",
    ]
    if group_column:
        observations.append(f"'{group_column}' was inferred as the candidate grouping column.")
    else:
        observations.append("No unambiguous treatment/control grouping column was inferred.")
    if anomalies:
        observations.append(f"Isolation Forest flagged {len(anomalies)} candidate unusual rows.")

    return _clean_json(
        {
            "analysis_id": str(uuid.uuid4()),
            "filename": filename,
            "rows": len(frame),
            "columns": len(frame.columns),
            "schema_summary": {
                "numeric_columns": numeric,
                "categorical_columns": categorical,
                "group_column": group_column,
                "identifier_candidates": identifier_candidates,
                "missing_values": missing,
            },
            "descriptive_statistics": descriptive,
            "group_comparisons": comparisons,
            "correlations": correlations[:50],
            "anomalies": anomalies,
            "charts": charts,
            "observations": observations,
            "reliability": {
                "level": "moderate",
                "notes": [
                    "Group inference is heuristic and must be checked by a researcher.",
                    "Outliers are candidates for review, not proof of experimental error.",
                    "Statistical associations do not establish causality.",
                ],
            },
            "disclaimer": "Research use only. Statistical output requires domain review.",
        }
    )

