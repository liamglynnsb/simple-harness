# Learnings ledger

Concepts we've worked through, in my own words, with corrections noted. Only
things I've actually explained back go in the main list. Newest at the bottom.

## 2026-10-05 · Layer 1, setup

**Terminal app.** A program that gives you a text window and runs a shell
inside it.
- Correction: not "any program that runs a shell". Claude's Bash tool and a
  Python script can start a shell without giving you a window.

**Shell vs. terminal app.** zsh is the shell that runs inside whichever terminal
app I open (Ghostty, Terminal.app, Cursor's panel). The terminal app only draws
text and relays keystrokes. The shell reads what I type and starts programs.
- Correction: I first said "the shell is the terminal window". Also, "terminal
  editor" should be "terminal app"; an editor is something like nano or Cursor.

**Exported variables are inherited.** A variable I export in a shell is visible
to programs started from that shell, but not to another terminal tab.
- Correction: it's inherited by any child process (Python, git, ls), not just
  child shells.

**`export` is what makes it inheritable.** Without `export`, a variable stays
inside that shell and a program started from it won't see it.

**`.env` is just a file.** It's useful because I can load it into the shell's
environment.
- Correction: the file does nothing by itself. Something has to read it, e.g.
  `source`, to put its contents into the environment.

**A virtual environment (`.venv`) is a private shelf of packages for this
project.** `pip install` puts packages there instead of in the system Python.
Running `.venv/bin/python script.py` starts that specific Python, which notices
its `pyvenv.cfg` and looks for imports on its own shelf. Anyone can rebuild it
from `requirements.txt`, so the folder itself is git-ignored.
- Correction: the shell knows nothing about virtual environments. I first said it
  "tells the terminal" what to launch; the shell just runs the program at that
  path, and the venv-awareness is inside Python.

**Reading `.env` into `os.environ` is Python's job, not the shell's.** A manual
`source .env` step isn't repeatable: in six months I wouldn't remember it, and
someone cloning the repo wouldn't know. So `client.py` calls `load_dotenv()`,
which reads `.env` and fills this process's own `os.environ`. A child process
can't change its parent's environment, but it can set its own.
- `.env` is found next to `client.py`, not in the current folder (except under
  `python -c`). `.env` is git-ignored, so a committed `.env.example` with
  placeholder values documents what's needed, and the README says to copy it.
- Correction: `load_dotenv()` doesn't call Python; it is Python code running in
  the same process. And Python never reads `.env` unless something tells it to.

**`api_key="dummy"` is a placeholder; the real key rides in a header.** The
Anthropic SDK requires an `api_key`, so I pass `"dummy"`. The SDK sends it as an
`x-api-key` header, which the gateway ignores. What the gateway actually checks is the
`x-gateway-key` header, set through `default_headers`, which carries my real
key from `os.environ`. Both headers go out on every request; only one matters.

**`os.environ["X"]` is a lookup in a table the process filled.** `os` is part of
Python's standard library (nothing to install). `os.environ` holds the name/value
pairs Python received at startup, plus whatever was added since. In this project
`load_dotenv()` reads `.env` and adds its pairs to that table, so
`os.environ["ANTHROPIC_API_KEY"]` finds the key there. A missing name is a
`KeyError`.
- Correction: I first said it "pulls the value from the shell". It isn't a live
  link to the shell; it's a snapshot taken at startup, and here the values mostly
  come from `.env` through `load_dotenv()`. The lookup reads the table; it doesn't
  call `load_dotenv`.
- `load_dotenv()` doesn't overwrite a variable that's already set in the shell.

**The word "client" and the word "inheritance" each mean two things.** `client.py`
is my own file; `client = make_client()` is a variable holding the SDK's object.
`from client import ...` is an import, not inheritance. Class inheritance
(`class B(A)`) is about classes; environment variables are "inherited" by child
processes. Neither applies to importing.

**Git's letters in Cursor.** `M` modified, `U` untracked, `A` staged, `D` deleted.

**One editor per file.** If I edit a file while Cursor has a different copy open,
one of us overwrites the other. This happened to `loop.py` twice.

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

**`**` unpacks a dictionary into named arguments.** `calculator(**block.input)`
means `calculator(operation=..., a=..., b=...)`. It works because the dict's
keys match the function's parameter names. I use it so the loop stays general
and doesn't spell out field names for every tool.
- Correction: `block.input` is a dictionary (named fields), not a list.
- Catch: if the model sends a field the function doesn't accept, Python errors.

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

**`while` controls the repeat; `append` only changes the data.** The loop goes
round again when the body ends, unless something exits. A branch I want to
continue (`tool_use`) just falls through. A branch that should stop (`end_turn`,
an unexpected reason) must `return`. After one branch of an `if/elif/else` runs,
the others are skipped.
- Correction: I thought `messages.append()` ended the pass. It only adds an item
  to a list. The next pass sends the updated list.

**Indentation decides what's inside what.** `tool_results = []` goes at the top of
each pass so old results don't pile up. The `messages.append(...)` for the
results goes after the `for`, at the same level as it, so one entry holds all the
results. Inside one block every line must be indented the same amount.

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

**`if __name__ == "__main__":` separates running a file from importing it.**
Python runs a file's top-level lines whenever it loads it, including on `import`.
`__name__` is `"__main__"` only when the file is run directly, so code under that
guard runs when I run the script and is skipped when another file imports it.
Definitions stay at the top level; the actions that call them go under the guard.
- Correction: importing isn't "nothing". It still runs the imports and the `def`
  lines. It just doesn't run the agent.

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

**Text blocks are joined with a newline, in one helper.** `+=` glues blocks together
with no separator ("done.Next..."). `collect_text` gathers each text block into a
list and returns `"\n".join(parts)`, which puts separators only between items and
returns `""` for no text. Both `end_turn` and `max_tokens` use it, and neither
assumes the first block is text.

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

**Python bits.** `print("a", x, y)` prints its arguments separated by spaces.
`[b.type for b in response.content]` is a list comprehension: `b` is an arbitrary
name for each item in turn, and the result is a list of the types.

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

## Explained to me, not yet said back in my own words

These came up along the way. I haven't restated them, so they stay here until I do.

- **Why Haiku 4.5.** It's the cheapest current Claude model ($1 / $5 per million
  input / output tokens, against $2 / $10 for Sonnet 5.5) and plenty for learning the
  loop mechanics, whose difficulty is in the harness, not the model. The model name
  comes from `HARNESS_MODEL`, so switching is one line. Through the gateway the slug is
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`: `` picks the
  provider, `us.` the region profile. A catalog listing doesn't prove my key can call
  a model; only a call does.
- **The gateway.** the gateway sits between my code and Bedrock. The request goes to
  `https://your-gateway.example.com` in the Anthropic Messages format. the gateway also adds its
  own `extra fields` (a guardrail check) to the reply object; I can ignore it.
- **Tokens and the context window.** A token is a chunk of text, roughly three
  quarters of a word. `max_tokens` caps one reply. The context window (about 200,000
  tokens for Haiku 4.5) caps everything in one call: the whole `messages` list plus
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

## Open items

- Rebuild `run_agent` from a blank file with nothing open (the ownership test).
- Add a `list_files` tool someday and watch the model recover from a wrong path.
- Layer 5 ideas from this ledger: retries for timeouts, tracing every tool call and
  result, deciding what to do about an empty reply, and which tools to send when
  there are many.

