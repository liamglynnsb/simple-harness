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

FUNCTIONS = {"calculator": calculator, "read_file": read_file}