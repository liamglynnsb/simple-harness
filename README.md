# simple-harness

A minimal tool-use agent harness built from scratch in Python, to learn how the
agent loop works by owning every line. No agent frameworks: just the Anthropic
Messages format (`tool_use`, `tool_result`, `stop_reason`) sent through a
the gateway to Claude on Bedrock.

Progress lives in [ROADMAP.md](ROADMAP.md). Concepts learned along the way are
in [LEARNINGS.md](LEARNINGS.md).

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
# then edit .env and put your real ANTHROPIC_API_KEY in it
```

`client.py` loads `.env` itself, so there is no `source` step. Never commit
`.env` or put keys in code.

## Run

`.env` is found next to `client.py`. Step scripts live in a folder per layer
(`layer1/`, `layer2/`, ...) and are named `l<layer>s<step>_<topic>.py`. Run them as
modules **from the project root**, so they can import `client` and `tools`:

```bash
python -m layer1.l1s1_stateless      # Step 1: stateless calls, token cost per turn
python -m layer1.l1s2_tool_use       # Step 2: define a tool, read the raw tool_use reply
python -m layer1.l1s3_one_tool_call  # Step 3b: one tool request handled by hand
python loop.py                       # Steps 3-5: the agent loop with two tools
```

## What's here

- `client.py`: the only file that knows about the gateway (base URL, headers, `.env`)
- `tools.py`: tool definitions (`CALCULATOR`, `READ_FILE`), their functions, and
  `FUNCTIONS`, the name-to-function lookup
- `loop.py`: `run_agent`, the loop. It branches on `stop_reason`, answers every
  `tool_use` with a `tool_result` (errors flagged `is_error`), and caps its passes
- `data/`: small text files for the `read_file` tool
- `layer1/`, `layer2/`, ...: the step scripts for each layer
- `ROADMAP.md`: layers and steps, with substeps; `LEARNINGS.md`: what I've learned
