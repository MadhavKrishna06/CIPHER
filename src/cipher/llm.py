"""Single place that builds the local Ollama chat model."""

from __future__ import annotations

from langchain_ollama import ChatOllama

from .config import OLLAMA_HOST, OLLAMA_MODEL


def get_llm(temperature: float = 0.1, json_mode: bool = False,
            schema: dict | None = None, model: str | None = None) -> ChatOllama:
    """Build the chat model.

    json_mode forces syntactically valid JSON but says nothing about the shape, so a
    small model can still drop a required field or flatten a nested object. Passing a
    JSON Schema instead is stronger: Ollama compiles it into a decoding grammar and
    gives zero probability to any token that would violate it, so the shape cannot
    come back wrong. Use schema whenever the output is parsed by code.
    """
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_HOST,
        temperature=temperature,
        num_ctx=8192,               # room for ~5 chunks + question + answer
        keep_alive="30m",           # keep weights loaded between requests
        format=schema or ("json" if json_mode else None),
    )
