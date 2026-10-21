"""Tests for mcp_client.py: the harness side of MCP, against the real mcp_server.py started as a subprocess.
No model, no network, no API."""
import os
import sys

import pytest

import loop
import mcp_client
import mcp_server
from fake_client import FakeClient, text_reply, tool_reply, tool_block

SERVER = [sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")]


def test_the_client_lists_the_servers_tools():
    with mcp_client.McpClient(SERVER) as client:
        tools = client.list_tools()
    assert tools == [mcp_server.TOOL]


def test_a_tool_definition_is_converted_to_the_model_api_format():
    definition = mcp_client.to_tool_definition(mcp_server.TOOL)
    assert definition["name"] == mcp_server.TOOL["name"]
    assert definition["description"] == mcp_server.TOOL["description"]
    assert definition["input_schema"] == mcp_server.TOOL["inputSchema"]
    assert "inputSchema" not in definition                      # the API spells it input_schema


def test_the_wrapper_function_calls_the_server_and_returns_the_text():
    with mcp_client.McpClient(SERVER) as client:
        count = mcp_client.make_tool_function(client, mcp_server.TOOL["name"])
        assert count(word="Strawberry", letter="r") == "3"      # called like any tool: with the model's input as named arguments


def test_several_calls_on_one_connection_keep_their_ids_straight():
    with mcp_client.McpClient(SERVER) as client:
        count = mcp_client.make_tool_function(client, mcp_server.TOOL["name"])
        assert [count(word="banana", letter="a"), count(word="banana", letter="n"), count(word="banana", letter="b")] == ["3", "2", "1"]


def test_a_protocol_error_raises_mcp_error_with_the_code():
    with mcp_client.McpClient(SERVER) as client:
        with pytest.raises(mcp_client.McpError) as caught:
            client.call_tool("no_such_tool", {})
    assert caught.value.code == -32602


def test_closing_the_client_stops_the_server():
    with mcp_client.McpClient(SERVER) as client:
        client.list_tools()
    assert client.process.returncode == 0                       # it exited on its own when its input closed


def test_a_tool_that_ran_and_failed_raises_mcp_tool_error_with_the_tools_own_message():
    with mcp_client.McpClient(SERVER) as client:
        count = mcp_client.make_tool_function(client, mcp_server.TOOL["name"])
        with pytest.raises(mcp_client.McpToolError, match="single character"):
            count(word="Strawberry", letter="rr")
        assert count(word="Strawberry", letter="r") == "3"      # the connection is still fine afterwards


def test_a_tool_failure_is_not_a_protocol_error():
    assert not issubclass(mcp_client.McpToolError, mcp_client.McpError)


def _run_loop_with_the_mcp_tool(monkeypatch, word, letter):
    """A scripted model calls the MCP tool through the real loop. Returns the tool_result the model received."""
    monkeypatch.setattr("loop.FUNCTIONS", dict(loop.FUNCTIONS))      # a private copy, so the real table stays untouched
    with mcp_client.McpClient(SERVER) as server:
        definitions = mcp_client.register_tools(server, loop.FUNCTIONS)
        name = mcp_server.TOOL["name"]
        model = FakeClient([tool_reply(tool_block(name, {"word": word, "letter": letter}, "id1")), text_reply("done")])
        messages = [{"role": "user", "content": "count"}]
        loop.run_agent(model, messages, definitions)
    return messages[2]["content"][0]


def test_register_tools_returns_definitions_in_the_model_format_and_fills_functions(monkeypatch):
    monkeypatch.setattr("loop.FUNCTIONS", dict(loop.FUNCTIONS))
    with mcp_client.McpClient(SERVER) as server:
        definitions = mcp_client.register_tools(server, loop.FUNCTIONS)
    assert [d["name"] for d in definitions] == [mcp_server.TOOL["name"]]
    assert "input_schema" in definitions[0]
    assert mcp_server.TOOL["name"] in loop.FUNCTIONS


def test_the_loop_runs_an_mcp_tool_like_any_other(monkeypatch):
    result = _run_loop_with_the_mcp_tool(monkeypatch, "Strawberry", "r")
    assert result["tool_use_id"] == "id1"
    assert result["content"] == "3" and "is_error" not in result


def test_an_mcp_tool_failure_reaches_the_model_as_a_flagged_error(monkeypatch):
    result = _run_loop_with_the_mcp_tool(monkeypatch, "Strawberry", "rr")
    assert result["is_error"] is True
    assert result["content"] == "Error: letter must be a single character, got: 'rr'"


def test_leaving_the_with_block_after_the_server_died_does_not_raise():
    with mcp_client.McpClient(SERVER, retries=0) as client:
        client.process.kill()                                    # the server dies mid-run
        client.process.wait()
        with pytest.raises(mcp_client.McpTransportError):
            client.list_tools()                                  # no retries allowed, so the failure is raised
    # reaching this line means close() coped with the dead server instead of raising BrokenPipeError
    assert client.process.returncode is not None


# ---- failure cases: a dead server, a silent server, garbage, and what is (and is not) retried ----

def _server_script(tmp_path, body):
    """Write a small stand-in server (Python source) and return the command that starts it."""
    path = tmp_path / "fake_server.py"
    path.write_text(body)
    return [sys.executable, str(path)]


def test_a_dead_server_is_restarted_and_the_request_is_retried():
    with mcp_client.McpClient(SERVER, retries=1) as client:
        old_pid = client.process.pid
        client.process.kill()
        client.process.wait()
        assert client.list_tools() == [mcp_server.TOOL]          # same answer, from a fresh process
        assert client.process.pid != old_pid


def test_the_wrapper_keeps_working_after_the_server_was_restarted():
    with mcp_client.McpClient(SERVER, retries=1) as client:
        count = mcp_client.make_tool_function(client, mcp_server.TOOL["name"])
        client.process.kill()
        client.process.wait()
        assert count(word="Strawberry", letter="r") == "3"       # the wrapper holds the client, not the process


def test_a_server_that_never_answers_times_out_with_a_clear_message():
    silent = ["import sys, time", "for line in sys.stdin:", "    time.sleep(60)"]
    command = [sys.executable, "-c", "\n".join(silent)]
    with mcp_client.McpClient(command, timeout=0.5, retries=0) as client:
        with pytest.raises(mcp_client.McpTransportError, match="did not answer within 0.5 seconds"):
            client.list_tools()


def test_the_final_error_says_how_many_times_it_tried():
    dies_at_once = [sys.executable, "-c", "import sys; sys.exit(1)"]
    with mcp_client.McpClient(dies_at_once, timeout=2, retries=2) as client:
        with pytest.raises(mcp_client.McpTransportError, match=r"tried 3 times"):
            client.list_tools()


def test_something_that_is_not_json_is_a_connection_failure():
    garbage = [sys.executable, "-c", "import sys\nfor line in sys.stdin:\n    print('this is not json', flush=True)"]
    with mcp_client.McpClient(garbage, timeout=2, retries=0) as client:
        with pytest.raises(mcp_client.McpTransportError, match="not valid JSON"):
            client.list_tools()


def test_a_protocol_error_is_never_retried():
    with mcp_client.McpClient(SERVER, retries=3) as client:
        pid = client.process.pid
        with pytest.raises(mcp_client.McpError) as caught:
            client.call_tool("no_such_tool", {})
        assert caught.value.code == -32602
        assert not isinstance(caught.value, mcp_client.McpTransportError)
        assert client.process.pid == pid                         # the server was not restarted: nothing was wrong with it


def test_a_server_failure_reaches_the_model_as_a_flagged_error_and_the_loop_carries_on(monkeypatch):
    monkeypatch.setattr("loop.FUNCTIONS", dict(loop.FUNCTIONS))
    dies_at_once = [sys.executable, "-c", "import sys; sys.exit(1)"]
    with mcp_client.McpClient(dies_at_once, timeout=2, retries=0) as server:
        wrapper = mcp_client.make_tool_function(server, "count_letters")
        loop.FUNCTIONS["count_letters"] = wrapper
        definitions = [{"name": "count_letters", "description": "x", "input_schema": {"type": "object"}}]
        model = FakeClient([tool_reply(tool_block("count_letters", {"word": "a", "letter": "a"}, "id1")), text_reply("done")])
        messages = [{"role": "user", "content": "count"}]
        answer = loop.run_agent(model, messages, definitions)
    result = messages[2]["content"][0]
    assert answer == "done"                                      # the loop finished normally
    assert result["is_error"] is True
    assert result["content"].startswith("Error: the tool server")


# ---- when the server can't be used at startup, the user decides ----

DEAD = [sys.executable, "-c", "import sys; sys.exit(1)"]


def test_a_working_server_registers_without_asking(monkeypatch):
    monkeypatch.setattr("loop.FUNCTIONS", dict(loop.FUNCTIONS))
    asked = []
    with mcp_client.McpClient(SERVER) as server:
        definitions = mcp_client.register_tools_or_ask(server, loop.FUNCTIONS, ask=lambda q: asked.append(q) or "n")
    assert [d["name"] for d in definitions] == [mcp_server.TOOL["name"]]
    assert asked == []                                          # nothing was wrong, so nobody was asked


def test_if_the_server_is_dead_and_the_user_says_yes_the_run_carries_on_without_mcp_tools(monkeypatch):
    functions = dict(loop.FUNCTIONS)
    asked = []
    with mcp_client.McpClient(DEAD, timeout=2, retries=0) as server:
        definitions = mcp_client.register_tools_or_ask(server, functions, ask=lambda q: asked.append(q) or "y")
    assert definitions == []
    assert mcp_server.TOOL["name"] not in functions             # nothing was registered
    assert len(asked) == 1 and "local tools" in asked[0]


def test_if_the_server_is_dead_and_the_user_says_no_the_error_is_raised():
    with mcp_client.McpClient(DEAD, timeout=2, retries=0) as server:
        with pytest.raises(mcp_client.McpTransportError):
            mcp_client.register_tools_or_ask(server, dict(loop.FUNCTIONS), ask=lambda q: "n")


def test_many_threads_can_share_one_client_without_their_requests_getting_mixed_up():
    import threading
    with mcp_client.McpClient(SERVER) as client:
        count = mcp_client.make_tool_function(client, mcp_server.TOOL["name"])
        words = ["a" * n for n in range(1, 13)]                  # twelve different words: the right answer is the length
        answers = {}
        def work(word):
            answers[word] = count(word=word, letter="a")
        threads = [threading.Thread(target=work, args=(word,)) for word in words]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert answers == {word: str(len(word)) for word in words}

