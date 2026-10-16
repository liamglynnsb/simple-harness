from client import make_client, model_name
from tools import FUNCTIONS, CALCULATOR, READ_FILE, LOAD_SKILL


def collect_text(response):
    """Join the text blocks of a reply into one string (other block kinds, like thinking or
    tool requests, are skipped). Joined with newlines so separate blocks don't run together."""
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


def run_agent(client, messages, tools, max_loops=10, max_tokens=1000):
    """The agent loop. Ask the model; if it wants tools, run them, send the results back, ask
    again; stop when it finishes.

    client      -- anything with messages.create(...): the real SDK client, or a fake in tests
    messages    -- the conversation so far; this function appends to it as it goes
    tools       -- the tool DEFINITIONS the model is allowed to use (not the functions)
    max_loops   -- the most passes allowed, so a stuck model can't loop (and spend) forever
    max_tokens  -- the limit on one reply; thinking tokens count against it
    Returns the model's final text, or a message saying why it stopped early.
    """
    for _ in range(max_loops):  # one pass = one call to the model
        tool_results = []  # reset every pass, so old results are never sent twice
        response = client.messages.create(
            model=model_name(),
            max_tokens=max_tokens,
            tools=tools,
            messages=messages,
        )
        # Keep the model's whole reply (thinking and tool requests included) in the history.
        messages.append({"role": "assistant", "content": response.content})
        # print("blocks this pass:", [b.type for b in response.content])
        if response.stop_reason == "tool_use":
            # The model wants tools run. Answer EVERY request in this reply, one result each.
            for block in response.content:
                if block.type == "tool_use":
                    print("calling", block.name, "with input", block.input) # helps with traceability
                    try:
                        # Look the tool up by name and call it with the model's inputs.
                        result = FUNCTIONS[block.name](**block.input)
                    except Exception as e:
                        # Anything a tool raises lands here: send it back flagged as an error, so the
                        # model still gets an answer and can recover. (An unknown tool name fails the lookup.)
                        if block.name not in FUNCTIONS:
                            result = "Unknown tool: " + block.name + ". Available tools: " + ", ".join(FUNCTIONS.keys())
                        else:
                            result = "Error: " + str(e)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                            "is_error": True,
                        })
                    else:
                        # No error: send the result back, matched to the request by its id.
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
            # All the results go back together in ONE user message; the next pass sends them.
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return collect_text(response)  # the model finished: its reply is the answer, no more calls
        elif response.stop_reason == "max_tokens":
            # Cut off by the length limit: return whatever text there is, plus a note saying so.
            note = "Response stopped; max tokens reached"
            text_results = collect_text(response)
            if text_results:
                return text_results + "\n" + note
            return note
        else:
            # Any other stop reason (e.g. a refusal): report it instead of looping on it.
            return "Response stopped due to: " + response.stop_reason
    # Reached only if every pass was used without the model finishing.
    return "Error: Max loops reached"


if __name__ == "__main__":  # runs only when this file is run directly, not when it is imported
    client = make_client()
    messages = [{"role": "user", "content": "Write release notes for a release that added dark mode and fixed a login bug."}]
    answer = run_agent(client, messages, [CALCULATOR, READ_FILE, LOAD_SKILL])
    print(answer)
    # for traceability, print the messages
    for m in messages:
        print(m["role"], "->", m["content"] if isinstance(m["content"], str) else [getattr(b, "type", None) or b.get("type") for b in m["content"]])