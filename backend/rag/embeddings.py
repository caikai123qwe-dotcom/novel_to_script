"""Gemini embeddings for RAG retrieval."""
from __future__ import annotations

import os
from typing import List, Sequence

import numpy as np
from google import genai
from google.genai import types

DEFAULT_EMBED_MODEL = "gemini-embedding-001"


class GeminiEmbeddings:
    def __init__(self, client: genai.Client | None = None, model: str | None = None):
        self._client = client or genai.Client()
        self._model = model or os.getenv("GEMINI_EMBED_MODEL", DEFAULT_EMBED_MODEL)

    def embed_texts(self, texts: Sequence[str], task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        vectors: List[List[float]] = []
        batch_size = 64
        text_list = list(texts)
        for i in range(0, len(text_list), batch_size):
            batch = text_list[i : i + batch_size]
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            for emb in response.embeddings:
                vectors.append(list(emb.values))
        return np.array(vectors, dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
