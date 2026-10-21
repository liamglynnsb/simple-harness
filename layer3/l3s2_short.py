"""Layer 3 Step 2: the parallel run once more, but now the orchestrator's task for each subagent is SHORT: the standing
instructions live in the subagent's system prompt (SUBAGENT_SYSTEM_PROMPT in tools.py), written once, so the orchestrator
writes far less. Compare with l3s2_sizes.py, where it wrote the whole instruction six times.

Run from the project root:   .venv/bin/python -m layer3.l3s2_short
"""
from layer3.l3s1_orchestrator import FILES
from layer3.l3s2_parallel import run

QUESTION_SHORT = (
    "For each of these documents, find the final answer stated in it and report one line per document, in the form "
    "'report_N.txt: <answer>'. You cannot read files yourself: use the delegate tool, one delegate call per document, "
    "and in each task just name the file path. The documents are: " + ", ".join(FILES) + "."
)

if __name__ == "__main__":
    run(QUESTION_SHORT, "subagents in parallel, standing instructions in their system prompt")
