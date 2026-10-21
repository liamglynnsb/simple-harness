"""Tests for measure.py: the wrapper must record each call and still behave like the client it wraps."""
from types import SimpleNamespace

from fake_client import FakeClient, text_reply
from measure import MeasuringClient


def reply_with_usage(text, input_tokens, output_tokens):
    reply = text_reply(text)
    reply.usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return reply


def test_each_call_is_recorded_and_summed():
    inner = FakeClient([reply_with_usage("a", 100, 10), reply_with_usage("b", 250, 20)])
    measured = MeasuringClient(inner)
    measured.messages.create(model="m", messages=[])
    measured.messages.create(model="m", messages=[])
    assert [c["input_tokens"] for c in measured.calls] == [100, 250]
    summary = measured.summary()
    assert summary["passes"] == 2
    assert summary["input_tokens"] == 350 and summary["output_tokens"] == 30


def test_the_wrapper_returns_the_real_reply_and_passes_the_arguments_on():
    inner = FakeClient([reply_with_usage("hello", 1, 1)])
    measured = MeasuringClient(inner)
    reply = measured.messages.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert reply.content[0].text == "hello"
    assert inner.calls[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_calls_can_be_told_apart_by_the_tools_they_were_given_and_summed_separately():
    inner = FakeClient([reply_with_usage("a", 100, 10), reply_with_usage("b", 40, 5), reply_with_usage("c", 60, 5)])
    measured = MeasuringClient(inner)
    measured.messages.create(model="m", messages=[], tools=[{"name": "delegate"}])       # an orchestrator call
    measured.messages.create(model="m", messages=[], tools=[{"name": "read_file"}])      # a subagent call
    measured.messages.create(model="m", messages=[], tools=[{"name": "read_file"}])      # another subagent call
    subagent_calls = [c for c in measured.calls if "delegate" not in c["tools"]]
    assert measured.summary(subagent_calls)["input_tokens"] == 100                       # 40 + 60
    assert measured.summary()["input_tokens"] == 200                                     # everything

