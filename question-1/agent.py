"""Agent — retrieval (P1+P2+RRF) tells which files, readFile tool reads them."""
import os
from llm import LLMClient
from retrieve import retrieve_docs
from config import FILE_CATALOG

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CHUNK_DIR = os.path.join(DATA_DIR, "chunks")

SYSTEM_PROMPT = """你是一个 On-Call 值班助手。你的职责是根据公司 SOP 文档，帮助值班工程师快速定位和解决问题。

## 可用工具

你有一个工具：`readFile(filename)` — 读取 data/ 目录下的 SOP 文件，返回文件内容。

## 工作流程

1. 系统会在用户问题前提供检索到的相关文件列表
2. 调用 readFile 读取这些文件
3. 基于文件内容给出具体、可操作的处理步骤

## 规则

- 必须基于 SOP 文档内容回答，不要编造
- 回答要分步骤、可操作
- 如果文件内容不够回答用户问题，说实话，不要猜测
- 给出答案时引用具体文件中的场景编号（如"场景二"）"""

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "readFile",
        "description": "读取 data/ 目录下的 SOP 文档，返回文件完整内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要读取的文件名，例如 'sop-001.html'、'sop-002.html'",
                }
            },
            "required": ["filename"],
        },
    },
}


def read_file(filename: str) -> str:
    safe = os.path.basename(filename)
    # Search chunks first, then main data dir
    for directory in (CHUNK_DIR, DATA_DIR):
        path = os.path.join(directory, safe)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return f"[错误] 文件 {filename} 不存在"


class OnCallAgent:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def chat(self, messages: list[dict]) -> dict:
        """
        messages: [{"role": "user"|"assistant", "content": "..."}]
        Returns: {"answer": str, "files_read": [str]}
        """
        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        query = " ".join(user_msgs[-3:]) if user_msgs else ""

        # 1. Chunk-level retrieval → map to parent documents
        top_docs = retrieve_docs(query, max_docs=5)
        if not top_docs:
            return {"answer": "未找到相关 SOP 文档，请提供更多信息。", "files_read": []}

        # 2. Build hint with full document filenames
        file_hint = "\n".join(f"  - {d}.html" for d in top_docs)
        file_hint += f"\n\n文件目录参考：\n{FILE_CATALOG}"
        augmented_query = f"系统检索到以下相关 SOP 文档，请使用 readFile 读取完整文件：\n{file_hint}\n\n用户问题：{query}"

        files_read = []
        api_messages = [
            {"role": "user", "content": augmented_query},
        ]

        # 3. Agent loop with readFile tool
        while True:
            resp = self._llm.chat(SYSTEM_PROMPT, api_messages, [READ_FILE_TOOL])

            if not resp.tool_calls:
                return {"answer": resp.text, "files_read": files_read}

            api_messages.append(self._llm.build_assistant_message(resp))

            for tc in resp.tool_calls:
                fname = tc.arguments.get("filename", "")
                content = read_file(fname)
                files_read.append(fname)
                api_messages.append(self._llm.build_tool_result(tc.id, content))


def create_agent() -> OnCallAgent:
    return OnCallAgent(LLMClient())
