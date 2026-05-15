import re
import math
from collections import defaultdict
import jieba


def tokenize(text: str) -> list[str]:
    """Tokenize text, preserving & as a searchable token."""
    text = re.sub(r"&", " & ", text)
    text = re.sub(r"\+", " + ", text)
    tokens = jieba.lcut(text)
    return [t.strip() for t in tokens if t.strip()]


class SearchEngine:
    # BM25 parameters
    K1 = 1.5
    B = 0.75

    # Field weights
    W_KEY_CONTENT = 3
    W_TITLE = 2
    W_BODY = 1

    def __init__(self):
        self._docs: dict[str, dict] = {}
        self._index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._avgdl: float = 0.0

    def index(self, doc_id: str, title: str, text: str, key_content: str = "") -> None:
        self._remove_doc(doc_id)
        tokens = tokenize(text)
        self._docs[doc_id] = {
            "title": title,
            "text": text,
            "key_content": key_content,
            "len": len(tokens),
        }
        self._avgdl = 0.0
        for pos, token in enumerate(tokens):
            self._index[token].append((doc_id, pos))

    def _remove_doc(self, doc_id: str) -> None:
        if doc_id not in self._docs:
            return
        for token in tokenize(self._docs[doc_id]["text"]):
            if token in self._index:
                self._index[token] = [
                    (did, pos) for did, pos in self._index[token] if did != doc_id
                ]
                if not self._index[token]:
                    del self._index[token]
        self._avgdl = 0.0
        del self._docs[doc_id]

    def search(self, query: str) -> list[dict]:
        if not query or not query.strip():
            return []

        query_tokens = tokenize(query.strip())
        if not query_tokens:
            return []

        # Compute avgdl lazily
        N = len(self._docs)
        if N == 0:
            return []
        if self._avgdl == 0.0:
            self._avgdl = sum(d["len"] for d in self._docs.values()) / N

        # BM25 score per document
        scores: dict[str, float] = defaultdict(float)

        for token in query_tokens:
            postings = self._index.get(token, [])
            df = len(set(did for did, _ in postings))
            if df == 0:
                continue
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

            for doc_id, _ in postings:
                doc = self._docs[doc_id]
                tf = sum(1 for did, _ in postings if did == doc_id)
                dl = doc["len"]
                bm25_tf = (tf * (self.K1 + 1)) / (tf + self.K1 * (1 - self.B + self.B * dl / self._avgdl))
                scores[doc_id] += idf * bm25_tf * self.W_BODY

        # Title and key_content bonuses
        for token in query_tokens:
            for doc_id in scores:
                doc = self._docs[doc_id]
                if token in doc["title"]:
                    scores[doc_id] += self.W_TITLE
                if token in doc["key_content"]:
                    scores[doc_id] += self.W_KEY_CONTENT

        if not scores:
            return []

        # Normalize to [0, 1]
        max_score = max(scores.values())
        if max_score > 0:
            scores = {k: round(v / max_score, 4) for k, v in scores.items()}

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [
            {
                "id": doc_id,
                "title": self._docs[doc_id]["title"],
                "snippet": self._snippet(doc_id, query_tokens),
                "score": score,
            }
            for doc_id, score in ranked
        ]

    def _snippet(self, doc_id: str, query_tokens: list[str]) -> str:
        text = self._docs[doc_id]["text"]
        match_pos = len(text)
        match_token = ""
        for token in query_tokens:
            idx = text.find(token)
            if 0 <= idx < match_pos:
                match_pos = idx
                match_token = token
        if not match_token:
            return text[:100]
        ctx_radius = 30
        start = max(0, match_pos - ctx_radius)
        end = min(len(text), match_pos + len(match_token) + ctx_radius)
        snippet = text[start:end]
        snippet = snippet.replace(match_token, f"<mark>{match_token}</mark>", 1)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return prefix + snippet + suffix


engine = SearchEngine()
