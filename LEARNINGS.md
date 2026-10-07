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

## 2026-10-06 · Layer 1, Step 3 (the loop, in progress)

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

## Explained to me, not yet said back in my own words

- `os.environ["X"]` is a lookup in the environment the process was started with.
  It doesn't read `.env`.
- Why `client.py` has `api_key="dummy"` plus an `x-gateway-key` header: the
  SDK requires an `api_key`, and the real key the gateway checks is the header.
