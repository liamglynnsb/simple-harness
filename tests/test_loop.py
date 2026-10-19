import pytest
from loop import run_agent, AgentStopped
from fake_client import FakeClient, text_reply, tool_reply, tool_block
from tools import CALCULATOR, DELEGATE
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

def test_unknown_tool_name_finish():
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

def test_tool_raise_finish():
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

def test_no_system_prompt_finish():
    client = FakeClient([text_reply("howzit")])
    messages = [{"role": "user", "content": "hello"}]
    answer = run_agent(client, messages, [])
    assert "system" not in client.calls[0]
    assert len(messages) == 2
    assert len(client.calls) == 1
    assert client.replies == []

def test_system_prompt_finish():
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1")), text_reply("The result is 4")])
    messages = [{"role": "user", "content": "What is 2 + 2?"}]
    answer = run_agent(client, messages, [CALCULATOR], system="Be concise.")
    assert messages[2]["content"][0]["tool_use_id"] == "id1"
    assert messages[2]["content"][0]["content"] == "4"
    assert client.calls[0]["system"] == "Be concise."
    assert client.calls[1]["system"] == "Be concise."
    assert "is_error" not in messages[2]["content"][0]
    assert answer == "The result is 4"
    assert len(messages) == 4
    assert len(client.calls) == 2
    assert client.replies == []

def test_delegate_finish(monkeypatch):
    task = "Find the magic word."
    client = FakeClient([
        tool_reply(tool_block("delegate", {"task": task}, "id1")),   # parent, call 1: delegate
        text_reply("The magic word is banana."),                     # child: answers at once, no tools
        text_reply("Banana"),                                        # parent, call 2: its own final answer
    ])
    # delegate() calls make_client() to get the child's client; make it return the fake, so no real API call
    monkeypatch.setattr("client.make_client", lambda: client)
    messages = [{"role": "user", "content": "What is the magic word?"}]
    answer = run_agent(client, messages, [DELEGATE])
    child_messages = client.calls[1]["messages"]       # the child's own list, recorded by the fake
    assert child_messages is not messages              # two separate lists
    assert len(child_messages) == 2                    # the child saw its task and its own answer, nothing else
    assert child_messages[0]["content"] == task        # the child's history starts with just the task
    assert len(messages) == 4                          # the parent's history: question, delegate request, result, answer
    assert messages[1]["content"][0].name == "delegate"
    assert messages[2]["content"][0]["content"] == "The magic word is banana."   # only the child's final text
    assert answer == "Banana"
    assert len(client.calls) == 3
    assert client.replies == []

def test_tool_not_given_is_refused():
    # read_file exists in FUNCTIONS, but this agent was only given the calculator
    client = FakeClient([
        tool_reply(tool_block("read_file", {"path": "data/a.txt"}, "id1")),
        text_reply("I can't read files."),
    ])
    messages = [{"role": "user", "content": "What does data/a.txt say?"}]
    answer = run_agent(client, messages, [CALCULATOR])
    result = messages[2]["content"][0]
    assert result["tool_use_id"] == "id1"
    assert result["is_error"] == True
    assert result["content"] == "Unknown tool: read_file. Available tools: calculator"
    assert "banana" not in result["content"]            # the file was never read
    assert answer == "I can't read files."
    assert len(client.calls) == 2
    assert client.replies == []

def test_raise_on_failure_raises_instead_of_returning():
    # one pass allowed, and the model keeps asking for a tool, so the pass limit is hit
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "a": 1, "b": 1}, "id1"))])
    messages = [{"role": "user", "content": "keep adding"}]
    with pytest.raises(AgentStopped, match="pass limit"):
        run_agent(client, messages, [CALCULATOR], max_loops=1, raise_on_failure=True)


def test_failed_subagent_reaches_parent_as_an_error(monkeypatch):
    # the child never finishes: it asks for read_file on all 10 of its passes (the default pass limit)
    child_passes = [tool_reply(tool_block("read_file", {"path": "data/a.txt"}, "c" + str(n))) for n in range(10)]
    client = FakeClient(
        [tool_reply(tool_block("delegate", {"task": "Read data/a.txt."}, "id1"))]   # parent, call 1
        + child_passes                                                                # the child, 10 calls
        + [text_reply("The helper failed.")]                                          # parent, call 2
    )
    monkeypatch.setattr("client.make_client", lambda: client)
    messages = [{"role": "user", "content": "What does data/a.txt say?"}]
    answer = run_agent(client, messages, [DELEGATE])
    result = messages[2]["content"][0]
    assert result["tool_use_id"] == "id1"
    assert result["is_error"] == True                      # the parent is told it failed, not handed text as an answer
    assert result["content"].startswith("Error: The subagent did not finish: it reached its pass limit")
    assert answer == "The helper failed."
    assert client.replies == []