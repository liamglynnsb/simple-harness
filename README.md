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

`.env` is found next to `client.py`, so scripts can be run from any folder. Each
step is its own script so earlier steps stay readable:

```bash
python step1_stateless.py
```
