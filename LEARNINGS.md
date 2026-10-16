# Learnings (index)

The ledger of what I've learned while building the harness, split in two:

- **[learnings/harness.md](learnings/harness.md): the theory of the harness.** How tool use works,
  tokens and cost, the loop's design, errors and recovery, skills versus tools, the experiments, and
  why the loop is tested the way it is.
- **[learnings/code.md](learnings/code.md): the code itself.** Python mechanics, project and tooling
  habits (venv, `.env`, git, pytest), and software-design principles.

Where to file a new entry: if it explains *how agents, models or the API behave or should be
designed*, it goes in `harness.md`. If it explains *how to write or run the code*, it goes in
`code.md`. An entry that is genuinely both goes where its title points, with a one-line pointer in
the other file.

## Open items

- Rebuild `run_agent` from a blank file with nothing open (the ownership test).
- Add a `list_files` tool someday and watch the model recover from a wrong path.
- Layer 5 ideas from this ledger: retries for timeouts, tracing every tool call and
  result, deciding what to do about an empty reply, and which tools to send when
  there are many.
