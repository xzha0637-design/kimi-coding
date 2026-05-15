import re
import numpy as np
from sentence_transformers import SentenceTransformer


# Generic failure words that don't help distinguish between departments
_FAIL_WORDS = {
    "挂了", "崩了", "坏了", "打不开", "出问题", "出错了", "不行了",
    "异常", "失败", "报错", "超时", "卡住了", "有问题", "出故障",
    "连不上", "访问不了", "不能用", "用不了", "加载不了", "没反应",
    "无响应", "太慢", "慢了", "不动了", "怎么办", "怎么处理",
}


def weight_query(query: str) -> str:
    """Strip generic failure words, repeat the subject 3x to amplify its signal."""
    subject = query
    for w in _FAIL_WORDS:
        subject = subject.replace(w, "")
    subject = re.sub(r"\s+", " ", subject).strip()
    if not subject or subject == query:
        return query
    return f"{subject} {subject} {subject} {query}"


class SemanticEngine:
    def __init__(self, model_name: str = "BAAI/bge-base-zh-v1.5"):
        self._model = SentenceTransformer(model_name)
        self._docs: dict[str, dict] = {}

    def index(self, doc_id: str, title: str, text: str,
              department: str = "", key_content: str = "") -> None:
        self._docs[doc_id] = {"title": title, "text": text}
        dept_original, _, dept_expanded = department.partition("\n")
        doc_repr = (
            f"部门：{dept_original}。部门说明：{dept_expanded}。"
            f"部门：{dept_original}。部门说明：{dept_expanded}。"
            f"关键内容：{key_content}。关键内容：{key_content}。"
            f"标题：{title}。"
            f"正文：{text[:2000]}"
        )
        self._docs[doc_id]["embedding"] = self._model.encode(
            doc_repr, normalize_embeddings=True
        )

    def search(self, query: str, top_k: int = 10, min_score: float = 0.0) -> list[dict]:
        if not query or not query.strip():
            return []
        q_vec = self._model.encode(weight_query(query.strip()), normalize_embeddings=True)
        scores = {}
        for doc_id, doc in self._docs.items():
            scores[doc_id] = round(float(np.dot(q_vec, doc["embedding"])), 4)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranked = [(did, s) for did, s in ranked if s >= min_score]
        if top_k > 0:
            ranked = ranked[:top_k]
        return [
            {
                "id": doc_id,
                "title": self._docs[doc_id]["title"],
                "snippet": self._snippet(doc_id),
                "score": score,
            }
            for doc_id, score in ranked
        ]

    def _snippet(self, doc_id: str) -> str:
        text = self._docs[doc_id]["text"]
        return text[:150] + ("..." if len(text) > 150 else "")


engine_v2 = SemanticEngine()
