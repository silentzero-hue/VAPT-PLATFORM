"""LLM provider abstraction: Anthropic + OpenAI-compatible.

Each provider has a single `chat(messages, tools)` method that the agent
loop drives. We deliberately do not type these as the SDK union types —
the runtime is provider-agnostic.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings


SYSTEM_PROMPT_HOUSE_STYLE = """You are a senior security analyst writing a pentest report.
House style:
 - Plain English, third person, present tense for the present state.
 - Each unique vulnerability gets ONE narrative block; the report lists
   every asset it appears on, but you do not duplicate the impact/
   recommendation per asset.
 - Severity and urgency definitions (per workspace override if any):
   Critical = immediate, exploitable, full compromise. SLA 7d.
   High = exploitable with limited conditions or significant impact. SLA 14d.
   Medium = real risk but needs chaining or has mitigations. SLA 30d.
   Low = informational or hardening. SLA 60d.
   Info = no direct impact, hygiene only. SLA 90d.
 - For Impact: explain business consequence to the client.
 - For Recommendation: provide concrete, version-pinned remediation.
 - Never claim a report is "final" or "approved" — that is a human action.
You have MCP tools. Use them; do not invent data.
When the user asks to draft, finish by calling flag_for_human_review
(or render_report then flag_for_human_review). Do not call any approve
function — that does not exist as a tool for you, by design.
"""


class LLMClient:
    """Thin wrapper that hides SDK differences from the agent loop."""

    def __init__(self) -> None:
        self.kind = settings.llm_provider
        if self.kind == "anthropic":
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=settings.llm_api_key)
        elif self.kind == "openai":
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url or None,
            )
        elif self.kind == "local":
            # Local model. The chat() method handles the local branch directly.
            self._client = None
        else:
            raise ValueError(f"unknown provider {settings.llm_provider}")

    async def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """Return a normalized dict with keys:
          - text: str | None
          - tool_calls: list[{id, name, arguments(dict)}]
          - finish_reason: str
        """
        if self.kind == "local":
            from app.services.agent import local as local_provider
            return local_provider.chat(messages, tools)
        if self.kind == "anthropic":
            sys = next((m["content"] for m in messages if m.get("role") == "system"), None)
            user_messages = [m for m in messages if m.get("role") != "system"]
            resp = await self._client.messages.create(  # type: ignore[attr-defined]
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                system=sys or SYSTEM_PROMPT_HOUSE_STYLE,
                tools=tools,  # type: ignore[arg-type]
                messages=user_messages,  # type: ignore[arg-type]
            )
            text = None
            calls: list[dict] = []
            for block in resp.content:
                if block.type == "text":
                    text = block.text
                elif block.type == "tool_use":
                    calls.append({"id": block.id, "name": block.name, "arguments": block.input})
            return {
                "text": text,
                "tool_calls": calls,
                "finish_reason": resp.stop_reason or "end_turn",
            }
        # OpenAI-compatible
        oa_messages = [{"role": "system", "content": SYSTEM_PROMPT_HOUSE_STYLE}]
        oa_messages.extend(messages)
        resp = await self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            messages=oa_messages,  # type: ignore[arg-type]
            tools=[{"type": "function", "function": t} for t in tools],  # type: ignore[arg-type]
        )
        msg = resp.choices[0].message
        calls = []
        for tc in (msg.tool_calls or []):
            import json
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn else ""
            arguments = getattr(fn, "arguments", "{}") if fn else "{}"
            try:
                args = json.loads(arguments or "{}")
            except Exception:
                args = {}
            calls.append({"id": tc.id, "name": name, "arguments": args})
        return {
            "text": msg.content,
            "tool_calls": calls,
            "finish_reason": resp.choices[0].finish_reason or "stop",
        }
