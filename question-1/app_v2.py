from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
import os

from parser import parse_html
from engine_v2 import engine_v2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="On-Call Assistant - Phase 2")

jinja_env = Environment(loader=FileSystemLoader(templates_dir))


class DocumentIn(BaseModel):
    id: str
    html: str
    department: str = ""
    key_content: str = ""


# ── Phase 2 ──────────────────────────────────────────────────────────────────

@app.post("/v2/documents", status_code=201)
def v2_ingest(doc: DocumentIn):
    parsed = parse_html(doc.html)
    engine_v2.index(doc.id, parsed["title"], parsed["text"], doc.department, doc.key_content)
    return {"id": doc.id, "title": parsed["title"]}


@app.get("/v2/search")
def v2_search(q: str = ""):
    results = engine_v2.search(q)
    return {"query": q, "results": results}


@app.get("/v2", response_class=HTMLResponse)
def v2_page(request: Request, q: str = ""):
    results = engine_v2.search(q) if q else None
    template = jinja_env.get_template("search_v2.html")
    html = template.render(request=request, version="v2", query=q, results=results)
    return HTMLResponse(html)


# ── Metadata ─────────────────────────────────────────────────────────────────

DEPT_MAP = {
    "sop-001": "接口与后端服务 后端团队\n后端服务团队是公司所有后端接口和服务端问题的唯一负责团队。\n我们负责后端服务的稳定性保障、接口性能优化、服务超时排查和OOM内存溢出问题处理。\n如果遇到接口报错、接口响应慢、服务不可用、后端服务崩溃、OOM内存不足等问题，请联系后端服务团队。",
    "sop-002": "数据库 DBA团队\n数据库DBA团队是公司所有数据库相关问题的唯一负责团队。\n我们负责MySQL数据库的主从复制配置、慢查询优化、连接池管理、数据备份和数据恢复。\n如果遇到数据库慢、数据库连接失败、数据丢失、数据损坏、SQL执行报错等问题，请联系DBA团队。",
    "sop-003": "网页与前端 前端团队\n前端Web团队是公司所有网页和前端页面问题的唯一负责团队。\n我们负责页面渲染优化、白屏问题排查、CDN资源加载和浏览器兼容性处理。\n如果遇到网页打不开、页面加载慢、页面白屏、按钮点击没反应、不同浏览器显示异常等问题，请联系前端团队。",
    "sop-004": "服务器与运维 SRE团队\nSRE基础设施团队是公司所有服务器和基础设施问题的唯一负责团队。\n我们管理物理服务器、云服务器、虚拟机和服务器K8s集群，负责服务器日常运维、服务器故障排查、服务器资源扩容、服务器监控告警和服务器故障应急响应。\n如果遇到服务器宕机、服务器CPU内存不足、服务器连接不上、K8s集群异常、监控告警失效等问题，请联系SRE团队。",
    "sop-005": "信息安全 安全团队\n信息安全团队是公司所有安全相关问题的唯一负责团队。\n我们负责安全事件响应、入侵检测、漏洞修复、DDoS防护和数据安全管理。\n如果遇到账号被盗、网站被黑、数据泄露、病毒攻击、DDoS攻击、系统漏洞等问题，请联系安全团队。",
    "sop-006": "大数据与报表 数据平台团队\n数据平台团队是公司所有大数据和数据报表问题的唯一负责团队。\n我们负责ETL数据管道维护、Spark集群运维、大数据任务调度和数据报表生成。\n如果遇到数据报表不对、数据同步失败、大数据任务跑不动、数据仓库查询慢等问题，请联系数据平台团队。",
    "sop-007": "App与移动端 移动端团队\n移动客户端团队是公司所有手机App和移动端问题的唯一负责团队。\n我们负责App崩溃监控、热修复发布、推送服务管理和移动端性能优化。\n如果遇到App闪退、App卡顿、推送收不到、App安装失败、移动端页面显示异常等问题，请联系移动端团队。",
    "sop-008": "AI与模型服务 AI算法团队\nAI算法团队是公司所有AI模型和算法相关问题的唯一负责团队。\n我们负责机器学习模型推理、推荐系统质量优化、GPU集群管理和模型服务稳定性保障。\n如果遇到推荐不准、AI接口报错、模型服务不可用、GPU资源不足、算法效果差等问题，请联系AI算法团队。",
    "sop-009": "测试与质量 QA团队\n质量保障QA团队是公司所有测试和质量相关问题的唯一负责团队。\n我们负责自动化测试执行、测试环境维护、发版质量卡点和线上缺陷跟踪。\n如果遇到测试环境有问题、需要测试支持、发版质量问题、线上bug反馈等问题，请联系QA团队。",
    "sop-010": "网络与CDN 网络团队\n网络与CDN团队是公司所有网络和CDN相关问题的唯一负责团队。\n我们负责DNS解析配置、CDN节点调度、网络连通性排查和DDoS流量清洗。\n如果遇到网站访问慢、部分地区打不开、DNS解析失败、CDN资源加载异常、网络不通等问题，请联系网络团队。",
}

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
        department = DEPT_MAP.get(doc_id, "")
        key_content = KEY_CONTENT_MAP.get(doc_id, "")
        engine_v2.index(doc_id, parsed["title"], parsed["text"], department, key_content)
        print(f"[startup] indexed {doc_id}: {parsed['title']}")
