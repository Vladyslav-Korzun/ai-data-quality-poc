from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class RAGChunk:
    """A retrieved knowledge chunk with its source and relevance score."""
    source: str
    text: str
    score: float


def _read_knowledge_files(knowledge_dir: str) -> List[Tuple[str, str]]:
    """
    Read .md/.txt files from the knowledge directory.

    Returns:
        A list of (source_name, file_text) tuples.
        Source name is returned as a relative path to the knowledge directory
        when possible, so it's more informative than just the filename.
    """
    root = Path(knowledge_dir)
    if not root.exists() or not root.is_dir():
        return []

    docs: List[Tuple[str, str]] = []

    for fp in sorted(root.glob("**/*")):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in {".md", ".txt"}:
            continue

        content = fp.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            continue

        # Use a stable, human-friendly source label
        try:
            source = str(fp.relative_to(root))
        except ValueError:
            source = fp.name

        docs.append((source, content))

    return docs


def _split_into_chunks(text: str, max_chars: int = 900) -> List[str]:
    """
    Split text into chunks using a simple paragraph-based heuristic.

    Args:
        text: Document text.
        max_chars: Soft max character size per chunk.

    Returns:
        List of chunks (strings). Chunks are concatenations of paragraphs
        up to max_chars.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf = ""

    for part in paragraphs:
        if len(buf) + len(part) + 2 <= max_chars:
            buf = (buf + "\n\n" + part).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = part

    if buf:
        chunks.append(buf)

    return chunks


def retrieve_context(
    query: str,
    knowledge_dir: str = "knowledge",
    top_k: int = 4,
) -> List[RAGChunk]:
    """
    Retrieve relevant context from local knowledge files using TF-IDF similarity.

    This is a lightweight, local-only RAG approach suitable for a PoC:
    - No external vector DB
    - No embeddings API calls
    - Fast and easy to explain to stakeholders

    Args:
        query: User question.
        knowledge_dir: Directory containing .md/.txt files.
        top_k: Max number of chunks to return.

    Returns:
        A list of RAGChunk sorted by relevance (highest score first).
    """
    docs = _read_knowledge_files(knowledge_dir)
    if not docs:
        return []

    sources: List[str] = []
    chunks: List[str] = []

    for source, content in docs:
        for ch in _split_into_chunks(content):
            sources.append(source)
            chunks.append(ch)

    if not chunks:
        return []

    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(chunks)
    q = vectorizer.transform([query])

    # Similarity for TF-IDF L2-normalized vectors behaves like cosine similarity.
    scores = (X @ q.T).toarray().ravel()
    if scores.size == 0:
        return []

    idx = np.argsort(-scores)[:top_k]

    out: List[RAGChunk] = []
    for i in idx:
        if scores[i] <= 0:
            continue
        out.append(RAGChunk(source=sources[i], text=chunks[i], score=float(scores[i])))

    return out


def format_context(chunks: List[RAGChunk]) -> str:
    """
    Format retrieved chunks into a single text block to be injected into the LLM prompt.
    """
    if not chunks:
        return ""

    blocks = []
    for c in chunks:
        blocks.append(f"[{c.source} | score={c.score:.3f}]\n{c.text}")

    return "\n\n---\n\n".join(blocks)
