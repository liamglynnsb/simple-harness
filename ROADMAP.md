# Roadmap

Read this first at the start of every session. Tick items off as we finish them.
Rule: don't build ahead of the step we're on. Later layers wrap the loop; they
never rewrite it.

## Layer 1: the bare loop (no frameworks)  <- WE ARE HERE

- [x] Step 1: plain API call; show the model is stateless; print token cost per turn
- [ ] Step 2: define one tool; inspect the raw `tool_use` response and `stop_reason`
- [ ] Step 3: the loop: branch on `stop_reason`, handle `max_tokens`, iteration cap
- [ ] Step 4: second tool; several tool calls in one response (one `tool_result` each)
- [ ] Step 5: break a tool on purpose; return an error `tool_result`; watch recovery

## Layer 2: extensions

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
