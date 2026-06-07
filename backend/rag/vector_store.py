"""In-memory vector store with cosine similarity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._ids: List[str] = []
        self._texts: List[str] = []
        self._metadata: List[Dict[str, Any]] = []
        self._vectors: Optional[np.ndarray] = None

    def clear(self) -> None:
        self._ids.clear()
        self._texts.clear()
        self._metadata.clear()
        self._vectors = None

    def add_many(
        self,
        ids: List[str],
        texts: List[str],
        vectors: np.ndarray,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if metadata is None:
            metadata = [{} for _ in ids]
        self._ids.extend(ids)
        self._texts.extend(texts)
        self._metadata.extend(metadata)
        if self._vectors is None or len(self._vectors) == 0:
            self._vectors = vectors.astype(np.float32)
        else:
            self._vectors = np.vstack([self._vectors, vectors.astype(np.float32)])

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> List[SearchResult]:
        if self._vectors is None or len(self._ids) == 0:
            return []
        q = query_vector.astype(np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-10)
        m = self._vectors
        m_norm = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-10)
        scores = m_norm @ q_norm
        k = min(top_k, len(scores))
        top_idx = np.argsort(scores)[::-1][:k]
        return [
            SearchResult(
                chunk_id=self._ids[i],
                text=self._texts[i],
                score=float(scores[i]),
                metadata=dict(self._metadata[i]),
            )
            for i in top_idx
        ]
