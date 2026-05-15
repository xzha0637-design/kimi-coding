from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
import os

from agent import create_agent

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_agent()
    return _agent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="On-Call Assistant - Phase 3")

jinja_env = Environment(loader=FileSystemLoader(templates_dir))


class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role": "user"|"assistant", "content": "..."}]


# ── Phase 3 ──────────────────────────────────────────────────────────────────

@app.get("/v3", response_class=HTMLResponse)
def v3_page(request: Request):
    template = jinja_env.get_template("chat.html")
    html = template.render(request=request, version="v3")
    return HTMLResponse(html)


@app.post("/v3/chat")
def v3_chat(req: ChatRequest):
    try:
        result = get_agent().chat(req.messages)
        return result
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": f"Agent error: {str(e)}"}, status_code=500)
