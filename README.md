# TraceAssist

TraceAssist answers questions about a Linux kernel trace in plain language: *"What does this
trace do?"*, *"Why is this program slow? Give me the thread."*, *"What are the longest
system calls of worker-2?"*.

It runs inside the [Eclipse Trace Compass](https://eclipse.dev/tracecompass/) Trace Server.
Trace Compass's analyses work out the facts from the trace: thread states, who woke whom, the
critical path, system call latencies, CPU use. An LLM (OpenAI) then writes the answer from
those facts, with their numbers.

This repository holds everything needed to try it on three traces of the same program, recorded
for 2, 10 and 30 minutes:

- `traceassist-server.jar`, which installs TraceAssist in a Trace Server and starts it;
- a Trace Compass Trace Server to run it in (Linux, x86-64);
- the traces;
- `ask.py`, a small terminal client.

## What you need

| | |
|---|---|
| **Operating system** | Linux on x86-64. For macOS or Windows, see [Other platforms](#other-platforms). |
| **An OpenAI API key** | Your own. TraceAssist asks for it when it starts, and never saves it. Each answer uses roughly 10–20k input tokens on your OpenAI account. |
| **Memory** | 8 GB of RAM or more. The server used up to 4.6 GB on the 30-minute trace. |
| **Disk** | About 4 GB for the downloads, unpacked. The analysis files Trace Compass writes need another 0.6 GB (2-minute trace), 2.8 GB (10-minute) and 8.3 GB (30-minute). |
| **Java** | Nothing to install: the Trace Server includes Java 21, which can also run the jar. Any Java 11 or later works too. |
| **Python 3.8+** | Optional, for `ask.py`. `curl` works too. |
| **Internet access** | To `api.openai.com`. |

## 1. Download

The large files are attached to the [v0.1.0 release](https://github.com/sneh2001patel/traceassist/releases/tag/v0.1.0):

| File | Size | What it is |
|---|---|---|
| `traceassist-server.jar` | 0.3 MB | Installs TraceAssist in the Trace Server and starts it. |
| `trace-compass-server-0.18.0-linux-x86_64.tar.gz` | 102 MB | Eclipse Trace Compass Trace Server 0.18.0 for Linux x86-64, the version TraceAssist was tested with. |
| `batch-server-2m-20261013-190630.tar.xz` | 24 MB | The 2-minute trace (140 MB unpacked). |
| `batch-server-10m-20261013-194601.tar.xz` | 118 MB | The 10-minute trace (684 MB unpacked). |
| `batch-server-30m-20261013-191113.tar.xz` | 351 MB | The 30-minute trace (2.0 GB unpacked). |
| `SHA256SUMS` | | Checksums of the files above. |

```bash
mkdir traceassist && cd traceassist
URL=https://github.com/sneh2001patel/traceassist/releases/download/v0.1.0
for f in traceassist-server.jar trace-compass-server-0.18.0-linux-x86_64.tar.gz \
         batch-server-2m-20261013-190630.tar.xz SHA256SUMS; do
    curl -fLO "$URL/$f"
done
# optional, larger: batch-server-10m-20261013-194601.tar.xz  batch-server-30m-20261013-191113.tar.xz
curl -fLO https://raw.githubusercontent.com/sneh2001patel/traceassist/main/ask.py

sha256sum -c --ignore-missing SHA256SUMS          # each file should say OK
tar xzf trace-compass-server-0.18.0-linux-x86_64.tar.gz     # -> trace-compass-server/
for f in batch-server-*.tar.xz; do tar xJf "$f"; done        # -> batch-server-*/
```

## 2. Start TraceAssist

```bash
JAVA=$(ls -d trace-compass-server/plugins/org.eclipse.justj.openjdk.hotspot.jre.*.linux.x86_64_*/jre/bin/java)
$JAVA -jar traceassist-server.jar start --server trace-compass-server
```

(Or use `java -jar …` if you have Java 11 or later installed.)

1. It installs TraceAssist in the server. That happens the first time only; see
   [What the jar changes](#what-the-jar-changes).
2. It asks for your **OpenAI API key** without showing what you type, and checks it with OpenAI.
3. It starts the server. When you see

   ```
   Ready. In VS Code, point the Trace Viewer at http://localhost:8081 and TraceAssist at http://127.0.0.1:8092.
   ```

   TraceAssist is answering on `http://127.0.0.1:8092`.

Leave it running, and ask questions from another terminal. Ctrl+C stops the server.

To start without the prompt, either set the key in the environment (`OPENAI_API_KEY=sk-... $JAVA -jar
traceassist-server.jar start ...`) or pass `--api-key-file <file>`, a file whose first line is the key.

## 3. Ask questions

With `ask.py`, follow-up questions continue the conversation:

```bash
python3 ask.py batch-server-2m-20261013-190630/trace/kernel
you> What does this trace do?
you> Which thread is the bottleneck of batch_server?
you> Why is it slow?
```

Ask one question and exit:

```bash
python3 ask.py batch-server-10m-20261013-194601/trace/kernel -q "Why is this trace slow? Give me the thread."
```

With `curl` only:

```bash
curl -s http://127.0.0.1:8092/ask -H 'Content-Type: application/json' -d '{
  "trace_path": "'"$PWD"'/batch-server-2m-20261013-190630/trace/kernel",
  "question": "Which thread is the bottleneck of batch_server?"
}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["answer"])'
```

The `trace_path` must be the absolute path of the folder that holds the trace's `metadata`
file (`…/trace/kernel`).

### Questions to try

- *What does this trace do?*
- *Why is this trace slow? Give me the thread.*
- *Which thread is the bottleneck of batch_server?*
- *What is worker-2 waiting on?*
- *What are the longest system calls of worker-2?*
- *How long does the flusher hold the lock, and how much faster would it be without the sleep?*
- *Which thread waited longest to be scheduled?*
- *When was worker-2's CPU usage highest?*

### What the right answers are

Each trace records the same program, `batch_server`. A main thread hands work to four workers
in rounds and waits for all of them. **worker-2 is slow on purpose**: after its CPU work, it
waits on a lock that the `flusher` thread holds through a ~40 ms sleep (a simulated disk
write-back). So every round takes about 42 ms instead of about 20 ms. The chain is
batch_server ← worker-2 (futex) ← flusher (futex) ← timer.

The traces also record everything else that was running on the machine at the time (a 16-CPU
Linux desktop), as background activity.

| Trace | Length | batch_server PID | worker-2 TID | flusher TID | Rounds |
|---|---|---|---|---|---|
| `batch-server-2m-…` | 120 s | 159971 | 159975 | 159977 | 1,305 |
| `batch-server-10m-…` | 600 s | 200393 | 200412 | 200414 | 6,528 |
| `batch-server-30m-…` | 1,800 s | 164853 | 164857 | 164859 | 19,580 |

Each trace folder holds the program's own record of what happened:
- `ground_truth/ground_truth.json`: the configuration, the threads, and the expected answer;
- `ground_truth/rounds.csv`: every round's duration and lock wait;
- `program.log`.

### How long it takes

The first question on a trace is the slowest, because Trace Compass indexes and analyzes the
whole trace then. Later questions on the same trace reuse that work.

These times were measured on a 16-CPU machine with the default 4 GB of memory, without the
model's time. The model adds about 10–30 s per answer.

| Trace | First question | Later questions | Analysis files |
|---|---|---|---|
| 2 minutes | ~30 s | 2–11 s | 0.6 GB |
| 10 minutes | ~1¾ min | 7–60 s | 2.8 GB |
| 30 minutes | ~5½ min (~4 min after a server restart) | 30 s–5 min | 8.3 GB |

## Options

```
java -jar traceassist-server.jar start --server DIR [options]
java -jar traceassist-server.jar install --server DIR [--port N] [--force]
```

| Option | Default | |
|---|---|---|
| `--server DIR` | | The Trace Server folder (holds `tracecompass-server` and `plugins/`). |
| `--port N` | 8092 | TraceAssist's port. |
| `--tsp-port N` | 8081 | The Trace Server's own port (the Trace Server Protocol). |
| `--memory SIZE` | `4g` | The server's Java heap. |
| `--workspace DIR` | `~/.tracecompass-webapp` | Where the server keeps its data and the analysis files. |
| `--api-key-file FILE` | | Read the key from the first line of FILE. |
| `--ask-key` | | Ask for the key even if `OPENAI_API_KEY` is set. |
| `--skip-key-check` | | Don't check the key with OpenAI before starting. |
| `--force` | | Install even if the Trace Server's version wasn't tested. |

## What the jar changes

`install`, which `start` also runs, changes only the Trace Server folder:

1. **Adds the TraceAssist plug-in** (`plugins/org.eclipse.tracecompass.traceassist.server_0.1.0.jar`).
2. **Registers it** in `configuration/config.ini`, so it starts with the server, together with
   its port.
3. **Replaces one Trace Compass class** in `plugins/org.eclipse.tracecompass.analysis.graph.core_*.jar`:
   `AbstractCriticalPathModule`. The replacement adds a time window to the critical-path
   analysis, which TraceAssist uses to explain one slow round. It is checked against the
   server's version, 5.1.x.

The original files are kept in `trace-compass-server/backup-before-traceassist/`. To undo the
install, copy them back and delete the TraceAssist plug-in.

The analysis files are in `<workspace>/.tracecompass-temp/`, which is
`~/.tracecompass-webapp/.tracecompass-temp/` unless you used `--workspace`. Delete that folder
to free the disk space; the next question rebuilds what it needs.

## Your API key

- **Where it comes from:** `--api-key-file`, else the `OPENAI_API_KEY` environment variable,
  else a hidden prompt.
- **Before starting:** the jar sends the key to OpenAI once, to check it, and stops if OpenAI
  rejects it.
- **Where it goes:** to the server process only, through its environment. It is never written
  to a file. The jar shows only `sk-…` and its last 4 characters.
- **What uses it:** the server, for its calls to `api.openai.com`. TraceAssist uses the model
  for three small AI skills (which thread a question is about, checking candidate threads, and
  which views show the answer) and for writing the answer.

## Troubleshooting

| Problem | Fix |
|---|---|
| `port 8081 is already in use` | Another Trace Server is running. Stop it, or use `--tsp-port` and `--port`. |
| `OpenAI rejected the API key (HTTP 401)` | Check the key at platform.openai.com. |
| The first question takes minutes | That's normal for the 10- and 30-minute traces; see [How long it takes](#how-long-it-takes). |
| `OutOfMemoryError` in the server output | Start it with more memory, e.g. `--memory 8g`. |
| `is not an LTTng trace folder` (`ask.py`) | Pass the `…/trace/kernel` folder, or the run folder that contains it. |
| `TraceAssist is not reachable` | The server isn't running, or isn't ready yet: wait for `Ready.` |

## Other platforms

The included Trace Server is for Linux on x86-64. For macOS or Windows, download the Trace
Server for your system from
[download.eclipse.org/tracecompass.incubator/trace-server/rcp](https://download.eclipse.org/tracecompass.incubator/trace-server/rcp/),
then run the jar with `--server` pointing at it.

TraceAssist was tested only with version 0.18.0 on Linux. The jar refuses a Trace Server whose
critical-path library isn't version 5.1.x; `--force` installs anyway, at your own risk.

## Not included

- **The TMLL service** (an optional Python service at `127.0.0.1:8000`). It adds some system
  call evidence and reference documentation to the answers. Without it, TraceAssist answers
  from Trace Compass's analyses alone. All the questions above work.
- **A graphical viewer.** To look at the traces, open them in
  [Trace Compass](https://eclipse.dev/tracecompass/), or in the Trace Viewer for VS Code
  pointed at this server (`http://localhost:8081`).

## Licenses

The Trace Server archive is Eclipse Trace Compass, under the
[Eclipse Public License 2.0](https://www.eclipse.org/legal/epl-2.0/), and is unmodified. The jar
modifies the installed copy as described in [What the jar changes](#what-the-jar-changes). The
traces were recorded with LTTng by the author.
