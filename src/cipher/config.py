"""Central configuration. Reads .env at repo root; falls back to safe defaults."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Repo root = two levels above this file (src/cipher/config.py)
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _path(env_key: str, default: str) -> Path:
    value = os.getenv(env_key, default)
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text")

RAW_DIR: Path = _path("RAW_DIR", "data/raw")
CHROMA_DIR: Path = _path("CHROMA_DIR", "data/chroma")
MANIFEST_PATH: Path = _path("MANIFEST_PATH", "data/manifest.json")

CHUNK_WORDS: int = int(os.getenv("CHUNK_WORDS", "500"))
CHUNK_OVERLAP_WORDS: int = int(os.getenv("CHUNK_OVERLAP_WORDS", "50"))

WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "true").lower() == "true"

COLLECTION_NAME = "cs5342"
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".md"}
