"""Local HTTP API for CIPHER. Bound to the loopback interface only.

Run it with:
    uvicorn cipher.api:app --host 127.0.0.1 --port 8000

Why a separate process from the UI: the Streamlit page talks to this API, and this
API talks to Ollama. Every hop is loopback, so the Round 2 local-only packet capture
shows a short, explainable set of conversations and nothing else. It also leaves a
real HTTP boundary for the bonus access-control work.

Security properties this file is responsible for:
  * host is 127.0.0.1, so nothing is reachable from another machine
  * no CORS middleware, so a web page cannot call it from the browser
  * quiz answer keys stay in this process; responses carry Question.for_student()
  * the input guard runs here, before retrieval, so a direct API call cannot skip it
  * the internet toggle is enforced here, not in the browser
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import retriever
from .config import (
    COLLECTION_NAME,
    EMBED_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    WEB_SEARCH_ENABLED,
)
from .qa_agent import ask
from .quiz_agent import QTYPES, Question, generate, grade

app = FastAPI(title="CIPHER", description="Local network security tutor and quiz bot")

# Generated quizzes, keyed by quiz id. Answer keys must never reach the browser, so
# they stay here. In memory on purpose: restarting the API drops quizzes in progress,
# which is a fair trade for keys that are never written to disk.
_QUIZZES: OrderedDict[str, list[Question]] = OrderedDict()
_MAX_QUIZZES = 32


def _chunk_dict(c) -> dict:
    return {
        "citation": c.citation,
        "source": c.source,
        "page": c.page,
        "distance": c.score,
        "text": c.text,
    }


# --- requests ----------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=5, ge=1, le=20)
    web: bool | None = None          # None means fall back to the .env setting


class QuizRequest(BaseModel):
    mode: str = Field(default="random", pattern="^(random|topic)$")
    topic: str | None = Field(default=None, max_length=200)
    count: int = Field(default=3, ge=1, le=10)
    types: list[str] = Field(default=list(QTYPES))
    verify: bool = True


class GradeRequest(BaseModel):
    quiz_id: str
    index: int = Field(ge=0)
    answer: str = Field(default="", max_length=4000)
    web: bool | None = None          # None means fall back to the .env setting


# --- endpoints ---------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    """Report whether the local stack is actually up.

    Checked before anything else by the UI, because every earlier failure in this
    project started as an Ollama connection error surfacing as a stack trace.
    """
    models: list[str] = []
    ollama_up = False
    detail = None
    try:
        r = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3.0)
        r.raise_for_status()
        models = [m["model"] for m in r.json().get("models", [])]
        ollama_up = True
    except Exception as exc:                      # network, timeout, bad JSON
        detail = f"{type(exc).__name__}: {exc}"

    chunks = None
    try:
        chunks = retriever.count()
    except Exception as exc:
        detail = detail or f"{type(exc).__name__}: {exc}"

    return {
        "ollama": ollama_up,
        "ollama_host": OLLAMA_HOST,
        "chat_model": OLLAMA_MODEL,
        "chat_model_present": any(m.startswith(OLLAMA_MODEL.split(":")[0]) for m in models),
        "embed_model": EMBED_MODEL,
        "embed_model_present": any(m.startswith(EMBED_MODEL) for m in models),
        "models": models,
        "collection": COLLECTION_NAME,
        "chunks": chunks,
        "web_search_default": WEB_SEARCH_ENABLED,
        "detail": detail,
    }


@app.get("/sources")
def sources() -> dict:
    return {"sources": retriever.sources()}


@app.post("/ask")
def ask_endpoint(req: AskRequest) -> dict:
    try:
        a = ask(req.question, k=req.k, web=req.web)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc

    return {
        "question": a.question,
        "answer": a.answer,
        "grounded": a.grounded,
        "partial": a.partial,
        "weak_match": a.weak_match,
        "best_distance": a.best_distance,
        "blocked_by": a.blocked_by,
        "sources": [_chunk_dict(c) for c in a.sources],
        "web_sources": [{"title": w.title, "url": w.url, "snippet": w.snippet} for w in a.web_sources],
        # Trace for the Round 2 capture write-up: what was retrieved for this prompt
        # and the exact text handed to the local model.
        "trace": {
            "retrieved": [_chunk_dict(c) for c in a.retrieved],
            "context": a.context,
            "raw": a.raw,
            "citations_repaired": a.citations_repaired,
        },
    }


@app.post("/quiz/generate")
def quiz_generate(req: QuizRequest) -> dict:
    bad = [t for t in req.types if t not in QTYPES]
    if bad:
        raise HTTPException(status_code=422, detail=f"unknown question types: {bad}")
    if req.mode == "topic" and not (req.topic or "").strip():
        raise HTTPException(status_code=422, detail="topic mode needs a topic")

    try:
        questions = generate(mode=req.mode, topic=req.topic, count=req.count,
                             types=tuple(req.types), verify=req.verify)
    except PermissionError as exc:               # blocked by the input guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc

    if not questions:
        raise HTTPException(status_code=404, detail="No usable passages found for that topic.")

    quiz_id = uuid.uuid4().hex
    _QUIZZES[quiz_id] = questions
    while len(_QUIZZES) > _MAX_QUIZZES:
        _QUIZZES.popitem(last=False)

    return {
        "quiz_id": quiz_id,
        "questions": [q.for_student() for q in questions],
    }


@app.post("/quiz/grade")
def quiz_grade(req: GradeRequest) -> dict:
    questions = _QUIZZES.get(req.quiz_id)
    if questions is None:
        raise HTTPException(status_code=404, detail="Unknown or expired quiz. Generate a new one.")
    if req.index >= len(questions):
        raise HTTPException(status_code=422, detail="question index out of range")

    question = questions[req.index]
    try:
        result = grade(question, req.answer, web=req.web)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"{type(exc).__name__}: {exc}") from exc

    return {
        "correct": result.correct,
        "score": result.score,
        "feedback": result.feedback,
        "reference": result.reference,
        "citation": result.citation,
        "similarity": result.similarity,
        "judge_verdict": result.judge_verdict,
        "passage": question.passage,
        "web_sources": [{"title": w.title, "url": w.url, "snippet": w.snippet}
                        for w in result.web_sources],
    }
