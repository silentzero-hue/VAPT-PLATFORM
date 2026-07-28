"""Local LLM provider (llama-cpp-python) for air-gapped deployments.

Strictly opt-in: when LLM_PROVIDER=local AND the model path is set,
the agent runtime uses this client instead of Anthropic/OpenAI.
The provider abstraction in services.agent.providers.LLMClient already
dispatches on settings.llm_provider; this module is the "local" branch.
"""

from __future__ import annotations

import os
from typing import Any

from app.core.logging import get_logger
from app.core.config import settings

log = get_logger(__name__)

_MODEL = None


def _load():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    path = os.environ.get("LOCAL_LLM_PATH", "")
    if not path or not os.path.exists(path):
        log.warning("local_llm_unavailable", path=path)
        return None
    try:
        from llama_cpp import Llama
        _MODEL = Llama(
            model_path=path,
            n_ctx=int(os.environ.get("LOCAL_LLM_CTX", "8192")),
            n_gpu_layers=int(os.environ.get("LOCAL_LLM_GPU_LAYERS", "0")),
        )
        return _MODEL
    except Exception as e:  # noqa: BLE001
        log.error("local_llm_load_failed", err=str(e))
        return None


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Minimal chat() with OpenAI-style tool support. Returns the same
    normalized dict as LLMClient.chat()."""
    m = _load()
    if m is None:
        return {"text": "local LLM not available", "tool_calls": [], "finish_reason": "error"}
    # llama-cpp's chat template expects OpenAI-style messages
    try:
        resp = m.create_chat_completion(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            tools=tools,
        )
        msg = resp["choices"][0]["message"]
        calls = []
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function", {}) or {}
            calls.append({
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": fn.get("arguments", ""),
            })
        return {
            "text": msg.get("content"),
            "tool_calls": calls,
            "finish_reason": resp["choices"][0].get("finish_reason", "stop"),
        }
    except Exception as e:  # noqa: BLE001
        log.exception("local_llm_call_failed")
        return {"text": f"error: {e}", "tool_calls": [], "finish_reason": "error"}
