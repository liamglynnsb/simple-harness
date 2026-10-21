"""Layer 3 Step 2: the parallel run again, but each subagent is asked to look at the file sizes first (list_files now shows
them), so it can ask for all its pieces in one turn instead of one piece at a time. Compare with l3s2_parallel.py.

Run from the project root:   .venv/bin/python -m layer3.l3s2_sizes
"""
from layer3.l3s1_orchestrator import QUESTION
from layer3.l3s2_parallel import run

QUESTION_WITH_SIZES = QUESTION + (
    " Tell each subagent to first list data/workload, which shows every file's size in bytes, and then to request ALL "
    "the pieces it still needs in a single turn (read_file returns 4,000 characters per piece; use the start input)."
)

if __name__ == "__main__":
    run(QUESTION_WITH_SIZES, "subagents in parallel, told to check sizes first")
