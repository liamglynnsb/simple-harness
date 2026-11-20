# How the harness works

A model can only write text. The harness is the code around it that sends the conversation, runs the tools the model asks for, enforces the rules, and decides when to stop.

Seven figures, in the order a request meets them. They show the full design; [ROADMAP.md](../ROADMAP.md) says which layers are built so far.

## Architecture

![Architecture of the harness: a caller passes a question to run_agent, which sends requests through client.py to a stateless model API, and runs each requested tool through execute_tool, which applies hooks and calls tool functions. Tools reach a data folder, skill files, an MCP server in a separate process, and worker subagents. Evals and a production shell are planned around it.](architecture/01-architecture.svg)

*The harness is the client: it holds the conversation, the tools and the rules, and the model is a stateless service it calls. Evals drive it from outside, as the caller; the production shell wraps the loop so it can run unattended.*

**Who decides, who enforces.** The model decides what to do next: answer, or ask for a tool with certain inputs. The harness does everything else. It runs the tool, checks the request against its rules and stops the run at its limits. Anything that must always hold is code in the harness, because a prompt is only advice.

**Why one choke point.** Every tool call goes through `execute_tool`, including a worker's. That makes it the one place to scope tools, log calls, block a path outside `data/` and cut an over-long result before it enters the history.

**Why workers.** The whole history is re-sent on every call, so one agent that reads six files pays for all of them again each time. A worker reads one file in its own small conversation and returns only the answer. Six files cost about 60% fewer tokens that way; one file costs more.

## One question through the loop

The question: *Read data/a.txt and data/b.txt, and work out 12 × 12.* The three jobs are independent, so the model asks for all three tools in one reply and the run takes two passes.

![Sequence of one run: the caller's question becomes the first message; run_agent sends request 1 to the model; the model replies with stop_reason tool_use and three tool requests; each goes through execute_tool and comes back as a tool_result; run_agent sends request 2 with the whole history; the model replies with stop_reason end_turn; the text is returned as the answer.](architecture/02-loop.svg)

*One pass is one call to the model. The model keeps nothing between calls, so request 2 carries the whole history, and the list of messages is the only memory there is.*

**The pairing rule.** Every `tool_use` block needs a `tool_result` with the same id in the next message, or the API rejects the request. That is why a failed tool still gets a result, flagged `is_error`, and why a turn waits for its slowest tool.

**Other ways a pass ends**

- `max_tokens`: the reply was cut off; a cut-off tool request is never run.
- A refusal or any other stop reason: reported, never looped on.
- The pass limit, a rate limit, a timeout or the token budget: the run stops and says why.

**When the tool is delegate.** Step 3 starts a worker, which is this same loop again with a fresh message list and two file tools. Several workers run at once in threads. A worker that can't finish raises an error, so the orchestrator sees a failure and not a fake answer.

## What goes out in a request

Every call to the model is one self-contained request. The loop builds it from four parts, and the model sees nothing else.

![One request to the model, drawn as a stack: the model name and reply limit, the system prompt, the list of tool definitions, and the list of messages. The load_skill definition carries the skill menu. The model can call load_skill, and the skill's body then comes back as a tool_result that joins the messages.](architecture/03-request.svg)

*A skill is delivered through a tool: its one-line menu entry travels in the `load_skill` definition, and its full instructions enter the conversation only when the model asks for them.*

**Why skills load on demand.** Carrying every skill's full text in every request is paid on each pass, needed or not. A menu costs a fraction, and the body is paid only when used. With three small skills the two designs are close; with a large library, loading on demand wins at every usage level.

**The menu entry is the trigger.** The model picks a skill from its name and description alone, so both have to say when to use it. With a vague name and a vague description the skill was never loaded, and the answer still looked fluent.

**Prompts advise, code enforces.** The system prompt and a loaded skill are instructions the model usually follows and can skip. In one run it started calculating before it had read the skill. A rule that must hold goes in a hook.

## How the code reads a reply

The SDK turns the API's JSON into objects. A reply is one `Message`; its `content` is a list of typed blocks, and the loop tells them apart by `block.type`. The example is the reply from pass 1 above, with a thinking block and a line of text added.

![The model's reply as a tree, and what the loop does with each part. The reply is a Message object with a stop_reason, a content list of blocks, and usage. The loop branches on stop_reason, appends the whole content list to the history, skips thinking blocks, joins text blocks into the answer, runs the named function for each tool_use block with its input and answers it with a tool_result carrying its id, and counts the usage.](architecture/04-reply.svg)

*Two fields drive everything: `stop_reason` says which branch to take, and `content` holds what to act on. The model's request for a tool is data in a block; nothing runs until the harness looks the name up and calls the function.*

**Objects in, dicts out.** What comes back is objects, read with a dot: `block.name`. What the harness sends is plain dicts, written with brackets: `{"type": "tool_result", "tool_use_id": ...}`. The reply's blocks can be appended to the history as they are.

**Never assume the first block.** `content[0]` may be a thinking block, and a finished reply can hold no text at all. So the loop walks the list and checks each block's type. A tool request in a reply that was cut off by `max_tokens` is never run.

**Why the whole reply is kept.** The model has no memory, so its own tool requests have to be in the next request for the results to make sense. Dropping the assistant turn, or one of its blocks, breaks the pairing and the API rejects the call.

## Where hooks plug in

A hook is a function the loop calls at a fixed moment, without knowing what the function does. Adding a rule means adding a function to a list. The loop passes through nine such moments; the numbers on the flow match the cards.

![The loop drawn as a flow with nine numbered hook points: before the run, before each model call, on an error or retry, after each reply, before a tool, around a subagent, after a tool, when the model says it is done, and when the run ends. A card beside the flow lists what plugs in at each point.](architecture/05-hooks.svg)

*Which point a rule belongs at depends on what it needs to see and what it needs to change: a rule about one tool call sits at the tool hooks, a rule about the whole history sits before the model call.*

**How a hook answers.** A before-hook returns nothing to allow the call, or a reason to block it. The reason goes back to the model as a flagged error, so it can try something else. An after-hook returns the result, changed or not.

**When a hook crashes.** The question is whether skipping it would let something bad through. The path guard is marked critical, so its crash stops the whole run. A logger's crash is recorded and the call goes ahead. The harness records the failure itself, with the traceback.

**Hooks and prompts.** A hook runs every time. A prompt or a skill only asks the model to behave, and it can be ignored. Anything that must never happen is a hook; anything that needs judgement is advice.

## How an MCP tool is reached

MCP is a protocol for tools that live in another program. The server is ordinary code with no model in it. To the model, `count_letters` looks like any other tool: it sees a definition and gets a result. Everything between is the harness talking to the server.

![How an MCP tool is reached. At startup the harness starts the server as a separate process, asks it for its tools with tools/list, and registers a wrapper function and a definition for each. On a tool call, the model asks for count_letters, the wrapper sends a tools/call request down the server's stdin, the server runs its own code and replies on stdout, and the text comes back to the model as a tool_result.](architecture/06-mcp.svg)

*Two ids are in play and they never mix: the model's `tool_use` id pairs a request with its result in the conversation, and the JSON-RPC id pairs a line sent to the server with the line that comes back.*

**What goes down the pipe**

```json
{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
 "params": {"name": "count_letters",
            "arguments": {"word": "strawberry", "letter": "r"},
            "_meta": {"…/protocolVersion": "2026-07-28",
                      "…/clientCapabilities": {}}}}
```

**What comes back**

```json
{"jsonrpc": "2.0", "id": 7,
 "result": {"resultType": "complete",
            "content": [{"type": "text", "text": "3"}],
            "isError": false}}
```

**Three ways it fails**

- The tool ran and failed (`isError`): the message goes to the model as a flagged result, so it can correct its input.
- The request was wrong (a JSON-RPC error): retrying can't help, so it isn't retried.
- The connection failed (dead, silent for 10 s, or garbage): the server is restarted and the request sent once more.

**What the harness adds.** It converts the server's `inputSchema` into the model's `input_schema`, lets one request use the pipe at a time, and shuts the server down by closing its stdin. If the server can't be used at startup, a person decides whether to go on with the local tools.

**What it buys and costs.** The gain is a tool someone else built and maintains, in any language, with its credentials kept in the server's own environment and never shown to the model. The cost is a second process and every way it can die. For a tiny tool, a local function is simpler.

## The orchestrator and its workers

For a job made of independent pieces, one agent hands each piece to a worker. A worker is the same loop again, started by the `delegate` tool, with a conversation of its own. Time runs left to right; the bar lengths are illustrative.

![A fan-out drawn against time. The orchestrator's first pass writes six delegate calls. Six workers start together and each makes three model calls in its own conversation. The orchestrator waits until the slowest worker returns, then its second pass combines the answers, applying three rules for messy, failed and conflicting results.](architecture/07-workers.svg)

*The whole run takes two orchestrator passes plus the slowest worker, not the sum of the workers. Six reports took 11.9 s this way against 57.2 s one worker at a time, while the model calls themselves added up to 43.5 s.*

**What isolation buys.** Each worker carries only its own file, so no conversation grows large: the biggest was about 7,500 tokens, against about 43,000 for one agent reading all six. A failed worker is one flagged result; the others carry on.

**What it costs.** Every worker pays its own setup on each of its calls, and the task has to say everything, because the worker sees nothing else. For one or two small files a single agent with good instructions was cheaper and faster.

**When to use it.** Six files: about 57% fewer tokens and 40% less time than one agent. One file: about 30% more tokens. Fix the instructions first; reach for workers when the pieces are independent and each is big to read.

**What keeps it bounded.** A cap on how many workers one turn may start, and a token budget for the whole run. Each call reserves its worst case before it starts, because parallel workers would otherwise all pass the check and then spend at once.

## The parts at a glance

| Part | What it is | Use it for |
|---|---|---|
| Loop | Ask the model, run the tools it requests, send the results back, repeat until it finishes or a limit stops it. | Everything; the rest plugs into it. |
| Tools | A definition the model reads, paired with a function the harness runs. | Anything that must be exact or must touch the world. |
| Skills | Instruction files. A one-line menu is always in view; the body loads when the model asks. | Know-how and procedures. Advice only. |
| Hooks | Functions attached before and after every tool call. | Rules that must hold whatever the model does. |
| MCP | A standard protocol for tools that live in another program. | Capabilities someone else built and maintains. |
| Orchestrator and workers | One agent splits the job; workers run the pieces in parallel, each in its own conversation; the orchestrator combines the answers. | Many independent pieces that are each big to read. |
| Limits | Pass limit, reply length, per-call timeout, workers per turn, token budget for the run. | Bounding cost and a model that gets stuck. |
| Synthesis rules | What the orchestrator does with a messy, failed or conflicting worker result: extract, retry once, then report what is missing. | Partial answers that say what they lack. |
| Evals | Tasks with known answers, verifiers, repeated runs, a calibrated LLM judge. | Knowing whether a change helped. |
| Production shell | Tracing, retries and fallback, context management, caching, structured output, guardrails, streaming. | Running unattended. |
