from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
import os

from parser import parse_html
from engine import engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="On-Call Assistant")

jinja_env = Environment(loader=FileSystemLoader(templates_dir))


class DocumentIn(BaseModel):
    id: str
    html: str
    key_content: str = ""


# ── Phase 1 ──────────────────────────────────────────────────────────────────

@app.post("/v1/documents", status_code=201)
def v1_ingest(doc: DocumentIn):
    if not doc.id or not doc.id.strip():
        return JSONResponse({"error": "id is required"}, status_code=400)
    if not doc.html or not doc.html.strip():
        return JSONResponse({"error": "html is required"}, status_code=400)
    parsed = parse_html(doc.html)
    engine.index(doc.id, parsed["title"], parsed["text"], doc.key_content)
    return {"id": doc.id, "title": parsed["title"]}


@app.get("/v1/search")
def v1_search(q: str = ""):
    results = engine.search(q)
    return {"query": q, "results": results}


@app.get("/v1", response_class=HTMLResponse)
def v1_page(request: Request, q: str = ""):
    results = engine.search(q) if q else None
    template = jinja_env.get_template("search.html")
    html = template.render(request=request, version="v1", query=q, results=results)
    return HTMLResponse(html)


# ── Key content metadata per document ───────────────────────────────────────

KEY_CONTENT_MAP = {
    "sop-001": "OOM 排查、服务超时、降级策略、故障分级",
    "sop-002": "主从延迟、慢查询、连接池满、数据恢复",
    "sop-003": "页面白屏、CDN 资源加载失败、兼容性、性能劣化",
    "sop-004": "K8s 集群问题、监控告警、容量规划、故障响应",
    "sop-005": "安全事件分级、入侵检测、漏洞响应",
    "sop-006": "数据管道故障、ETL 失败、Spark 集群",
    "sop-007": "App 崩溃率、热修复、推送服务",
    "sop-008": "模型推理延迟、推荐质量下降、GPU 集群",
    "sop-009": "测试环境故障、自动化测试、发版卡点",
    "sop-010": "CDN 节点故障、DNS 异常、DDoS 防护",
}

# ── Bootstrap: index all data/ files on startup ─────────────────────────────

@app.on_event("startup")
def load_data():
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.isdir(data_dir):
        return
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".html"):
            continue
        doc_id = fname.replace(".html", "")
        path = os.path.join(data_dir, fname)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        parsed = parse_html(html)
        key_content = KEY_CONTENT_MAP.get(doc_id, "")
        engine.index(doc_id, parsed["title"], parsed["text"], key_content)
        print(f"[startup] indexed {doc_id}: {parsed['title']}")
