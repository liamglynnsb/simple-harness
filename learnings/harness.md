# Learnings: the theory of the harness

What I've learned about how an agent harness works: tool use, tokens and cost, the loop's
design, errors and recovery, skills versus tools, the experiments I ran, and why the loop is
tested the way it is. Each entry is in my own words, with corrections noted. The Python and
tooling side is in [code.md](code.md); the index and open items are in [../LEARNINGS.md](../LEARNINGS.md).
The SDK's data structures are in [anthropic-sdk-reference.md](anthropic-sdk-reference.md), and the
meaning of every term in [glossary.md](glossary.md).
Newest at the bottom of each section.

## 2026-10-05 · Layer 1, setup

**The SDK needs an `api_key`; a gateway may want its own header.** The Anthropic SDK requires an
`api_key` and sends it as an `x-api-key` header. Some gateways ignore that header and check one of their
own instead, set through `default_headers`; then the SDK's key can be a placeholder and the real key rides
in the gateway's header. Both go out on every request; only one matters.

## 2026-10-05 · Layer 1, Step 1 (stateless calls and token cost)

**The model is stateless.** It has no memory between calls. Each call is one
request and one response, and the server forgets it afterward.
- The "conversation" is only the `messages` list I send each time. To make the
  model know my name, I had to include the earlier turns myself.
- My first attempt had the order backwards and ended on an `assistant` entry, so
  the model continued its own message instead of answering. The list is taken as
  the true record, so it must read like the real conversation, in order.

**Input tokens grow because of the history.** Each turn's input is roughly the
old input + the most recent output + the new question.
- Correction: I first predicted both input and output tokens would keep rising.

**Output tokens depend on the reply, not the history.** A reply's length is
decided by what was asked, so output tokens jump around instead of climbing.

**`max_tokens` caps output only, and a cut-off reply is not a simpler one.**
With `max_tokens=5` the model said "Hi, how are you" and stopped mid-sentence.
- Correction: I first read that as "less complex". The proof is `stop_reason`:
  `end_turn` means the model finished; `max_tokens` means it was cut off.

## 2026-10-05 · Layer 1, Step 2 (defining a tool, reading the raw reply)

**A tool is a name, a description, and an input schema.** The schema is JSON
Schema: an object with named properties, each with a type, plus a `required`
list. `enum` means the listed values are the only allowed ones.
- The model never runs the tool. It reads the definitions as part of its prompt
  and writes a JSON object shaped like the schema when it wants one used.

**The raw reply changes shape when the model wants a tool.** Instead of a text
block, `content` holds a `tool_use` block, with the tool's name and the inputs in
the format we defined. The inputs are an object with named fields, not a list of
values.

**The tool's name is the `"name"` field, not my Python variable.** The variable
(`calculator_tool`) exists only in my script. Only the dictionary's contents are
sent, so the model sees `calculator`.

**`stop_reason` tells me what to do next.** `end_turn`: the model finished.
`max_tokens`: it was cut off. `tool_use`: the turn is paused, and it's on me to
run the tool and send back the result.
- Correction: the model stopping isn't "done". The question isn't answered yet;
  the result of the calculation still has to come from my code.

## 2026-10-06 · Layer 1, Step 3 (the loop)

**A tool has two halves that must agree.** The definition (name, description,
schema) is what the model reads. The function is what actually runs. The
schema's field names must match the function's parameter names.

**`response.content` is a list of blocks, told apart by `type`.** The SDK turns
the API's JSON into objects like `TextBlock` and `ToolUseBlock`. To find a tool
request I go through the list and check `block.type == "tool_use"`. The reply can
hold more than one kind of block.

**The harness runs every tool I define.** The model only decides whether to use
a tool, which one, and with what inputs. Server-side tools (web search, code
execution) are the exception, and I'm not using them.

**One tool cycle, unrolled.** Ask, get `stop_reason: tool_use`, my code runs the
function, I send a `tool_result`, the model finishes with `end_turn`. The number
in the answer is the one my function computed; the model only wrote the sentence.

**Why the block `id` is sent back.** Each `tool_use` block has its own unique id.
My `tool_result` carries it as `tool_use_id`, so the model can match each answer
to its request. This matters most when one reply holds several tool requests. The
API rejects a `tool_use` with no matching `tool_result`.

**Anthropic keeps no memory of tool calls.** The model sees its own `tool_use`
blocks (in the assistant entry I appended) and my `tool_result` (in the user
entry) because I send the whole record every time. That's why
`messages.append({"role": "assistant", "content": response.content})` can't be
skipped.

**Two names for two audiences.** `CALCULATOR` is the definition (the menu): it
goes to the model as `tools=[...]`. `FUNCTIONS` maps a tool name to the real
Python function (the kitchen): my loop uses it to run what the model asked for.
The model needs the first to know what it can ask for; my code needs the second
to do it.
- Correction: `tools` must be a **list** of definitions, even for one tool, and
  `FUNCTIONS` is a dict, so `FUNCTIONS[0]` is a `KeyError`; it's looked up by key.

**`end_turn` needs no second call.** When `stop_reason` is `end_turn`, `response`
already holds the final answer. Take the text and `return` it. A second call would
send a list ending on the assistant's own turn.

**`stop_reason` has seven values, not three.** `end_turn`, `max_tokens`,
`tool_use`, `stop_sequence`, `pause_turn`, `refusal`,
`model_context_window_exceeded`. A loop that treats "not `tool_use`" as "done"
would report a refusal or a cut-off as a good answer.

**The iteration cap uses `for _ in range(max_loops)`.** `range(n)` yields `0` to
`n-1`: it starts at 0 and the upper bound is excluded, so `range(10)` is exactly 10
passes. The `for` takes the next number each pass and ends when they run out.
`max_loops=10` in the `def` is a default: used when the caller passes nothing,
replaced when the caller passes a value. Defaults go after required parameters.
- Every normal exit inside the loop is a `return`, so the line **after** the loop
  is reachable only if all passes were used with no answer. That's where the
  "max loops reached" message goes, with no flag or counter to manage.
- The cap check is a separate question from the `stop_reason` chain ("how many
  passes?" vs "what do I do with this reply?"). Tested with `max_loops=1`: the
  tool runs on pass 1, but its result is never sent back, so the cap message
  returns.

**The `max_tokens` branch: the loop collects, the decision comes after.** Set the
empty string before the loop, add each text block's text inside it, then decide
after it: text plus a note on a new line, or the note alone if there was no text.
- Don't `return` inside the collecting loop (it stops at the first block) and
  don't reset the string inside it (it forgets earlier text). Don't index
  `content[0].text`: a cut-off reply may not start with a text block, and a
  truncated tool request must never be run.
- `if text_results:` is true when the string is non-empty. Empty strings, lists,
  dicts, `0` and `None` are falsy.
- The other block types (thinking, server-side tool results) don't appear in this
  setup, so checking `block.type == "text"` and ignoring the rest is safe.

**A final `else` stops unexpected stop reasons from looping.** An `else` belongs
to whichever `if` it lines up with, by indentation. Without one on the stop-reason
chain, a `refusal` would match nothing, the loop would re-send the same messages
every pass, and I'd pay for each call until the cap hit, with a misleading message.

**The model decides when it's done; the harness reads the signal.** Nothing in my
code says "stop after the calculation". After the tool result comes back, the model
writes its answer and emits an end-of-turn marker, which the API reports as
`stop_reason: end_turn`. The model could equally ask for another tool, so it
controls how many passes happen.
- Division of labor: the model decides what to do next; the harness executes it,
  feeds results back, and enforces limits (cap, `max_tokens`, unexpected reasons).

**A finished reply could in principle contain no text.** Reasons I know of: only
non-text blocks (thinking, server tools; not in this setup), or an empty reply
right after tool results (a known quirk, seen when extra text is added next to the
`tool_result` blocks; I send only the results). I haven't seen it happen here.
To diagnose, print `response.stop_reason`, the list of block types, and
`response.usage.output_tokens`, and look at the last messages sent. How to handle
it (retry, message, error) is a Layer 5 decision.

**Tool definitions cost tokens on every call, so the harness chooses what to send.**
Like the history, definitions are re-sent each request (stateless). A thousand tools
would add a huge amount of input every time and make the model worse at choosing.
Nothing filters automatically; options are routing a short list, on-demand tool
search, or grouping behind a subagent. With a handful of tools, send them all.

## 2026-10-06 · Layer 1, Step 4 (a second tool, several calls in one reply)

**Adding a tool touches `tools.py` and the call site, not the loop.** A tool is a
definition, a function, and a `FUNCTIONS` entry. `run_agent` takes whatever tools
it's given, so only the place that calls it changes (`[CALCULATOR, READ_FILE]`).
The schema's property name, its `required` list, and the function's parameter
must all agree. A mismatched `required` list was caught while adding `read_file`.

**The model got the file path from my question.** Nothing in the code names the
`data` folder. A relative path is resolved from the folder the script is run in,
not from where `loop.py` lives (unlike `.env`, which is found next to
`client.py`). Searching for files needs another tool (like `list_files`), not a
change to the loop: the tool supplies the capability, the model the judgment.

**Whether the model batches tool calls depends on whether one needs another's
result.** In 4b the calculator's numbers had to come from the file, so it took
separate passes (read, then calculate, then answer). In 4c ("read a.txt and
b.txt, and also compute 12 x 12") the jobs were independent, so one reply held
three `tool_use` blocks and the whole thing took two passes.
- Correction: I predicted the reads together, then the calculation. I had assumed
  the calculation needed numbers from the files; it didn't.
- Batching is the model's choice, not a guarantee. Fewer passes means fewer tokens,
  since every pass re-sends the history.

**Every `tool_use` needs its own `tool_result`, and the API checks.** The message
list alternates: user question, assistant with N `tool_use` blocks, user with N
`tool_result` blocks, assistant text. The ids pair them. When I sent back only one
of three, the next call failed with a 400 that named the two unanswered ids.
- My loop didn't fail by itself; the server validated the list on the next call.
- A 400 `BadRequestError` means the request is invalid, so retrying changes
  nothing. A timeout (`APITimeoutError`) is a network problem, so retrying can help.
  Neither is a `stop_reason`; both raise exceptions.

## 2026-10-15 · Layer 1, Step 5 (when tools fail)

**An unprotected tool failure takes down the whole run.** Asking for a missing file
made `open()` raise `FileNotFoundError`. Nothing caught it, so it travelled up
through `run_agent` to the top of the script and the program died, and the model
never learned what happened. Reading a traceback: start at the bottom line, then
find the last line that points into my own files.

**Catch the failure and send it back as an error result.** `try` wraps only the one
risky call, `except Exception as e` appends a `tool_result` with the matching id,
the error text, and `"is_error": True`, and `else` appends the normal result.
`is_error` is a real optional field on `tool_result` in the SDK. Sending an error
result still answers the request, so the API's one-result-per-request rule holds.
For a missing file the model reported the problem and asked for a path; it didn't
retry because it has no tool for looking around.

**An error in processing is different from an error in meaning.** With the
calculator returning `"banana"` there was no exception, so `except` and `is_error`
never ran: the harness can't tell nonsense from an answer.
- Correction: I predicted the model would return "banana". It used its own
  arithmetic instead. For 12 x 12 it said nothing about the broken tool; for
  1234 x 5678 it said the calculator gave an unexpected result. Its handling isn't
  consistent, and a silently broken tool can still produce a good-looking answer.
  That's the case for tracing every tool call and result (Layer 5).

**The error message is part of whether the model can recover.** An unknown tool
name raises a `KeyError` whose text is just the name (`'weather'`). Bad arguments
raise a `TypeError` that names the function and the problem, which is useful. So
the harness checks for an unknown tool and sends `Unknown tool: X. Available tools:
...`, and everything else sends `"Error: " + str(e)`, both flagged `is_error`.
- When one line has two ways to fail (look up the function, then call it), split
  it into two steps so each can be handled. A condition I expect can happen is
  better tested directly than caught.
- Mistake worth remembering: moving the unknown-tool check into the `except` left
  `result` unassigned for every other failure, so it would have crashed or sent the
  previous tool's result. Tracing one case by hand through the code caught it.

## 2026-10-15 · Layer 2, Step 1 (a skill as a tool)

**Tool definitions cost tokens, and the API adds a prompt of its own.** The same
message with and without tools differed by about 500 input tokens (I guessed 100). My
two definitions are about 130 to 175 tokens. The rest is a fixed tool-use system prompt
that the API builds when `tools` isn't empty: fixed instructions, then my definitions
as JSON Schema, then any system prompt, then the tool settings (docs: 286 tokens for
Haiku 5.5 with `auto`, 406 with `any` or `tool`; its exact wording isn't published). It
is paid on every request, because the API is stateless. `tool_choice`: `auto` lets the
model decide, `any` forces some tool, `tool` forces a named one, `none` forbids tools.
Forced use skips thinking.
- Correction: it isn't just "appended"; the API assembles it. I call the model through
  Bedrock, so I can't say which layer does the assembling, but the measured overhead
  shows it happens.

**A skill is a header and a body.** The header (a name and a one-line description) is
cheap and always visible; the body loads only when the model asks for it. The
**name and description together are the trigger** (the menu entry is `name: description`): they have to
say *when* to use the skill, not what it does. Either half can carry it, as 1f showed.
My first description for `verify-arithmetic` said what it does ("verifies any arithmetic
by solving the inverse"), so the model had nothing to match a request against.
- Three skills, three jobs: `verify-arithmetic` changes *behaviour* (the model already
  used the calculator unprompted, so "use the calculator" would have shown nothing);
  `expense-policy` carries *knowledge* the model can't guess (a right answer proves it
  was loaded); `release-notes-format` is a decoy, to test that it picks the right skill or none.

**Edge-case rules have to be right.** I wrote "if b is 0 the inverse can't be run", and
that was too broad. Only multiplication breaks, because its inverse divides by `b`; the
fix is to divide by the other factor, and dividing by zero is already an error in the
original calculation. A model follows a wrong rule exactly as written, so one wrong edge
case is worse than none.

**Read once at startup; look up on demand.** `read_skills` runs once and builds a dict:
name -> {description, body}. `load_skill(name)` only looks in that dict. The definition
(with the menu) goes to the model on every request; the function runs only if the model
asks for it. A missing or broken file therefore fails when the program starts, where I
see it, not in the middle of a conversation.

**Exceptions: the tool raises, the loop catches.** An exception is an error signal that
travels up through whoever called the function until something catches it. `if` + `raise`
*produces* the error (throwing); `try` / `except` *responds* to it (catching). In the
harness: `load_skill` checks the name and raises with a message only it can write (it
knows the valid names); the loop has one broad `try` / `except` that guarantees every
request gets an answer, flagged `is_error`.
- Why raise, not return a message: a returned string looks like data and gets no flag
  (the banana problem in 5c). And an unhandled `KeyError` reaches the model as just
  `Error: 'bogus-skill'`. Here the model already has the valid names (the menu and the
  `enum`), so it would probably recover anyway; the clear message is a habit and a
  judgment call, not a necessity for this one tool.
- Correction: I first said the catch goes inside `load_skill`. It doesn't. The tool
  raises; the loop catches. A `try` / `except` inside a tool would only be there to
  translate an error, not to handle it.
- Where to handle errors: check at the edges where outside input enters, raise where I
  know the details, catch where I can do something useful. Never swallow an error
  (`except: pass`). Weigh how likely a failure is and how bad it is: a rare `../.env`
  path matters. Two styles have names: "look before you leap" (check first) and "easier
  to ask forgiveness than permission" (try it and catch).

**Thinking tokens count against `max_tokens`, and a description can be enough to trigger a skill.**
Running the expense question three times with `max_tokens=300`: every run called
`load_skill("expense-policy")`, and every run was cut off ("Response stopped; max tokens
reached"). The blocks showed why: `['thinking', 'tool_use']`, then `['thinking', 'text']`
or, in one run, only `['thinking']`. Haiku 5.5 thinks by default, and that thinking uses
the budget. The `max_tokens` branch handled the no-text case as designed (it returned just
the note). I raised the limit to 1000; making it a parameter is step 3a.
- Correction: I predicted the model might not load the policy unless I said I was from
  Fernbrook. It loaded it every time: the first clause of the description ("whether
  something can be expensed or reimbursed") was enough. The answers quoted the $37 cap, a
  number it couldn't have guessed, which shows the skill was used.
- For small talk, three runs made no tool calls (no false alarm), but the replies
  described the skills ("arithmetic with checks", "Fernbrook Co. expense policy"). The
  menu is visible to the model on every request, so it shapes answers even when nothing
  loads. Anything in a description is effectively public to the model.

**Skill selection worked, but a skill advises; it doesn't enforce (1d).** Four tasks, three
runs each, 12 of 12 correct: the expense question loaded `expense-policy`, arithmetic loaded
`verify-arithmetic` and then called the calculator twice (the inverse check, where before it
made one call) in the exact two-line format, small talk loaded nothing, and release notes
loaded only the decoy.
- The route varied. In two arithmetic runs the model asked for the skill and the first
  multiplication in the *same* reply, so it started calculating before reading the skill; in
  one it went skill first. For this skill the order doesn't matter. For a rule that must hold
  it would, so: soft guidance is words in the description or skill; hard guarantees are code
  (a hook that refuses a call until the skill is loaded, or `disable_parallel_tool_use` in
  `tool_choice`, which limits the model to one tool call per reply). Ask: what happens if the
  model ignores it?
- Where a skill leaves room, the output varies. The release-notes skill said "headings"
  without saying how, and one run used `## Added` while two used plain `Added`. To get
  identical output, be exact.

### 1e: Upfront vs Fetch, the token comparison (worked numbers)

The question: is it cheaper to carry every skill's instructions in every request (**Upfront**,
no `load_skill` tool), or to carry only a short menu and load a body when the model asks
(**Fetch**, what I built)?

| | **Upfront** | **Fetch** (`load_skill`) |
|---|---|---|
| In every request | all 3 skill bodies, about 800 tokens | the menu only, about 144 tokens |
| How the model gets the instructions | already there | it calls `load_skill` (an extra pass) |

Unit: input-token equivalents, where 1 input token = 1 and 1 output token = 5 (output costs
about five times as much, per the price list). Thinking and tool calls are output.

**One request:**

| Request type | Upfront | Fetch |
|---|---|---|
| doesn't need a skill | 800 | 144 |
| needs a skill (100 thinking tokens on the loading pass) | 800 | 1,255 (605 input + 650 for the extra pass's thinking and tool call) |

**100 requests, three skills, 100 thinking tokens:**

| Requests needing a skill | Upfront | Fetch | Cheaper |
|---|---|---|---|
| 10% | 80,000 | 25,510 | Fetch by 68% |
| 30% | 80,000 | 47,730 | Fetch by 40% |
| 60% | 80,000 | 81,060 | about equal |
| 80% | 80,000 | 103,280 | Upfront by 23% |

With 300 thinking tokens the crossover drops to about 30%. **The thinking on the loading pass is
the swing factor.**

**20 skills (menu 1,040 tokens, bodies 5,400), 300 thinking tokens:** Fetch is cheaper at every
usage level (by 64% at 30% use, 47% at 60%, 25% at 100%).

Takeaways:
1. Fetch saves nearly everything on requests that don't need a skill.
2. With three small skills it's close, and Upfront can win if most requests need a skill and the
   loading pass thinks a lot.
3. With a big library, Fetch wins everywhere. That is the real reason skills load on demand.

Assumptions: sizes are estimated (characters / 4); the thinking amount is a guess, not
measured; one skill per request. Prompt caching (Layer 5 Step 4) could make Upfront much
cheaper, because cached input costs about a tenth. Passes multiply both designs: every
pass re-sends what's in the request.
- Correction: my first version of the comparison forgot the passes and mixed input and output
  tokens as if they cost the same. I also left "on-demand" undefined in the first table,
  which confused the comparison; "Upfront" and "Fetch" are clearer names.

**1f: breaking discovery on purpose. A miss looks fluent.** Two experiments on `release-notes-format`:

| Name | Description | What the model did |
|---|---|---|
| `release-notes-format` | clear | loaded it |
| `release-notes-format` | "skill file" (vague) | **still loaded it** (the name carried the signal) |
| `skill-file-test` | "skill file" (vague) | **never loaded it** (blocks: `['text']`, no tool call) |
| vague | clear | not tested; I'd expect it to load |

With both halves vague, the answer ignored the skill: "Here are release notes for the update:" instead of
a one-line summary, `**New Features**` / `**Bug Fixes**` / `**Other Changes**` instead of Added / Changed /
Fixed, an invented "Other Changes" filler and a made-up version number (it admitted both), and extra text
after the last bullet. Nothing crashed and nothing was flagged. Only checking the output against the skill's
rules reveals a miss, which is the case for Layer 4 verifiers.
- Correction: I said "the description is the trigger". It's the name and description together; either can
  carry it. Make both say what the skill is for.
- Correction: when it answered without the skill I called that "its own thinking". It used its general
  habits; that run had no thinking block at all. Thinking is the separate scratch-space feature.
- A comment in a skill's *header* is silently ignored (my reader takes only the first two header lines); a
  comment in the *body* would be sent to the model and paid for. To switch a skill off, move it out of
  `skills/` or rename it so it doesn't end in `.md`.

### Tools vs skills, and which extension for which job (decision guide)

One sentence each: a **tool** is code the harness runs, and it *does* something (computes,
fetches, writes, checks). A **skill** is text the model reads, and it teaches the model *how*.
In my harness the line is easy to miss because `load_skill` is itself a tool: the skill is
delivered through a tool but is data, not code.

| | **Tool** | **Skill** |
|---|---|---|
| Who does the work | my code, identical every time | the model, applying the text with judgment |
| Reliability | deterministic; a tested function is right | probabilistic; usually followed, can be skipped or misread |
| Can it change the world? | yes (runs real code) | no, it only advises |
| Can a rule be enforced? | yes, the harness can refuse or validate | no, it's a request |
| Who can edit it | a programmer | anyone who can write text |
| Cost | the definition on every request, plus a pass per call | the menu on every request, plus the body when loaded |
| Best at | exactness, data, side effects | judgment, procedures, style, domain know-how |

Rules of thumb:
1. If a correct answer can be *computed*, use a tool (a calculator beats a skill saying "multiply
   carefully").
2. If it needs *judgment guided by know-how* (a house style, a workflow, a policy to interpret),
   use a skill.
3. If a rule must *never* be broken, don't use a skill. Use code: a tool that refuses, or a hook.
   A skill asks, and the model can race ahead of it (seen in 1d).
4. They combine: `verify-arithmetic` told the model how to use the calculator. Tools are the
   verbs, skills are the playbooks.

The whole Layer 2 map:

| Job | Use |
|---|---|
| act or compute exactly | tool |
| teach a procedure or supply know-how | skill |
| enforce a rule | hook (code) |
| keep a messy subtask out of the main conversation | subagent |
| reach a capability that lives in another program | MCP |

Why it matters: a wrong choice fails quietly. A policy written as a skill can be misapplied while
sounding sure; a tool with a huge description inflates every request; a "must never" rule written
as advice is a hole. My own experiments showed each of these.

## 2026-10-15 · Layer 2, Step 2 (tests with a scripted fake model)

**Why test the loop with a fake model, not the real one.** (1) I can't control what the real model
replies, so a test can't depend on it (non-determinism, variation and unpredictability are one
problem). (2) I can't reach the rare branches on demand (an unexpected `stop_reason`, the pass
cap). (3) Every real run costs money and time. A fake returns exactly the replies I script, in
order: free, instant, identical every time.
- The limit: a fake model tells me whether *my code* handles each situation correctly. It can't
  tell me how the *real model* behaves (does it pick the right skill, follow the rules, recover
  from an error). That is what evals measure in Layer 4. Fakes test the harness; evals measure the
  model inside it.
- Correction: I said "we still need to test the client side". The harness *is* the client (the
  program that sends requests); the model is the server. What the fake can't cover is the
  *server* side, the model's behaviour.
- What the loop needs from a client: a `messages.create(...)` method, and from each reply
  `stop_reason`, `content`, and per block `type`, `text`, `name`, `input` and `id`. A fake only
  has to look like that.

**Assert the effects, not only the output (2e).** I broke the loop on purpose, with the cap one too low,
and `test_max_loops_finish` still passed its check on the returned string (`"Error: Max loops reached"`),
because the loop did still hit the cap, just earlier. It failed on `len(messages)` (5 instead of 7),
since that count shows how many passes actually ran. Different bugs can give the same output, so a test
should also assert the effects that tell the right behaviour from the likely wrong ones: the messages,
the number of calls, and what's left of the script.
- Correction: I first called this making the asserts "MECE". Assertions can overlap, and the call count
  would have caught this bug too, so they needn't be mutually exclusive. They can't be exhaustive
  either, because I can't list every failure mode. The practical rule is to think of the plausible
  bugs and confirm that some assertion would catch each, then prove it by breaking the code on purpose.

## 2026-10-19 · Layer 2, Step 3 (a subagent)

**When delegating pays off (3d, worked analysis, not measured).** The API is stateless, so everything in
the parent's history is re-sent on every later pass. Delegating pays off when the main chat would otherwise
carry a lot of tokens for something that is a one-off and won't be referenced again: the child reads the big
file, and only its short answer enters the parent's history. If I'll keep referring to the content, or want
it handy, I might as well keep it in the main chat, because delegating again would cost another full child
run.
- Explained to me, not yet said back: delegating has a fixed cost (the child's own calls, each with the
  tool-use prompt and its tool definitions), so for a tiny file it costs more. The saving also compounds
  only if the parent makes several more passes after the read; with an answer on the very next pass the
  two setups cost about the same. And the parent receives only the child's answer, so detail it leaves out
  has to be fetched with another delegation.
- Not measured: the real totals. The cost part of 3d was closed as a worked analysis. Layer 5 tracing will
  record `usage` per call, and then the comparison can be run from real runs.

**Getting lost in the details while building (noticed first-hand, Layer 2 Step 3).** I noticed that an LLM
collaborator can get lost in the details and lose sight of the bigger picture, as we did here. Over the
Layer 2 tests and the delegate step, the work drifted into Python mechanics (`*blocks`, `monkeypatch`,
import cycles, dict syntax), while the goal was understanding the harness.
- Explained to me, not yet said back: each step looked reasonable on its own, and the assistant follows the
  current thread. Nothing in the process checked the work against the goal until I stopped and asked
  whether it was still serving it. So the person directing the work has to do that check: now and then ask
  "does this still serve the goal?" and write the goal where the assistant reads it (here, `CLAUDE.md`).
  This matters for agents in general: a long task can drift in the same way, so a harness may need an
  explicit check of progress against the goal. It is a Layer 5 item (Step 3, context and memory).

## 2026-10-21 · Layer 2, Step 4 (hooks)

**Hooks.** A hook is a point where I can attach my own function to a process without changing the process.
Before-hooks run before a tool executes, and after-hooks run after it has. The loop doesn't name the
functions; it calls whatever is registered in a list (`BEFORE_HOOKS`), so adding a rule is adding a function
to the list. Calling functions directly would also work, but then the loop has to know each one by name.
- Correction: I first thought a hook is "a manual check I create". A hook isn't necessarily a check. It can
  observe (the call trace), decide (block or allow), or change something (after-hooks, 4e). The logging
  counts as a hook because of where and how it attaches, not because it checks anything.

**What should be a hook.** A rule that applies to any tool that uses local files should be a hook, because
one function covers all of them. A rule used in a single place, like expense formatting, stays where it's
used. The test is whether the rule spans several tools and must hold whatever the model does.

**How a hook blocks (decided, 4c).** It returns a reason string to block, and `None` to allow, because a
block is an intentional policy decision and not an error in the code. An exception means a bug. A file
scope is defined once, at the start, for the whole harness (just `data/`), and it is enforced by resolving
the real destination of a path (`..` and symlinks included), since the rule is about where a path ends up
and not how it is written.

**Recovery needs a way to look and an inferable target (4d).** With `list_files` added, the model recovered
from the near-miss path "data/number.txt" by listing `data/` and reading `numbers.txt`. For the path
"data/magic.txt", with no likely match, it listed the folder and then stopped and asked. The harness provides the means to
recover, and it doesn't guarantee a retry.
- Explained to me, not yet said back: a hook is deterministic: it runs every time, unlike a prompt, which
  only asks the model to behave. Hook points beyond tools: before a run starts, before each model call
  (trim history, change the system prompt), after each model reply, when the model says it's done, when a
  run ends, on errors and retries, and around subagents. Several Layer 5 items are hooks at those points
  (tracing, retries, context trimming, guardrails). The costs are indirection (the order of hooks can
  matter, and what happens before a tool is spread across a list) and the question in 4f of what a hook
  that crashes should do. For a very small harness, putting everything in one place is fine.

**Where hooks are normally run (hook points).** *Explained to me, not yet said back.* Tool calls are only the
most common point; the loop passes through several moments where the harness has information and control.
In terms of `run_agent`:

| hook point | where in the loop | what it could do | in this project |
|---|---|---|---|
| before a run starts | before the first model call | check or rewrite the user's input, add context, start a trace | not built |
| before each model call | just before `client.messages.create(...)` | trim old history, change the system prompt, count tokens, enforce a budget | Layer 5 Step 3 (context), Step 4 (caching) |
| after each model reply | right after the reply arrives | log `usage` and `stop_reason`, check the output, spot a refusal | Layer 5 Step 1 (tracing) |
| before a tool | `execute_tool`, before the call | log, allow or block | built: `BEFORE_HOOKS` (4b, 4c) |
| after a tool | `execute_tool`, after the call | observe, trim or redact a result | Layer 2 Step 4e |
| when the model says it's done | the `end_turn` branch | check the answer; if it isn't good enough, send the model back for another pass | not built |
| when a run ends | after the loop returns | write the trace, report the cost | Layer 5 Step 1 |
| on an error or a retry | around the model call | retry, back off, switch model | Layer 5 Step 2 |
| around a subagent | around `delegate` | trace which agent did what, apply the child's own rules | Layer 3 Step 5 |

- As far as I know, Claude Code's own hooks follow the same pattern: its documented hook points include before and
  after a tool call, when a prompt is submitted, when the model stops, and when a session starts or ends. That is
  from memory of its docs, so check the names there before relying on them.
- Which point a rule belongs at depends on what it needs to see and what it needs to change: a rule about
  one tool call sits at the tool hooks, a rule about the whole history sits before the model call.

**A tool result that is far too long: truncate or summarise (4e).** A very long result goes into the history and is
re-sent on every later pass, slows every call, fills the context window, and can bury what matters. I chose
to truncate: if a result is above size X, cut it to X. It has to happen before the append: the after-hook runs
between the tool returning and the `tool_result` being built, so the long text never enters `messages`.
- Explained to me, not yet said back: the trade-offs.

| | truncate | summarise with a model |
|---|---|---|
| cost | free and instant | an extra model call per long result: money and time |
| predictability | the same result every time | varies from run to run |
| what is kept | the start; the tail is lost (the answer may be in the tail) | the gist, but details can be dropped or even invented |
| risk | the model may take a partial result for the whole | the file's own text is fed to a model, so hidden instructions in a file could steer the summariser |
| complexity | a few lines | a nested model call inside a hook, which raises 4f (what if it fails?) |

  Truncating has one rule that matters: the model must not mistake a partial result for the whole, so the cut
  result carries a note saying it was cut and how much was shown of how much existed. Summarising old history
  is planned for Layer 5 Step 3c.

**Truncating a result trades reach for tokens (4e demo).** Truncating a result is good for controlling tokens and
message size, at the cost of what the model can reach: if the answer, or context it needs, is in the part that was
cut, it isn't there. With `data/long_notes.txt` (17,115 characters, answer on the last line) the model saw the
first 4,000, couldn't find the answer, and said so, because the note carried the sizes. Truncation needs a way to
get the rest, or the information is unreachable.
- Correction: I first called the cost "accuracy". The model stayed accurate; what it lost was completeness. The note
  kept the failure honest instead of producing a wrong answer.
- Explained to me, not yet said back: the fix I chose is paging: `read_file` takes an optional `start` position, and
  the note says how to continue ("call again with start=4000"). The model chooses `start` on each call, as it
  chooses any tool input. The harness keeps control of the chunk size (set by the after-hook), the path rule (the
  before-hook runs whatever `start` is) and the pass limit. A subagent that summarises the file would not solve it
  alone, because the after-hook cuts the child's reads too; a child that pages through the file and returns only the
  answer combines the two ideas. A search tool (find lines containing a word) is a third option.

**Paging lets the model reach the whole file while keeping each result small (4e).** With `start`, the model read a
17,115-character file in five bounded chunks and found the answer on the last one. It didn't keep a count between
calls; the history, re-sent each time, held every chunk. The model's claim "after 200 lines of filler" was
supported by the line numbers in the text, which is what made it checkable.
- Correction: paging bounds the size of each result, not the total. Every chunk stays in the history and is re-sent
  on each later call, so reading all of a long file costs more input in total than one full read; the saving comes
  from stopping early, trimming old chunks, or letting a subagent page and return only the answer.
- Explained to me, not yet said back: by the last call the whole file was in the model's input, in five pieces. The
  model doesn't consult an index; it reads over text it has been sent. `start` controls how the pieces get there,
  and they stay until something removes them.

**When a hook crashes: ask whether skipping it would let something bad through (4f).** A crashed hook doesn't return
anything; it raises, and the exception travels up until something catches it. If nothing does, the run stops. What
the harness should do depends on what the hook is for, and the question to ask is: does this hook raise a blocking
issue, security or otherwise? The path guard enforces a security rule, so a crash should stop the whole run. The
logger only observes, so a crash should be recorded and let through, because it has no risk and blocking would cost
a whole run. Either way the harness records the failure itself, with the hook's name, the tool, the input and the
traceback, so we never depend on the model to report a bug in our own code. The model can't see any of this and
only gets the normal result.
- Correction: I first thought `log_call` never returns `None` and so never blocks. A Python function with no
  `return` returns `None`, which is exactly how a hook says "no objection". A crash is different: it isn't a return
  value but an exception. Also, a blocked logger call wouldn't necessarily stop the run; it comes back to the model
  as an error, but the task would likely fail anyway.
- Explained to me, not yet said back: `@critical` is a decorator, shorthand for
  `guard_file_paths = critical(guard_file_paths)`, which puts a label on the function. A bare `raise` inside an
  `except` re-raises the caught exception, and `except HookFailed` has to sit above `except Exception` because the
  first matching clause wins. `getattr(hook, "critical", False)` reads the label and defaults to not-critical for
  hooks without one. The log is opened in append mode and never resets; the run id and turn number are planned for
  Layer 5 tracing, with only a timestamp so far.

## 2026-10-21 · Layer 2, Step 5 (MCP)

**How a harness works with MCP (before reading the spec).** An MCP tool lives in a separate program instead of a
Python function in our own process. At startup the harness starts the server, asks it what tools it has, converts
the definitions into the model's `tools` format, and keeps a table of which server each tool name belongs to. The
model chooses tools exactly as before; the harness routes the call. To the server the harness sends the tool's name
and input, and the model's `tool_use` id stays with the harness, which puts it on the `tool_result`, with `is_error`
for a failure. Everything between is internal to the harness and the server, so, as with a subagent, the model only
sees a tool call and a tool result.
- Correction: I first called MCP "a universal format"; it is a protocol, a standard way of having the conversation.
  The server is ordinary code with no model in it, and the model, the loop and the reasoning live in the host. The
  routing logic is on the harness side.

**Credentials never go through the model.** Authentication is part of the connection between the harness and the
server, not of the model's messages. The best protection is that the model never has the secret at all: give the
model capabilities, not credentials.
- Explained to me, not yet said back: the risk is that a secret in the context can be written out (repeated in a
  reply or placed in another tool's input), and everything in the context travels: it is re-sent on every call, so it
  also reaches the gateway and provider and ends up in logs and traces. A local server over stdio is started as a
  child process and talks over its standard input and output; secrets reach it through its environment. A remote
  server uses an OAuth sign-in at the connection layer. There are two ids: the model's `tool_use` id, and the id on
  each request to the server, which only matches replies to requests. As I understand it, the messages are JSON in a
  request-and-reply style called JSON-RPC; to be confirmed against the spec in 5a.

**What changed in how a client and an MCP server agree to talk (5a).** Instead of aligning on the ways of talking
upfront, the current protocol includes them with every message: each request carries the protocol version and the
client's capabilities in its `_meta` field, and the server remembers nothing between requests. We keep that
information and send it each time. After a server restart there is nothing to resume, so we start it again and
retry the request that was in flight; the old design held the agreement in a session on the server, so a restart
meant doing the handshake again.
- Explained to me, not yet said back: the old design (revisions up to 2025-11-25) opened with an `initialize`
  handshake; the current one (2026-07-28) has none, and an optional `server/discover` request asks for the
  supported versions and capabilities. Messages are JSON-RPC 2.0, one per line on the server's standard input and
  output, which carries nothing else; logging goes to standard error; shutdown means closing the server's input. A
  tool definition has `name`, `description` and `inputSchema`; a call has `name` and `arguments`; a result has
  `content` and `isError`. An unknown tool or a malformed request is a JSON-RPC error, while a tool that ran and
  failed is a normal result with `isError: true`. Stdio servers take credentials from the environment. State that a
  tool needs across calls is carried by an explicit handle that the model passes on.

**stdin, stdout, and the pipe (Layer 2 Step 5).** Every program has standard streams: stdin for what it reads, stdout
for what it writes, stderr for logs. In `echo '{"a": 1}' | python -c "..."`, the `echo` did print, but to its stdout,
and the `|` connected that stdout to the second program's stdin; so nothing from `echo` appeared on the screen, and
the second program's own stdout, `2`, is what I saw. That is how the harness will talk to an MCP server over stdio:
it starts the server and writes JSON lines to its stdin, and reads JSON lines from its stdout. No network is involved.
- Correction: I first thought `echo` "doesn't print"; it does, to its stdout, which the pipe redirects.

**A hook as an external command, and why I dropped 4g.** A hook can be a separate program instead of a Python
function: the harness launches it, writes the tool call to its stdin, and reads its verdict from its exit code and
output. It runs at the same moment as any before-hook, and it pays off when the rule's authors aren't the harness's
authors (as with Claude Code), or the rule is in another language. For this harness a Python function is simpler, so
the concept was reinforced better in Step 5, and the idea is parked in the roadmap.
- Explained to me, not yet said back: a process ends with an integer exit code, where 0 means success; running
  commands named in a config file means trusting that config.

## Explained to me, not yet said back in my own words

These came up along the way. I haven't restated them, so they stay here until I do.

- **Which model, and why.** I started on Haiku 4.5 ($1 / $5 per million input /
  output tokens, against $2 / $10 for Sonnet 5.5): the cheapest current model then,
  and plenty for learning the loop, whose difficulty is in the harness, not the
  model. I have since moved to **Haiku 5.5**, which the docs list "from $0.10 / $0.50".
  The model name comes from `HARNESS_MODEL`, so switching was one line. Through
  a gateway the name can be a slug: a provider prefix, then a region profile (`us.`), then the
  provider's model ID (`us.anthropic.claude-haiku-4-5-20251001-v1:0` before,
  `us.anthropic.claude-haiku-5-5` now). A catalog listing doesn't prove my key can
  call a model; only a call does.
- **Everything measured in Steps 1-5 was on Haiku 4.5.** Token counts, the
  tool-definition overhead (about 496 tokens for 4.5, 286 for 5.5), and how the model
  handled the banana tool may all differ on 5.5, which uses adaptive thinking at
  `medium` effort by default. Thinking tokens count against `max_tokens`.
- **The gateway.** A gateway sits between my code and Bedrock. The request goes to the gateway's address
  in the Anthropic Messages format. A gateway may also add fields of its own to the reply object; I can
  ignore them.
- **Tokens and the context window.** A token is a chunk of text, roughly three
  quarters of a word. `max_tokens` caps one reply. The context window (about 200,000 tokens for Haiku 4.5, 1,000,000 for Haiku 5.5) caps everything in one call: the whole `messages` list plus
  the reply. A conversation is limited by size, not by the number of exchanges, and
  re-sending history is why long conversations get expensive.
- **The shape of a reply.** `messages.create` returns one `Message` with a `content`
  list of blocks, a `role` of `assistant`, a `stop_reason`, a `usage` with
  `input_tokens` and `output_tokens`, the `model`, and an `id`. `messages` is a list
  of dictionaries, each with a `role` and `content`. Lists count from 0, so
  `content[0]` is the first block.
- **The tool description is the model's only guide.** It reads the description to
  decide when a tool applies and how to fill the inputs (it repeated my
  "relative to the project's folder" wording back to me). Worth writing carefully.
- **Reading a network failure.** A timeout traceback ends with
  `APITimeoutError`; the deeper lines (a TLS handshake timeout) show the cause, and
  the SDK had already retried a couple of times. A plain `curl` to the host, with a
  timeout, separates "my connection" from "my code".
- **Small Python and git points.** Trailing commas after the last argument are
  allowed and tidy up diffs; `enumerate(items, start=1)` gives a counter; f-strings
  put values in text; `git mv` keeps a file's history through a rename;
  `git restore <file>` throws away uncommitted edits to one file (I used it to undo
  an experiment); a pattern like `.env.*` in `.gitignore` also hides `.env.example`,
  so it needs a `!.env.example` line.

## From the tool-use docs (skimmed)

- **Claude retries only because the harness sent the error back.** The docs say to
  continue the conversation with a `tool_result` flagged `is_error: true`, and
  Claude will try the tool again; for an invalid request (like a missing
  parameter) it retries a couple of times before apologizing. My `try`/`except`
  is what makes that possible. Without it, the model never sees the failure.
  - My `data/missing.txt` case was a valid request for a file that wasn't there, so
    the model reported it and didn't retry (it had nothing else to try).
- **`strict: true` on a tool definition** guarantees the inputs match the schema,
  which would prevent missing or mistyped parameters (the `TypeError` cases). It
  doesn't help when the tool itself fails, so `try`/`except` is still needed.
- **`tool_choice`** defaults to `auto` (the model decides each turn);
  `disable_parallel_tool_use: true` inside it limits the model to one tool call per
  turn, which would switch off the batching from Step 4. A system prompt can nudge
  how eagerly the model uses tools.
- **Tool definitions cost tokens on every request**, plus a hidden tool-use system
  prompt (about 496 tokens for Haiku 4.5 with `auto`), which is why a call with tools
  has far more input tokens than a plain one. Properties can carry their own
  `description` too, which mine don't yet.
- The SDK's **Tool Runner** runs this whole loop for you; I wrote it by hand.
