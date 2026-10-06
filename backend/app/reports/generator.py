from __future__ import annotations

import base64
import binascii
import html
import json
import uuid
from datetime import datetime, timezone
from typing import Any


def _validated_png_base64(value: Any) -> str | None:
    """Return a safe PNG payload for an HTML data URI, or omit invalid client data."""
    if not isinstance(value, str) or not value:
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return value if decoded.startswith(b"\x89PNG\r\n\x1a\n") else None


def _section(title: str, value: Any) -> str:
    if value is None:
        body = "<p>Not provided.</p>"
    elif isinstance(value, str):
        body = f"<p>{html.escape(value)}</p>"
    else:
        body = f"<pre>{html.escape(json.dumps(value, indent=2, ensure_ascii=False))}</pre>"
    return f"<section><h2>{html.escape(title)}</h2>{body}</section>"


def _visual_results(
    image_analysis: dict[str, Any] | None,
    experiment_analysis: dict[str, Any] | None,
) -> str:
    figures: list[str] = []
    if image_analysis:
        for key, caption in (
            ("overlay_png_base64", "Segmentation overlay"),
            ("mask_png_base64", "Predicted foreground mask"),
        ):
            encoded = _validated_png_base64(image_analysis.get(key))
            if encoded:
                figures.append(
                    f'<figure><img src="data:image/png;base64,{encoded}" alt="{caption}">'
                    f"<figcaption>{caption}</figcaption></figure>"
                )
    if experiment_analysis:
        for chart in experiment_analysis.get("charts", [])[:6]:
            encoded = _validated_png_base64(chart.get("png_base64"))
            if encoded:
                caption = html.escape(str(chart.get("title", "Experiment chart")))
                figures.append(
                    f'<figure><img src="data:image/png;base64,{encoded}" alt="{caption}">'
                    f"<figcaption>{caption}</figcaption></figure>"
                )
    body = "".join(figures) if figures else "<p>Not provided.</p>"
    return f'<section><h2>Visual results</h2><div class="figures">{body}</div></section>'


def generate_report(
    title: str,
    image_analysis: dict[str, Any] | None,
    experiment_analysis: dict[str, Any] | None,
    assistant_answer: dict[str, Any] | None,
) -> dict[str, str]:
    report_id = str(uuid.uuid4())
    references = assistant_answer.get("sources", []) if assistant_answer else []
    body = "".join(
        [
            _section("Input information", {
                "image": image_analysis.get("filename") if image_analysis else None,
                "experiment": experiment_analysis.get("filename") if experiment_analysis else None,
            }),
            _section("Analysis methodology", {
                "microscopy": image_analysis.get("method") if image_analysis else "Not performed",
                "experiment": "Descriptive statistics, Mann-Whitney U, Cohen's d, Spearman correlation, and Isolation Forest" if experiment_analysis else "Not performed",
            }),
            _section("Quantitative microscopy measurements", image_analysis.get("metrics") if image_analysis else None),
            _visual_results(image_analysis, experiment_analysis),
            _section("Statistical findings", experiment_analysis.get("group_comparisons") if experiment_analysis else None),
            _section("Detected observations", experiment_analysis.get("observations") if experiment_analysis else None),
            _section("AI interpretation", assistant_answer.get("answer") if assistant_answer else None),
            _section("Reliability notes", {
                "image": image_analysis.get("reliability") if image_analysis else None,
                "experiment": experiment_analysis.get("reliability") if experiment_analysis else None,
            }),
            _section("Suggested next investigations", [
                "Visually inspect segmentation masks against the original image.",
                "Validate findings on independent biological replicates.",
                "Correct inferential tests for multiple comparisons where applicable.",
            ]),
            _section("References", references),
        ]
    )
    document = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:15px system-ui;max-width:960px;margin:40px auto;padding:0 24px;color:#152238}}
h1{{color:#0f766e}}section{{border-top:1px solid #dce5ea;padding:12px 0}}pre{{white-space:pre-wrap;background:#f3f7f8;padding:14px;border-radius:8px}}
.warning{{background:#fff7ed;border-left:4px solid #f59e0b;padding:12px}}.figures{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
figure{{margin:0}}img{{display:block;max-width:100%;height:auto;border:1px solid #dce5ea}}figcaption{{color:#52616b;margin-top:5px}}</style></head><body>
<h1>{html.escape(title)}</h1><p>Generated {datetime.now(timezone.utc).isoformat()}</p>
<p class="warning">Research assistance only. Not a medical diagnostic report. AI interpretations are hypotheses requiring expert validation.</p>
{body}</body></html>"""
    return {
        "report_id": report_id,
        "filename": f"cellscope-report-{report_id[:8]}.html",
        "content_type": "text/html",
        "html": document,
    }
