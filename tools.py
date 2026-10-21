# Every tool the model can use lives here, in two halves that must agree:
#   1. a DEFINITION (a dict): what the model reads - name, description, and the shape of its inputs
#   2. a FUNCTION: the real code that runs when the model asks for that tool
# FUNCTIONS at the bottom maps each tool's name to its function.
import os
from hooks import is_sensitive_name
from skills import read_skills

# Read the skill files once, when this module is first imported (see skills.py).
skills_dict = read_skills()
# The menu for load_skill's description: one "name: description" line per skill (no bodies).
skills_descriptions = "\n".join([f"{name}: {skill['description']}" for name, skill in skills_dict.items()])


# What the model reads about the calculator: a name, a description, and the shape of its inputs.
# This is only the description of the tool. The function below is what actually runs.
CALCULATOR = {
    "name": "calculator",
    "description": "Do basic arithmetic on two numbers",
    "input_schema": {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["operation", "a", "b"],
    },
}

def calculator(operation, a, b):
    """The real calculator. Its parameter names must match the schema's property names above,
    because the loop calls it as calculator(**block.input)."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    else:
        return a / b

# The model's view of read_file: one input, a path (relative to where the script is run from).
READ_FILE = {
    "name": "read_file",
    "description": "Read a text file and return its contents. The path is relative to the project's folder. "
                   "A long file comes back cut off; to read on from where a result stopped, call again with start.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "start": {"type": "integer", "description": "Optional. The character position to start reading from (default 0)."},
        },
        "required": ["path"],
    }
}

def read_file(path, start=0):
    """Return the text of a file, from the character position `start` (default 0). A missing file raises an
    error, which the loop catches and sends back to the model. The scope (only inside data/) is enforced by
    the before-hook in hooks.py, and a long result is cut by the after-hook, so this function stays simple."""
    if not isinstance(start, int) or start < 0:
        raise ValueError("start must be a whole number, 0 or more")
    with open(path) as f:
        text = f.read()
    if start > 0 and start >= len(text):
        return "(nothing at this position: the file has " + str(len(text)) + " characters)"
    return text[start:]

# The model's view of list_files: one input, a folder path. The scope (only inside data/) is enforced by the
# before-hook in hooks.py, before this function ever runs.
LIST_FILES = {
    "name": "list_files",
    "description": "List the files and folders inside a folder, one name per line (folders end with /; each file shows its "
                   "size in bytes, which tells you how many pieces read_file will need). "
                   "Only folders inside data/ can be listed. Use it to find the right file name when a path is not found.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "A folder inside data/, for example 'data'"},
        },
        "required": ["path"],
    },
}

def list_files(path):
    """The names in a folder, one per line (folders end with /; a file shows its size in bytes). Hidden and
    secret-looking names are left out, using the same name test as the hook, so a listing never shows what a read
    would refuse. The size lets a model plan how many pieces a long file needs before it reads any."""
    names = []
    for name in sorted(os.listdir(path)):
        if is_sensitive_name(name):
            continue
        full = os.path.join(path, name)
        names.append(name + "/" if os.path.isdir(full) else name + " (" + str(os.path.getsize(full)) + " bytes)")
    return "\n".join(names) if names else "(empty)"

# The model's view of load_skill. The description carries the menu of skills (names and short
# descriptions only); the enum is generated from skills_dict so it can't drift out of date.
LOAD_SKILL = {
    "name": "load_skill",
    "description": f"Load one skill from the skills dictionary. Available skills: {skills_descriptions}",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": list(skills_dict.keys())},
        },
        "required": ["name"],
    }
}

def load_skill(name):
    """Return the full instructions (the body) of one skill.

    The model asks for a skill by name. An unknown name raises an error with a clear message;
    the loop catches it and sends it back flagged as an error, so the model can try again.
    """
    if name not in skills_dict:
        raise ValueError(f"Skill {name} not found. Please choose a valid skill from the following list: {sorted(skills_dict.keys())}")
    return skills_dict[name]["body"]

# The model's view of delegate. The description states what the subagent can do (its tools are fixed
# in delegate() below), so keep the two in step: change one, change the other.
DELEGATE = {
    "name": "delegate",
    "description": (
        "Hand a task to a separate subagent and get back only its final answer. "
        "The subagent can read text files in the project's folder (for example data/a.txt) and list folders, and nothing else. "
        "You cannot read files yourself, so use this whenever you need a file's contents. "
        "The subagent cannot see this conversation: it sees only the task text, so the task must contain "
        "everything it needs, including the file path, and say what to return."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "A complete, self-contained instruction for the subagent, for example "
                               "'Read data/a.txt and reply with its contents.'",
            },
        },
        "required": ["task"],
    },
}

# ---------------------------------------------------------------------------------------------------------
# YOU WRITE THIS: the standing instructions every subagent gets on every call (its system prompt). It is written
# once here, so the orchestrator doesn't have to repeat it in every task. It should say, for a subagent that is asked
# to find something in a file:
#   - look at the file's size first (list the folder: the listing shows each file's size in bytes)
#   - read_file returns 4,000 characters per piece and takes a `start` input: work out every piece the file needs
#     and request ALL of them in a single turn, not one at a time
#   - reply with only the answer, in the form the task asks for, and nothing else
SUBAGENT_SYSTEM_PROMPT = (
    "You are a subagent. You are given one task and you see nothing else, so do exactly that task and nothing more.\n"
    "\n"
    "When the task is to find something in a file:\n"
    "1. First list the file's folder with list_files. The listing shows each file's size in bytes.\n"
    "2. read_file returns at most 4,000 characters per piece and takes an optional start input, a character position. "
    "From the file's size, work out how many pieces it needs (they start at 0, 4000, 8000 and so on until the whole file "
    "is covered), and request ALL of them in a single turn. Do not read them one at a time.\n"
    "3. Once you have the whole text, reply with only the answer, in the form the task asks for, and nothing else."
)
# ---------------------------------------------------------------------------------------------------------


def delegate(task, client=None):
    if client is None:
        from client import make_client
        client = make_client()
    
    from loop import run_agent, AgentStopped # imported here so both files have been loaded (avoids a circular import)
    messages = [{"role": "user", "content": task}]
    try:
        # the child's tools are fixed here, not chosen by the model; a child that fails must raise, because
        # the parent would take any returned text for a real answer
        return run_agent(client, messages, [READ_FILE, LIST_FILES], raise_on_failure=True,
                         system=SUBAGENT_SYSTEM_PROMPT or None)  # the harness decides this, not the model; empty means none
    except AgentStopped as e:
        raise RuntimeError("The subagent did not finish: " + str(e))

# Name -> function. The loop looks up each tool request here: FUNCTIONS[block.name](**block.input).
# A new tool needs both a definition above and an entry here.
FUNCTIONS = {"calculator": calculator, "read_file": read_file, "list_files": list_files, "load_skill": load_skill, "delegate": delegate}