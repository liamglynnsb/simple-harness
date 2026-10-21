import os
import pytest
import hooks
from loop import run_agent, AgentStopped
from fake_client import FakeClient, text_reply, tool_reply, tool_block
from tools import CALCULATOR, DELEGATE, READ_FILE, LIST_FILES, list_files
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


def test_before_hooks_run_before_each_tool_call(monkeypatch):
    seen = []
    monkeypatch.setattr("hooks.BEFORE_HOOKS", [lambda name, tool_input: seen.append((name, tool_input))])
    client = FakeClient([
        tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1"),
                   tool_block("calculator", {"operation": "add", "a": 3, "b": 3}, "id2")),
        text_reply("done"),
    ])
    messages = [{"role": "user", "content": "two sums"}]
    run_agent(client, messages, [CALCULATOR])
    assert seen == [("calculator", {"operation": "add", "a": 2, "b": 2}),
                    ("calculator", {"operation": "add", "a": 3, "b": 3})]   # once per request, in order


@pytest.fixture
def data_scope(tmp_path, monkeypatch):
    """A scratch data/ folder as the allowed scope, plus a secret file OUTSIDE it (never the real .env)."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "ok.txt").write_text("fine")
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    monkeypatch.setattr("hooks.DATA_DIR", str(data))
    return tmp_path


def test_hook_allows_a_file_inside_data(data_scope):
    assert hooks.guard_file_paths("read_file", {"path": str(data_scope / "data" / "ok.txt")}) is None


def test_hook_blocks_a_file_outside_data(data_scope):
    reason = hooks.guard_file_paths("read_file", {"path": str(data_scope / "secret.txt")})
    assert reason is not None and "inside data/" in reason


def test_hook_ignores_other_tools(data_scope):
    assert hooks.guard_file_paths("calculator", {"operation": "add", "a": 1, "b": 1}) is None


def test_a_blocked_read_reaches_the_model_as_a_flagged_error(data_scope):
    client = FakeClient([
        tool_reply(tool_block("read_file", {"path": str(data_scope / "secret.txt")}, "id1")),
        text_reply("I can't read that."),
    ])
    messages = [{"role": "user", "content": "read the secret"}]
    run_agent(client, messages, [READ_FILE])
    result = messages[2]["content"][0]
    assert result["tool_use_id"] == "id1"
    assert result["is_error"] == True
    assert result["content"].startswith("Blocked: read_file can only use paths inside data/")
    assert "TOP SECRET" not in result["content"]            # the file was never read


def test_hook_blocks_dotdot_that_climbs_out_of_data(data_scope):
    # starts inside data/ but '..' steps back up and takes the secret in the folder above
    sneaky = os.path.join(str(data_scope / "data"), "..", "secret.txt")
    assert hooks.guard_file_paths("read_file", {"path": sneaky}) is not None


def test_hook_blocks_a_symlink_inside_data_that_points_outside(data_scope):
    # data/link.txt LOOKS like it is inside data/, but it is a shortcut to the secret outside it
    link = data_scope / "data" / "link.txt"
    os.symlink(str(data_scope / "secret.txt"), str(link))
    assert hooks.guard_file_paths("read_file", {"path": str(link)}) is not None


def test_hook_allows_dotdot_that_stays_inside_data(data_scope):
    # steps out of data/ and straight back in: the real destination is inside, so it is allowed
    roundabout = os.path.join(str(data_scope / "data"), "..", "data", "ok.txt")
    assert hooks.guard_file_paths("read_file", {"path": roundabout}) is None


def test_sensitive_names_are_recognised():
    assert hooks.is_sensitive_name(".env") and hooks.is_sensitive_name(".git")
    assert hooks.is_sensitive_name("server.PEM") and hooks.is_sensitive_name("my_secret_notes.txt")
    assert not hooks.is_sensitive_name("a.txt") and not hooks.is_sensitive_name("numbers.txt")


def test_hook_blocks_a_hidden_file_even_inside_data(data_scope):
    (data_scope / "data" / ".env").write_text("KEY=hidden")
    assert hooks.guard_file_paths("read_file", {"path": str(data_scope / "data" / ".env")}) is not None


def test_hook_applies_the_same_scope_to_list_files(data_scope):
    assert hooks.guard_file_paths("list_files", {"path": str(data_scope / "data")}) is None
    assert hooks.guard_file_paths("list_files", {"path": str(data_scope)}) is not None   # the folder above data/


def test_list_files_leaves_out_hidden_and_secret_looking_names(data_scope):
    (data_scope / "data" / ".env").write_text("KEY=hidden")
    (data_scope / "data" / "api_token.txt").write_text("hidden too")
    (data_scope / "data" / "notes").mkdir()
    assert list_files(str(data_scope / "data")) == "notes/\nok.txt"


def test_the_model_can_list_a_folder_inside_data_but_not_outside(data_scope):
    client = FakeClient([
        tool_reply(tool_block("list_files", {"path": str(data_scope / "data")}, "id1"),
                   tool_block("list_files", {"path": str(data_scope)}, "id2")),
        text_reply("done"),
    ])
    messages = [{"role": "user", "content": "list both"}]
    run_agent(client, messages, [LIST_FILES])
    inside, outside = messages[2]["content"]
    assert inside["content"] == "ok.txt" and "is_error" not in inside
    assert outside["is_error"] == True and outside["content"].startswith("Blocked: list_files can only use paths inside data/")
    assert "secret.txt" not in outside["content"]              # the file above data/ was never listed


def test_after_hook_leaves_a_short_result_alone():
    assert hooks.truncate_long_results("read_file", {}, "short") == "short"


def test_after_hook_cuts_a_long_result_and_says_so(monkeypatch):
    monkeypatch.setattr("hooks.MAX_RESULT_CHARS", 10)
    cut = hooks.truncate_long_results("read_file", {}, "0123456789ABCDEFGHIJ")
    assert cut.startswith("0123456789")
    assert "ABCDEFGHIJ" not in cut                                   # the tail is gone
    assert "[truncated: showing the first 10 of 20 characters]" in cut


def test_a_long_result_is_cut_before_it_enters_the_history(data_scope, monkeypatch):
    monkeypatch.setattr("hooks.MAX_RESULT_CHARS", 10)
    (data_scope / "data" / "long.txt").write_text("0123456789" + "x" * 500)
    client = FakeClient([
        tool_reply(tool_block("read_file", {"path": str(data_scope / "data" / "long.txt")}, "id1")),
        text_reply("done"),
    ])
    messages = [{"role": "user", "content": "read it"}]
    run_agent(client, messages, [READ_FILE])
    stored = messages[2]["content"][0]["content"]                    # what is in the history the model will be sent
    assert stored.startswith("0123456789") and "[truncated: showing the first 10 of 510 characters]" in stored
    assert "x" * 50 not in stored                                    # the long text never entered the history

