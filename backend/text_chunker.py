"""Split novels into chapters and sub-chunks for RAG indexing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

CHAPTER_PATTERNS = [
    r"第[零一二三四五六七八九十百千\d]+[章节幕]",
    r"Chapter\s+\d+",
    r"Act\s+[IVX\d]+",
    r"\n#{1,3}\s+.{2,}",
]

CHAPTER_REGEX = re.compile("|".join(f"({p})" for p in CHAPTER_PATTERNS), re.IGNORECASE | re.MULTILINE)


@dataclass
class Chapter:
    index: int
    title: str
    content: str

    @property
    def full_text(self) -> str:
        return f"{self.title}\n{self.content}".strip()


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    chapter_index: int
    chapter_title: str
    chunk_index: int


def split_into_chapters(text: str) -> List[Chapter]:
    matches = list(CHAPTER_REGEX.finditer(text))
    if not matches:
        return [Chapter(index=0, title="全文", content=text.strip())]

    chapters: List[Chapter] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        chapters.append(Chapter(index=0, title="序章", content=preamble))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        title = match.group(0).strip()
        body = block[len(title):].strip()
        chapters.append(Chapter(index=len(chapters), title=title, content=body))

    return chapters


def chunk_chapter(chapter: Chapter, chunk_size: int = 1500, overlap: int = 200) -> List[TextChunk]:
    full = chapter.full_text
    if len(full) <= chunk_size:
        return [TextChunk(chunk_id=f"ch{chapter.index}_c0", text=full, chapter_index=chapter.index, chapter_title=chapter.title, chunk_index=0)]

    chunks: List[TextChunk] = []
    start = 0
    chunk_index = 0
    while start < len(full):
        end = min(start + chunk_size, len(full))
        piece = full[start:end].strip()
        if piece:
            chunks.append(TextChunk(chunk_id=f"ch{chapter.index}_c{chunk_index}", text=piece, chapter_index=chapter.index, chapter_title=chapter.title, chunk_index=chunk_index))
            chunk_index += 1
        if end >= len(full):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_chunks(text: str, chunk_size: int = 1500, overlap: int = 200):
    chapters = split_into_chapters(text)
    all_chunks = []
    for chapter in chapters:
        all_chunks.extend(chunk_chapter(chapter, chunk_size=chunk_size, overlap=overlap))
    return chapters, all_chunks
