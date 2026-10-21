# Hooks: small functions the harness runs around every tool call, in one place (execute_tool in loop.py).
# A before-hook is called as hook(tool_name, tool_input) just before a tool runs. It returns None to let
# the call go ahead, or a string giving the reason to BLOCK it (a deliberate decision, not an error).
# The list is looked up at call time (hooks.BEFORE_HOOKS), so a test can swap it for its own.
import os
import traceback
from datetime import datetime, timezone

# The one place file tools may read from (decided for the whole harness, not chosen by the model).
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# What happens when a hook itself crashes depends on what the hook is for. Ask: if this hook were silently
# skipped, would something bad get through? If yes, mark it @critical: a crash stops the whole run (HookFailed).
# If no, the crash is recorded and the call goes ahead.
HOOK_FAILURE_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_failures.log")  # git-ignored


class HookFailed(Exception):
    """A critical hook crashed. Raised out of the loop to stop the run: the rule it enforces can't be trusted."""


def critical(hook):
    """Mark a hook as critical (used as @critical above its def)."""
    hook.critical = True
    return hook


def record_failure(hook, tool_name, tool_input):
    """Write a hook crash to HOOK_FAILURE_LOG (when, hook, tool, input, traceback) and print a one-line notice. The
    harness does this itself, so we never depend on the model to report a bug in our own code. A run id and a
    pass number are planned for Layer 5 (tracing), where they will be added to every record at once."""
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = "[" + when + "] hook " + hook.__name__ + " crashed on " + tool_name + " " + repr(tool_input) + "\n" + traceback.format_exc() + "\n"
    with open(HOOK_FAILURE_LOG, "a") as f:
        f.write(entry)
    print("HOOK FAILED:", hook.__name__, "on", tool_name, "(details in hook_failures.log)")


def log_call(tool_name, tool_input):
    """The trace line for every tool request. It replaced the print that used to sit in the loop."""
    print("calling", tool_name, "with input", tool_input)


# The tools that take a file or folder path. They all follow the same rule below.
FILE_TOOLS = ("read_file", "list_files")


def is_sensitive_name(name):
    """True for a file or folder name the model should never see or open: hidden names (.env, .git, ...) and
    names that look like secrets. This is a heuristic, a second layer: the real protection is the scope
    (only inside DATA_DIR), which no name can get around."""
    lowered = name.lower()
    return (
        lowered.startswith(".")
        or lowered.endswith((".pem", ".key"))
        or any(word in lowered for word in ("secret", "credential", "token"))
    )


@critical
def guard_file_paths(tool_name, tool_input):
    """One rule for every file tool: the path, once fully resolved, must be inside DATA_DIR, and nothing
    on the way down from DATA_DIR may be a sensitive name. Other tools pass.

    realpath() resolves '..' and symlinks first, so the check is on where the path REALLY leads,
    not on how it is written.
    """
    if tool_name not in FILE_TOOLS:
        return None
    path = tool_input.get("path")
    if not isinstance(path, str):
        return tool_name + " needs a text path"
    real = os.path.realpath(path)
    root = os.path.realpath(DATA_DIR)
    if os.path.commonpath([real, root]) != root:
        return tool_name + " can only use paths inside data/ (got: " + path + ")"
    inside = os.path.relpath(real, root)
    parts = [] if inside == "." else inside.split(os.sep)
    if any(is_sensitive_name(part) for part in parts):
        return tool_name + " can't use hidden or secret-looking names (got: " + path + ")"
    return None


BEFORE_HOOKS = [log_call, guard_file_paths]


# An after-hook is called as hook(tool_name, tool_input, result) once a tool has returned, and returns the result
# the model will see (it may change it). It runs before the tool_result is built, so what it returns is what
# enters the history. Like BEFORE_HOOKS, the list is looked up at call time.

MAX_RESULT_CHARS = 4000  # about 1,000 tokens; a result longer than this is cut


def truncate_long_results(tool_name, tool_input, result):
    """Cut any result longer than MAX_RESULT_CHARS, and say so, so the model can't mistake it for the whole."""
    if len(result) <= MAX_RESULT_CHARS:
        return result
    # For read_file the result began at the model's `start`, so work out where in the whole file we are.
    start = tool_input.get("start", 0) if tool_name == "read_file" else 0
    if not isinstance(start, int):
        start = 0
    shown_to = start + MAX_RESULT_CHARS
    note = "\n[truncated: showing characters " + str(start) + " to " + str(shown_to) + " of " + str(start + len(result))
    if tool_name == "read_file":
        note += ". Call read_file again with start=" + str(shown_to) + " to continue"
    return result[:MAX_RESULT_CHARS] + note + "]"


AFTER_HOOKS = [truncate_long_results]
