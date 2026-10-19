from loop import run_agent
from fake_client import FakeClient, text_reply, tool_reply, tool_block
from tools import CALCULATOR

def test_plain_finish():
    client = FakeClient([text_reply("hello")])
    messages = [{"role": "user", "content": "hi"}]
    answer = run_agent(client, messages, [])
    assert answer == "hello"
    assert len(client.calls) == 1
    assert client.replies == []

def test_tool_finish():
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1")), text_reply("The result is 4")])
    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["content"] == "4"
    assert "is_error" not in messages[2]["content"][0]
    assert answer == "The result is 4"
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []

def test_multiple_tool_finish():
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1"), tool_block("calculator", {"operation": "subtract", "a": 5, "b": 3}, "id2")), text_reply("2 + 2 is 4. 5 - 3 is 2.")])
    messages = [{"role": "user", "content": "What is 2 + 2? What is 5 - 3?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][1]["tool_use_id"] == "id2"
    assert messages[2]["content"][0]["content"] == "4"
    assert messages[2]["content"][1]["content"] == "2"
    assert "is_error" not in messages[2]["content"][0]
    assert "is_error" not in messages[2]["content"][1]
    assert answer == "2 + 2 is 4. 5 - 3 is 2."
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []

def test_unknown_tool_finish():
    client = FakeClient([tool_reply(tool_block("unknown", {"operation": "add", "a": 2, "b": 2}, "id1")), text_reply("That tool doesn't exist.")])
    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["content"].startswith("Unknown tool: unknown")
    assert messages[2]["content"][0]["is_error"] == True
    assert answer == "That tool doesn't exist."
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []