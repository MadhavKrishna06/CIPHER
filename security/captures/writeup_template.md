# Capture Write-Up Template

Copy everything below the line into Word, replace the bracketed parts, and save
as `<your_name>.docx`.

The assignment asks for five prompts, a screenshot of each, a detailed
explanation of the captured data, and a mapping between each prompt and the
data that was sent to the model. The structure below covers all four.

Write in your own words. A paragraph that reads like the template with names
swapped is worth less than a short paragraph that shows you looked at your own
capture. You may be asked about this in the Round 3 demo.

Section 4 has a worked example. Use it as a guide to the level of detail, then
write your own from your own screenshots.

---

# CS5342 Network Security Project

## Network Traffic Capture and Analysis

**Name:** [your name]
**Group:** [group number]
**Date of capture:** [date]
**Capture file:** [your_name].pcap
**Capture started / stopped:** [HH:MM] / [HH:MM]

## 1. What was captured

Interface: `\Device\NPF_Loopback`, the Npcap loopback adapter.

Capture filter: `tcp port 8501 or tcp port 8000 or tcp port 11434`

Internet citation lookup: **off** for the whole session.

CIPHER runs as three local processes. The Streamlit interface on port 8501
sends requests to the FastAPI backend on port 8000, and the backend sends
prompts to the Ollama model server on port 11434. All three use the loopback
address `127.0.0.1`, so none of this traffic reaches a network interface.

[One or two sentences in your own words on why the loopback adapter is needed,
and what a capture on Wi-Fi would have shown instead.]

## 2. Prompts used

| # | Prompt | Result |
|---|---|---|
| 1 | [prompt] | [grounded answer with N citations / not covered / partial] |
| 2 | [prompt] | [...] |
| 3 | [prompt] | [...] |
| 4 | [prompt] | [...] |
| 5 | Quiz on [topic] | [score, and whether feedback was cited] |

## 3. Prompt to model-input mapping

The assignment asks for a mapping between the prompt entered at step 1 of the
system workflow and the trace data sent to the local model at step 4. The
retrieval trace panel in the interface shows both for each question.

| # | Prompt | Passages retrieved | Best distance | Passages cited in the answer | Packet number in the capture |
|---|---|---|---|---|---|
| 1 | [prompt] | [N] | [0.xxx] | [citations] | [frame #] |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

To find the packet number: display filter `tcp.port == 11434`, then look for the
`POST /api/chat` whose body contains your question.

## 4. Detailed analysis

### 4.1 What a request looks like on the wire

[Screenshot: Wireshark with filter `tcp.port == 11434`, one packet selected.]

**Worked example.** With the filter `tcp.port == 11434` applied, my capture
shows eleven `POST /api/chat` requests to `127.0.0.1:11434`, one per question
plus the quiz generation and grading calls. Following the HTTP stream of frame
[N] shows the request body for my first prompt. It contains a system message
holding the eight tutor rules, then a user message with a `<context>` block of
five numbered passages taken from the course materials, then my question. The
passages are numbered rather than named: the model is given `[1]` through `[5]`
and never sees a file name or page number, so it cannot invent a source. The
interface resolves those numbers back to real citations after the answer comes
back.

The response is a JSON object containing the generated answer with citation
markers still in numeric form.

[Now write your own version of the above from your own capture. State your
frame number, how many requests you see, and what the body contained.]

### 4.2 Everything is plaintext, and why that is acceptable here

The HTTP traffic between the backend and the model server is not encrypted. The
prompt, the retrieved course passages and the generated answer are all readable
in the capture.

[Your own words on why this is or is not a problem. Points to consider:
loopback traffic never reaches a network interface, so there is no network
attacker position; but any process running as the same Windows user could read
it; and whether you think that is an acceptable trade-off for a local-only
system.]

### 4.3 Confirming nothing left the machine

[Screenshot: display filter `dns || tls.handshake.type == 1`, showing an empty
result.]

With the internet switch off, this filter returns no packets. The system made
no name lookups and opened no TLS sessions for the whole session.

[One or two sentences on why the absence of packets is the evidence here, and
what you would have expected to see had the switch been on.]

### 4.4 An ungrounded question

[Screenshot of the answer to prompt 4.]

Prompt 4 asked about [topic], which the course materials do not cover.

[What the system did. Did it refuse, answer partially, or invent something? A
refusal is the correct behaviour and the strongest evidence that answers come
from the course corpus rather than from the model's own training data. Say what
you saw.]

### 4.5 Quiz grading

[Screenshot of one graded answer, ideally an open-ended one.]

[What the feedback contained: the score, the course citation, and for an
open-ended question both the judge's score and the embedding similarity to the
reference answer. Say whether the two agreed, and what it means if they did
not.]

## 5. Observations and issues

[Two to four bullet points of your own. Anything that surprised you, anything
that looked wrong, anything you could not explain. Real observations are worth
more than filler. Examples of the kind of thing that counts: the first request
after startup taking much longer than the rest; the same passage appearing in
two different answers; a citation that looked wrong to you.]

## 6. Conclusion

[Three or four sentences. What the capture demonstrates about where the data
went, and whether the local-only claim held up in your session.]
