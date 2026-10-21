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

