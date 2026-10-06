"""Execute the documented offline retrieval and unsupported-answer checks."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agents import answer_question
from backend.app.rag import retrieve


def run() -> dict:
    cases = json.loads((ROOT / "evaluation" / "rag_cases.json").read_text(encoding="utf-8"))
    per_case = []
    for case in cases:
        hits = retrieve(case["question"], limit=3)
        ids = [hit["id"] for hit in hits]
        metadata_complete = all(all(hit.get(key) for key in ("id", "title", "url", "section")) for hit in hits)
        per_case.append({**case, "retrieved_ids": ids, "hit_at_3": case["expected_source"] in ids, "metadata_complete": metadata_complete})
    unsupported = answer_question("Explain quantum gravity topology without any experiment context")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_mode": "offline TF-IDF unigram/bigram cosine similarity",
        "cases": len(cases),
        "recall_at_3": sum(row["hit_at_3"] for row in per_case) / len(per_case),
        "citation_metadata_completeness": sum(row["metadata_complete"] for row in per_case) / len(per_case),
        "unsupported_answer_handling": {
            "passed": unsupported["evidence_sufficient"] is False,
            "answer": unsupported["answer"],
        },
        "per_case": per_case,
    }


if __name__ == "__main__":
    result = run()
    (ROOT / "evaluation" / "rag_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
