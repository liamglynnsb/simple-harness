# Hooks: small functions the harness runs around every tool call, in one place (execute_tool in loop.py).
# A before-hook is called as hook(tool_name, tool_input) just before a tool runs.
# The list is looked up at call time (hooks.BEFORE_HOOKS), so a test can swap it for its own.


def log_call(tool_name, tool_input):
    """The trace line for every tool request. It replaced the print that used to sit in the loop."""
    print("calling", tool_name, "with input", tool_input)


BEFORE_HOOKS = [log_call]
