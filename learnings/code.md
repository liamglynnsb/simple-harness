# Learnings: the code itself

What I've learned about the code and the tools around it: Python mechanics (`self`, `**kwargs`,
`partition`, `__main__`), project habits (virtual environment, `.env`, git, pytest), and
software-design principles. Each entry is in my own words, with corrections noted. The theory of
how the harness works is in [harness.md](harness.md); the index and open items are in
[../LEARNINGS.md](../LEARNINGS.md).
The SDK's data structures are in [anthropic-sdk-reference.md](anthropic-sdk-reference.md), and the
meaning of every term in [glossary.md](glossary.md). Newest at the bottom of each section.

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

## 2026-10-06 · Layer 1, Step 3 (the loop)

**`**` unpacks a dictionary into named arguments.** `calculator(**block.input)`
means `calculator(operation=..., a=..., b=...)`. It works because the dict's
keys match the function's parameter names. I use it so the loop stays general
and doesn't spell out field names for every tool.
- Correction: `block.input` is a dictionary (named fields), not a list.
- Catch: if the model sends a field the function doesn't accept, Python errors.

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

**`if __name__ == "__main__":` separates running a file from importing it.**
Python runs a file's top-level lines whenever it loads it, including on `import`.
`__name__` is `"__main__"` only when the file is run directly, so code under that
guard runs when I run the script and is skipped when another file imports it.
Definitions stay at the top level; the actions that call them go under the guard.
- Correction: importing isn't "nothing". It still runs the imports and the `def`
  lines. It just doesn't run the agent.

**Text blocks are joined with a newline, in one helper.** `+=` glues blocks together
with no separator ("done.Next..."). `collect_text` gathers each text block into a
list and returns `"\n".join(parts)`, which puts separators only between items and
returns `""` for no text. Both `end_turn` and `max_tokens` use it, and neither
assumes the first block is text.

## 2026-10-06 · Layer 1, Step 4 (a second tool, several calls in one reply)

**Python bits.** `print("a", x, y)` prints its arguments separated by spaces.
`[b.type for b in response.content]` is a list comprehension: `b` is an arbitrary
name for each item in turn, and the result is a list of the types.

## 2026-10-15 · Layer 2, Step 1 (a skill as a tool)

**One source of truth.** The tool's menu of skills is generated from the skill files, not
typed by hand, so it can't drift out of date. Same idea as the definition and function
agreeing on parameter names, and `.env.example` against the README.

**Python I used while building it.** `Path(folder).glob("*.md")` finds files, in no
guaranteed order (use `sorted(...)` for a stable menu). `text.partition("\n---\n")`
returns three pieces (I keep the first and last; `_` takes the middle).
`line.split(": ", 1)` returns a *list*, so I take `[1]`; the `1` matters because
descriptions contain colons. `.items()` hands out key and value together, and a `for`
creates the names I use for them. `print(read_skills())` runs the inner call first.
`pass` is a placeholder that does nothing. `python` isn't on the PATH unless the venv is
activated, so I run `.venv/bin/python`, and step scripts as modules from the root.

## 2026-10-15 · Layer 2, Step 2 (tests with a scripted fake model, in progress)

**A fake client is a script played back in order; the test supplies the intelligence.** The fake has
no logic and never looks at the question. Each test writes its own tiny script (the replies the "model"
gives in that scenario), and the fake hands them out one per call and logs what it was sent. The test
then checks the log. The real loop runs unchanged; only the model's replies are dummies. Pairing is by
order, not content. Standard practice: a queue of canned responses is the usual way to fake a
sequential service; Python's own `unittest.mock.Mock(side_effect=[...])` does exactly this, and an
iterator (`iter` / `next`), an index counter or `collections.deque` are equivalent ways to write it.
- `self.replies.pop(0)` takes the **front** of the list (replies play in order); a bare `pop()` takes the
  last one, which would play them backwards. The **log holds the inputs the loop sent**, not the replies.
  When the script runs out, an extra call fails loudly (`IndexError`), which is a useful signal, and
  after a test `client.replies == []` shows the whole script was used.
- `self.replies = list(replies)` makes a copy, so the fake never empties the test's own list.
- Correction: I first thought the fake needed logic to detect the question and choose a reply. It doesn't.
- Correction: I said the log receives the replies as they are used; it records the arguments instead.

**Classes, `self`, and the parentheses.** A class bundles state (the script, the log) with behaviour
(`create`). Defining a class is not inheritance (`class B(A)`); I've used classes all along (the SDK's
client and reply objects), I just hadn't defined one. `self` is written as the first parameter only when
*defining* a method; when *calling* `obj.method(...)`, Python fills it in. A plain function has no
`self`. `__init__` runs once when the object is created. `make_client()` is a plain function that
*creates* an object; methods are *called on* objects.
- `name` is the thing itself; `name()` runs it now. `SimpleNamespace(create=self._create)` stores the
  method to run later; with parentheses it ran at setup and stored its result, so the loop later tried
  to call a string (`'str' object is not callable`). Recipe card vs cooked meal.
- `**kwargs` in a `def` collects all named arguments into one dict; `**something` in a *call* spreads a
  dict out into named arguments (the opposite direction; I used it in `FUNCTIONS[...](**block.input)`).
- `SimpleNamespace(a=1, b=2)` is a plain object whose attributes are the names given (read with a dot,
  nests, no class to write). It is how the fake builds replies and blocks. `self.messages = self` is a
  circular reference (an object pointing at itself), not recursion: nothing runs repeatedly, and it only
  causes trouble if something tries to walk all of an object's contents (JSON conversion fails).

**Why `content` is a list, and why a `text_reply` helper.** A real reply holds several blocks in order
(thinking, text, tool requests), and the loop does `for block in response.content`, so even a one-block
reply is a list of one. `text_reply(text)` builds the nested reply (`stop_reason` plus a `content` list
with one text block) so tests stay short and the reply's shape lives in one place. The values are what
the SDK hands the loop, not the raw JSON the model produces.

**How tests are laid out and found.** The arrow goes from tests to the loop, never the reverse:
`tests/test_loop.py` imports `run_agent` and the fake; production code never imports test code. This
works because `run_agent` receives its `client` as an argument (dependency injection), so a fake can be
passed in without changing the loop. A file name with a hyphen can't be imported (`test-client.py` is
a syntax error), so use underscores. pytest finds tests by naming convention: files `test_*.py`,
functions `test_*`; helpers like `fake_client.py` aren't collected; every matching file runs, each test
independently, with one summary. `python -m pytest` runs the pytest in my venv and puts the project root
on the import path; `-m` means "run a module by name" (Python's flag), `-q` means quiet and `-v`
verbose (pytest's); `--collect-only` lists what it found without running it.
- The limit: the fake shows whether *my code* handles each situation. How the real model behaves is the
  server side, which evals measure in Layer 4.
