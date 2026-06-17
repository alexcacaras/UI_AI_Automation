import requests


def ask_llm(elements, goal):
    with open("commands.md", "r", encoding="utf-8") as f:
        commands_doc = f.read()

    element_text = ""
    for el in elements:
        element_text += f"{el['index']}: {el['tag']} \"{el['name']}\"\n"

    prompt = f"""You are controlling a web browser to accomplish a goal.

GOAL: {goal}

Here are the actionable elements on the current page (index: tag "name"):
{element_text}

Here are the commands you can use and how they work:
{commands_doc}

Respond with EXACTLY ONE action, nothing else.

Your action:"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen3:14b",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]


if __name__ == "__main__":

    fake_elements = [
        {"index": 1, "tag": "a", "name": "Skip to main content"},
        {"index": 2, "tag": "a", "name": "Navigator"},
        {"index": 3, "tag": "a", "name": "My Client Groups"},
        {"index": 4, "tag": "input", "name": "Search by Name"},
        {"index": 5, "tag": "a", "name": "Settings and Actions"},
    ]

    answer = ask_llm(fake_elements, "Click on My Client Groups")
    print("AI said:")
    print(answer)