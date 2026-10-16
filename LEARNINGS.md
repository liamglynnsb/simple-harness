# Learnings (index)

The ledger of what I've learned while building the harness, split by kind into four files:

- **[learnings/harness.md](learnings/harness.md): the theory of the harness.** How tool use works,
  tokens and cost, the loop's design, errors and recovery, skills versus tools, the experiments, and
  why the loop is tested the way it is.
- **[learnings/code.md](learnings/code.md): the code itself.** Python mechanics, project and tooling
  habits (venv, `.env`, git, pytest), and software-design principles.
- **[learnings/anthropic-sdk-reference.md](learnings/anthropic-sdk-reference.md): the SDK's data structures.**
  What `Message`, content blocks and `usage` are and how they connect, the request shapes, and a whole
  tool round trip as data. A reference to look things up in, not a ledger of what I've learned.
- **[learnings/glossary.md](learnings/glossary.md): the vocabulary.** Every term the project uses, in
  plain words, alphabetical. Start here if a word in any file is unfamiliar.

Where to file a new entry: if it explains *how agents, models or the API behave or should be
designed*, it goes in `harness.md`. If it explains *how to write or run the code*, it goes in
`code.md`. An entry that is genuinely both goes where its title points, with a one-line pointer in
the other file.

## Rules for new entries (these keep the documentation from drifting)

1. Draft entries in my own wording, with corrections noted, and show them before saving.
2. Every new term goes in `learnings/glossary.md` in the same commit, as `**term** definition`.
3. Refer to a step with its layer ("Layer 2 Step 1"), never a bare "Step 4".
4. Don't write counts ("47 entries"), dates for "now" or "in progress" markers that go stale; link instead.
5. Link files that exist, by path. State each fact in one place and link to it from elsewhere.
6. Before committing, run `.venv/bin/python scripts/check_docs.py` and fix what it reports.

## Open items

- Rebuild `run_agent` from a blank file with nothing open (the ownership test).
- Add a `list_files` tool someday and watch the model recover from a wrong path.
- Layer 5 ideas from this ledger: retries for timeouts, tracing every tool call and
  result, deciding what to do about an empty reply, and which tools to send when
  there are many.
