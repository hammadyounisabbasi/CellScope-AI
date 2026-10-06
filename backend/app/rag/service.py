from __future__ import annotations

from functools import lru_cache
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .knowledge import DOCUMENTS


@lru_cache
def _index() -> tuple[TfidfVectorizer, Any]:
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([doc["text"] + " " + doc["title"] for doc in DOCUMENTS])
    return vectorizer, matrix


def retrieve(question: str, limit: int = 3, minimum_score: float = 0.05) -> list[dict[str, Any]]:
    vectorizer, matrix = _index()
    query = vectorizer.transform([question])
    scores = cosine_similarity(query, matrix)[0]
    ranked = sorted(enumerate(scores), key=lambda pair: pair[1], reverse=True)
    return [
        {**DOCUMENTS[index], "score": round(float(score), 4)}
        for index, score in ranked[:limit]
        if score >= minimum_score
    ]

