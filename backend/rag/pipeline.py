"""RAG pipeline: index novel chunks, analyze globally then per chapter."""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

from models import AIGlobalDraft, AIAct
from text_chunker import Chapter, build_chunks
from rag.embeddings import GeminiEmbeddings
from rag.vector_store import InMemoryVectorStore

ProgressCallback = Optional[Callable[[str], None]]


class NovelRAGPipeline:
    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client or genai.Client()
        self._embeddings = GeminiEmbeddings(self._client)
        self._store = InMemoryVectorStore()
        self._model = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    def _progress(self, cb: ProgressCallback, message: str) -> None:
        if cb:
            cb(message)

    def index_novel(
        self,
        text: str,
        reference_texts: Optional[List[str]] = None,
        progress_callback: ProgressCallback = None,
    ) -> List[Chapter]:
        self._progress(progress_callback, "RAG: 分块并生成向量嵌入...")
        chapters, chunks = build_chunks(text)
        if not chunks:
            return chapters
        vectors = self._embeddings.embed_texts([c.text for c in chunks])
        self._store.clear()
        self._store.add_many(
            [c.chunk_id for c in chunks],
            [c.text for c in chunks],
            vectors,
            [
                {
                    "chapter_index": c.chapter_index,
                    "chapter_title": c.chapter_title,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )
        if reference_texts:
            ref_vectors = self._embeddings.embed_texts(reference_texts)
            self._store.add_many(
                [f"ref_{i}" for i in range(len(reference_texts))],
                list(reference_texts),
                ref_vectors,
                [{"source": "reference"} for _ in reference_texts],
            )
        return chapters

    def retrieve_context(self, query: str, top_k: int = 10) -> str:
        qv = self._embeddings.embed_query(query)
        hits = self._store.search(qv, top_k=top_k)
        return "\n\n---\n\n".join(h.text for h in hits)

    def _llm_json(self, prompt: str, schema: type) -> Any:
        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=schema,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return schema.model_validate_json(response.text)

    def analyze_global(
        self,
        chapters: List[Chapter],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        self._progress(progress_callback, "RAG: 分析全局故事线与人物...")
        sample = "\n".join(ch.full_text[:1500] for ch in chapters[:15])
        context = self.retrieve_context("主线剧情 人物关系 主题 背景设定", top_k=12)
        prompt = (
            "你是资深影视编剧。请根据检索到的小说片段与章节摘要，提炼全局剧本草案要素。\n\n"
            f"检索上下文:\n{context}\n\n章节摘要:\n{sample}"
        )
        draft = self._llm_json(prompt, AIGlobalDraft)
        return draft.model_dump()

    def analyze_chapter(
        self,
        chapter: Chapter,
        global_draft: Dict[str, Any],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        context = self.retrieve_context(f"{chapter.title}\n{chapter.content[:800]}", top_k=10)
        prompt = (
            "在以下全局设定下，将本章节改编为一幕戏剧结构（含场景、节拍与对白候选）。\n"
            f"Logline: {global_draft.get('logline')}\n"
            f"Theme: {global_draft.get('theme')}\n"
            f"Tone: {global_draft.get('tone')}\n\n"
            f"检索上下文:\n{context}\n\n"
            f"本章内容:\n{chapter.full_text[:14000]}"
        )
        act = self._llm_json(prompt, AIAct)
        return act.model_dump()

    def run(
        self,
        text: str,
        reference_texts: Optional[List[str]] = None,
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        chapters = self.index_novel(text, reference_texts, progress_callback)
        global_draft = self.analyze_global(chapters, progress_callback)
        acts: List[Dict[str, Any]] = []
        total = len(chapters)
        for idx, chapter in enumerate(chapters, start=1):
            if chapter.title == "序章" and not chapter.content.strip():
                continue
            self._progress(
                progress_callback,
                f"RAG: 章节分析 {idx}/{total} — {chapter.title}",
            )
            acts.append(self.analyze_chapter(chapter, global_draft, progress_callback))
        return {**global_draft, "acts": acts}


def analyze_novel_with_rag(
    text: str,
    progress_callback: ProgressCallback = None,
    reference_texts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return NovelRAGPipeline().run(
        text,
        reference_texts=reference_texts,
        progress_callback=progress_callback,
    )
