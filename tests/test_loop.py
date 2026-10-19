from loop import run_agent
from fake_client import FakeClient, text_reply, tool_reply, tool_block
from tools import CALCULATOR
from types import SimpleNamespace

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

def test_unknown_tool_name_finish():
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "divide", "a": 2, "b": 0}, "id1")), text_reply("I can't divide by zero.")])
    messages = [{"role": "user", "content": "What is 2 / 0?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["content"].startswith("Error: division by zero")
    assert messages[2]["content"][0]["is_error"] == True
    assert answer == "I can't divide by zero."
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []

def test_unknown_tool_argument_finish():
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "x": 2, "b": 2}, "id1")), text_reply("That tool doesn't take that argument.")])
    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["is_error"] == True
    assert answer == "That tool doesn't take that argument."
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []

def test_max_tokens_reply_text_finish():
    client = FakeClient([text_reply("h", "max_tokens")])
    messages = [{"role": "user", "content": "hello"}]
    answer = run_agent(client, messages, [])
    assert answer == "h" + "\n" + "Response stopped; max tokens reached"
    assert len(messages) == 2
    assert len(client.calls) == 1
    assert client.replies == []

def test_max_tokens_reply_no_text_finish():
    client = FakeClient([SimpleNamespace(stop_reason="max_tokens", content=[SimpleNamespace(type="thinking", thinking="")])])
    messages = [{"role": "user", "content": "hello"}]
    answer = run_agent(client, messages, [])
    assert answer == "Response stopped; max tokens reached"
    assert len(messages) == 2
    assert len(client.calls) == 1
    assert client.replies == []

def test_other_stop_reason_finish():
    client = FakeClient([text_reply("Response stopped due to refusal", "refusal")])
    messages = [{"role": "user", "content": "hello"}]
    answer = run_agent(client, messages, [])
    assert answer == "Response stopped due to: refusal"
    assert len(messages) == 2
    assert len(client.calls) == 1
    assert client.replies == []

def test_max_loops_finish():
    client = FakeClient([
        tool_reply(tool_block("calculator", {"operation": "add", "a": 1, "b": 1}, "id1")),
        tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id2")),
        tool_reply(tool_block("calculator", {"operation": "add", "a": 3, "b": 3}, "id3")),
    ])
    messages = [{"role": "user", "content": "keep adding"}]
    answer = run_agent(client, messages, [CALCULATOR], max_loops=3)
    assert answer == "Error: Max loops reached"
    assert len(messages) == 7
    assert len(client.calls) == 3
    assert client.replies == []