"""Load the synthetic dataset into Postgres (wipes tenant data first).

    python -m db.init          # once
    python -m seed.load        # any time; resets the demo sandbox in a few seconds
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from sqlalchemy import insert, text

from db.models import Base, PolicyChunk, PolicyDoc
from db.session import admin_session
from rag.ingest import chunk_markdown
from seed.generate import generate, uid, write_ground_truth

POLICY_DIR = Path(__file__).with_name("policies")


def load(seed: int = 42) -> dict[str, int]:
    ds = generate(seed)
    write_ground_truth(ds)
    org_id = ds.tables["organizations"][0]["id"]
    counts: dict[str, int] = {}
    with admin_session() as s:
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        s.execute(text(f"TRUNCATE {names} CASCADE"))
        for table in Base.metadata.sorted_tables:
            rows = ds.tables.get(table.name)
            if rows:
                s.execute(insert(table), rows)
                counts[table.name] = len(rows)
        for path in sorted(POLICY_DIR.glob("*.md")):
            doc_id = uid("policy", path.stem)
            s.execute(insert(PolicyDoc), [{"id": doc_id, "org_id": org_id,
                                           "title": path.stem.replace("_", " ").title(),
                                           "version": "2.1", "source": path.name}])
            chunks = chunk_markdown(path.read_text(encoding="utf-8"))
            s.execute(insert(PolicyChunk), [
                {"id": uid("chunk", doc_id, i), "org_id": org_id, "doc_id": doc_id,
                 "section": c.section, "text": c.text, "embedding": None}
                for i, c in enumerate(chunks)])
            counts["policy_chunks"] = counts.get("policy_chunks", 0) + len(chunks)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    started = time.perf_counter()
    result = load(parser.parse_args().seed)
    print(result)
    print(f"Sandbox reset in {time.perf_counter() - started:.1f}s")
