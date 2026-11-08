# Your Wireshark Capture: One-Page Runbook

CS5342 group project, Round 2. Every group member submits their own packet
capture and their own short write-up. This takes about 15 minutes at the
laptop and about 20 minutes of writing afterwards, which you can do anywhere.

You do not need to install anything. Everything runs on the project laptop.

## What you are submitting

Two files, named with your own name:

```
<your_name>.pcap     the packet capture you record
<your_name>.docx     your explanation of what it shows
```

## What the system is

CIPHER is a tutor and quiz bot that answers network security questions from
the course slides and textbooks. It runs entirely on this one machine: nothing
is sent to an external service unless the "Internet citation lookup" switch in
the sidebar is turned on.

That is the thing your capture is evidence for.

Three parts talk to each other over the loopback interface, `127.0.0.1`:

```
Streamlit page  :8501  ->  FastAPI backend  :8000  ->  Ollama model  :11434
```

Because it is all loopback, a normal Wi-Fi capture shows nothing from the
application. You capture on the loopback adapter instead.

## Step 1: get your prompt set

Ask the project owner which numbered set in `prompt_sets.md` is yours. Each
member has a different set of five prompts so that no two captures are alike.
Have it open before you start.

## Step 2: check the app is running

The three terminals should already be running. Open `http://localhost:8501`
and check the sidebar reads something like:

```
Ollama up - 2686 chunks
```

Ask one throwaway question first. The first question after startup loads the
model and takes about a minute; every later one takes a few seconds. You do
not want that minute inside your capture.

## Step 3: start the capture

Set the sidebar toggle "Internet citation lookup" to **off**.

In a new PowerShell window, replacing `<your_name>`:

```powershell
D:\Wireshark\dumpcap.exe -i "\Device\NPF_Loopback" -w D:\dev\CIPHER\security\captures\<your_name>.pcap -f "tcp port 8501 or tcp port 8000 or tcp port 11434"
```

Leave it running. Write down the time you started.

## Step 4: run your five prompts

For each of your five prompts:

1. Type it into the Tutor tab and press Ask.
2. Wait for the answer.
3. Expand **Retrieval trace: prompt to model input** underneath the answer.
4. Screenshot the whole window, with the trace panel open.

The trace panel is the important part. It shows your prompt, which course
passages were retrieved with their distance scores, and the exact text that was
sent to the model. That is the mapping the assignment asks for, visible in one
screenshot.

Name your screenshots `<your_name>_prompt1.png` through `prompt5.png`.

## Step 5: stop the capture

Press Ctrl+C in the dumpcap window. Write down the time you stopped.

Check the file exists and is not empty:

```powershell
Get-ChildItem D:\dev\CIPHER\security\captures\<your_name>.pcap
```

A few hundred kilobytes is normal. If it is near zero, the capture did not
attach to the loopback adapter and needs redoing.

## Step 6: look at your own capture

Open your `.pcap` in Wireshark: `D:\Wireshark\Wireshark.exe`.

Type this into the display filter bar at the top and press Enter:

```
tcp.port == 11434
```

Those are the requests from the backend to the local model. Right-click any
packet, choose Follow, then HTTP Stream. You will see the full prompt that was
sent, including the course passages that were retrieved for you.

Three things to notice, because you will write about them:

1. The prompt and the course text are readable. There is no encryption on
   loopback. This is fine, and worth saying out loud rather than hiding: the
   traffic never reaches a network interface, so there is no network attacker
   who could see it. It does mean another program running as the same Windows
   user could read it.
2. The address is `127.0.0.1` on both sides of every conversation. Nothing has
   a public address.
3. Your five prompts appear in the capture in the order you asked them, and
   each one is followed by a request to the model containing the retrieved
   passages. That is the prompt-to-trace link.

Now try this filter:

```
dns || tls.handshake.type == 1
```

You should get nothing at all. No name lookups, no TLS handshakes. With the
internet switch off, the system made no attempt to contact anything.

## Step 7: write it up

Use `writeup_template.md`. It has the section headings, the table to fill in,
and a worked example from the project owner's own capture so you can see the
level of detail expected.

Write it in your own words. You will be in the room for the Round 3 demo and
may be asked about your own capture.

Save as `<your_name>.docx`.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Sidebar says the API is unreachable | the uvicorn terminal is not running |
| Sidebar says Ollama is not running | the `ollama serve` terminal is not running |
| `.pcap` is near zero bytes | wrong interface; re-run `dumpcap.exe -D` and find the loopback line |
| dumpcap says permission denied | run PowerShell as administrator |
| First question takes a minute | normal, the model is loading; ask a throwaway one before capturing |
| Answer says the materials do not cover it | normal and correct behaviour; keep it, it is a good thing to show |
