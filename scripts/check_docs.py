"""Check that the documentation is consistent with the repository and with itself.

    .venv/bin/python scripts/check_docs.py            # check the repo this script lives in
    .venv/bin/python scripts/check_docs.py --root DIR # check another copy (used to test the checker)

Run it before every commit that touches a doc, a script, a tool or a path. It exits non-zero and
prints one line per problem. Fix the docs, don't weaken the checker. What it checks:

 1. Markdown links resolve.
 2. Every file path named in `backticks` exists, or is planned in an unticked ROADMAP item.
 3. The README's run commands point at real modules and files, and every step script is listed.
 4. ROADMAP structure: steps and substeps numbered consecutively; a step is ticked exactly when
    all its (non-optional) substeps are; "WE ARE HERE" appears once; the "Where we are" line
    names the first unticked substep.
 5. The ledger index links every file in learnings/, and says the right number of them.
 6. Facts stated in two places agree: the default model (CLAUDE.md vs .env.example), the tools
    (README vs FUNCTIONS in tools.py), every learnings file named in CLAUDE.md.
 7. No duplicated ledger entry titles; no TODO/FIXME left behind; no known-stale phrases.
 8. The glossary's terms each have a definition.
 9. The SDK reference's claims still hold (runs scripts/gen_sdk_reference.py --check).
10. The SDK reference keeps real-interaction material and test-only material apart: the fake client
    and its helpers may appear only in the section titled "For tests only" and after it.
11. No tracked file contains a term from LOCAL_FORBIDDEN_TERMS.txt (an optional git-ignored list of terms; the check is skipped if the file is missing).
"""
import argparse
import ast
import pathlib
import re
import subprocess
import sys

PATH_EXTS = (".py", ".md", ".txt", ".example", ".toml", ".json", ".jsonl")
# Paths that appear in the docs on purpose but needn't exist as files in the repo.
ALLOWED_MISSING = {
    "data/missing.txt",      # the deliberately missing file from Layer 1 Step 5
    ".env",                  # git-ignored; exists locally, not in the repo
    "../.env",               # the example path that read_file shouldn't allow
    "LOCAL_NOTES.md",        # git-ignored local notes
    "layer<N>/",
    "test-client.py",        # the ledger's example of a file name Python can't import (a hyphen)
}
KNOWN_DIRS = {"layer1", "layer2", "layer3", "layer4", "layer5", "tests", "learnings", "scripts", "skills", "data", "evals"}
STDLIB_MODULES = {"venv", "pytest", "pip"}       # `python -m X` for these isn't one of our files
STALE_PHRASES = [            # things that were true once and are now wrong
    "split in two",
    "the two files it points to",
    "step1_stateless",
]
OPTIONAL = re.compile(r"\(optional\)", re.I)


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def doc_files(root: pathlib.Path):
    files = sorted(root.glob("*.md")) + sorted((root / "learnings").glob("*.md"))
    return [f for f in files if f.name != "LOCAL_NOTES.md"]


# ---------------------------------------------------------------- ROADMAP parsing
def roadmap_blocks(text: str):
    """Yield (ticked, block_text) for every checkbox item, with its indented continuation lines."""
    lines, blocks, cur = text.split("\n"), [], None
    for ln in lines:
        m = re.match(r"^(\s*)- \[( |x)\] ", ln)
        if m:
            if cur: blocks.append(cur)
            cur = [m.group(2) == "x", ln]
        elif cur is not None and (ln.startswith("      ") or ln.startswith("        ")) and ln.strip():
            cur[1] += "\n" + ln
        elif cur is not None and (not ln.strip() or ln.startswith("#")):
            blocks.append(cur); cur = None
    if cur: blocks.append(cur)
    return blocks


def parse_roadmap(text: str):
    """Return a list of steps: dicts with layer, number, ticked, substeps [(letter, ticked, optional)]."""
    steps, layer, step = [], None, None
    for ln in text.split("\n"):
        m = re.match(r"^## Layer (\d+)", ln)
        if m:
            layer, step = int(m.group(1)), None
            continue
        if ln.startswith("## "):
            layer, step = None, None
            continue
        if layer is None:
            continue
        m = re.match(r"^- \[( |x)\] Step (\d+)\b", ln)
        if m:
            step = {"layer": layer, "number": int(m.group(2)), "ticked": m.group(1) == "x", "subs": [], "loose": []}
            steps.append(step)
            continue
        if re.match(r"^- \[", ln):
            step = None                                    # a checkpoint or standalone item
            continue
        m = re.match(r"^  - \[( |x)\] (\d+)([a-z])\b(.*)", ln)
        if m and step is not None:
            step["subs"].append((m.group(3), m.group(1) == "x", bool(OPTIONAL.search(ln))))
            continue
        m = re.match(r"^  - \[( |x)\] ", ln)
        if m and step is not None:
            step["loose"].append((m.group(1) == "x", ln.strip()))
    return steps


# ---------------------------------------------------------------- the checks
def check_links(root, problems):
    for f in doc_files(root):
        for target in re.findall(r"(?<![\w\]])\[[^\]]+\]\(([^)\s]+)\)", read(f)):
            if target.startswith(("http", "mailto:", "#")):
                continue
            if not (f.parent / target.split("#")[0]).resolve().exists():
                problems.append(f"{f.relative_to(root)}: broken link -> {target}")


def planned_paths(roadmap_text):
    planned = set()
    for ticked, block in roadmap_blocks(roadmap_text):
        if not ticked:
            planned |= set(path_tokens(block))
    return planned


def path_tokens(text):
    """Backticked tokens that are meant as file or folder paths in the repo."""
    out = []
    for tok in re.findall(r"`([^`\n]+)`", text):
        if re.search(r"[\s*<>{}()=,:|]", tok) or tok.startswith(("http", "~", "/", ".venv/", "$", "@", "!")):
            continue
        if "/" in tok:
            if tok.endswith("/") or tok.endswith(PATH_EXTS) or tok.split("/")[0] in KNOWN_DIRS:
                out.append(tok)
        elif tok.endswith(PATH_EXTS) and tok not in PATH_EXTS:
            out.append(tok)
    return out


def exists_somewhere(root, f, tok):
    """True if the path exists from the root or the doc's folder, or (for a bare file name that
    docs use in prose) if exactly one file of that name exists in the repo."""
    if (root / tok).exists() or (f.parent / tok).exists():
        return True
    if "/" not in tok:
        hits = [h for h in root.rglob(tok) if ".venv" not in h.parts and ".git" not in h.parts]
        return len(hits) == 1
    return False


def path_of_roadmap(root):
    return root / "ROADMAP.md"


def check_paths(root, problems, roadmap_text):
    planned = planned_paths(roadmap_text)
    for f in doc_files(root):
        text = read(f)
        in_roadmap_ticked = None
        if f.name == "ROADMAP.md":
            # in the roadmap, a ticked item may only name files that exist
            for ticked, block in roadmap_blocks(text):
                if ticked:
                    for tok in path_tokens(block):
                        if tok not in ALLOWED_MISSING and not exists_somewhere(root, path_of_roadmap(root), tok):
                            problems.append(f"ROADMAP.md: a ticked item names a file that doesn't exist: {tok}")
            continue
        for tok in path_tokens(text):
            if tok in ALLOWED_MISSING or tok in planned:
                continue
            if exists_somewhere(root, f, tok):
                continue
            problems.append(f"{f.relative_to(root)}: names a path that doesn't exist and isn't planned in ROADMAP: {tok}")


def check_readme_commands(root, problems):
    readme = root / "README.md"
    if not readme.exists():
        problems.append("README.md is missing"); return
    text = read(readme)
    listed = set()
    for block in re.findall(r"```bash\n(.*?)```", text, re.S):
        for ln in block.splitlines():
            ln = ln.split("#")[0].strip()
            if not ln.startswith((".venv/bin/python", "python", ".venv/bin/pip")):
                continue
            parts = ln.split()
            if "-m" in parts:
                mod = parts[parts.index("-m") + 1]
                if mod in STDLIB_MODULES:
                    continue
                path = root / (mod.replace(".", "/") + ".py")
                listed.add(str(path.relative_to(root)))
                if not path.exists():
                    problems.append(f"README.md: run command names a module that doesn't exist: {mod}")
            elif "-r" in parts:
                req = parts[parts.index("-r") + 1]
                if not (root / req).exists():
                    problems.append(f"README.md: install command names a file that doesn't exist: {req}")
            else:
                script = next((p for p in parts[1:] if p.endswith(".py")), None)
                if script:
                    listed.add(script)
                    if not (root / script).exists():
                        problems.append(f"README.md: run command names a script that doesn't exist: {script}")
    for step_script in sorted(root.glob("layer*/l*s*_*.py")):
        if str(step_script.relative_to(root)) not in listed:
            problems.append(f"README.md: step script not listed in the Run section: {step_script.relative_to(root)}")


def check_roadmap(root, problems):
    path = root / "ROADMAP.md"
    text = read(path)
    steps = parse_roadmap(text)
    per_layer = {}
    for s in steps:
        per_layer.setdefault(s["layer"], []).append(s)
    for layer, ss in per_layer.items():
        nums = [s["number"] for s in ss]
        first = 0 if layer == 2 else 1
        if nums != list(range(first, first + len(nums))):
            problems.append(f"ROADMAP.md: Layer {layer} steps are not numbered consecutively: {nums}")
    for s in steps:
        letters = [l for l, _, _ in s["subs"]]
        if letters != [chr(97 + i) for i in range(len(letters))]:
            problems.append(f"ROADMAP.md: Layer {s['layer']} Step {s['number']} substep letters not consecutive: {letters}")
        required = [(l, t) for l, t, opt in s["subs"] if not opt]
        if required:
            all_done = all(t for _, t in required)
            if s["ticked"] and not all_done:
                problems.append(f"ROADMAP.md: Layer {s['layer']} Step {s['number']} is ticked but a substep isn't")
            if not s["ticked"] and all_done:
                problems.append(f"ROADMAP.md: Layer {s['layer']} Step {s['number']} has every substep ticked but the step isn't")
        if s["ticked"]:
            for done, ln in s["loose"]:
                if not done and not OPTIONAL.search(ln):
                    problems.append(f"ROADMAP.md: a ticked step (Layer {s['layer']} Step {s['number']}) has an unticked item: {ln[:60]}")
    here = len(re.findall(r"WE ARE HERE", text))
    if here != 1:
        problems.append(f"ROADMAP.md: 'WE ARE HERE' should appear exactly once, found {here}")
    first_open = None
    for s in steps:
        for letter, ticked, opt in s["subs"]:
            if not ticked and not opt:
                first_open = f"Layer {s['layer']}, Step {s['number']}, substep {s['number']}{letter}"
                break
        if first_open:
            break
    m = re.search(r"\*\*Where we are:\*\*\s*Layer (\d+), Step (\d+)[^\n]*?substep (\d+[a-z])", text)
    if not m:
        problems.append("ROADMAP.md: no '**Where we are:** Layer N, Step N ... substep Nx' line")
    elif first_open and f"Layer {m.group(1)}, Step {m.group(2)}, substep {m.group(3)}" != first_open:
        problems.append(f"ROADMAP.md: 'Where we are' says Layer {m.group(1)}, Step {m.group(2)}, substep {m.group(3)} "
                        f"but the first unticked substep is {first_open}")


def check_index(root, problems):
    idx = root / "LEARNINGS.md"
    if not idx.exists():
        problems.append("LEARNINGS.md (the index) is missing"); return
    text = read(idx)
    files = sorted((root / "learnings").glob("*.md"))
    for f in files:
        if f"learnings/{f.name}" not in text:
            problems.append(f"LEARNINGS.md: the index doesn't link learnings/{f.name}")
    words = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    m = re.search(r"split in (\w+):", text)
    if m and m.group(1) != words.get(len(files), str(len(files))):
        problems.append(f"LEARNINGS.md: says 'split in {m.group(1)}' but learnings/ has {len(files)} files")


def check_facts(root, problems):
    claude = root / "CLAUDE.md"
    env = root / ".env.example"
    if claude.exists() and env.exists():
        m = re.search(r"HARNESS_MODEL=(\S+)", read(env))
        if m and m.group(1) not in read(claude):
            problems.append(f"CLAUDE.md: default model doesn't match .env.example ({m.group(1)})")
    tools = root / "tools.py"
    readme = root / "README.md"
    if tools.exists() and readme.exists():
        tree = ast.parse(read(tools))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "FUNCTIONS" for t in node.targets):
                names = [k.value for k in node.value.keys]
                for n in names:
                    if n not in read(readme):
                        problems.append(f"README.md: tool '{n}' is in FUNCTIONS (tools.py) but not mentioned")
    if claude.exists():
        for f in (root / "learnings").glob("*.md"):
            if f.name not in read(claude):
                problems.append(f"CLAUDE.md: doesn't mention learnings/{f.name}")


def check_text_hygiene(root, problems):
    titles = {}
    for f in doc_files(root):
        text = read(f)
        for phrase in STALE_PHRASES:
            if phrase in text and f.name != "check_docs.py":
                problems.append(f"{f.relative_to(root)}: stale phrase: {phrase!r}")
        for marker in ("TODO", "FIXME", "XXX"):
            if re.search(rf"\b{marker}\b", text):
                problems.append(f"{f.relative_to(root)}: leftover {marker}")
        if f.parent.name == "learnings" and f.name in ("harness.md", "code.md"):
            for t in re.findall(r"^\*\*([^*\n].*?)\.\*\*", text, re.M):
                titles.setdefault(t, []).append(f.name)
    for t, where in titles.items():
        if len(where) > 1:
            problems.append(f"ledger entry title appears more than once ({', '.join(where)}): {t[:60]}")


def check_glossary(root, problems):
    g = root / "learnings" / "glossary.md"
    if not g.exists():
        problems.append("learnings/glossary.md is missing"); return
    for term, body in re.findall(r"^\*\*(.+?)\*\*\s*(.*?)(?=^\*\*|\Z)", read(g), re.M | re.S):
        if len(body.strip()) < 20:
            problems.append(f"glossary: term has no real definition: {term}")


def check_sdk_reference(root, problems):
    script = root / "scripts" / "gen_sdk_reference.py"
    if script.exists() and (root / "learnings" / "anthropic-sdk-reference.md").exists():
        r = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True, cwd=root)
        if r.returncode != 0:
            problems.append("SDK reference: a claim in the text no longer holds: " + (r.stderr.strip().splitlines() or ["?"])[-1])


TEST_ONLY_TERMS = ["FakeClient", "SimpleNamespace", "text_reply", "tool_reply", "fake_client"]


def check_real_vs_test(root, problems):
    """In the SDK reference, how the harness really talks to the model (everything before the
    'For tests only' section) must not mention the test doubles."""
    ref = root / "learnings" / "anthropic-sdk-reference.md"
    if not ref.exists():
        return
    text = read(ref)
    marker = text.find("For tests only")
    if marker == -1:
        problems.append("learnings/anthropic-sdk-reference.md: no 'For tests only' section found")
        return
    real_part = text[:text.rfind("\n", 0, marker)]
    for term in TEST_ONLY_TERMS:
        if term in real_part:
            problems.append(f"learnings/anthropic-sdk-reference.md: test-only term {term!r} appears outside the 'For tests only' section")


def check_forbidden_terms(root, problems):
    """Fail if a tracked file mentions anything in LOCAL_FORBIDDEN_TERMS.txt (an optional file, not tracked)."""
    terms_file = root / "LOCAL_FORBIDDEN_TERMS.txt"
    if not terms_file.exists():
        return
    patterns = [re.compile(l.strip(), re.I) for l in read(terms_file).splitlines() if l.strip() and not l.startswith("#")]
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.splitlines()
    for name in tracked:
        path = root / name
        try:
            text = read(path)
        except Exception:
            continue  # not a text file
        for pat in patterns:
            if pat.search(text):
                problems.append(f"{name}: contains a term from LOCAL_FORBIDDEN_TERMS.txt (pattern {pat.pattern!r})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parent.parent))
    root = pathlib.Path(ap.parse_args().root).resolve()
    problems = []
    roadmap_text = read(root / "ROADMAP.md")
    check_links(root, problems)
    check_paths(root, problems, roadmap_text)
    check_readme_commands(root, problems)
    check_roadmap(root, problems)
    check_index(root, problems)
    check_facts(root, problems)
    check_text_hygiene(root, problems)
    check_glossary(root, problems)
    check_sdk_reference(root, problems)
    check_real_vs_test(root, problems)
    check_forbidden_terms(root, problems)
    if problems:
        print(f"{len(problems)} documentation problem(s):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("documentation checks passed")


if __name__ == "__main__":
    main()
