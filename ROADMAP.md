# Roadmap

Read this first at the start of every session. Tick items off as we finish them.
Rule: don't build ahead of the step we're on. Later layers wrap the loop; they
never rewrite it.

Whenever we split a step into pieces, record the pieces here as substeps (`1a`,
`1b`, ...) with the file each one produced, so the shape of the build is on record.

## Layer 1: the bare loop (no frameworks)  (one item left: the rebuild test)

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
  - [x] Once it works: remind Liam to skim the tool-use docs
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
- [x] Step 4: second tool; several tool calls in one response (one `tool_result` each)
  - [x] 4a: second tool `read_file` in `tools.py` (definition, function, `FUNCTIONS`
        entry) plus small files in `data/` for it to read
  - [x] 4b: one task needing both tools in sequence ("read numbers.txt, multiply the
        two numbers"); print each tool call (name, inputs) to watch the passes
  - [x] 4c: several tool calls in one reply ("read a.txt and b.txt, and compute
        12 x 12"); inspect the raw reply and check one `tool_result` per block, ids matched
  - [x] 4d: check the invariants: the shape of the `messages` list after a
        multi-tool pass; leave a result out on purpose and read the API's complaint
- [x] Step 5: break a tool on purpose; return an error `tool_result`; watch recovery
  - [x] 5a: let a tool fail with nothing protecting the loop ("read
        data/missing.txt"); see what the unprotected loop does
  - [x] 5b: catch the exception around the tool call; return a `tool_result` with
        `is_error: true` and the error text; watch the model recover
  - [x] 5c: garbage without an exception (a tool returns nonsense or `None`); see
        how the model copes, and why `is_error` doesn't help here
  - [x] 5d: other failure kinds the loop should survive: an unknown tool name,
        bad arguments; what makes an error message useful for recovery

- [ ] Layer 1 hardening (found in a review of Layer 1; reasons in PLAN.md). Not
      required by the original brief, but cheap, and worth doing before the loop is
      restructured in Layer 2 Step 3:
  - [ ] H1: tests with a scripted fake model in `tests/` (end_turn, several tool
        calls, unknown tool, tool error, max_tokens, unexpected stop_reason, max_loops)
  - [ ] H2: watch a real recovery: give the model a way to fix its own failure (a
        `list_files` tool after a wrong path) and see a retry succeed
  - [ ] H3: measure what tool definitions cost: same prompt with and without `tools`,
        compare `input_tokens`
  - [ ] H4: make `max_tokens` a parameter of `run_agent` instead of a fixed 300
  - [ ] H5: rotate the the gateway key

## Layer 2: extensions  <- WE ARE HERE

Order is deliberate (easier concepts first, the biggest last): skill, subagent, hook,
MCP. Skill and subagent only add tools; the hook restructures the loop's tool-running
code; MCP is a separate program plus a protocol whose spec recently changed.
Scripts are `l2s<step>_<topic>.py`. Details and pitfalls for every step are in PLAN.md.

- [ ] Step 1: a skill file as a tool (`skills/`, `l2s1_skill.py`)
  - [ ] 1a: write two skills: a text file each, with a name, a one-line description,
        and instructions whose effect is checkable (a required answer format)
  - [ ] 1b: a `load_skill` tool that returns a skill's instructions; the tool's
        description lists only the skills' names and descriptions
  - [ ] 1c: a task where the model chooses to load a skill, then follows it
  - [ ] 1d: compare token cost: skill loaded on demand vs always included
- [ ] Step 2: a subagent with scoped tools (`l2s2_subagent.py`)
  - [ ] 2a: add an optional system prompt to `run_agent` (first use of `system`)
  - [ ] 2b: a `delegate` tool: runs a fresh `run_agent` with its own history and a
        short list of tools, and returns only its final text
  - [ ] 2c: see the isolation: the parent's `messages` never contain the child's turns;
        compare token cost of parent and child
  - [ ] 2d: scoping: the child lacks a tool, asks for it anyway, and fails the way 5d
        taught (unknown tool)
  - [ ] 2e: limits: the child hits its own `max_loops` or errors; what the parent sees
  - [ ] 2f: is it worth it? same task with and without the subagent
- [ ] Step 3: a hook around tool calls (`hooks.py`, `l2s3_hooks.py`)
  - [ ] 3a: pull the tool-running code out of the loop into `execute_tool`; the H1
        tests must still pass
  - [ ] 3b: before-hooks: a list of functions called before each tool; first one logs
        the call (replaces the trace print)
  - [ ] 3c: a blocking hook: `read_file` only inside `data/`, returning a flagged error
        result; then try to get around your own rule (`..`, absolute path, symlink)
  - [ ] 3d: after-hooks: see or change a result (truncate, redact); observing vs changing
  - [ ] 3e: a hook that itself fails: fail open or fail closed, and why
  - [ ] 3f (optional): command hooks that read the call as JSON on stdin, like Claude Code
- [ ] Step 4: a tiny MCP server with one tool (`mcp_client.py`, `l2s4_mcp.py`)
  - [ ] 4a: read the current spec's stdio page; decide official Python SDK vs a
        hand-written server; write down what changed from the older handshake
  - [ ] 4b: a minimal server exposing one tool; talk to it by hand in the terminal
        (pipe JSON lines in) to see the protocol
  - [ ] 4c: harness side: start the server, list its tools, convert them to the
        `tools` format, route calls by name
  - [ ] 4d: one task using a local tool and the MCP tool; failures (server dies, bad
        reply) come back as `is_error` results; shut the process down cleanly
  - [ ] 4e: compare in-process tools with MCP: what you gain, what it costs
- [ ] Layer 2 checkpoint: explain each of the four extensions back; rebuild the hook
      mechanism from a blank file

## Layer 3: multi-agent  (builds on the Layer 2 subagent; `orchestrator.py`)

- [ ] Step 1: baseline: one orchestrator delegating N independent subtasks one after
      another, plus the single-agent version of the same job (time and tokens for both)
  - [ ] 1a: build a workload: several data files and a per-file question
  - [ ] 1b: single agent does it all; record tokens, passes and wall-clock time
  - [ ] 1c: orchestrator with sequential `delegate` calls; record the same numbers
- [ ] Step 2: parallel fan-out
  - [ ] 2a: run the subagents in threads; each gets its own `messages` (no shared lists)
  - [ ] 2b: measure speedup and watch for rate-limit errors from the gateway
  - [ ] 2c: keep results in order and handle one worker finishing much later
- [ ] Step 3: let the orchestrator plan the split
  - [ ] 3a: the model proposes subtasks as structured data; validate the plan
  - [ ] 3b: cap the fan-out width and the plan size
- [ ] Step 4: synthesis
  - [ ] 4a: combine worker results into one answer (what to send, what to drop)
  - [ ] 4b: partial failure: one worker errors or times out; inject failures with fakes
  - [ ] 4c: conflicting or missing results; say what is uncertain
- [ ] Step 5: budgets and tracing across agents
  - [ ] 5a: per-worker and total caps (tokens, passes, seconds), with a kill switch
  - [ ] 5b: trace ids linking parent and child calls in the logs
- [ ] Step 6: is it worth it? single agent vs multi-agent on cost, latency, quality
- [ ] Layer 3 checkpoint: explain fan-out, isolation and synthesis back; rebuild the
      fan-out from a blank file

## Layer 4: evals and judges  (`evals/`: tasks, runner, verifiers, judge, report)

- [ ] Step 1: the task set
  - [ ] 1a: unit tests vs evals: what each can and cannot tell you
  - [ ] 1b: 12-20 hand-written tasks with known answers across categories (one tool,
        two tools in sequence, parallel calls, tool error, garbage tool, unknown tool,
        skill use, subagent use)
  - [ ] 1c: a task file format and a check that every task is well formed
- [ ] Step 2: the runner and trajectory logs
  - [ ] 2a: run every task through `run_agent`
  - [ ] 2b: write each full trajectory to a JSONL log (messages, tool calls and
        results, tokens, time, stop reasons, errors, model, settings)
  - [ ] 2c: a cost guard that stops a run at a spend limit
- [ ] Step 3: verifiers
  - [ ] 3a: outcome checks (exact, number within tolerance, contains, regex)
  - [ ] 3b: process checks (tool called with these arguments, forbidden tool not
        called, at most N passes, nothing read outside `data/`)
  - [ ] 3c: test the verifiers themselves on hand-made trajectories
- [ ] Step 4: pass@k
  - [ ] 4a: n samples per task; pass@1 and pass@k with the unbiased estimator
  - [ ] 4b: uncertainty on small samples (confidence intervals) and run-to-run noise
- [ ] Step 5: reading trajectories
  - [ ] 5a: classify failures; cost per success
  - [ ] 5b: make one change (e.g. a tool description) and measure before and after
- [ ] Step 6: an LLM judge
  - [ ] 6a: a rubric and a judge prompt that returns a structured score
  - [ ] 6b: a calibration set with known answers; measure agreement (accuracy,
        confusion matrix, Cohen's kappa)
  - [ ] 6c: bias checks (answer position, length, same-model preference)
  - [ ] 6d: compare the judge with the verifiers where both apply; decide where to
        trust it
- [ ] Step 7: regression runs: the suite before and after a change or a model swap,
      with a pass/fail gate
- [ ] Layer 4 checkpoint: explain pass@k, verifier vs judge, calibration back; rerun
      the whole suite from a clean checkout

## Layer 5: production shell  (wraps the loop; `runner.py` and friends)

Order is deliberate: see first (tracing), survive (retries), scale (context), save
(caching), shape (structured output), defend (injection tests, then guardrails),
stream last because it changes the loop's shape.

- [ ] Step 1: cost and latency tracing
  - [ ] 1a: a record per model call and per tool call (time, tokens, stop reason,
        tool name, errors); run, pass and call spans
  - [ ] 1b: a price table kept in config and an estimated cost per run
  - [ ] 1c: a summary: totals, p50 and p95 latency, tokens per pass; compare with the
        gateway's own logs
- [ ] Step 2: retries and model fallback
  - [ ] 2a: sort errors into retry (timeout, connection, 429, 5xx) and do not retry (400)
  - [ ] 2b: backoff with jitter, honour a retry-after header, cap the attempts, and
        decide how it interacts with the SDK's built-in retries
  - [ ] 2c: fall back to another model after repeated failure
  - [ ] 2d: test all of it with a fake client that injects failures
- [ ] Step 3: context and memory management
  - [ ] 3a: measure history growth on a long task
  - [ ] 3b: trim old tool results and old turns without orphaning a `tool_use` or
        `tool_result` (the Step 4 pairing rule)
  - [ ] 3c: summarize old history with a cheap call
  - [ ] 3d: a notes file the agent writes to and reads from
  - [ ] 3e: check with an eval that nothing important was lost
- [ ] Step 4: prompt caching
  - [ ] 4a: probe that the gateway passes `cache_control` through
  - [ ] 4b: cache the tool definitions and the stable prefix; watch
        `cache_read_input_tokens`
  - [ ] 4c: find what silently breaks the cache
- [ ] Step 5: schema-validated structured output
  - [ ] 5a: a final-answer tool whose input schema is the output schema
  - [ ] 5b: validate in code; on failure send the error back and retry once
  - [ ] 5c: probe whether the gateway supports the API's native structured outputs
  - [ ] 5d: measure how often the output is valid, with the eval suite
- [ ] Step 6: prompt-injection testing
  - [ ] 6a: poisoned files and tool results (instructions hidden in data)
  - [ ] 6b: run the attacks with the Layer 4 suite, k samples each; record how often
        they succeed against today's harness
- [ ] Step 7: guardrails
  - [ ] 7a: secret and PII redaction on user input, tool results and final output
  - [ ] 7b: output checks (valid schema, length, nothing that looks like a secret)
  - [ ] 7c: treat tool results as untrusted data; least-privilege tools
  - [ ] 7d: rerun the Step 6 attacks and the normal suite; count blocked attacks and
        false positives
- [ ] Step 8: streaming
  - [ ] 8a: stream a reply and print as it arrives
  - [ ] 8b: rebuild the final message (including tool input) so the loop is unchanged
  - [ ] 8c: time to first token; what a mid-stream failure does to retries and guardrails
- [ ] Step 9: capstone: one entry point that runs the whole stack, a full eval run,
      README and ledger brought up to date
- [ ] Layer 5 checkpoint: explain each production concern back; rebuild the run
      wrapper (retry, trace, guardrail) from a blank file

## Parking lot (not planned; revisit after Layer 5)

- [ ] a shell/terminal tool (powerful and risky: plan permissions or a sandbox first)
- [ ] the memory tool, Anthropic's built-in context editing and compaction
- [ ] the SDK's Tool Runner and the Claude Agent SDK, compared with this harness
- [ ] thinking and effort settings; remote MCP servers and their authentication
