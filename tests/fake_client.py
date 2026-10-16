from types import SimpleNamespace

class FakeClient:
    """A stand-in for the real SDK client, for tests. It plays back scripted replies.

    It has no logic: each time the loop asks for a reply, it hands out the next one from
    the script (in order) and writes down what it was sent. The test decides the script,
    then checks the log afterward.
    """

    def __init__(self, replies):
        self.replies = list(replies)  # the script; list() makes a copy, so the test's own list is never emptied
        self.calls = []               # a log of every call's arguments, for the test to inspect
        # The loop calls client.messages.create(...), so .messages must exist and have a create.
        # No parentheses after _create: store the method to run later, not run it now.
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        """Stands in for the real messages.create. **kwargs collects every named argument
        the loop passed (model, max_tokens, tools, messages) into one dict."""
        self.calls.append((kwargs))     # job 1: write down what we were sent
        return self.replies.pop(0)      # job 2: hand back the next scripted reply (the front of the list)