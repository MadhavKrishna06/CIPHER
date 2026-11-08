# CIPHER

**C**ourse **I**ntelligence for **P**rivacy-preserving **H**ands-on **E**ducation and **R**eview

CS5342 Network Security group project, Texas Tech University, Fall 2026.

---

## 1. Project description

CIPHER is a local, privacy-preserving network security tutor and quiz bot. It answers
course questions from the class's own lecture slides and textbooks with a citation on
every claim, and it generates and grades quizzes over that same material.

The defining constraint is that course material never leaves the machine. All retrieval
and all language-model inference run locally through Ollama against a ChromaDB vector
store on local disk. The only traffic that ever leaves the host is an optional web
search for supplementary references, and that request carries the user's query text
only, never a passage from a course document. This is not a claim taken on trust: it was
verified with Wireshark by all seven group members independently, and the captures and
write-ups are in [`security/`](security/).

The system is built from two agents:

| Agent | Responsibility |
|---|---|
| **Q&A Tutor** | Understands a course question, retrieves the relevant passages from the local vector database, answers from those passages only, and attaches a citation (file plus page or slide number) to each claim. Adds web references when the local match is weak. |
| **Quiz** | Generates random or topic-specific quizzes in three formats (multiple choice, true/false, open-ended), grades the user's answer against a reference answer drawn from the source passage, and returns cited feedback with a numeric score. |

---

## 2. Features

**Q&A Tutor**

- Retrieval-augmented answers drawn only from the local corpus
- Per-claim citations resolved in Python after the model answers, so a citation cannot be invented
- Explicit refusal when the course materials do not cover the question, rather than a guess
- Weak-match detection: when the closest passage is farther than `WEAK_MATCH_DISTANCE`, the answer is supplemented with web references and labelled as such
- Retrieval trace panel showing exactly which passages were retrieved, their distances, and the literal text handed to the local model
- Input guard that rejects prompt-injection patterns before any inference runs

**Quiz**

- Two modes: randomly generated questions, and questions on a topic the user names
- Three formats: multiple choice, true/false, open-ended
- Generate-then-verify: each generated question is checked against its source passage before it reaches the user
- Grading on two independent signals — embedding similarity between the user's answer and the reference answer, and a separate language-model judge verdict
- Cited feedback, including internet citations when enabled
- Answer keys stay in the backend process and are never sent to the browser

**System**

- Web interface (Streamlit). The assignment prohibits a command-line interface
- SHA-256 integrity manifest over every ingested document; a changed file is refused until a human approves it
- Both the API and the UI bound to `127.0.0.1`, so nothing is reachable from another machine
- Telemetry disabled in ChromaDB and Streamlit, in code as well as in configuration
- Internet access controlled by a single switch (`WEB_SEARCH_ENABLED`) enforced in the backend, not in the browser
- `/health` endpoint reporting whether Ollama is up, which models are present, and how many chunks are indexed

---

## 3. System architecture

```
        Browser (localhost:8501)
               │  HTTP, loopback
               ▼
        Streamlit UI  ── ui/app.py
         holds no course data, no answer keys
               │  HTTP, loopback (127.0.0.1:8000)
               ▼
   ┌───────────────────────────────────────────────┐
   │  FastAPI backend  ── src/cipher/api.py        │
   │                                               │
   │   input guard ── src/cipher/guard.py          │
   │        │                                      │
   │        ├── Q&A Tutor Agent  ── qa_agent.py    │
   │        └── Quiz Agent       ── quiz_agent.py  │
   │                   │                           │
   │                   ▼                           │
   │        Retriever  ── retriever.py             │
   └───────────┬───────────────────┬───────────────┘
               │                   │
               ▼                   ▼
   ChromaDB (data/chroma)    Ollama (localhost:11434)
   local disk, 2686 chunks   qwen2.5:3b  + nomic-embed-text
                                         │
                                         │ [optional, query text only]
                                         ▼
                              DuckDuckGo  ── web_search.py
```

Three processes, three loopback hops. The split between UI and API is deliberate: it
keeps course data and quiz answer keys on one side of an HTTP boundary, makes the
local-only packet capture a short and explainable set of conversations, and leaves a
real authentication point for the bonus access-control work.

**Ingestion pipeline**

```
data/raw/**  →  SHA-256 hash check (integrity.py, manifest.json)
             →  page / slide text extraction (loaders.py)
             →  header and boilerplate filtering (textfilter.py)
             →  220-word chunks, 40-word overlap (ingest.py)
             →  local embeddings via nomic-embed-text
             →  ChromaDB collection "cs5342" (data/chroma)
```

**Query flow**

1. The user submits a prompt in the browser.
2. Streamlit posts it to the local API over loopback.
3. The input guard checks the prompt for injection patterns. A rejected prompt never reaches a model.
4. The prompt is embedded locally and used to query ChromaDB, which returns the `k` nearest passages with distances.
5. The passages are numbered `[1]`–`[5]` and placed in the prompt with no filename, page or title attached, so the model cannot fabricate a citation. The prompt goes to Ollama.
6. The model answers citing passage numbers. The application resolves those numbers back to file and page in Python, then renders the answer with its sources.

Full threat model, including trust boundaries and attack surface:
[`security/threat_model.md`](security/threat_model.md).

---

## 4. Training data and data formats

CIPHER is not fine-tuned. The model weights are unmodified; the course knowledge enters
the system entirely through retrieval. "Training data" here therefore means the indexed
corpus.

**Corpus**

| Source | Files | Format |
|---|---|---|
| CS5342 lecture slides, Lecture 01 – Lecture 11 | 11 | PDF |
| Kurose, *Computer Networking: A Top-Down Approach* | 1 | PDF |
| Stallings, *Network Security Essentials* | 1 | PDF |

13 documents, 2686 indexed chunks as of the manifest dated 2026-10-16.

Loaders exist for `.pdf`, `.pptx`, `.docx`, `.txt` and `.md`
(`SUPPORTED_EXTENSIONS` in `src/cipher/config.py`), so a source in any of those formats
can be added without code changes.

**Why the course documents are not in this repository.** `data/raw/` and `data/chroma/`
are gitignored. The textbooks are copyrighted and the vector store holds their text
verbatim; the repository is public. Place your own copies in `data/raw/slides/` and
`data/raw/textbooks/` and build the index locally, as described in section 7.

**Data formats inside the system**

*Chunk record in ChromaDB* — one per 220-word window:

```
id        "<rel_path>#<chunk_index>"
document  the chunk text
metadata  { source: "slides/Lecture 03.pdf",
            page: 12,
            kind: "slide" | "page",
            rel_path: "slides/Lecture 03.pdf",
            chunk_index: 7 }
embedding 768-dim vector from nomic-embed-text
```

*Integrity manifest* (`data/manifest.json`, committed):

```json
{
  "files": {
    "slides/Lecture 01.pdf": {
      "bytes": 790239,
      "sha256": "be4fa2f6acc0de33a01cd376329f5983e84545037b5e3c3cfcb236f4d8679b15",
      "ingested_at": "2026-10-16T02:04:24+00:00"
    }
  },
  "updated_at": "2026-10-16T02:04:24+00:00"
}
```

*Quiz question* — the student-facing form omits the answer key, which never leaves the
backend process:

```
qtype      "mcq" | "tf" | "open"
stem       question text
options    list of choices (mcq only)
passage    the source passage the question was generated from
citation   "Stallings NSE.pdf, p. 214"
answer     reference answer — backend only, stripped by Question.for_student()
```

---

## 5. Prerequisites

| Requirement | Version used | Notes |
|---|---|---|
| Operating system | Windows 11 | macOS and Linux work; only the activation command differs |
| Python | 3.11 or newer | `requires-python = ">=3.11"` |
| [Ollama](https://ollama.com) | 0.34.4 | Must be running and listening on `localhost:11434` |
| RAM | 16 GB | 8 GB is workable with `qwen2.5:3b` |
| GPU | NVIDIA GTX 1650, 4 GB VRAM | Optional. CPU-only works but is several times slower |
| Disk | ~6 GB | Models, vector database and corpus |
| Wireshark | 4.6.8 | Only for the Round 2 network verification tasks |

Pull the models before first run:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

`qwen2.5:7b` gives noticeably better grounding and fits in 4 GB VRAM only at reduced
context. The default is the 3B model because every group member has to run this.

**The embedding model digest matters.** Use `nomic-embed-text` at digest
`0a109f422b47`. A different digest produces different vectors, and a vector database
built with one digest will not retrieve correctly when queried with another.

---

## 6. Requirements

All Python dependencies are pinned in [`requirements.txt`](requirements.txt). They are
pinned rather than left open because seven people had to reproduce the same retrieval
results for the Round 2 captures, and an unpinned `chromadb` can refuse to open a
`data/chroma/` written by a different version.

| Area | Libraries |
|---|---|
| Web interface | `streamlit` 1.64.0 |
| Backend API | `fastapi` 0.141.1, `uvicorn[standard]` 0.53.0, `httpx` 0.28.1 |
| RAG framework | `langchain` 1.4.2 and the `langchain-core` / `-community` / `-ollama` / `-chroma` / `-text-splitters` packages |
| Vector database | `chromadb` 1.5.9 |
| Local inference | `ollama` 0.6.2 |
| Document loaders | `pypdf` 6.19.0, `python-pptx` 1.0.2, `python-docx` 1.2.0 |
| Internet citations | `ddgs` 9.16.0 (DuckDuckGo, no API key) |
| Configuration | `python-dotenv` 1.2.3 |
| Bonus: access control | `python-jose[cryptography]` 3.5.0, `passlib[bcrypt]` 1.7.4 |

No API key is required anywhere in the system. DuckDuckGo search needs none, and there
is no cloud model provider. This removes the entire key-management risk class described
in the threat model.

---

## 7. Step-by-step instructions for execution

### 7.1 Install

```bash
git clone https://github.com/MadhavKrishna06/CIPHER.git
cd CIPHER
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e .
```

Create the configuration file:

```bash
copy .env.example .env          # cp on macOS / Linux
```

The defaults in `.env.example` are the values used for all Round 2 measurements. Edit
only if your Ollama host or model names differ.

### 7.2 Add the course documents

```
data/raw/slides/      Lecture 01.pdf ... Lecture 11.pdf
data/raw/textbooks/   Kurose Computer Networking.pdf
                      Stallings NSE.pdf
```

Both directories are gitignored. See section 4 for why.

### 7.3 Build the knowledge base

```bash
python -m cipher.ingest
```

Every file is SHA-256 hashed, the digest is recorded in `data/manifest.json`, then the
file is chunked, embedded locally and stored in ChromaDB. Expect several minutes for the
two textbooks on first run; embedding is the slow step.

Other ingestion modes:

```bash
python -m cipher.ingest --verify          # integrity report only, writes nothing
python -m cipher.ingest --accept-changes  # re-ingest files whose hash changed
python -m cipher.ingest --reset           # wipe the vector database and start over
```

Confirm the index was built:

```bash
python -m cipher.ingest --verify
```

Every file should report `VERIFIED`.

### 7.4 Start Ollama

```bash
ollama serve
```

If the Ollama desktop application is already running, it is already serving and this
step can be skipped.

### 7.5 Start the backend API

In its own terminal, with the virtual environment active:

```bash
uvicorn cipher.api:app --host 127.0.0.1 --port 8000
```

`--host 127.0.0.1` is required, not cosmetic. It is what keeps the API unreachable from
other machines on the network.

Check it:

```bash
curl http://127.0.0.1:8000/health
```

A healthy response reports `"ollama": true`, both models present, and a non-zero
`"chunks"` count.

### 7.6 Start the web interface

In a third terminal, with the virtual environment active:

```bash
streamlit run ui/app.py
```

Open <http://localhost:8501>. Binding and telemetry are already set in
`.streamlit/config.toml`, so no command-line flags are needed.

### 7.7 Use it

**Tutor tab.** Type a course question and submit. The answer appears with a citation per
claim. Expand *Retrieval trace: prompt to model input* to see which passages were
retrieved, their distances, and the exact text sent to the local model.

**Quiz tab.** Choose *random* or *topic*, pick the question formats and a count, and
generate. Answer each question and submit for grading. Feedback shows the reference
answer, its citation, the embedding similarity score and the judge verdict.

**Internet references.** The *Use web references* toggle in the sidebar controls whether
DuckDuckGo is consulted. Turn it off to run fully offline; this is the setting used for
the local-only packet capture.

### 7.8 Quick retrieval test without the UI

For debugging retrieval only:

```bash
python scripts/query_test.py "What are the goals of network security?"
```

---

## 8. Documentation

| Document | Contents |
|---|---|
| [`security/threat_model.md`](security/threat_model.md) | Attack surface diagram, trust boundaries, asset table, the three mandatory risks with mitigations, verification plan, and the Round 2 findings against our own design |
| [`security/adversarial_log.md`](security/adversarial_log.md) | Prompt-injection and jailbreak attempts A1–A4: the prompt, the agent's response, the verdict and the fix made afterwards |
| [`security/integrity_check.md`](security/integrity_check.md) | How hash verification works, and why it guards against a poisoned knowledge base |
| [`security/captures/procedure.md`](security/captures/procedure.md) | The capture procedure, reproducible on any member's machine |
| [`security/captures/member_runbook.md`](security/captures/member_runbook.md) | Per-member runbook for the five-prompt capture |
| [`security/captures/prompt_sets.md`](security/captures/prompt_sets.md) | The seven prompt sets and their assignment to members |

Interactive API documentation is served by FastAPI at
<http://127.0.0.1:8000/docs> while the backend is running.

Code-level documentation lives in module docstrings. `src/cipher/api.py` and
`ui/app.py` open with the security properties each file is responsible for.

---

## 9. Security verification

Four verification tasks were completed and are documented in [`security/`](security/):

1. **Threat model** — attack surface, trust boundaries, and mitigations for prompt injection, vector-database exposure and secrets handling.
2. **Network traffic verification** — Wireshark captures in both the local-only and internet-assisted scenarios, by all seven members independently. Combined 38,755 packets. In every capture, `ip.addr != 127.0.0.1` returned 0 packets and `dns || tls.handshake.type == 1` returned 0 packets during local-only operation.
3. **Adversarial testing** — four injection and jailbreak attempts logged with responses and fixes.
4. **Knowledge base integrity** — SHA-256 manifest over all 13 documents, with changed files refused until explicitly approved.

The verification also found three real weaknesses in our own design, which are recorded
in `security/threat_model.md` §6 and fixed: the search backend reaching hosts beyond
DuckDuckGo with the query in the URL, the Streamlit server listening on all interfaces,
and default telemetry left enabled.

---

## 10. Repository layout

```
src/cipher/          application package
  api.py             FastAPI backend, loopback only
  qa_agent.py        Q&A Tutor Agent
  quiz_agent.py      Quiz Agent: generation, verification, grading
  retriever.py       ChromaDB query and the single citation builder
  guard.py           input guard, runs before any inference
  ingest.py          chunk, embed and store pipeline
  integrity.py       SHA-256 manifest and verification
  loaders.py         PDF / PPTX / DOCX / text extraction
  textfilter.py      header and boilerplate filtering
  similarity.py      embedding similarity for quiz grading
  web_search.py      DuckDuckGo lookup, query text only
  llm.py             Ollama call with optional JSON Schema
  config.py          .env-driven settings
ui/app.py            Streamlit web interface
scripts/             helper and debugging scripts
security/            threat model, adversarial log, integrity notes, captures
data/raw/            course documents (local only, gitignored)
data/chroma/         vector database (local only, gitignored)
data/manifest.json   integrity manifest (committed)
docs/                reports and slides (gitignored)
.streamlit/          UI binding and telemetry configuration
```

---

## 11. Submission contents

Round 2 deliverables and where each comes from in this repository:

| Deliverable | Contents |
|---|---|
| `1_prototype.zip` | `src/`, `ui/`, `scripts/`, `.streamlit/`, `requirements.txt`, `pyproject.toml`, `.env.example`, `data/manifest.json`, the per-member `student_name.docx` and `student_name.pcap` files, and the prototype README |
| `1_round2.pptx` | Round 2 slides, built to the format in the assignment |
| `1_security.zip` | `security/captures/local_only_loopback.pcap`, `local_only_external.pcap`, `internet_assisted.pcap`, the traffic write-up, `security/adversarial_log.md`, `security/integrity_check.md`, `security/threat_model.md` |
| GitHub repository link | This repository |

`data/raw/` and `data/chroma/` are excluded from the repository for the copyright reason
given in section 4. Rebuild the index with section 7.3.

---

## 12. Team

Seven members. The contribution table is maintained in the Round 1 group report; every
member is a contributor on this repository and completed an independent traffic capture,
documented in `security/captures/` and in their own write-up.
