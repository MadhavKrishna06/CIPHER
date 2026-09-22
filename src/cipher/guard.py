"""Deterministic input guard, layer 1 of the prompt-injection defense.

Runs before retrieval, before the LLM and before any web lookup. Pattern
matching is cheap and cannot be argued with, unlike prompt rules that a small
model follows only some of the time. Later layers: system prompt rules
(layer 2) and OFF_TOPIC / NOT_COVERED marker detection (layer 3).

Bypassable by rephrasing; that is expected and logged in
security/adversarial_log.md as attempts are found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Attempts to read or override the agent's instructions.
_META = [
    r"\b(system|initial|hidden|secret)\s+(prompt|instructions?|message)\b",
    r"\byour\s+(rules?|instructions?|guidelines?|configuration|config|prompt|directives?)\b",
    r"\b(what|which)\s+rules?\s+(do\s+you|you)\s+follow\b",
    r"\bignore\s+(all\s+|the\s+|any\s+)?(previous|prior|above|earlier)\b",
    r"\bdisregard\s+(all\s+|the\s+|your\s+)?(previous|prior|above|rules|instructions)\b",
    r"\b(you\s+are\s+now|act\s+as|pretend\s+(to\s+be|you\s+are))\b.*\b(dan|unrestricted|no\s+restrictions|developer\s+mode|jailbroken)\b",
    r"\bjailbreak\b",
    r"\brepeat\s+(everything|all|the\s+text)\s+(above|before)\b",
    r"\bhow\s+(do|were)\s+you\s+(work|configured|programmed|trained|built)\b",
]

# Questions that assume conversation memory the agent does not have.
_MEMORY = [
    r"\b(last|previous|earlier|prior|first)\s+(question|answer|message|prompt|query)\b",
    r"\bwhat\s+did\s+i\s+(ask|say)\b",
    r"\b(you|we)\s+(said|asked|discussed|talked\s+about)\s+(earlier|before|previously)\b",
    r"\bearlier\s+you\s+(said|mentioned)\b",
]

_META_RE = [re.compile(p, re.IGNORECASE) for p in _META]
_MEMORY_RE = [re.compile(p, re.IGNORECASE) for p in _MEMORY]

META_REPLY = "I can only help with network security topics from this course."
MEMORY_REPLY = "I do not keep conversation history, so I cannot see earlier questions. Please ask your question in full."


@dataclass
class Verdict:
    kind: str            # "ok" | "meta" | "memory"
    pattern: str | None  # regex that fired, for the adversarial log
    reply: str | None    # canned reply when kind != "ok"


def classify(question: str) -> Verdict:
    for rx in _META_RE:
        if rx.search(question):
            return Verdict("meta", rx.pattern, META_REPLY)
    for rx in _MEMORY_RE:
        if rx.search(question):
            return Verdict("memory", rx.pattern, MEMORY_REPLY)
    return Verdict("ok", None, None)
