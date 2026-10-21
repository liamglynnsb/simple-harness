# Measuring what a run costs: wrap the model client, and every call is timed and its token usage written down.
# (run_agent doesn't report usage, so the numbers have to be collected around the client. Layer 5 builds proper tracing.)
import time
from types import SimpleNamespace


class MeasuringClient:
    """Looks like the real client (it has .messages.create), forwards every call to it, and records what each call cost.

        measured = MeasuringClient(make_client())
        run_agent(measured, messages, tools)
        print(measured.summary())
    """

    def __init__(self, client):
        self.client = client
        self.calls = []  # one dict per call: how long it took and how many tokens went in and out
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        started = time.time()
        response = self.client.messages.create(**kwargs)
        self.calls.append({
            "seconds": time.time() - started,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        })
        return response

    def summary(self):
        return {
            "passes": len(self.calls),
            "input_tokens": sum(c["input_tokens"] for c in self.calls),
            "output_tokens": sum(c["output_tokens"] for c in self.calls),
            "model_seconds": sum(c["seconds"] for c in self.calls),
        }
