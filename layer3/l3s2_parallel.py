"""Layer 3 Step 2a: the same orchestrator job as l3s1_orchestrator.py, but the six subagents run AT THE SAME TIME
(parallel_tools=True), each in its own thread with its own `messages`. Compare its numbers with the two baselines.

Run from the project root:   .venv/bin/python -m layer3.l3s2_parallel
"""
import time

import client as client_module
from client import make_client
from layer3.l3s1_orchestrator import QUESTION
from loop import run_agent
from measure import MeasuringClient
from scripts.make_workload import FACTS
from tools import DELEGATE

def run(question, label):
    measured = MeasuringClient(make_client())
    client_module.make_client = lambda: measured  # so each subagent's calls are counted (see l3s1_orchestrator.py)
    messages = [{"role": "user", "content": question}]
    started = time.time()
    answer = run_agent(measured, messages, [DELEGATE], max_loops=30, max_tokens=2000, parallel_tools=True)
    wall_clock = time.time() - started
    print("\n=== " + label + " ===")
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
    print(f"  wall-clock: {wall_clock:.1f}s   (baseline 21.9s; one at a time 57.2s)")
    print(f"  time the model calls added up to: {measured.summary()['model_seconds']:.1f}s   (if this is much more than the wall-clock, calls overlapped)")


if __name__ == "__main__":
    run(QUESTION, "subagents in parallel")
