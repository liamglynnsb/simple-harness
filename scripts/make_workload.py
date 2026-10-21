"""Generate the Layer 3 workload: six long documents, each with one buried fact, in data/workload/.

    .venv/bin/python scripts/make_workload.py            # (re)write the files
    .venv/bin/python scripts/make_workload.py --answers  # print the answer key (kept here, NOT in data/, so the model can't read it)

Every file is 200 numbered filler lines plus one line "The final answer is N." at a different position, so reading
cost differs by file. The question asked of each file is the same: "What is the final answer in <file>?"
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOLDER = ROOT / "data" / "workload"
LINES = 200

# file number -> (the answer, the line after which the fact is placed)
FACTS = {1: (7, 5), 2: (12, 60), 3: (31, 120), 4: (45, 190), 5: (58, 30), 6: (63, 200)}


def build(number, answer, after_line):
    lines = []
    for n in range(1, LINES + 1):
        lines.append(f"Document {number}, line {n}: this is filler text so that the document is long; nothing on this line matters.")
        if n == after_line:
            lines.append(f"The final answer is {answer}.")
    return "\n".join(lines) + "\n"


def main():
    if "--answers" in sys.argv:
        for number, (answer, after_line) in FACTS.items():
            print(f"report_{number}.txt -> {answer}  (placed after line {after_line})")
        return
    FOLDER.mkdir(parents=True, exist_ok=True)
    for number, (answer, after_line) in FACTS.items():
        (FOLDER / f"report_{number}.txt").write_text(build(number, answer, after_line))
    print("wrote", len(FACTS), "files to", FOLDER.relative_to(ROOT))


if __name__ == "__main__":
    main()
