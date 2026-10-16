from pathlib import Path

def read_skills(folder="skills"):
    """Read every skill file in the folder into a dict: {name: {"description": ..., "body": ...}}.

    A skill file is a `name:` line, a `description:` line, a line with ---, then the
    instructions (the body). This runs once, when tools.py is first imported; load_skill
    later just looks things up in the result and never touches the files.
    """
    skills = {}
    for path in Path(folder).glob("*.md"):  # every .md file in the folder (order is not guaranteed)
        text = path.read_text()
        # split at the first "---" line: the header is before it, the body after it
        header, _, body = text.partition("\n---\n")
        lines = header.splitlines()
        # each header line looks like "name: value": split once on ": " and keep the value ([1])
        name = lines[0].split(": ", 1)[1]
        description = lines[1].split(": ", 1)[1]
        skills[name] = {"description": description, "body": body}  # the name is the key
    return skills   

if __name__ == "__main__":  # only when this file is run directly, not when it is imported
    print(read_skills())