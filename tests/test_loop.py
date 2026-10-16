from loop import run_agent
from fake_client import FakeClient, text_reply, tool_reply
from tools import CALCULATOR

def test_plain_finish():
    client = FakeClient([text_reply("hello")])
    messages = [{"role": "user", "content": "hi"}]
    answer = run_agent(client, messages, [])
    assert answer == "hello"
    assert len(client.calls) == 1
    assert client.replies == []

def test_tool_finish():
    client = FakeClient([tool_reply("calculator", {"operation": "add", "a": 2, "b": 2}, "id1"), text_reply("The result is 4")])
    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["result"] == 4
    assert messages[2]["content"][0]["is_error"] == False
    assert answer == "The result is 4"
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []
