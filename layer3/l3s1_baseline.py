"""Layer 3 Step 1b: the baseline. ONE agent does the whole workload by itself: read six long documents (in pieces)
and report the final answer in each. We record passes, tokens and wall-clock time, so that multi-agent has a number to beat.

Run from the project root:   .venv/bin/python -m layer3.l3s1_baseline
"""
import time

from client import make_client
from loop import run_agent
from measure import MeasuringClient
from scripts.make_workload import FACTS
from tools import READ_FILE, LIST_FILES

FILES = [f"data/workload/report_{n}.txt" for n in FACTS]
QUESTION = ("For each of these documents, find the final answer stated in it and report one line per document, "
            "in the form 'report_N.txt: <answer>'. The documents are: " + ", ".join(FILES) + ".")

if __name__ == "__main__":
    measured = MeasuringClient(make_client())
    messages = [{"role": "user", "content": QUESTION}]
    started = time.time()
    # max_loops is raised from the default 10: reading six documents in pieces can take many passes
    answer = run_agent(measured, messages, [READ_FILE, LIST_FILES], max_loops=60, max_tokens=2000)
    wall_clock = time.time() - started

    print("\n--- the agent's answer ---")
    print(answer)
    print("\n--- checking it against the answer key ---")
    for number, (expected, _) in FACTS.items():
        line = next((l for l in answer.splitlines() if f"report_{number}" in l), "")
        print(f"  report_{number}.txt expected {expected:>2}:", "OK" if str(expected) in line else "WRONG or missing", "|", line.strip()[:60])
    print("\n--- what it cost ---")
    summary = measured.summary()
    print("  passes (model calls):", summary["passes"])
    print("  input tokens:", summary["input_tokens"], "| output tokens:", summary["output_tokens"])
    print(f"  wall-clock: {wall_clock:.1f}s (of which waiting on the model: {summary['model_seconds']:.1f}s)")
    print("  input tokens on each pass:", [c["input_tokens"] for c in measured.calls])
