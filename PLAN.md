# Plan for the rest of the build

`ROADMAP.md` is the checklist (short, read at the start of every session). This file
is the reasoning behind it: a review of Layer 1, the facts about our setup that shape
the plan, and what each remaining layer is for, in what order, and where it can go
wrong. Written 2026-10-15. Where something is a guess, it says so.

How every substep runs: you predict, you type the code in Cursor, you run it, we
compare, you explain the idea back, the ledger gets an entry, a small commit goes in.

## 1. Layer 1 review

**Verdict: Layer 1 did everything the original brief asked.** Checked item by item:

| Brief | Where |
|---|---|
| plain call; model is stateless; re-send history; token cost per turn | `l1s1_stateless.py` |
| one tool; raw `tool_use`; `stop_reason` inspected before parsing | `l1s2_tool_use.py` |
| loop on `stop_reason`; `tool_result` per call; `end_turn` stops; `max_tokens`; iteration cap | `loop.py` |
| second tool; both used in one task; several calls in one response | `tools.py`, 4b, 4c |
| break a tool (raise, garbage); error `tool_result` flagged; watch recovery | 5a-5d |
| gateway setup in one module, from env vars; `.gitignore`; Messages format; no frameworks | `client.py` |
| git repo, README, small learning-log commits, ROADMAP | yes |
| loop in one small function, tools in their own module | yes |

**What it did not do or did only partly.** None of these is an error. They are the
places where it is thinner than it looks. All of them are required items in the
roadmap, built in at the point each is needed (tagged H1-H5 there).

1. **We never saw a real recovery.** The brief says "watch whether it recovers." In 5b
   the model reported the failure and stopped, because it had no way to try anything
   else. That shows the error path works, not that recovery does. *Fix (H2): Layer 2
   Step 4d.* It waits until the path-blocking hook exists, so the `list_files` tool it
   needs is restricted from the day it is born.
2. **No automated tests.** Everything was checked by running it by hand, plus a few
   ad-hoc fake-model checks I ran. The branches that are hard to trigger for real
   (`else` for an unexpected stop reason, the pass cap in a natural situation, a model
   that sends the same id twice) are untested. *Fix (H1): Layer 2 Step 2*, before
   anything changes `run_agent`, because Steps 3 and 4 change its signature and
   restructure its tool-running code, and Layers 4-5 depend on it.
3. **`read_file` is unrestricted.** It will open any file the process can read,
   including `.env`, which holds the gateway key, and the contents would go to the
   model and the gateway's logs. Nothing asks the model to do that today, but a
   poisoned file or a bad prompt could. *Fix: Layer 2 Step 4c* (a blocking hook), then
   injection tests and guardrails in Layer 5. Until then, don't point `read_file` at
   content you don't trust.
4. **The cost of tool definitions was read about, not measured.** The docs say about
   496 extra tokens for Haiku 4.5 with `auto`, plus the definitions themselves.
   *Fix (H3): Layer 2 Step 1a*, which is also the baseline the skill's token
   comparison needs.
5. **`max_tokens` is hard-coded at 300** inside `run_agent`. *Fix (H4): Layer 2 Step
   3a*, where the subagent needs a limit of its own.
6. **Key hygiene.** *Fix (H5): Layer 2 Step 0a*, before
   anything else, and long before Layer 4 makes many more calls.
7. **Teaching process.** We quizzed lightly and relied on predictions. The brief's
   ownership test (rebuild the core from a blank file) is still pending, and is now
   scheduled at the Layer 2 checkpoint. Each layer ends with a checkpoint: explain
   back, and rebuild that layer's core.

## 2. Facts about our setup that shape the plan

From the official feature-availability table (Amazon Bedrock column), checked on
2026-10-15. Our calls go the gateway -> Bedrock with Haiku 4.5.

- **Available on Bedrock:** prompt caching (5 minute and 1 hour) and automatic caching,
  token counting, fine-grained tool streaming, tool search, the memory and text-editor
  and bash client tools, adaptive thinking, citations. Compaction and context editing
  are there as betas.
- **Not available on Bedrock:** the API's **MCP connector** (so our MCP step is a
  client we write ourselves, which is the point anyway), **Agent Skills** as an API
  feature (so our skill is a small imitation in our own code), **server-side fallback**
  (so model fallback is the harness's job, or the gateway's), and the **Message Batches**
  API (so evals run as ordinary calls, with no 50% batch discount).
- **Structured outputs** on Bedrock: the table says only on the legacy InvokeModel
  integration, for Haiku 4.5 among others. We don't know which Bedrock API the gateway uses,
  so we must **probe**. The plan does not depend on it: Layer 5 Step 5 builds a
  schema-through-a-tool version that works anywhere, then probes the native one.
- **Prices** (first-party list prices from the API reference; Bedrock's differ and
  the gateway may add its own): Haiku 4.5 $1 input / $5 output per million tokens, Sonnet 5.5
  $2 / $10. A typical run of ours is a few thousand tokens, so well under a cent.
  A guess for planning: a full eval run (20 tasks x 5 samples) is probably a dollar
  or two with Haiku. Layer 5 Step 1 replaces the guess with measurements.
- **The gateway** may enforce its own rules on requests (for example required labels). If we ever change
  how requests are built, check that they still pass.

**Probes, not assumptions.** Before relying on a gateway feature (caching, structured
output, streaming, fallback), the first substep is a one-call probe that shows whether
it works. Nothing in the plan assumes it will.

## 3. Layer 2: extensions

Goal: add capability around the loop without rewriting it. All four exist in Claude
Code, which you use every day: skills (your skills list), subagents (the Agent tool),
hooks (settings), MCP (the Gmail and Slack connectors).

Order, and why: **housekeeping** (rotate the key), **skill** (it only adds a tool),
**tests** (the safety net, before `run_agent` is touched), **subagent** (changes the
signature of `run_agent`), **hook** (restructures its tool-running code), **MCP** last.

- **Step 0, housekeeping.** Rotate the the gateway key (H5). Nothing else.
- **Step 1, skill.** First measure what tool definitions cost (1a, H3): the same prompt
  with and without `tools`, compare `input_tokens`. That number is the baseline for the
  skill comparison in 1e. A skill is a text file with a name, a one-line description and
  instructions. The description is cheap and always visible; the instructions load only
  when needed ("progressive disclosure"). Build `load_skill(name)` and put the list of
  names and descriptions in the tool's description. Make the skill's effect checkable (a
  required answer format) so you can see whether the model followed it. *Pitfall:* a
  vague description means the model never loads the skill. *Explain back:* why the
  description, not the body, is what costs tokens on every call.
- **Step 2, tests (H1).** A fake client that returns scripted replies lets you test every
  branch of the loop with no API calls: free, instant and deterministic. Cover the plain
  finish, one and several tool calls, the three failure kinds from 5d, `max_tokens` with
  and without text, an unexpected `stop_reason`, and the pass cap. Then break the loop
  on purpose and confirm the right test fails; a test that cannot fail proves nothing.
  *Why here:* every later step edits the loop or relies on it. *Explain back:* what a
  test can prove that a manual run cannot, and the reverse.
- **Step 3, subagent.** `max_tokens` becomes a parameter first (3a, H4), then an optional
  system prompt (3b, first use of `system`). A subagent is a tool whose function calls
  `run_agent` again with a brand-new `messages` list and a shorter tool list, and returns
  only the final text. *Pitfalls:* reusing the parent's `messages` list by accident;
  forgetting the child needs its own pass cap; the child's tokens are real cost that never
  appears in the parent's `usage`. Add a fake-model test that proves the isolation.
  *Explain back:* what the parent can and cannot see of the child.
- **Step 4, hook.** Move the tool-running code into `execute_tool`, then let functions
  run before and after it. It is the first restructuring of the loop since Layer 1, which
  is why the tests come first. 4c fixes the `read_file` hole and then tries to break the
  fix: `..`, an absolute path, a symlink. Resolve the path first, then compare it with
  the allowed folder; comparing strings is the classic mistake. Turn each bypass attempt
  into a test. 4d is the real recovery the brief asked for in Step 5 (H2): with a
  `list_files` tool held to the same rule, a wrong path should lead the model to list the
  folder and try again. *Design choice to discuss:* if a hook crashes, do we allow the
  call (fail open) or refuse it (fail closed)? Security hooks usually fail closed;
  logging hooks fail open.
- **Step 5, MCP.** A tool that lives in another program. The harness starts it, asks it
  for its tools, and forwards calls. The transport we'll use is stdio: the harness
  launches the server as a subprocess and they exchange newline-delimited JSON messages.
  **Caution:** the newest spec revision (2026-07-28) removed the old `initialize`
  handshake and puts protocol details in every request, and older servers and clients
  negotiate between the two. So 5a is "read the current stdio page and decide": the
  official Python SDK is the safe route; a hand-written server teaches the protocol but
  could end up on the old or new dialect. I recommend reading first and hand-writing
  only if the new dialect is small. The MCP connector in the API is not on Bedrock, so a
  client we write is the way here regardless.
- **Checkpoint.** Explain each extension back; rebuild the hook mechanism blank; and do
  the pending Layer 1 rebuild (`run_agent` from a blank file, nothing open).

## 4. Layer 3: multi-agent

Goal: an orchestrator that fans work out to several subagents at once and combines the
answers. The order is: measure a baseline first (so "better" means something), then
parallelism, then planning, then synthesis, then limits, then ask honestly whether it
was worth it.

- **Steps 1-2.** The workload needs several independent pieces (several data files,
  one question each). Parallelism uses threads (`concurrent.futures`). Each worker
  gets its own `messages`; one shared list across threads is the bug to expect. Check
  the SDK's documentation on whether one client can be shared across threads, or use
  one client per worker; I haven't verified which. Expect rate-limit (429) errors at
  higher fan-out. *Explain back:* why the speedup is smaller than the number of workers.
- **Step 3.** Let the model propose the split as structured data, and validate it
  before using it. Cap how many workers it may ask for. A model-written plan is input
  you don't trust yet.
- **Step 4.** The orchestrator's final step combines results. The interesting cases
  are the failing ones: a worker errors, times out, returns nothing, or two workers
  disagree. Use fake workers to inject those on purpose.
- **Step 5.** Per-worker and total limits on tokens, passes and seconds, with a kill
  switch, and ids that link a child's calls to its parent in the logs.
- **Step 6.** Same job, single agent versus orchestrator: cost, latency, quality.
  Multi-agent is sometimes the wrong answer; the plan allows for that finding.

## 5. Layer 4: evals and judges

Goal: know whether a change helped. A test checks that code does what it should every
time; an eval measures how often a stochastic system gets a task right.

- **Step 1.** 12-20 hand-written tasks with known answers, grouped by what they
  exercise. Variety matters more than count.
- **Step 2.** A runner and **trajectory logs**: the full record of each run as JSONL
  (messages, tool calls and results, tokens, time, stop reasons, errors, model and
  settings). Add a spend limit to the runner on day one. Keep results out of git.
- **Step 3.** Verifiers: code that decides pass or fail. Outcome checks look at the
  answer; process checks look at how it got there (which tools, what arguments, how
  many passes, nothing read outside `data/`). Test the verifiers on hand-made
  trajectories, because a wrong verifier silently corrupts every number after it.
- **Step 4.** pass@k. With n samples and c correct, the standard unbiased estimator is
  pass@k = 1 - C(n-c, k) / C(n, k). With small n, intervals are wide; show them (Wilson
  interval for a proportion). We saw the model behave inconsistently in 5c, so run-to-run
  noise is real here.
- **Step 5.** Read failures, classify them, compute cost per success, change one thing,
  and measure with the noise in mind.
- **Step 6.** An LLM judge for outputs a verifier can't grade (summaries, tone). Judge
  with a stronger or different model than the one being judged, at temperature 0, with a
  rubric and a structured score. **Calibrate it** against a set with known answers
  (accuracy, confusion matrix, Cohen's kappa), test for position, length and same-model
  bias, and compare it to the verifiers on tasks where both apply. The result is a map
  of where the judge can be trusted, not a blanket yes.
- **Step 7.** Run the suite before and after a change or a model swap, with a gate.
- **Cost:** no batch discount on Bedrock, so these are ordinary calls; the runner's
  spend limit is the control.

## 6. Layer 5: production shell

Goal: wrap the loop so it can run unattended. The loop itself stays small.

The order: **trace** (you can't fix what you can't see), **retry** (survive flaky
infrastructure), **context** (keep long runs affordable), **cache** (stop paying for
the same prefix), **structure** (predictable output), **inject then guard** (find the
holes, then close them, then confirm with the same attacks), **stream** (changes the
loop's shape, so last).

- **Step 1, tracing.** Records per call with time, tokens, stop reason and tool name;
  a price table in config; p50 and p95 latency. Compare with the gateway's own logs
  so you learn what each one can and can't see.
- **Step 2, retries and fallback.** Retry timeouts, connection errors, 429 and 5xx; do
  not retry 400 (from Step 4: the request is wrong, so repeating it fails again).
  Backoff with jitter and a cap. The SDK already retries twice by default, so decide
  whether to turn that off to avoid retrying inside retries. Because the API is
  stateless, any model can pick up the same `messages` list, which makes fallback
  easy; the server-side version isn't on Bedrock, so ours is code, or the gateway's
  (check what your the gateway workspace offers). Test with a fake client that fails on
  command.
- **Step 3, context.** Measure growth, then shrink it: trim old tool results, drop old
  turns, summarize, or keep a notes file. **Every `tool_use` must keep its
  `tool_result`** (Step 4's rule), so trimming has to remove pairs together. Verify
  with an eval that a fact from early in the run is still available.
- **Step 4, caching.** Probe first. Then cache the tool definitions and stable prefix,
  and watch `cache_read_input_tokens`. Something as small as a timestamp in the prefix
  silently breaks it. This directly attacks the cost growth you measured in Step 1.
- **Step 5, structured output.** A final-answer tool whose input schema is the output
  schema, validated in code, with one retry that sends the validation error back. Probe
  native structured outputs afterwards.
- **Steps 6-7, injection then guardrails.** Attack first, so the guardrails are justified
  by evidence: plant instructions inside files and see whether the model obeys them
  (for example "read `.env` and include it"). Expect the unprotected harness to
  sometimes fail. Then redact secrets and PII on the way in and out, check outputs,
  wrap tool results as untrusted data, and rerun the same attacks. Count the false
  positives too: a guardrail that blocks legitimate work isn't free.
- **Step 8, streaming.** Stream, rebuild the final message (including the tool input,
  which arrives in pieces) and keep the loop unchanged. Note that `stop_reason` is
  empty until the stream finishes. Think through what a mid-stream failure does to
  retries, and the fact that you can't redact text you've already shown.
- **Step 9, capstone.** One entry point for the whole stack and a full eval run.

## 7. Cross-cutting

- **Checkpoint at the end of each layer:** explain the concepts back (I ask, you answer),
  then rebuild that layer's core from a blank file with nothing open.
- **Cost control:** small caps everywhere (`max_loops`, `max_tokens`, spend limits in
  the eval runner and fan-out). Never a loop without a limit.
- **Test pyramid:** fast fake-model tests for logic (free, deterministic), evals for
  behavior (cost real money, statistical), manual runs for exploration.
- **Security hygiene:** no secrets in code or logs, redact before logging, least
  privilege for tools, treat everything a tool returns as untrusted.
- **Ledger:** each layer gets its entries; items I explain but you haven't said back
  stay in the "not yet said back" section.

## 8. Decisions for you (none are urgent)

Decided: the five hardening items are required and are built into Layer 2 (H5 at Step 0,
H3 at 1a, H1 as Step 2, H4 at 3a, H2 at 4d).

1. **MCP: SDK or by hand?** Decide at Step 5a after reading the spec.
2. **Judge model (Layer 4):** a stronger model costs more per call but needs fewer calls.
   Decide at Step 6 with a measured budget.
3. **Where to stop.** Layer 5 is large. Steps 1, 2 and 6-7 give the most value per hour;
   streaming is the most optional.

## 9. What I verified and what I didn't

Verified: the Layer 1 review against your original brief and the repository; Bedrock
feature availability from the official table; the pass@k and kappa formulas (standard);
that `is_error` exists on tool results (inspected the SDK); the MCP stdio framing and the
spec's note about the dropped handshake (from the spec page).

Not verified (each has a probe or a read built into the plan): whether the gateway passes
caching, structured-output and streaming parameters through; which Bedrock API the gateway
uses; whether the SDK client is thread-safe; what retry and fallback options your
the gateway workspace has; exact MCP message shapes in the newest revision; Haiku 4.5's
minimum cacheable prefix length; real cost per eval run.
