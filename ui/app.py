"""CIPHER web interface. The assignment prohibits a command-line interface.

Run the API first, then this:
    uvicorn cipher.api:app --host 127.0.0.1 --port 8000
    streamlit run ui/app.py

This page holds no course data and no answer keys. It renders what the local API
returns, so every retrieval and every model call happens on the other side of
loopback. The retrieval trace panel exists for the Round 2 capture write-up, which
has to map each prompt to the data sent to the local model.
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

API = os.getenv("CIPHER_API", "http://127.0.0.1:8000")

# Quiz generation runs several model calls per question, so the client has to wait
# much longer than a normal web request.
TIMEOUT = httpx.Timeout(600.0, connect=5.0)

st.set_page_config(page_title="CIPHER", page_icon="🔐", layout="wide")


def api_get(path: str):
    return httpx.get(f"{API}{path}", timeout=TIMEOUT).json()


def api_post(path: str, payload: dict):
    r = httpx.post(f"{API}{path}", json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        try:
            raise RuntimeError(r.json().get("detail", r.text))
        except ValueError:
            raise RuntimeError(r.text)
    return r.json()


# --- sidebar: is the local stack actually up? --------------------------------

with st.sidebar:
    st.title("CIPHER")
    st.caption("Local network security tutor and quiz bot. CS5342.")

    try:
        health = api_get("/health")
    except Exception as exc:
        st.error(f"API unreachable at {API}\n\n{type(exc).__name__}")
        st.code("uvicorn cipher.api:app --host 127.0.0.1 --port 8000")
        st.stop()

    if not health["ollama"]:
        st.error("Ollama is not running.")
        st.code("ollama serve")
        st.caption(health.get("detail") or "")
        st.stop()

    st.success(f"Ollama up · {health['chunks']} chunks")
    st.caption(f"chat: {health['chat_model']}  ·  embed: {health['embed_model']}")
    if not health["chat_model_present"]:
        st.warning(f"Model {health['chat_model']} not pulled.")
    if not health["embed_model_present"]:
        st.warning(f"Model {health['embed_model']} not pulled.")

    st.divider()
    web = st.toggle(
        "Internet citation lookup",
        value=bool(health["web_search_default"]),
        help="Off means nothing leaves this machine. Turn it off for the local-only "
             "packet capture, on for the internet-assisted one.",
    )
    k = st.slider("Passages to retrieve", 1, 10, 5)
    show_trace = st.toggle("Show retrieval trace", value=True,
                           help="Needed for the Round 2 capture write-up.")

    st.divider()
    with st.expander("Knowledge base"):
        try:
            for name in api_get("/sources")["sources"]:
                st.caption(name)
        except Exception:
            st.caption("unavailable")


tutor_tab, quiz_tab = st.tabs(["Tutor", "Quiz"])


# --- tutor -------------------------------------------------------------------

with tutor_tab:
    st.subheader("Ask a course question")
    question = st.text_input("Question", placeholder="What is a replay attack?",
                             label_visibility="collapsed")
    if st.button("Ask", type="primary", disabled=not question.strip()):
        with st.spinner("Retrieving and answering locally..."):
            try:
                a = api_post("/ask", {"question": question, "k": k, "web": web})
            except Exception as exc:
                st.error(str(exc))
                a = None

        if a:
            if a["blocked_by"]:
                st.warning(a["answer"])
                st.caption(f"Blocked by input guard, pattern: `{a['blocked_by']}`")
            else:
                st.markdown(a["answer"])

                flags = []
                if not a["grounded"]:
                    flags.append("not covered by course material")
                if a["partial"]:
                    flags.append("course material only mentions the topic")
                if a["weak_match"]:
                    flags.append("weak retrieval match")
                if flags:
                    st.info(" · ".join(flags))

                if a["sources"]:
                    st.markdown("**Course sources**")
                    for c in a["sources"]:
                        st.caption(f"{c['citation']}  (distance {c['distance']:.3f})")

                if a["web_sources"]:
                    st.markdown("**Web references**")
                    for w in a["web_sources"]:
                        st.caption(f"[{w['title']}]({w['url']})")

            if show_trace and a.get("trace"):
                with st.expander("Retrieval trace: prompt to model input"):
                    st.caption("Step 1, the prompt sent to the system:")
                    st.code(a["question"], language="text")
                    st.caption(f"Retrieved {len(a['trace']['retrieved'])} passages:")
                    for i, c in enumerate(a["trace"]["retrieved"], start=1):
                        cited = any(s["citation"] == c["citation"] for s in a["sources"])
                        st.caption(f"[{i}] {c['citation']}  distance {c['distance']:.3f}"
                                   f"{'  (cited)' if cited else ''}")
                    st.caption("Step 4, the exact context given to the local model:")
                    st.code(a["trace"]["context"], language="text")


# --- quiz --------------------------------------------------------------------

with quiz_tab:
    st.subheader("Take a quiz")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        mode = st.radio("Mode", ["random", "topic"], horizontal=True)
    with col2:
        topic = st.text_input("Topic", placeholder="Kerberos",
                              disabled=(mode == "random"))
    with col3:
        count = st.number_input("Questions", 1, 10, 3)

    types = st.multiselect("Formats", ["mcq", "tf", "open"],
                           default=["mcq", "tf", "open"],
                           format_func=lambda t: {"mcq": "Multiple choice",
                                                  "tf": "True/False",
                                                  "open": "Open ended"}[t])

    if st.button("Generate quiz", type="primary", disabled=not types):
        with st.spinner("Writing and checking questions locally..."):
            try:
                quiz = api_post("/quiz/generate", {
                    "mode": mode,
                    "topic": topic or None,
                    "count": int(count),
                    "types": types,
                })
                st.session_state["quiz"] = quiz
                st.session_state["results"] = {}
            except Exception as exc:
                st.error(str(exc))

    quiz = st.session_state.get("quiz")
    if quiz:
        results = st.session_state.setdefault("results", {})

        for i, q in enumerate(quiz["questions"]):
            st.divider()
            label = {"mcq": "Multiple choice", "tf": "True/False", "open": "Open ended"}[q["qtype"]]
            st.markdown(f"**Q{i + 1}** · {label}")
            st.write(q["prompt"])

            key = f"ans_{quiz['quiz_id']}_{i}"
            if q["qtype"] == "mcq":
                options = q.get("options", {})
                choice = st.radio(
                    "Your answer", sorted(options),
                    format_func=lambda letter, o=options: f"{letter}. {o[letter]}",
                    key=key, index=None,
                )
                answer = choice or ""
            elif q["qtype"] == "tf":
                choice = st.radio("Your answer", ["true", "false"], key=key,
                                  index=None, horizontal=True)
                answer = choice or ""
            else:
                answer = st.text_area("Your answer", key=key, height=100)

            if st.button("Submit", key=f"go_{quiz['quiz_id']}_{i}"):
                with st.spinner("Grading..."):
                    try:
                        results[i] = api_post("/quiz/grade", {
                            "quiz_id": quiz["quiz_id"],
                            "index": i,
                            "answer": answer,
                            "web": web,
                        })
                    except Exception as exc:
                        st.error(str(exc))

            r = results.get(i)
            if r:
                if r["correct"]:
                    st.success(f"Correct · score {r['score']:.2f}")
                else:
                    st.error(f"Incorrect · score {r['score']:.2f}")
                st.write(r["feedback"])
                if r["similarity"] is not None:
                    st.caption(f"Embedding similarity to the reference answer: "
                               f"{r['similarity']:.3f} · judge verdict: {r['judge_verdict']}")
                st.caption(f"Reference answer: {r['reference']}")
                st.caption(f"Source: {r['citation']}")
                if r.get("web_sources"):
                    st.caption("Further reading:")
                    for w in r["web_sources"]:
                        st.caption(f"[{w['title']}]({w['url']})")
                if show_trace:
                    with st.expander("Passage this question came from"):
                        st.write(r["passage"])

        answered = [results[i]["score"] for i in results]
        if answered:
            st.divider()
            st.metric("Score so far",
                      f"{sum(answered):.2f} / {len(answered)}",
                      f"{sum(answered) / len(answered) * 100:.0f}%")
