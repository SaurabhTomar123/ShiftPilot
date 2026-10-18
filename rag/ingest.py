"""Policy ingestion: split markdown by heading, then by size with overlap.

Embeddings are optional at seed time (no API key needed to start). Run
`python -m rag.ingest --embed` later to fill policy_chunks.embedding, then switch
search_policy to hybrid retrieval (see TODO in mcp_server/tools/read.py).
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

MAX_WORDS = 300  # ~400 tokens
OVERLAP_WORDS = 45  # ~60 tokens
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class Chunk:
    section: str
    text: str


def chunk_markdown(markdown: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    path: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        if not body:
            return
        section = " > ".join(path) or "Introduction"
        words = body.split()
        if len(words) <= MAX_WORDS:
            chunks.append(Chunk(section, body))
            return
        step = MAX_WORDS - OVERLAP_WORDS
        for start in range(0, len(words), step):
            chunks.append(Chunk(section, " ".join(words[start:start + MAX_WORDS])))
            if start + MAX_WORDS >= len(words):
                break

    for line in markdown.splitlines():
        m = HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[: level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return chunks


def embed_missing() -> int:
    """Fill embeddings for chunks that have none. Needs an embedding API key."""
    import litellm
    from sqlalchemy import select

    from core.config import settings
    from db.models import PolicyChunk
    from db.session import admin_session

    with admin_session() as s:
        rows = s.scalars(select(PolicyChunk).where(PolicyChunk.embedding.is_(None))).all()
        for i in range(0, len(rows), 64):
            batch = rows[i:i + 64]
            resp = litellm.embedding(model=settings().embedding_model,
                                     input=[f"{r.section}\n{r.text}" for r in batch])
            for row, item in zip(batch, resp.data, strict=True):
                row.embedding = item["embedding"]
        return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed", action="store_true")
    if parser.parse_args().embed:
        print(f"Embedded {embed_missing()} chunks.")
