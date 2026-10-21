"""Tests for mcp_server.py. Each test starts the real server as a process and talks to it through pipes, the same
way the harness will: one JSON line in on stdin, one JSON line out on stdout. No model, no network, no API."""
import json
import os
import subprocess
import sys

import mcp_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}


def run_server(*messages, raw=None):
    """Send the messages (dicts) to a fresh server, close its stdin, and return (replies, stdout, stderr, exit code)."""
    text = raw if raw is not None else "".join(json.dumps(m) + "\n" for m in messages)
    done = subprocess.run([sys.executable, os.path.join(ROOT, "mcp_server.py")], input=text,
                          capture_output=True, text=True, timeout=10, cwd=ROOT)
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    return replies, done.stdout, done.stderr, done.returncode


def request(request_id, method, **params):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**params, "_meta": META}}


def call(request_id, word, letter):
    return request(request_id, "tools/call", name=mcp_server.TOOL["name"], arguments={"word": word, "letter": letter})


def test_tools_list_returns_the_tool_and_echoes_the_id():
    [reply], _, _, _ = run_server(request(7, "tools/list"))
    assert reply["id"] == 7
    assert reply["result"]["resultType"] == "complete"
    assert reply["result"]["tools"] == [mcp_server.TOOL]


def test_a_call_returns_the_count_as_text():
    [reply], _, _, _ = run_server(call(1, "Strawberry", "r"))
    assert reply["result"]["content"] == [{"type": "text", "text": "3"}]
    assert reply["result"]["isError"] is False


def test_the_count_ignores_upper_and_lower_case():
    [lower, upper], _, _, _ = run_server(call(1, "strawberry", "r"), call(2, "STRAWBERRY", "r"))
    assert lower["result"]["content"][0]["text"] == upper["result"]["content"][0]["text"] == "3"


def test_a_bad_input_is_a_flagged_result_not_a_protocol_error():
    [reply], _, _, _ = run_server(call(1, "Strawberry", "rr"))
    assert "error" not in reply                       # the tool ran and failed, so this is a normal result
    assert reply["result"]["isError"] is True
    assert "single character" in reply["result"]["content"][0]["text"]


def test_an_unknown_tool_is_a_protocol_error():
    [reply], _, _, _ = run_server(request(1, "tools/call", name="nope", arguments={}))
    assert reply["error"]["code"] == -32602


def test_an_unknown_method_is_a_protocol_error():
    [reply], _, _, _ = run_server(request(1, "does/not/exist"))
    assert reply["error"]["code"] == -32601


def test_a_request_without_meta_is_rejected():
    [reply], _, _, _ = run_server({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert reply["error"]["code"] == -32602


def test_an_unsupported_protocol_version_is_rejected_with_the_supported_list():
    bad = {"jsonrpc": "2.0", "id": 1, "method": "tools/list",
           "params": {"_meta": {**META, "io.modelcontextprotocol/protocolVersion": "1900-01-01"}}}
    [reply], _, _, _ = run_server(bad)
    assert reply["error"]["code"] == -32022
    assert reply["error"]["data"] == {"supported": ["2026-07-28"], "requested": "1900-01-01"}


def test_server_discover_lists_the_supported_versions():
    [reply], _, _, _ = run_server(request(1, "server/discover"))
    assert reply["result"]["supportedVersions"] == ["2026-07-28"]
    assert "tools" in reply["result"]["capabilities"]


def test_a_notification_gets_no_reply():
    replies, stdout, stderr, _ = run_server({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}})
    assert replies == [] and stdout == ""
    assert "notifications/cancelled" in stderr         # logs go to stderr, never stdout


def test_a_line_that_is_not_json_gets_a_parse_error_and_the_server_carries_on():
    replies, _, _, _ = run_server(raw="this is not json\n" + json.dumps(request(2, "tools/list")) + "\n")
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["id"] == 2                       # the next request was still served


def test_stdout_carries_only_json_lines_and_the_server_exits_when_stdin_closes():
    _, stdout, _, code = run_server(request(1, "tools/list"), call(2, "a", "a"))
    assert code == 0
    for line in stdout.splitlines():
        json.loads(line)                               # every line is a valid message
