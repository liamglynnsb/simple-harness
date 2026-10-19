# Roadmap

**Where we are:** Layer 2, Step 3 (a subagent), substep 3e: scoping, so the loop refuses a tool the agent wasn't given.

Read this first at the start of every session. Tick items off as we finish them, and update the
"Where we are" line in the same commit (`scripts/check_docs.py` checks that it names the first
unticked substep, and that a step is ticked exactly when all its substeps are).
Rule: don't build ahead of the step we're on. Later layers wrap the loop; they
never rewrite it. Every layer's checkpoint also includes a documentation audit: run
`scripts/check_docs.py`, then read the README, ROADMAP, PLAN and learnings through once as if
returning after a month.

Whenever we split a step into pieces, record the pieces here as substeps (`1a`,
`1b`, ...) with the file each one produced, so the shape of the build is on record.

## Layer 1: the bare loop (no frameworks)  (the rebuild test is scheduled at the Layer 2 checkpoint)

- [x] Step 1: plain API call; show the model is stateless; print token cost per turn
  - [x] 1a: repo, venv, README, ROADMAP, `.gitignore`
  - [x] 1b: config via environment variables and `.env` (key never in the repo)
  - [x] 1c: `client.py`, the one module that knows about the gateway
  - [x] 1d: first plain call; read the raw `Message` (content, stop_reason, usage)
  - [x] 1e: two calls prove statelessness; fix by re-sending history in order
  - [x] 1f: loop over turns, printing input/output tokens per turn
        (`layer1/l1s1_stateless.py`)
- [x] Step 2: define one tool; inspect the raw `tool_use` response and `stop_reason`
  - [x] 2a: the tool definition: name, description, JSON-schema `input_schema`
  - [x] 2b: call with `tools=[...]`; read the raw `tool_use` block and
        `stop_reason: tool_use` before parsing anything (`layer1/l1s2_tool_use.py`)
  - [x] Skim the tool-use docs (done)
        (https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [x] Step 3: the loop: branch on `stop_reason`, handle `max_tokens`, iteration cap
  - [x] 3a: real calculator function in `tools.py`, plus the `FUNCTIONS` lookup
  - [x] 3b: one tool request handled by hand (`layer1/l1s3_one_tool_call.py`)
  - [x] 3c: the loop in `loop.py` (`tool_use` and `end_turn` branches, `else` stopgap)
  - [x] 3d: handle `max_tokens` properly, add an iteration cap
        (also: `__main__` guard; final `else` for unexpected stop reasons)
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

## Layer 2: extensions  <- WE ARE HERE

Order is deliberate: housekeeping, then the skill (it only adds a tool), then tests
(the safety net, before `run_agent` is changed), then the subagent (changes
`run_agent`'s signature), then the hook (restructures the tool-running code), and MCP
last (a separate program plus a protocol whose spec recently changed).
Step scripts live in `layer2/` and are named `l2s<step>_<topic>.py`. The five findings from the
Layer 1 review (tagged H1 to H5 below) are required and built in at the point each is needed;
the reasons are in PLAN.md section 1, and details for every step are in PLAN.md section 3.

- [x] Step 0: before building anything new
  - [x] 0a: rotate the the gateway key and update `.env` (H5). Done: new key in `.env`, a real call worked, old key revoked.
  - [x] 0b: the model changed from Haiku 4.5 to Haiku 5.5 (`HARNESS_MODEL`). Run the
        loop once to confirm the slug works through the gateway; check whether
        thinking tokens eat into `max_tokens=300` (empty or cut-off replies); then
        update `.env.example`, `CLAUDE.md`, and the ledger's model notes (done; the run
        worked). Found in 1d: thinking tokens do count against `max_tokens`; at 300, three
        expense-policy runs were cut off (one had only a thinking block), so it was
        raised to 1000. Everything measured in Steps 1-5 was on Haiku 4.5.
- [x] Step 1: a skill file as a tool (`skills/`, `skills.py`, `LOAD_SKILL` in `tools.py`, `layer2/l2s1_tool_cost.py`)
  - [x] 1a: measure what tool definitions cost: the same prompt with and without
        `tools`, compare `input_tokens` (H3); this is the baseline for 1e
  - [x] 1b: three skill files in `skills/` (specs in PLAN.md; Liam drafted `verify-arithmetic`, and with explicit
        permission Claude finished it and wrote the other two), each a name, a one-line
        description, then instructions: `verify-arithmetic` (behaviour: re-check every
        calculation with the inverse operation), `expense-policy` (knowledge: made-up
        rules the model can't guess; long on purpose) and a decoy `release-notes-format`
  - [x] 1c: a `load_skill` tool: the names and descriptions go in the tool's
        description and the body comes back on demand. Look the name up in a dict of
        known skills; never build a file path from the model's text. An unknown name
        returns an error that lists the real ones
  - [x] 1d: run tasks, three times each: an expense question (loads the policy), an
        arithmetic question (loads verify-arithmetic; the trace shows an extra inverse
        call), small talk (loads nothing), release notes (loads only the decoy)
  - [x] 1e: token cost over a mixed workload, not one task: on-demand adds a round trip whenever a
        skill is used, so work out the break-even share of requests that need a skill. Done as a worked
        analysis (`learnings/harness.md`, "1e: Upfront vs Fetch"); thinking tokens per pass are still
        unmeasured, and Layer 5 tracing will supply them
  - [x] 1f: break it on purpose: a vague description, and watch the skill never load
- [x] Step 2: tests for the loop with a scripted fake model (`tests/fake_client.py`, `tests/test_loop.py`)
      (H1), the safety net before `run_agent` is changed
  - [x] 2a: a fake client that returns scripted replies, with no API calls (`FakeClient`, plus a
        `text_reply` helper)
  - [x] 2b: tests: a plain finish; one tool call; several tool calls in one reply
        with the ids matched (`test_plain_finish`, `test_tool_finish`, `test_multiple_tool_finish`;
        the helpers are `text_reply`, `tool_block` and `tool_reply` in `tests/fake_client.py`)
  - [x] 2c: tests: unknown tool, a tool that raises, bad arguments; each gives a
        flagged error result (`test_unknown_tool_name_finish`, `test_tool_raise_finish`,
        `test_unknown_tool_argument_finish`)
  - [x] 2d: tests: `max_tokens` with and without text, an unexpected `stop_reason`,
        the pass cap reached (`test_max_tokens_reply_text_finish`, `test_max_tokens_reply_no_text_finish`,
        `test_other_stop_reason_finish`, `test_max_loops_finish`)
  - [x] 2e: one command runs them all; break the loop on purpose and watch the right
        test fail (a test that can't fail proves nothing). Broke it three ways: a wrong id in the error
        branch, `is_error` removed, and the cap off by one in each direction; only the tests that run
        the changed path failed, each in its own way
- [ ] Step 3: a subagent with scoped tools (`layer2/l2s3_subagent.py`)
  - [x] 3a: make `max_tokens` a parameter of `run_agent` instead of a fixed 300 (H4);
        the tests stay green (done early, before the tests existed)
  - [x] 3b: add an optional system prompt to `run_agent` (first use of `system`); sent on every pass
        when given, left out of the request when not (`test_no_system_prompt_finish`,
        `test_system_prompt_finish`); checked by breaking it on purpose (first pass only)
  - [x] 3c: a `delegate` tool: runs a fresh `run_agent` with its own history and a
        short list of tools, and returns only its final text (`DELEGATE` and `delegate` in `tools.py`;
        the child gets `read_file`, the parent only `delegate`; `loop.py` run for real)
  - [x] 3d: see the isolation: the parent's `messages` never contain the child's
        turns; write a fake-model test that proves it; compare token cost (seen in a real run; proved by
        `test_delegate_finish`, checked by breaking `delegate`; the cost comparison was closed as a worked
        analysis in `learnings/harness.md`, to be measured with Layer 5 tracing)
  - [ ] 3e: scoping: the child lacks a tool, asks for it anyway, and fails the way Layer 1 Step 5d
        taught (unknown tool)
  - [ ] 3f: limits: the child hits its own `max_loops` or errors; what the parent sees
  - [ ] 3g: is it worth it? the same task with and without the subagent
- [ ] Step 4: a hook around tool calls (`hooks.py`, `layer2/l2s4_hooks.py`)
  - [ ] 4a: pull the tool-running code out of the loop into `execute_tool`; every
        test must still pass
  - [ ] 4b: before-hooks: a list of functions called before each tool; the first one
        logs the call (replaces the trace print)
  - [ ] 4c: a blocking hook: `read_file` only inside `data/`, returning a flagged
        error result; then try to get around your own rule (`..`, absolute path,
        symlink) and turn each attempt into a test
  - [ ] 4d: watch a real recovery (H2): add a `list_files` tool held to the same
        rule, ask for a wrong path, and see the model list the folder and retry
        successfully; compare with what Layer 1 Step 5b showed
  - [ ] 4e: after-hooks: see or change a result (truncate, redact); observing vs
        changing
  - [ ] 4f: a hook that itself fails: fail open or fail closed, and why
  - [ ] 4g (optional): command hooks that read the call as JSON on stdin, like
        Claude Code
- [ ] Step 5: a tiny MCP server with one tool (`mcp_client.py`, `layer2/l2s5_mcp.py`)
  - [ ] 5a: read the current spec's stdio page; decide official Python SDK vs a
        hand-written server; write down what changed from the older handshake
  - [ ] 5b: a minimal server exposing one tool; talk to it by hand in the terminal
        (pipe JSON lines in) to see the protocol
  - [ ] 5c: harness side: start the server, list its tools, convert them to the
        `tools` format, route calls by name
  - [ ] 5d: one task using a local tool and the MCP tool; failures (server dies, bad
        reply) come back as `is_error` results; shut the process down cleanly
  - [ ] 5e: compare in-process tools with MCP: what you gain, what it costs
- [ ] Layer 2 checkpoint: explain each of the four extensions back; rebuild the hook
      mechanism from a blank file; and do the pending Layer 1 rebuild (`run_agent`
      from a blank file, nothing open)

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
        `tool_result` (the Layer 1 Step 4 pairing rule)
  - [ ] 3c: summarize old history with a cheap call
  - [ ] 3d: a notes file the agent writes to and reads from
  - [ ] 3e: check with an eval that nothing important was lost
  - [ ] 3f: keep the goal in view on a long task (noticed first-hand in Layer 2 Step 3): restate the goal
        in the system prompt or re-inject it, add a periodic progress-against-goal check, and test with
        an eval that a long task doesn't drift
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

## Backlog (wanted, not yet scheduled)

- [x] A separate markdown reference of the Anthropic SDK's data structures: `learnings/anthropic-sdk-reference.md`
      (how `Message`, its content blocks and `usage` fit together, the request shapes, a full tool round trip
      as data). Its field tables are generated from the installed SDK, and
      `.venv/bin/python scripts/gen_sdk_reference.py --check` verifies the claims in its text; rerun it after
      upgrading the SDK.

- [ ] **A follow-along course for friends**, made from these learnings once the build is done. Not started;
      decide the shape when we get there. Notes for then: each layer as concept, then what to build (a spec),
      then predict, run, compare, then break it on purpose; plumbing (fakes, helpers, test scaffolding)
      given as starter code, with the harness-defining parts left for the learner; this repo as the worked
      solution; the Python-mechanics entries in `learnings/code.md` as an appendix, not the main path;
      make the setup work with a plain Anthropic API key or any gateway; ask who the friends are and what Python
      they already know.
      A lesson for it: working with an LLM, keep checking the work against the goal (see
      `learnings/harness.md`, "Getting lost in the details").

## Parking lot (not planned; revisit after Layer 5)

- [ ] a shell/terminal tool (powerful and risky: plan permissions or a sandbox first)
- [ ] the memory tool, Anthropic's built-in context editing and compaction
- [ ] the SDK's Tool Runner and the Claude Agent SDK, compared with this harness
- [ ] thinking and effort settings; remote MCP servers and their authentication
