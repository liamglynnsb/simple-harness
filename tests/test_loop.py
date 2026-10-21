import os
import re
import threading
import time
import pytest
import hooks
import loop
from loop import run_agent, AgentStopped
from fake_client import FakeClient, text_reply, tool_reply, tool_block
from tools import CALCULATOR, DELEGATE, READ_FILE, LIST_FILES, list_files, read_file
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
    assert "[truncated: showing characters 0 to 10 of 20" in cut


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
    assert stored.startswith("0123456789") and "showing characters 0 to 10 of 510" in stored
    assert "Call read_file again with start=10 to continue" in stored
    assert "x" * 50 not in stored                                    # the long text never entered the history


def test_read_file_start_reads_from_a_position(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("0123456789ABCDEFGHIJ")
    assert read_file(str(f)) == "0123456789ABCDEFGHIJ"
    assert read_file(str(f), start=10) == "ABCDEFGHIJ"
    assert read_file(str(f), start=20).startswith("(nothing at this position")


def test_read_file_rejects_a_bad_start(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("abc")
    for bad in (-1, "5", 1.5):
        with pytest.raises(ValueError):
            read_file(str(f), start=bad)


def test_the_model_can_page_through_a_long_file(data_scope, monkeypatch):
    monkeypatch.setattr("hooks.MAX_RESULT_CHARS", 10)
    path = str(data_scope / "data" / "long.txt")
    (data_scope / "data" / "long.txt").write_text("0123456789" + "ABCDEFGHIJ" + "KLMNO")
    client = FakeClient([
        tool_reply(tool_block("read_file", {"path": path}, "id1")),
        tool_reply(tool_block("read_file", {"path": path, "start": 10}, "id2")),
        tool_reply(tool_block("read_file", {"path": path, "start": 20}, "id3")),
        text_reply("found it"),
    ])
    messages = [{"role": "user", "content": "read all of it"}]
    run_agent(client, messages, [READ_FILE])
    first, second, third = (messages[i]["content"][0]["content"] for i in (2, 4, 6))
    assert first.startswith("0123456789") and "start=10 to continue" in first
    assert second.startswith("ABCDEFGHIJ") and "start=20 to continue" in second
    assert third == "KLMNO"                                    # the last piece fits, so no note


@pytest.fixture
def failure_log(tmp_path, monkeypatch):
    log = tmp_path / "hook_failures.log"
    monkeypatch.setattr("hooks.HOOK_FAILURE_LOG", str(log))
    return log


def _crashing_hook(tool_name, tool_input):
    raise RuntimeError("bug in the hook")


def test_a_crashing_noncritical_hook_is_recorded_and_the_call_goes_ahead(monkeypatch, failure_log):
    monkeypatch.setattr("hooks.BEFORE_HOOKS", [_crashing_hook])
    client = FakeClient([
        tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1")),
        text_reply("4"),
    ])
    messages = [{"role": "user", "content": "2+2"}]
    run_agent(client, messages, [CALCULATOR])
    result = messages[2]["content"][0]
    assert result["content"] == "4" and "is_error" not in result       # the tool ran anyway
    text = failure_log.read_text()
    assert "_crashing_hook" in text and "calculator" in text and "bug in the hook" in text   # what, where, and the traceback
    assert re.match(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text)                       # and when


def test_a_crashing_critical_hook_stops_the_run(monkeypatch, failure_log):
    monkeypatch.setattr("hooks.BEFORE_HOOKS", [hooks.critical(_crashing_hook)])
    client = FakeClient([tool_reply(tool_block("calculator", {"operation": "add", "a": 2, "b": 2}, "id1"))])
    messages = [{"role": "user", "content": "2+2"}]
    with pytest.raises(hooks.HookFailed):
        run_agent(client, messages, [CALCULATOR])
    assert len(messages) == 2                                           # no tool_result was ever built: the tool never ran
    assert "_crashing_hook" in failure_log.read_text()                  # and it was recorded


def test_a_critical_failure_in_a_subagent_stops_the_parent_too(monkeypatch, failure_log):
    monkeypatch.setattr("hooks.BEFORE_HOOKS", [hooks.critical(_crashing_hook)])
    client = FakeClient([
        tool_reply(tool_block("delegate", {"task": "read it"}, "id1")),   # parent
        tool_reply(tool_block("read_file", {"path": "x"}, "id2")),        # child: its hook crashes
    ])
    monkeypatch.setattr("client.make_client", lambda: client)
    messages = [{"role": "user", "content": "go"}]
    with pytest.raises(hooks.HookFailed):
        run_agent(client, messages, [DELEGATE])


# ---- parallel tools: the requests in one turn run at the same time, and results stay paired with their requests ----

def _two_requests(name_a, name_b):
    return FakeClient([
        tool_reply(tool_block(name_a, {}, "id1"), tool_block(name_b, {}, "id2")),
        text_reply("done"),
    ])


def test_parallel_tools_really_run_at_the_same_time(monkeypatch):
    meeting = threading.Barrier(2, timeout=5)        # each tool waits here until the OTHER one has also arrived
    def meet_a():
        meeting.wait()
        return "a done"
    def meet_b():
        meeting.wait()
        return "b done"
    monkeypatch.setattr("loop.FUNCTIONS", {**loop_functions(), "meet_a": meet_a, "meet_b": meet_b})
    messages = [{"role": "user", "content": "go"}]
    run_agent(_two_requests("meet_a", "meet_b"), messages, [{"name": "meet_a"}, {"name": "meet_b"}], parallel_tools=True)
    results = messages[2]["content"]
    assert [r["content"] for r in results] == ["a done", "b done"]    # impossible if they had run one after the other


def test_results_stay_in_request_order_even_when_the_first_finishes_last(monkeypatch):
    def slow():
        time.sleep(0.4)
        return "slow"
    def quick():
        return "quick"
    monkeypatch.setattr("loop.FUNCTIONS", {**loop_functions(), "slow": slow, "quick": quick})
    messages = [{"role": "user", "content": "go"}]
    run_agent(_two_requests("slow", "quick"), messages, [{"name": "slow"}, {"name": "quick"}], parallel_tools=True)
    results = messages[2]["content"]
    assert [(r["tool_use_id"], r["content"]) for r in results] == [("id1", "slow"), ("id2", "quick")]


def test_without_the_setting_tools_still_run_one_after_another(monkeypatch):
    order = []
    def first():
        order.append("first start"); time.sleep(0.2); order.append("first end")
        return "1"
    def second():
        order.append("second start")
        return "2"
    monkeypatch.setattr("loop.FUNCTIONS", {**loop_functions(), "first": first, "second": second})
    messages = [{"role": "user", "content": "go"}]
    run_agent(_two_requests("first", "second"), messages, [{"name": "first"}, {"name": "second"}])
    assert order == ["first start", "first end", "second start"]       # the default behaviour is unchanged


def test_a_failing_tool_in_a_parallel_turn_is_flagged_and_the_others_still_return(monkeypatch):
    def boom():
        raise ValueError("it broke")
    def fine():
        return "fine"
    monkeypatch.setattr("loop.FUNCTIONS", {**loop_functions(), "boom": boom, "fine": fine})
    messages = [{"role": "user", "content": "go"}]
    run_agent(_two_requests("boom", "fine"), messages, [{"name": "boom"}, {"name": "fine"}], parallel_tools=True)
    first, second = messages[2]["content"]
    assert first["is_error"] is True and first["content"] == "Error: it broke"
    assert second["content"] == "fine" and "is_error" not in second


def loop_functions():
    """A copy of the loop's tool table, so a test can add its own tools without touching the real one."""
    return dict(loop.FUNCTIONS)

