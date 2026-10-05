# simple-harness

A minimal tool-use agent harness built from scratch in Python, to learn how the
agent loop works by owning every line. No agent frameworks: just the Anthropic
Messages format (`tool_use`, `tool_result`, `stop_reason`) sent through a
the gateway to Claude on Bedrock.

Progress lives in [ROADMAP.md](ROADMAP.md).

## Setup

```bash
python3.12 -m venv .venv          # Python 3.10+ required (macOS system python is too old)
source .venv/bin/activate
pip install -r requirements.txt
```

Configuration comes from environment variables only. Never put keys in the repo.

```bash
export ANTHROPIC_API_KEY="..."
export HARNESS_MODEL="us.anthropic.claude-haiku-4-5-20251001-v1:0"
```

## Run

Each step is its own script so earlier steps stay readable:

```bash
python step1_stateless.py
```
