# Hooks: small functions the harness runs around every tool call, in one place (execute_tool in loop.py).
# A before-hook is called as hook(tool_name, tool_input) just before a tool runs. It returns None to let
# the call go ahead, or a string giving the reason to BLOCK it (a deliberate decision, not an error).
# The list is looked up at call time (hooks.BEFORE_HOOKS), so a test can swap it for its own.
import os

# The one place file tools may read from (decided for the whole harness, not chosen by the model).
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def log_call(tool_name, tool_input):
    """The trace line for every tool request. It replaced the print that used to sit in the loop."""
    print("calling", tool_name, "with input", tool_input)


def only_inside_data(tool_name, tool_input):
    """Block read_file unless the path, once fully resolved, is inside DATA_DIR. Other tools pass.

    realpath() resolves '..' and symlinks first, so the check is on where the path REALLY leads,
    not on how it is written.
    """
    if tool_name != "read_file":
        return None
    path = tool_input.get("path")
    if not isinstance(path, str):
        return "read_file needs a text path"
    real = os.path.realpath(path)
    root = os.path.realpath(DATA_DIR)
    if os.path.commonpath([real, root]) != root:
        return "read_file can only read files inside data/ (got: " + path + ")"
    return None


BEFORE_HOOKS = [log_call, only_inside_data]
