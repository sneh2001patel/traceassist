#!/usr/bin/env python3
"""Ask TraceAssist questions about a trace, from the terminal.

    python3 ask.py <trace folder>                      # a conversation: type questions, Ctrl+D to quit
    python3 ask.py <trace folder> -q "What does this trace do?"

<trace folder> is the LTTng kernel trace folder (the one holding `metadata`), e.g.
batch-server-2m-20261013-190630/trace/kernel. Needs only Python 3.8+, no packages.
The Trace Server with TraceAssist must be running (java -jar traceassist-server.jar start ...).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def ask(server: str, trace: str, question: str, previous: dict, rag: bool) -> None:
    body = {"trace_path": trace, "question": question, "rag": rag, "stream": True}
    if previous.get("target"):
        body["previous_target"] = previous["target"]
    if previous.get("response_id"):
        body["previous_response_id"] = previous["response_id"]
    request = urllib.request.Request(
        f"{server}/ask", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    started = time.time()
    print("(analyzing the trace...)", end="", flush=True)
    try:
        with urllib.request.urlopen(request, timeout=3600) as response:
            for line in response:
                if not line.strip():
                    continue
                event = json.loads(line)
                kind = event.get("type")
                if kind == "plan":
                    print("\r" + " " * 30 + "\r", end="")
                    previous["target"] = event.get("target")
                    if event.get("why_section"):
                        print(event["why_section"] + "\n")
                elif kind == "delta":
                    print(event["text"], end="", flush=True)
                elif kind == "done":
                    previous["response_id"] = event.get("response_id") or previous.get("response_id")
                    print(f"\n\n({time.time() - started:.1f} s)")
                elif kind == "error":
                    print(f"\nerror: {event.get('error')}")
    except urllib.error.HTTPError as error:
        print(f"\nerror: HTTP {error.code}: {error.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as error:
        print(f"\nerror: TraceAssist is not reachable at {server} ({error.reason}). Is the server running?")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask TraceAssist about an LTTng kernel trace.")
    parser.add_argument("trace", help="the kernel trace folder (holds `metadata`)")
    parser.add_argument("-q", "--question", help="ask one question and exit")
    parser.add_argument("--server", default="http://127.0.0.1:8092", help="TraceAssist endpoint")
    parser.add_argument("--no-rag", action="store_true", help="no reference documentation")
    args = parser.parse_args()

    trace = Path(args.trace).expanduser().resolve()
    if not (trace / "metadata").is_file():
        found = sorted(p.parent for p in trace.rglob("metadata") if (p.parent / "index").is_dir())
        if len(found) == 1:
            trace = found[0]
        else:
            print(f"error: {trace} is not an LTTng trace folder (no `metadata` file)", file=sys.stderr)
            return 2
    previous: dict = {}
    if args.question:
        ask(args.server, str(trace), args.question, previous, not args.no_rag)
        return 0
    print(f"Trace: {trace}\nAsk a question (follow-ups continue the conversation; Ctrl+D to quit).\n")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question:
            print()
            ask(args.server, str(trace), question, previous, not args.no_rag)
            print()


if __name__ == "__main__":
    sys.exit(main())
