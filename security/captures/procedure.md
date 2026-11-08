# Network Traffic Verification Procedure

CS5342 CIPHER, Round 2. This is the group-level procedure for the two required
capture scenarios. Run it once, on the project laptop, before any member does
their individual capture, so that every individual capture follows a method
already known to work.

Per-member instructions are in `member_runbook.md`.

## Why this is harder than it looks

CIPHER runs entirely on one machine. The Streamlit page talks to the FastAPI
backend, and the backend talks to Ollama. All three conversations use the
loopback interface, `127.0.0.1`. They never reach a network card.

A capture on Wi-Fi or Ethernet therefore shows nothing from the application,
which is easy to mistake for a failed capture. Loopback traffic on Windows is
only visible through the Npcap loopback adapter.

That same fact is what makes the local-only claim provable. The evidence has
two halves, and they live on two different interfaces:

| Claim | Interface | What the evidence looks like |
|---|---|---|
| The system really ran | loopback | traffic on ports 8501, 8000, 11434 |
| Nothing left the machine | Wi-Fi | absence of any application traffic |

Capture both. One alone proves nothing.

## Interfaces on this machine

Confirm the numbering before each session, because it changes when adapters
come and go:

```powershell
D:\Wireshark\dumpcap.exe -D
```

As of 2026-10-25 on the project laptop:

```
4. \Device\NPF_{FD19DED4-6776-4FCB-A279-CA69FC7A4334} (Wi-Fi)
8. \Device\NPF_Loopback (Adapter for loopback traffic capture)
```

## Before capturing

Start the three processes, each in its own terminal:

```powershell
ollama serve
```

```powershell
cd D:\dev\CIPHER; .venv\Scripts\Activate.ps1; uvicorn cipher.api:app --host 127.0.0.1 --port 8000
```

```powershell
cd D:\dev\CIPHER; .venv\Scripts\Activate.ps1; streamlit run ui/app.py
```

Then open `http://localhost:8501` and ask one throwaway question. This loads the
model into memory. Without it, the first captured request includes a 60-second
model load and the capture is mostly idle time.

## Scenario 1: local-only inference

Goal: confirm no course document content leaves the machine.

Set the sidebar toggle "Internet citation lookup" to off. The toggle is enforced
in the backend, not the browser, so turning it off genuinely prevents the lookup
rather than only hiding the results.

Start both captures:

```powershell
D:\Wireshark\dumpcap.exe -i "\Device\NPF_Loopback" -w security\captures\local_only_loopback.pcap -f "tcp port 8501 or tcp port 8000 or tcp port 11434"
```

```powershell
D:\Wireshark\dumpcap.exe -i "\Device\NPF_{FD19DED4-6776-4FCB-A279-CA69FC7A4334}" -w security\captures\local_only_external.pcap
```

Note the wall-clock time you started. Then, in the UI:

1. Ask three questions in the Tutor tab.
2. Generate a quiz and answer two questions, one right and one wrong.
3. Expand the Retrieval trace panel on one answer and screenshot it.

Stop both captures with Ctrl+C. Record the stop time.

While the processes are still running, capture the corroborating evidence that
the backend holds no external connections:

```powershell
Get-Process python | ForEach-Object { Get-NetTCPConnection -OwningProcess $_.Id -ErrorAction SilentlyContinue } | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State
```

Every row should show `127.0.0.1` on both sides. Screenshot it.

### Reading the local-only captures

Open `local_only_loopback.pcap`. Useful display filters:

```
tcp.port == 8501 || tcp.port == 8000 || tcp.port == 11434
http.request.uri contains "/api/"
http.request.uri contains "/ask"
```

Follow the HTTP stream of a POST to `127.0.0.1:11434/api/chat`. You will see the
full prompt, including the retrieved course passages, in cleartext.

State that plainly in the write-up. It is not a flaw, and pretending otherwise
would be worse than reporting it. Loopback traffic never reaches a network
interface, so there is no network attacker position to defend against. What it
does mean is that any process already running as this user could read the
prompts. That is a local privilege-separation question rather than a network
one, and it belongs in the threat model under data exposure.

Now open `local_only_external.pcap`, the Wi-Fi capture. There will be background
operating-system traffic: Windows Update, NTP, mDNS, name resolution. That is
the machine, not CIPHER. Show that none of it belongs to the application:

```
dns
tls.handshake.type == 1
```

Within your recorded start and stop times there should be no DNS query for any
search engine and no TLS ClientHello carrying a search-engine SNI. Combined with
the `Get-NetTCPConnection` output showing only loopback endpoints, that is the
proof.

## Scenario 2: internet-assisted citation lookup

Goal: identify which external service is contacted and what is sent.

Set the sidebar toggle "Internet citation lookup" to on.

```powershell
D:\Wireshark\dumpcap.exe -i "\Device\NPF_{FD19DED4-6776-4FCB-A279-CA69FC7A4334}" -w security\captures\internet_assisted.pcap
```

Ask a question the course materials cover thinly, so the web lookup fires. The
backend reaches for the internet when retrieval is weak or the model reports
only partial coverage. Good candidates:

- What is post-quantum cryptography?
- What is a SIM swap attack?

Also answer one quiz question wrong, which attaches further-reading links.

Stop the capture.

### Reading the internet-assisted capture

```
dns.qry.name contains "duckduckgo"
tls.handshake.extensions_server_name contains "duckduckgo"
```

Expect exactly one destination: `html.duckduckgo.com`. Take the resolved address
from the DNS response and follow the conversation:

```
ip.addr == <address from the DNS answer>
```

Four things to write up, in this order:

1. The destination is visible in the clear. The DNS query name and the TLS
   ClientHello `server_name` extension both carry `html.duckduckgo.com` as
   plaintext, before any encryption is negotiated. An observer on the network
   learns that this machine used a search engine, and when.
2. The query is not visible. Follow the TLS stream. After the handshake the
   payload is ciphertext. The question text is inside the request body and
   cannot be read from the capture.
3. Only the question is sent. This is a code property, not something the capture
   can show on its own: `search()` in `src/cipher/web_search.py` receives the
   question string and nothing else. Retrieved passages, the generated answer,
   the reference answer and the student's own quiz answer are never passed to it.
   Cite the function in the write-up.
4. One host, pinned deliberately. See the finding below.

## Finding: the search backend was not what the threat model claimed

The Round 1 threat model and README both stated that internet lookups go to
DuckDuckGo. Traffic analysis during preparation for this capture showed
otherwise. The `ddgs` library defaults to `backend="auto"`, which selects from
eighteen engines at runtime. A single query for `kerberos replay attack`
contacted three hosts:

```
https://grokipedia.com/api/typeahead?query=kerberos+replay+attack&limit=1
https://en.wikipedia.org/w/api.php?...&search=kerberos%20replay%20attack
https://html.duckduckgo.com/html/
```

Two of the three carried the query text in the URL query string, where it is the
most likely thing to end up in a server access log.

Three problems. The documented privacy claim was false. The destination was
non-deterministic, so no two members would have captured the same host. And the
set of third parties receiving course-related queries was unbounded.

Fix: `src/cipher/web_search.py` now pins `backend="duckduckgo"`. Verified after
the change, a query contacts `html.duckduckgo.com` and nothing else.

This is worth presenting as a result rather than as a correction. The traffic
verification task found a real mismatch between the system's documented
behaviour and its actual behaviour, which is what the task is for.

## Output files

Group-level, submitted in `groupno_security.zip`:

```
local_only_loopback.pcap     the system working, loopback only
local_only_external.pcap     the absence of external traffic
internet_assisted.pcap       the DuckDuckGo lookup
traffic_writeup.docx         what each capture shows
```

Per member, submitted alongside:

```
<student_name>.pcap
<student_name>.docx
```

Captures live in `security/captures/`, which is gitignored. They are submitted
through RaiderCanvas, not committed.
