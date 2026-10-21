"""Layer 3 Step 1c: an orchestrator hands each document to a subagent with `delegate`, ONE AFTER ANOTHER. Same workload and
the same numbers as the baseline (l3s1_baseline.py), so the two can be compared. Nothing runs at the same time yet:
this is the control that shows what isolation costs by itself. Step 2 adds parallelism.

Run from the project root:   .venv/bin/python -m layer3.l3s1_orchestrator
"""
import time

import client as client_module          # imported by name so delegate's own make_client() can be pointed at the measuring client
from client import make_client
from loop import run_agent
from measure import MeasuringClient
from scripts.make_workload import FACTS
from tools import DELEGATE

FILES = [f"data/workload/report_{n}.txt" for n in FACTS]
QUESTION = ("For each of these documents, find the final answer stated in it and report one line per document, "
            "in the form 'report_N.txt: <answer>'. You cannot read files yourself: use the delegate tool, one delegate "
            "call per document. A subagent sees only the task you give it, so name the file path and ask it to reply with "
            "just the final answer. The documents are: " + ", ".join(FILES) + ".")

if __name__ == "__main__":
    measured = MeasuringClient(make_client())
    # delegate() builds its own client for each subagent; point it at the measuring client so the subagents' calls
    # are counted too (the same workaround the delegate tests use: the loop can't hand delegate a client)
    client_module.make_client = lambda: measured
    messages = [{"role": "user", "content": QUESTION}]
    started = time.time()
    answer = run_agent(measured, messages, [DELEGATE], max_loops=30, max_tokens=2000)
    wall_clock = time.time() - started

    print("\n--- the orchestrator's answer ---")
    print(answer)
    print("\n--- checking it against the answer key ---")
    for number, (expected, _) in FACTS.items():
        line = next((l for l in answer.splitlines() if f"report_{number}" in l), "")
        print(f"  report_{number}.txt expected {expected:>2}:", "OK" if str(expected) in line else "WRONG or missing", "|", line.strip()[:60])

    orchestrator_calls = [c for c in measured.calls if "delegate" in c["tools"]]
    subagent_calls = [c for c in measured.calls if "delegate" not in c["tools"]]
    print("\n--- what it cost ---")
    for label, calls in (("orchestrator", orchestrator_calls), ("all subagents", subagent_calls), ("TOTAL", measured.calls)):
        s = measured.summary(calls)
        print(f"  {label:<14} passes {s['passes']:>3} | input tokens {s['input_tokens']:>7} | output tokens {s['output_tokens']:>5}")
    print(f"  wall-clock: {wall_clock:.1f}s")
    print("  orchestrator input tokens on each pass:", [c["input_tokens"] for c in orchestrator_calls])
    print("  largest single subagent call, in input tokens:", max((c["input_tokens"] for c in subagent_calls), default=0))
