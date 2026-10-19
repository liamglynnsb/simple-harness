# Every tool the model can use lives here, in two halves that must agree:
#   1. a DEFINITION (a dict): what the model reads - name, description, and the shape of its inputs
#   2. a FUNCTION: the real code that runs when the model asks for that tool
# FUNCTIONS at the bottom maps each tool's name to its function.
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
    "description": "Read a file and return its contents. The path is relative to the project's folder.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    }
}

def read_file(path):
    """Return the text of a file. A missing file raises an error, which the loop catches and
    sends back to the model. NOTE: it can open ANY file the process can read (including .env);
    restricting it is planned for Layer 2, Step 4 (a blocking hook)."""
    with open(path) as f:
        return f.read()

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
        "The subagent can read text files in the project's folder (for example data/a.txt) and nothing else. "
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

def delegate(task, client=None):
    if client is None:
        from client import make_client
        client = make_client()
    
    from loop import run_agent # we need to import run agent here to make sure both files have been loaded and avoid circular imports
    messages = [{"role": "user", "content": task}]
    answer = run_agent(client, messages, [READ_FILE])  # the child's tools: fixed here, not chosen by the model
    return answer

# Name -> function. The loop looks up each tool request here: FUNCTIONS[block.name](**block.input).
# A new tool needs both a definition above and an entry here.
FUNCTIONS = {"calculator": calculator, "read_file": read_file, "load_skill": load_skill, "delegate": delegate}