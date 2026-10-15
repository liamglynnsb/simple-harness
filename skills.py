from pathlib import Path

def read_skills(folder="skills"):
    skills = {}
    for path in Path(folder).glob("*.md"):
        text = path.read_text()
        header, _, body = text.partition("\n---\n")
        lines = header.splitlines()
        name = lines[0].split(": ", 1)[1]
        description = lines[1].split(": ", 1)[1]
        skills[name] = {"description": description, "body": body}
    return skills   
