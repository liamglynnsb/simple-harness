# Roadmap

Read this first at the start of every session. Tick items off as we finish them.
Rule: don't build ahead of the step we're on. Later layers wrap the loop; they
never rewrite it.

Whenever we split a step into pieces, record the pieces here as substeps (`1a`,
`1b`, ...) with the file each one produced, so the shape of the build is on record.

## Layer 1: the bare loop (no frameworks)  <- WE ARE HERE

- [x] Step 1: plain API call; show the model is stateless; print token cost per turn
  - [x] 1a: repo, venv, README, ROADMAP, `.gitignore`
  - [x] 1b: config via environment variables and `.env` (key never in the repo)
  - [x] 1c: `client.py`, the one module that knows about the gateway
  - [x] 1d: first plain call; read the raw `Message` (content, stop_reason, usage)
  - [x] 1e: two calls prove statelessness; fix by re-sending history in order
  - [x] 1f: loop over turns, printing input/output tokens per turn
        (`l1s1_stateless.py`)
- [x] Step 2: define one tool; inspect the raw `tool_use` response and `stop_reason`
  - [x] 2a: the tool definition: name, description, JSON-schema `input_schema`
  - [x] 2b: call with `tools=[...]`; read the raw `tool_use` block and
        `stop_reason: tool_use` before parsing anything (`l1s2_tool_use.py`)
  - [ ] Once it works: remind Liam to skim the tool-use docs
        (https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [x] Step 3: the loop: branch on `stop_reason`, handle `max_tokens`, iteration cap
  - [x] 3a: real calculator function in `tools.py`, plus the `FUNCTIONS` lookup
  - [x] 3b: one tool request handled by hand (`l1s3_one_tool_call.py`)
  - [x] 3c: the loop in `loop.py` (`tool_use` and `end_turn` branches, `else` stopgap)
  - [x] 3d: handle `max_tokens` properly, add an iteration cap
        (also: `__main__` guard; final `else` for unexpected stop reasons)
  - [ ] Rebuild the loop from a blank file with nothing open (ownership test)
  - [x] Loose end: `end_turn` used `content[0].text`; both branches now use a
        `collect_text` helper that joins text blocks with a newline
- [ ] Step 4: second tool; several tool calls in one response (one `tool_result` each)
  - [x] 4a: second tool `read_file` in `tools.py` (definition, function, `FUNCTIONS`
        entry) plus small files in `data/` for it to read
  - [ ] 4b: one task needing both tools in sequence ("read numbers.txt, multiply the
        two numbers"); print each tool call (name, inputs) to watch the passes
  - [ ] 4c: several tool calls in one reply ("read a.txt and b.txt, and compute
        12 x 12"); inspect the raw reply and check one `tool_result` per block, ids matched
  - [ ] 4d: check the invariants: the shape of the `messages` list after a
        multi-tool pass; leave a result out on purpose and read the API's complaint
- [ ] Step 5: break a tool on purpose; return an error `tool_result`; watch recovery

## Layer 2: extensions

- [ ] (idea, once more comfortable) a shell/terminal tool. Powerful and risky: the
      model could run arbitrary commands, so plan permissions or a sandbox first.
- [ ] A skill file exposed as a tool the loop can call
- [ ] A tiny MCP server exposing one tool
- [ ] A subagent with scoped tools
- [ ] A hook that runs around tool calls

## Layer 3: multi-agent

- [ ] Orchestrator that fans work out to parallel subagents and synthesizes results

## Layer 4: evals and judges

- [ ] Small eval harness: task set, run, verifiers, trajectory logs, pass@k
- [ ] LLM judge calibrated against known answers

## Layer 5: production shell

- [ ] Retries and model fallback
- [ ] Schema-validated structured output
- [ ] Guardrails: PII/secret redaction, output checks
- [ ] Prompt-injection testing on tool results
- [ ] Cost and latency tracing
- [ ] Context/memory management (trim or summarize history as it grows)
- [ ] Streaming
