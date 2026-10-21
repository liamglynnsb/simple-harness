# Glossary

Every term this project uses, in plain words, so that coming back after a break doesn't mean
re-learning the vocabulary. Alphabetical. A term marked *(planned)* is on the roadmap but not
built yet. Where a term has a fuller explanation, the file to look in is named. Index:
[../LEARNINGS.md](../LEARNINGS.md).

**adaptive thinking** A mode where the model decides for itself how much to reason before answering, steered by an effort level (default `medium` on Haiku 5.5). It is on by default with this model. The reasoning uses output tokens and counts against `max_tokens`. See `harness.md`.

**agent loop** The code that repeatedly asks the model, runs any tools it requests, sends the results back, and stops when the model finishes. In this repo it is `run_agent` in `loop.py`.

**AgentStopped** *(Layer 2 Step 3)* An exception raised when a run ends without a real answer (pass limit, cut off, refusal) and the caller asked for `raise_on_failure=True`. A class with a name and nothing else: it inherits everything from `Exception`, and the name lets a caller catch exactly this failure.

**assert** A line in a test that must be true; if it isn't, the test fails. For example `assert result == "hello"`.

**assistant** One of the two roles in a conversation: the messages written by the model. The other is `user`.

**attribute** A named piece of data on an object, read with a dot: `block.name`. Compare with a *key* on a dict, read with brackets.

**Bedrock** Amazon's service that hosts Claude models. My calls reach it through a gateway.

**binary** A file of machine code produced by a compiler. The operating system loads it and the processor runs it directly.

**block (content block)** One piece of a reply or of a message's content: a text block, a thinking block, a tool request (`tool_use`), and so on. A reply's `content` is a list of blocks. See `anthropic-sdk-reference.md`.

**bytecode** A compact in-between form that Python turns your text into before its interpreter runs it. One reason interpreted and compiled are not strict categories.

**checkpoint** The last item of each layer in the roadmap: explain the concepts back, and rebuild that layer's core from a blank file with nothing open.

**class** A Python blueprint that bundles data with the functions that use it. `FakeClient` is a class I wrote; `Anthropic` (the SDK's client) is one I use. Defining a class is not inheritance. See `code.md`.

**client** Two meanings. In "client and server", my harness is the client (it sends requests) and the model is the server. And `client = make_client()` is the SDK object that sends the requests.

**compiler** A program that translates source text into machine code once, ahead of time, producing a binary that runs without a translator. C, Rust and Go are compiled.

**content** The list of blocks inside a reply (`response.content`). In a request, a message's `content` is a string or a list of blocks.

**context window** The most tokens the model can handle in one call: the whole history plus the reply. About 1,000,000 for Haiku 5.5. Not the same as `max_tokens`, which limits one reply.

**decoy** A skill included on purpose to test that the model does not load a skill that isn't relevant (`release-notes-format`).

**default value** What a parameter takes when the caller leaves it out, written in the `def` line: `system=None`. It is what makes a parameter optional.

**delegate** *(Layer 2 Step 3)* The tool that hands a task to a subagent: it runs a fresh `run_agent` with its own `messages` and a fixed list of tools, and returns only the child's final text. The harness, not the model, decides the child's tools.

**dependency injection** Passing something a function needs (like the client) in as an argument instead of creating it inside. It's why a fake client can replace the real one without touching the loop.

**dict** A Python dictionary: a lookup from keys to values, like `{"name": "calculator"}`.

**end_turn** A `stop_reason` meaning the model finished its answer.

**enum** In a JSON Schema, a list of the only values a field may have.

**environment variable** A named value a program inherits from the shell that started it. `ANTHROPIC_API_KEY` and `HARNESS_MODEL` are read from the environment. `.env` is a git-ignored file of them that `client.py` loads. See `code.md`.

**eval** *(planned, Layer 4)* A measurement of how often the whole system gets tasks right, run many times because the model varies. A test checks that code behaves; an eval measures behaviour.

**exception** An error signal that travels up through the code that called the function until something catches it. `raise` throws one; `try` / `except` catches one. In the harness, a tool raises and the loop catches. See `harness.md` and `code.md`.

**exit code** A whole number a program returns when it ends. By convention 0 means success and anything else means failure.

**f-string** A string with an `f` before the quote; anything in `{}` is replaced by its value. `f"turn {n}"`.

**fake client (test double)** A stand-in for the real client in tests: it plays back scripted replies in order and records what it was sent. `tests/fake_client.py`. See `code.md`.

**FUNCTIONS** The dict in `tools.py` that maps each tool's name to the function that runs it.

**gateway** A service between my code and the model: requests go to it, and it forwards them to the provider (here, Bedrock). It is optional; the harness also works against the API directly.

**guardrail** *(planned, Layer 5)* A check on what goes into or comes out of the model: redacting secrets, validating output, blocking unsafe actions.

**harness** All the code around the model: the loop, the tools, the history, and the limits. This project builds one from scratch.

**hook** A function attached at a defined point in the harness, which runs there every time without the loop naming it. A before-hook runs before a tool and can allow the call (return `None`) or block it (return a reason); an after-hook runs after a tool and sees the result. Hooks are registered in a list (`BEFORE_HOOKS` in `hooks.py`). See `harness.md`.

**hook point** A moment in the loop where hooks can be attached: before or after a tool, before a model call, after a model reply, when the model says it's done, when a run ends, on an error or retry, or around a subagent. See the table in `harness.md`.

**index** A position in a list, counting from 0: `messages[2]` is the third item.

**input_schema** The JSON Schema inside a tool definition that describes the inputs the tool takes.

**interpreter** A program that reads another program's text and carries it out as it goes, every time it runs. `python` and the shell (zsh) are interpreters, and are themselves binaries of machine code.

**is_error** A flag on a `tool_result` saying the tool failed, so the model reads the content as an error message and not as data.

**JSON / JSON Schema** JSON is a text format for structured data (dicts, lists, strings, numbers). JSON Schema is a standard way of describing the shape of some JSON; tool inputs are described with it.

**key** The name that labels a value in a dict, read with brackets: `block_dict["tool_use_id"]`. Missing keys raise a `KeyError`.

**kwargs** In a function definition, `**kwargs` collects all named arguments into one dict. In a call, `**some_dict` spreads a dict out into named arguments (the opposite). See `code.md`.

**layer / step / substep** How the roadmap is organized. A layer is a stage (1 to 5), a step is a unit within it, a substep is a lettered piece of a step. "Layer 2 Step 1, 1c" means the third piece of the first step of the second layer.

**ledger** The learnings files: what I've learned, in my own words, with corrections noted. See `../LEARNINGS.md`.

**list comprehension** A short way to build a list in one line: `[b.type for b in blocks]`.

**load_skill** The tool that returns a skill's full instructions when the model asks for one by name.

**machine code** The only language a processor runs: a small set of numeric instructions specific to that chip. Every other language is translated into it first.

**max_loops** The most passes `run_agent` will make, so a stuck model can't loop and spend forever.

**max_tokens** The limit on one reply, counted in output tokens (thinking included).

**MCP** *(planned, Layer 2 Step 5)* Model Context Protocol: a standard for tools that live in a separate program, which the harness starts and talks to.

**menu** The list of skill names and one-line descriptions placed inside `load_skill`'s description. The model sees the menu on every request and asks for a body only if it needs one.

**Message / messages** Two different things. `Message` is the SDK's object for one reply from the model. `messages` is the list of the conversation I send with each request. See `anthropic-sdk-reference.md`.

**model slug** The model's name as your API or gateway wants it, for example `claude-haiku-5-5` on the API directly. It lives in `HARNESS_MODEL`.

**non-deterministic** Giving different outputs for the same input. The model is; that's why evals run things several times.

**paging (pagination)** Reading a long thing in pieces: each call returns one chunk, and the caller asks for the next by giving a start position. `read_file`'s `start` is the position; the harness fixes the chunk size.

**pass** One iteration of the agent loop, which is one call to the model.

**pipe** The `|` in a command, or the connection a program sets up when it starts another one: what the left program writes to its stdout arrives as the right program's stdin.

**process** A program while it is running, with its own memory and its own stdin, stdout and stderr. Running the same program twice makes two processes. A crash in one process doesn't crash another.

**program** A file of instructions that a computer can run. When it is running it is a process. `python` is a program; `loop.py` is a script it runs.

**progressive disclosure** Showing a short summary always and the details only on request. How skills work: the menu is always visible, the body loads on demand.

**prompt caching** *(planned, Layer 5)* Reusing a stable part of a request at a much lower price, instead of paying full price to re-send it every pass.

**prompt injection** *(planned, Layer 5)* Instructions hidden inside data (a file, a tool result) that try to make the model do something the user didn't ask for.

**pytest** The tool that finds and runs the tests: files named `test_*.py`, functions named `test_*`. Run with `.venv/bin/python -m pytest -q`.

**reply** The model's answer to one request: a `Message` object.

**role** Who wrote a message: `"user"` or `"assistant"`.

**scoping** Limiting an agent to the tools it was given. The model can ask for any tool name, so the loop checks each request against the agent's own `tools` list and refuses the rest as unknown. Advising the model isn't enough; the check is in code.

**script** A program run by an interpreter, as `loop.py` is run by `python`. Not a different kind of thing from a program, only a looser name for a small or interpreted one.

**SDK** Software development kit: the `anthropic` Python package that sends requests and turns replies into objects.

**self** Inside a class's methods, the object itself. Written as the first parameter when defining a method, and filled in automatically when calling one.

**server-side tool** A tool the model's provider runs for me (such as web search). I don't use any; every tool here runs in my own code.

**shell** A program (zsh on this Mac) that starts other programs and connects their streams, and an interpreter for a small language of commands, `|` and `>`. See `code.md`.

**SimpleNamespace** A plain Python object whose attributes are whatever names you give it. Used to build fake replies in tests.

**single source of truth** Each fact lives in exactly one place and everything else is derived from it or links to it, so copies can't disagree. The skill menu is generated from the skill files for this reason.

**skill** A text file with a name, a one-line description and instructions. The model loads it on demand with `load_skill`. A skill advises; it can't enforce. See `harness.md` (tools vs skills).

**stateless** The API remembers nothing between calls. The "conversation" exists only in the `messages` list I send each time.

**stderr** *(standard error)* The channel for a program's logs and warnings, separate from its stdout. An MCP server may write anything to it; the client may capture or ignore it.

**stdin** *(standard input)* The channel a program reads its input from. A pipe can connect another program's output to it. In MCP over stdio, the harness writes JSON lines to the server's stdin.

**stdout** *(standard output)* The channel a program writes its normal output to. By default it shows on the terminal; a pipe can send it to another program's stdin instead. In MCP over stdio, the server's stdout carries only valid protocol messages.

**stop_reason** The field on a reply saying why the model stopped: `end_turn`, `tool_use`, `max_tokens`, and a few others.

**subagent** *(planned, Layer 2 Step 3)* A helper that runs its own separate loop, with its own history and a limited set of tools, and hands back only its final text.

**subprocess** A program that another program starts and keeps in touch with, through pipes. The harness starts an MCP server as a subprocess.

**system prompt** Instructions given to the model separate from the conversation. When tools are passed, the API also builds a hidden one containing the tool-use instructions and my tool definitions; that's part of why tools cost input tokens on every request.

**thinking** The model's reasoning before it answers, returned as `thinking` blocks. Its tokens are billed as output and count against `max_tokens`.

**token** The unit the model reads and writes: roughly three quarters of a word. Cost and limits are counted in tokens. Input tokens are what I send; output tokens are what it generates (about five times the price).

**tool** Something the model can ask my code to do. It has two halves that must agree: a *definition* (what the model reads) and a *function* (what runs).

**tool definition** The dict the model reads about a tool: `name`, `description`, `input_schema`. Sent in the request's `tools`.

**tool_choice** A request setting that controls whether the model may, must, or may not use tools (`auto`, `any`, `tool`, `none`).

**tool_result** My answer to a tool request: a block carrying the matching `tool_use_id` and the result (or an error, flagged `is_error`). Every `tool_use` needs one.

**tool_use** A block in a reply where the model asks for one of my tools to be run, with a unique `id`, the tool's `name` and its `input`.

**traceback** The report Python prints when an error isn't caught. Read it from the bottom: the last line is the error, then find the last line that points into my own files.

**usage** The token counts for one reply (`input_tokens`, `output_tokens`, and more). One per reply, not per block. See `anthropic-sdk-reference.md`.

**venv (virtual environment)** A project-private folder (`.venv`) holding this project's installed Python packages. I run its Python directly: `.venv/bin/python`.

**verifier** *(planned, Layer 4)* Code that decides whether a task's result passes, by checking the answer or how it was reached.
