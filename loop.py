import os
import sys

import hooks
import mcp_client
from client import make_client, model_name
from tools import FUNCTIONS, CALCULATOR, READ_FILE, LIST_FILES, LOAD_SKILL, DELEGATE


class AgentStopped(Exception):
    """A run ended without a real final answer (pass limit, cut off, refusal...). Raised only when
    run_agent is called with raise_on_failure=True, so a caller can't mistake the failure for an answer."""


def collect_text(response):
    """Join the text blocks of a reply into one string (other block kinds, like thinking or
    tool requests, are skipped). Joined with newlines so separate blocks don't run together."""
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)


def execute_tool(block, allowed):
    """Run ONE tool request and return the tool_result dict for it (flagged is_error if it failed).

    Every tool call passes through here, so this is the one place where rules about tool calls
    can be applied (hooks, in Layer 2 Step 4). `allowed` is the list of tool names this agent was given.
    """
    try:
        # Before-hooks run first, for every request (see hooks.py): one logs the call, one can block it.
        for hook in hooks.BEFORE_HOOKS:
            try:
                reason = hook(block.name, block.input)
            except Exception:
                hooks.record_failure(hook, block.name, block.input)  # always recorded, with the traceback
                if getattr(hook, "critical", False):
                    raise hooks.HookFailed(hook.__name__ + " crashed on " + block.name)  # stop the whole run
                continue  # a non-critical hook crashed: carry on without it
            if reason is not None:  # a hook decided to block this call; tell the model why, flagged as an error
                return {"type": "tool_result", "tool_use_id": block.id, "content": "Blocked: " + reason, "is_error": True}
        # Scoping: only run a tool this agent was given, even if FUNCTIONS has it. The model
        # can ask for any name; the tools list only controls what it is shown.
        if block.name not in allowed:
            raise PermissionError(block.name)
        # Look the tool up by name and call it with the model's inputs.
        result = FUNCTIONS[block.name](**block.input)
    except hooks.HookFailed:
        raise  # a critical hook crashed: let it stop the run, don't turn it into a tool error
    except Exception as e:
        # Anything a tool raises lands here: send it back flagged as an error, so the
        # model still gets an answer and can recover. (A tool the agent wasn't given, or one
        # that doesn't exist, is reported as unknown.)
        if block.name not in allowed or block.name not in FUNCTIONS:
            result = "Unknown tool: " + block.name + ". Available tools: " + ", ".join(allowed)
        else:
            result = "Error: " + str(e)
        return {"type": "tool_result", "tool_use_id": block.id, "content": str(result), "is_error": True}
    # No error. After-hooks may change the result (for example cut it) before it goes into the history.
    result = str(result)
    for hook in hooks.AFTER_HOOKS:
        result = hook(block.name, block.input, result)
    # Send the result back, matched to the request by its id.
    return {"type": "tool_result", "tool_use_id": block.id, "content": result}


def run_agent(client, messages, tools, max_loops=10, max_tokens=1000, system = None, raise_on_failure=False):
    """The agent loop. Ask the model; if it wants tools, run them, send the results back, ask
    again; stop when it finishes.

    client      -- anything with messages.create(...): the real SDK client, or a fake in tests
    messages    -- the conversation so far; this function appends to it as it goes
    tools       -- the tool DEFINITIONS the model is allowed to use (not the functions)
    max_loops   -- the most passes allowed, so a stuck model can't loop (and spend) forever
    max_tokens  -- the limit on one reply; thinking tokens count against it
    system      -- the system message to use for the model
    raise_on_failure -- if True, a run that ends without a real answer raises AgentStopped instead of
                        returning a message (delegate uses this, so the parent sees an error)
    Returns the model's final text, or a message saying why it stopped early.
    """
    allowed = [t["name"] for t in tools]  # the tools THIS agent was given; FUNCTIONS holds every tool there is

    def stopped(message, reason):
        """The run is ending without a real answer: raise if the caller asked for that, else return the message."""
        if raise_on_failure:
            raise AgentStopped(reason)
        return message

    for _ in range(max_loops):  # one pass = one call to the model
        tool_results = []  # reset every pass, so old results are never sent twice
        request = {
            "model": model_name(),
            "max_tokens": max_tokens,
            "tools": tools,
            "messages": messages,
        }
        if system is not None:
            request["system"] = system
        response = client.messages.create(**request)

        # Keep the model's whole reply (thinking and tool requests included) in the history.
        messages.append({"role": "assistant", "content": response.content})
        # print("blocks this pass:", [b.type for b in response.content])
        if response.stop_reason == "tool_use":
            # The model wants tools run. Answer EVERY request in this reply, one result each.
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append(execute_tool(block, allowed))
            # All the results go back together in ONE user message; the next pass sends them.
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason == "end_turn":
            return collect_text(response)  # the model finished: its reply is the answer, no more calls
        elif response.stop_reason == "max_tokens":
            # Cut off by the length limit: return whatever text there is, plus a note saying so.
            note = "Response stopped; max tokens reached"
            text_results = collect_text(response)
            if text_results:
                return stopped(text_results + "\n" + note, "it was cut off by max_tokens (partial text: " + text_results + ")")
            return stopped(note, "it was cut off by max_tokens before writing any text")
        else:
            # Any other stop reason (e.g. a refusal): report it instead of looping on it.
            return stopped("Response stopped due to: " + response.stop_reason, "it stopped due to: " + response.stop_reason)
    # Reached only if every pass was used without the model finishing.
    return stopped("Error: Max loops reached", "it reached its pass limit (max_loops=" + str(max_loops) + ")")


if __name__ == "__main__":  # runs only when this file is run directly, not when it is imported
    client = make_client()
    server_command = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")]
    # The server is a second process. `with` guarantees it is shut down when the run ends, even if the run crashes.
    with mcp_client.McpClient(server_command) as mcp:
        mcp_definitions = mcp_client.register_tools(mcp, FUNCTIONS)  # adds the server's tools to FUNCTIONS
        tools = [READ_FILE, LIST_FILES] + mcp_definitions            # local tools and the server's tools, one list
        # Needs both kinds of tool, and the question names the server's tool: a model that can count a word itself won't reach for it unprompted.
        messages = [{"role": "user", "content": "Read data/hard_word.txt. Then use the count_letters tool to count how many times the letter 'o' appears in that word."}]
        answer = run_agent(client, messages, tools)
    print(answer)
    # for traceability, print the messages
    for m in messages:
        print(m["role"], "->", m["content"] if isinstance(m["content"], str) else [getattr(b, "type", None) or b.get("type") for b in m["content"]])
