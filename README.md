# CIPHER

**C**ourse **I**ntelligence for **P**rivacy-preserving **H**ands-on **E**ducation and **R**eview

A local, privacy-preserving network security tutor and quiz bot for CS5342 (Texas Tech University, Fall 2026).
All inference runs on the user's machine via Ollama; course documents never leave the host.
Internet access is limited to optional citation lookup, and only the user's query text is sent.

## Agents

| Agent | Purpose |
|---|---|
| Q&A Tutor | Answers course questions from the local knowledge base with per-chunk citations (file + page/slide). Optionally adds web references. |
| Quiz | Generates random or topic-specific quizzes (multiple choice, true/false, open-ended), grades answers, and gives cited feedback. |

## Architecture

```
Browser ──> Web UI (Streamlit / React) ──> FastAPI backend
                                              ├── Q&A Tutor Agent ──┐
                                              ├── Quiz Agent ───────┤
                                              │                     ▼
                                              │             Retriever ──> ChromaDB (data/chroma, local disk)
                                              │                     │
                                              └──> Ollama (localhost:11434): qwen2.5 + nomic-embed-text
                                                    [optional] DuckDuckGo search: query text only
```

Ingestion: `data/raw/*` → SHA-256 integrity check (`data/manifest.json`) → page/slide extraction → ~500-word chunks → local embeddings → ChromaDB.

## Prerequisites

- Windows 10/11, macOS, or Linux
- Python 3.11+
- [Ollama](https://ollama.com) with models pulled:
  ```bash
  ollama pull qwen2.5:3b
  ollama pull nomic-embed-text
  ```
- Wireshark (only for the network verification tasks)

## Setup

```bash
git clone https://github.com/MadhavKrishna06/CIPHER.git
cd CIPHER
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e .
copy .env.example .env          # cp on macOS/Linux
```

Place course documents (PDF, PPTX, DOCX, TXT, MD) in `data/raw/`. They are gitignored.

## Build the knowledge base

```bash
python -m cipher.ingest                   # hash-check, then ingest new files
python -m cipher.ingest --verify          # integrity report only
python -m cipher.ingest --accept-changes  # re-ingest files whose hash changed
python -m cipher.ingest --reset           # wipe the vector DB and start over
```

Every source file is SHA-256 hashed before ingestion and recorded in `data/manifest.json` (committed).
A file whose hash no longer matches is refused until re-approved with `--accept-changes`.
This prevents silently poisoned or tampered documents from entering the knowledge base.

Quick retrieval test:

```bash
python scripts/query_test.py "What are the goals of network security?"
```

## Run

_Coming in Round 2._

## Security verification

See [`security/`](security/) for the threat model, adversarial testing log, and traffic capture write-ups.

## Repository layout

```
src/cipher/       application package
  config.py       .env-driven settings
  integrity.py    SHA-256 manifest and verification
  loaders.py      PDF / PPTX / DOCX / text extraction
  ingest.py       chunk + embed + store pipeline
scripts/          helper scripts
data/raw/         course documents (local only)
data/chroma/      vector database (local only)
data/manifest.json
security/         threat model, adversarial log, capture write-ups
docs/             reports and slides
```

## Team

_Contribution table maintained in the Round 1 report._
