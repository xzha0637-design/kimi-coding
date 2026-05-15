"""Hybrid chunk-level retrieval: P1 (BM25) + P2 (embedding) → weighted merge + threshold."""
import os
from parser import parse_html
from chunker import chunk_all, CHUNK_DIR

_p1 = None
_p2 = None
_chunk_meta: dict[str, dict] = {}  # chunk_filename → {title, h2, h3, source_doc}

# Defaults
W1 = 0.3   # P1 weight
W2 = 0.7   # P2 weight
THRESHOLD = 0.35
MAX_K = 5
MIN_K = 1


def _ensure_loaded():
    global _p1, _p2, _chunk_meta
    if _p1 is not None:
        return
    from engine import engine as p1
    from engine_v2 import engine_v2 as p2

    # Chunk if not already done
    if not os.path.isdir(CHUNK_DIR) or not os.listdir(CHUNK_DIR):
        chunk_all()

    data_dir = os.path.dirname(CHUNK_DIR)
    base_docs = {}
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".html") or "chunk" in fname:
            continue
        doc_id = fname.replace(".html", "")
        path = os.path.join(data_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        parsed = parse_html(html)
        base_docs[doc_id] = parsed

    # Index chunks
    from app_v2 import DEPT_MAP, KEY_CONTENT_MAP
    for cfname in sorted(os.listdir(CHUNK_DIR)):
        if not cfname.endswith(".html"):
            continue
        cpath = os.path.join(CHUNK_DIR, cfname)
        with open(cpath, "r", encoding="utf-8") as f:
            chtml = f.read()
        parsed = parse_html(chtml)
        chunk_id = cfname.replace(".html", "")

        # Derive department/key_content from source doc
        source = cfname.split("_chunk-")[0]
        dept = DEPT_MAP.get(source, "")
        key = KEY_CONTENT_MAP.get(source, "")

        p1.index(chunk_id, parsed["title"], parsed["text"], key)
        p2.index(chunk_id, parsed["title"], parsed["text"], dept, key)

        _chunk_meta[chunk_id] = {
            "title": parsed["title"],
            "source": source,
        }

    _p1 = p1
    _p2 = p2


def _scored_chunks(query: str, threshold: float = THRESHOLD) -> list[tuple[str, float]]:
    """Retrieve chunks with scores. Returns [(chunk_id, score), ...] above threshold."""
    _ensure_loaded()

    # P1: BM25 keyword
    p1_results = _p1.search(query)
    p1_map = {r["id"]: r["score"] for r in p1_results}

    # P2: embedding semantic
    p2_results = _p2.search(query)
    p2_map = {r["id"]: r["score"] for r in p2_results}

    # Normalize each to [0, 1]
    def norm(d):
        if not d:
            return {}
        mx = max(d.values())
        return {k: v / mx for k, v in d.items()} if mx > 0 else {}

    n1 = norm(p1_map)
    n2 = norm(p2_map)

    # Weighted merge
    all_ids = set(n1.keys()) | set(n2.keys())
    scores = {}
    for cid in all_ids:
        scores[cid] = W1 * n1.get(cid, 0) + W2 * n2.get(cid, 0)

    # Threshold filter, then sort
    above = [(cid, s) for cid, s in scores.items() if s >= threshold]
    above.sort(key=lambda x: x[1], reverse=True)
    if not above:
        above = [max(scores.items(), key=lambda x: x[1])]
    return above


def retrieve(query: str, top_k: int = MAX_K, threshold: float = THRESHOLD) -> list[str]:
    """Retrieve relevant chunk filenames. Returns [chunk_id, ...]."""
    return [cid for cid, _ in _scored_chunks(query, threshold)[:top_k]]


def retrieve_docs(query: str, max_docs: int = 5, threshold: float = THRESHOLD) -> list[str]:
    """Chunk-level retrieval → max score + breadth bonus → ranked parent documents."""
    import math
    chunks = _scored_chunks(query, threshold)

    # Per-document: track max score and count of chunks above threshold
    doc_max: dict[str, float] = {}
    doc_cnt: dict[str, int] = {}
    for cid, score in chunks:
        source = _chunk_to_parent(cid)
        doc_max[source] = max(doc_max.get(source, 0), score)
        doc_cnt[source] = doc_cnt.get(source, 0) + 1

    # Score = max_chunk_score + breadth bonus (sqrt to subdue large counts)
    doc_scores = {}
    for source in doc_max:
        bonus = 0.02 * math.sqrt(max(doc_cnt[source] - 1, 0))
        doc_scores[source] = round(doc_max[source] + bonus, 4)

    ranked = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in ranked[:max_docs]]


def _chunk_to_parent(chunk_id: str) -> str:
    """Extract parent document ID from chunk ID."""
    if "_chunk-" in chunk_id:
        return chunk_id.split("_chunk-")[0]
    return chunk_id


def get_meta(chunk_id: str) -> dict:
    """Get metadata for a chunk."""
    _ensure_loaded()
    return _chunk_meta.get(chunk_id, {})
