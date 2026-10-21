# simple-harness

A minimal tool-use agent harness built from scratch in Python, to learn how the
agent loop works by owning every line. No agent frameworks: just the Anthropic
Messages format (`tool_use`, `tool_result`, `stop_reason`) sent to Claude, directly
or through a gateway.

Progress lives in [ROADMAP.md](ROADMAP.md). Concepts learned along the way are
in [LEARNINGS.md](LEARNINGS.md); unfamiliar word? See the [glossary](learnings/glossary.md).

## Setup

Python 3.10+ is required (the macOS system python is too old).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configuration comes from a `.env` file in the project folder. It is git-ignored,
so every person creates their own:

```bash
cp .env.example .env
# then edit .env and put your real ANTHROPIC_API_KEY in it (and the optional gateway lines, only if you use one)
```

`client.py` loads `.env` itself, so there is no `source` step. Never commit
`.env` or put keys in code.

The tests (Layer 2 Step 2, under `tests/`) need one more package:
`.venv/bin/pip install -r requirements-dev.txt`. Run them with `.venv/bin/python -m pytest -q`
(they use a scripted fake client, so no API calls and no cost).

## Run

`.env` is found next to `client.py`. Step scripts live in a folder per layer
(`layer1/`, `layer2/`, ...) and are named `l<layer>s<step>_<topic>.py`. Run them as
modules **from the project root**, so they can import `client` and `tools`. These
commands call the virtual environment's Python directly (`.venv/bin/python`); if you
activate it first with `source .venv/bin/activate`, plain `python` works too:

```bash
.venv/bin/python -m layer1.l1s1_stateless      # L1 Step 1: stateless calls, token cost per turn
.venv/bin/python -m layer1.l1s2_tool_use       # L1 Step 2: define a tool, read the raw tool_use reply
.venv/bin/python -m layer1.l1s3_one_tool_call  # L1 Step 3b: one tool request handled by hand
.venv/bin/python -m layer2.l2s1_tool_cost      # L2 Step 1a: what tool definitions cost in tokens
.venv/bin/python -m layer3.l3s1_baseline      # L3 Step 1b: one agent does the whole workload; prints passes, tokens, time (calls the real model)
.venv/bin/python -m layer3.l3s2_sizes         # L3 Step 2: the parallel run again, with subagents told to check file sizes first (calls the real model)
.venv/bin/python -m layer3.l3s2_parallel      # L3 Step 2a: the same job with the six subagents running at the same time (calls the real model)
.venv/bin/python -m layer3.l3s1_orchestrator  # L3 Step 1c: the same workload through subagents, one at a time (calls the real model)
.venv/bin/python loop.py                       # the agent loop (see below)
```

`loop.py` runs **one hard-coded question** from its `__main__` block, giving the model two tools,
`read_file` and `list_files`, and asking for a file that doesn't exist, to watch it recover. The other tools
(`calculator`, `load_skill`, `delegate`) are defined in `tools.py` but not used in this run. Edit the `messages = [...]` line to try other questions.

## What's here

- `client.py`: the only file that knows how to reach the model (key, optional gateway address and headers, `.env`)
- `tools.py`: tool definitions (`CALCULATOR`, `READ_FILE`, `LIST_FILES`, `LOAD_SKILL`, `DELEGATE`), their functions, and
  `FUNCTIONS`, the name-to-function lookup
- `skills.py`: reads the files in `skills/` into a dict (name -> description and body)
- `skills/`: markdown skill files: a `name:` line, a `description:` line, a `---` line, then
  the instructions. The model sees only names and descriptions until it asks for a skill
- `mcp_server.py`: a minimal MCP server over stdio with one tool (`count_letters`); run it by hand and type JSON lines
  to see the protocol (Layer 2 Step 5)
- `mcp_client.py`: the harness side of MCP over stdio: starts a server as a subprocess, talks to it through its
  pipes, and wraps its tools as functions the loop can call (Layer 2 Step 5)
- `measure.py`: wraps the model client and records each call's time and token usage (used by the Layer 3 baseline)
- `hooks.py`: hooks, small functions the harness runs around every tool call (so far two before-hooks: one logs the call, one keeps the file tools inside `data/`; and one after-hook that cuts very long results)
- `loop.py`: `run_agent`, the loop. It branches on `stop_reason`, answers every `tool_use`
  with a `tool_result` (errors flagged `is_error`), and caps its passes
- `data/`: small text files for the `read_file` tool
- `layer1/`, `layer2/`, ...: the step scripts for each layer
- `tests/`: `fake_client.py` (a scripted stand-in for the model) and `test_loop.py`
- `scripts/`: `gen_sdk_reference.py` regenerates the tables in `learnings/anthropic-sdk-reference.md`
  from the installed SDK; `check_docs.py` checks the documentation for drift;
  `make_workload.py` writes the Layer 3 sample documents in `data/workload/`
- `ROADMAP.md`: layers and steps, with substeps; `PLAN.md`: the reasoning behind the plan;
  `LEARNINGS.md`: the index of what I've learned, with `learnings/harness.md` (the theory of the
  harness) and `learnings/code.md` (the code and tooling), `learnings/anthropic-sdk-reference.md` (SDK data structures)
  and `learnings/glossary.md` (every term); `CLAUDE.md`: how Claude Code works with me on this repo
