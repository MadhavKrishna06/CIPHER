"""Single place that builds the local Ollama chat model."""

from __future__ import annotations

from langchain_ollama import ChatOllama

from .config import OLLAMA_HOST, OLLAMA_MODEL


def get_llm(temperature: float = 0.1, json_mode: bool = False, model: str | None = None) -> ChatOllama:
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_HOST,
        temperature=temperature,
        num_ctx=8192,               # room for ~5 chunks + question + answer
        keep_alive="30m",           # keep weights loaded between requests
        format="json" if json_mode else None,
    )
