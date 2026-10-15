from skills import read_skills

skills_dict = read_skills()
skills_descriptions = "\n".join([f"{name}: {skill['description']}" for name, skill in skills_dict.items()])


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
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    else:
        return a / b

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
    with open(path) as f:
        return f.read()

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
    if name not in skills_dict:
        raise ValueError(f"Skill {name} not found. Please choose a valid skill from the following list: {list(skills_dict.keys())}")
    return skills_dict[name]["body"]


FUNCTIONS = {"calculator": calculator, "read_file": read_file, "load_skill": load_skill}