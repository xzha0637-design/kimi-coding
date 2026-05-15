"""LLM abstraction layer — agent.py depends on this, not on any specific SDK."""
import json
from dataclasses import dataclass, field
from openai import OpenAI
import config


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning_content: str = ""  # DeepSeek thinking mode


class LLMClient:
    """Unified LLM interface. Provider is determined by config.LLM_PROVIDER."""

    def __init__(self):
        provider = config.LLM_PROVIDER

        if provider == "deepseek":
            if not config.DEEPSEEK_API_KEY:
                raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY")
            self._client = OpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL,
            )
            self._model = config.DEEPSEEK_MODEL

        elif provider == "openai":
            if not config.OPENAI_API_KEY:
                raise RuntimeError("请设置环境变量 OPENAI_API_KEY")
            self._client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL,
            )
            self._model = config.OPENAI_MODEL

        elif provider == "anthropic":
            from anthropic import Anthropic
            if not config.ANTHROPIC_API_KEY:
                raise RuntimeError("请设置环境变量 ANTHROPIC_API_KEY")
            self._client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
            self._model = config.ANTHROPIC_MODEL
            self._provider = "anthropic"

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

        if provider != "anthropic":
            self._provider = "openai-compat"

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        if self._provider == "anthropic":
            return self._chat_anthropic(system_prompt, messages, tools)
        return self._chat_openai_compat(system_prompt, messages, tools)

    def _chat_openai_compat(self, system_prompt, messages, tools) -> LLMResponse:
        api_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            api_messages.append(dict(m))

        kwargs = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": 4096,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))
        reasoning = getattr(msg, "reasoning_content", "") or ""
        return LLMResponse(text=msg.content or "", tool_calls=tool_calls, reasoning_content=reasoning)

    def _chat_anthropic(self, system_prompt, messages, tools) -> LLMResponse:
        # Convert OpenAI-format tools to Anthropic format
        anthropic_tools = []
        for t in tools:
            func = t["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"],
            })

        api_messages = []
        for m in messages:
            api_messages.append({"role": m["role"], "content": m["content"]})

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system_prompt,
            tools=anthropic_tools,
            messages=api_messages,
        )

        text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))
        return LLMResponse(text=text, tool_calls=tool_calls)

    def build_tool_result(self, tool_call_id: str, content: str) -> dict:
        if self._provider == "anthropic":
            return {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": content,
            }
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    def build_assistant_message(self, response: LLMResponse) -> dict:
        if self._provider == "anthropic":
            blocks = []
            if response.text:
                blocks.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            return {"role": "assistant", "content": blocks}
        msg = {
            "role": "assistant",
            "content": response.text,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ],
        }
        if response.reasoning_content:
            msg["reasoning_content"] = response.reasoning_content
        return msg
