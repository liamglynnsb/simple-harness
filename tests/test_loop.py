from loop import run_agent
from fake_client import FakeClient, text_reply

def test_plain_finish():
    client = FakeClient([text_reply("hello")])
    starting_messages = [{"role": "user", "content": "hi"}]
    answer = run_agent(client, starting_messages, [])
    assert answer == "hello"
    assert len(client.calls) == 1
    assert client.replies == []