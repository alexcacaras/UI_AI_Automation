import json
import re
import requests
from dotenv import load_dotenv
load_dotenv()
import os


# ---------------------------------------------------------------------------
# PROVIDER SHIM
# ---------------------------------------------------------------------------
# One indirection so .env can swap where the healer's model runs. Local Ollama
# is the DEFAULT and stays the default: a heal prompt contains the page's
# element names, which on a Fusion page can be employee names. Nothing leaves
# the machine unless the user opts in.
#
# json_mode uses Ollama's constrained decoding (format:"json"), which forces
# syntactically valid JSON out of the model instead of asking nicely for it.

def _complete(prompt, json_mode=False):
    provider = os.getenv("HEALER_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return _complete_ollama(prompt, json_mode)
    raise ValueError(
        f"HEALER_PROVIDER='{provider}' is not implemented. "
        "Only 'ollama' exists today; a cloud provider slots in here."
    )


def _complete_ollama(prompt, json_mode):
    model = os.getenv("HEALER_MODEL") or os.getenv("MODEL")
    url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # num_ctx is the trap. A model's advertised context (gemma4:e4b = 131072) is
    # what it CAN do; Ollama allocates only num_ctx per request and defaults to
    # 4096. Go over it and the prompt is TRUNCATED SILENTLY — no error, and the
    # model answers confidently from a list it never fully received. An Oracle
    # Navigator page is hundreds of elements, so 4096 is not close to enough.
    #
    # temperature 0 because this is a lookup, not a composition. gemma's own
    # default is 1, which both hurts accuracy here and makes runs unrepeatable.
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": int(os.getenv("HEALER_NUM_CTX", "16384")),
            "temperature": float(os.getenv("HEALER_TEMPERATURE", "0")),
        },
    }
    if json_mode:
        body["format"] = "json"

    response = requests.post(f"{url}/api/generate", json=body, timeout=300)
    data = response.json()

    # prompt_eval_count is what Ollama ACTUALLY ingested. If it flatlines at
    # num_ctx, the prompt was clipped and the answer is worthless — that is the
    # difference between "the model is weak" and "the model was shown half a page".
    used = data.get("prompt_eval_count")
    limit = body["options"]["num_ctx"]
    if used is not None:
        warn = "  <-- AT LIMIT, PROMPT WAS TRUNCATED" if used >= limit else ""
        print(f"   [healer] {model}  prompt {used}/{limit} tokens{warn}")

    return data["response"]


def _extract_json(text):
    """Pull the first {...} object out of a model reply.

    format:"json" should make this unnecessary, but a swapped model (or a
    cloud one) may still wrap the object in prose or a ```json fence. Cheap
    insurance; returns None if there is nothing object-shaped in there.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# THE HEALER (Phase 6, Tier 1)
# ---------------------------------------------------------------------------

def _step_line(step):
    """One compact line describing a recorded step, for the path context."""
    bits = [step.get("action", "?")]
    if step.get("name"):
        bits.append(f'"{step["name"][:60]}"')
    if step.get("value"):
        bits.append(f'= {str(step["value"])[:30]!r}')
    if step.get("target"):
        bits.append(step["target"])
    return " ".join(bits)


def heal_step(step, elements, goal, rank="no match", steps=None, step_index=None):
    """Ask the model which CURRENT element is the one a failed step meant.

    This is NOT ask_llm. ask_llm answers "what action should I take next?" and
    may pick any element for any reason. heal_step answers a narrower question:
    "the recording pointed at a specific element, resolve() can no longer find
    it — which of the elements on screen right now IS it?" One question, one
    answer, no action vocabulary involved.

    `rank` is what resolve() last matched on. A step that has been degrading to
    'GUESS name+tag' for weeks was already drifting; telling the model that is
    a hint about HOW the locator was lost, not just that it was.

    Returns (element_dict_or_None, reason).
      element None  -> no plausible match; the run should still stop. This is
                       the give-up path that Tier 3 (vision) will hang off.
    """
    element_text = ""
    for el in elements:
        line = f"{el['index']}: <{el['tag']}>"
        if el.get("role"):
            line += f" role={el['role']}"
        line += f' "{el["name"]}"'
        if el.get("id"):
            line += f" id={el['id']}"
        if el.get("grid"):
            line += f" [grid cell row={el.get('row')} col={el.get('column')}]"
        element_text += line + "\n"

    # Describe the lost element from the durable fields the recording kept.
    lost = f'name: "{step.get("name", "")}"'
    lost += f'\n  tag: {step.get("tag", "") or "(not recorded)"}'
    lost += f'\n  id: {step.get("id", "") or "(none recorded)"}'
    if step.get("role"):
        lost += f'\n  role: {step["role"]}'
    if step.get("grid"):
        lost += (f'\n  grid cell: grid={step["grid"]} '
                 f'row={step.get("row")} col={step.get("column")}')

    # The recording's OTHER steps are the strongest context available, and they
    # are free — replay already holds them. The steps BEFORE the failure have
    # already run, which says what page we are standing on far more reliably
    # than a one-word goal. The steps AFTER are a hard constraint: whatever we
    # pick has to make them reachable. "Sales" stops looking plausible the
    # moment the model can see that the next step is "Time Management".
    path_text = ""
    if steps and step_index is not None:
        lines = []
        for i, s in enumerate(steps):
            marker = "  >>> " if i == step_index else "      "
            tail = "   <-- THIS STEP FAILED" if i == step_index else ""
            lines.append(f"{marker}{i + 1}. {_step_line(s)}{tail}")
        path_text = (
            "\nTHE FULL RECORDED TEST, IN ORDER:\n"
            + "\n".join(lines)
            + "\nEvery step above the failing one ALREADY RAN SUCCESSFULLY, so the page "
              "in front of you is the one they lead to. Every step below it still has to "
              "run: the element you pick must be the one that makes them reachable. If a "
              "candidate would send the test somewhere those later steps do not exist, it "
              "is the wrong candidate.\n"
        )

    prompt = f"""You are repairing a broken UI test step for an Oracle Fusion page.

A recorded test step points at one specific element on the page. The element
can no longer be found by its recorded id or name — the page has changed.
Your job is to decide which element CURRENTLY on the page is that same element.

THE ACTION THE STEP PERFORMS: {step.get('action', '')}
THE ELEMENT THE STEP IS LOOKING FOR:
  {lost}

How the locator was last matching before it broke: {rank}

WHAT THE TEST AS A WHOLE IS TRYING TO DO: {goal or "(not recorded)"}
{path_text}
ELEMENTS CURRENTLY ON THE PAGE:
{element_text}
RULES:
- This is an IDENTITY question, not a ranking question. You are not choosing the
  best available element. You are deciding whether the lost element is on this
  page at all, and if so, which one it is.
- Very often it is NOT on the page, and -1 is then the correct answer. -1 is a
  normal, expected answer, not a failure. Answer -1 whenever you are unsure.
- A control that does a RELATED job is not the same control. "Delete" is not
  "Search". A substitute is always wrong: a wrong pick makes the test click
  something it was never meant to click, and the test then passes having tested
  nothing. Giving up is safe; substituting is not.
- If the recorded test path is shown above, it is your strongest evidence. Check
  every candidate against it: would the steps AFTER the failing one still be
  reachable if the test clicked this? If they would not, it is the wrong element,
  however similar the label looks.
- Pick an element only when it is the SAME control with a changed label or id.
  Labels get reworded ("Filters" -> "Show Filters"); ids get renumbered. That is
  the case you are here to catch.
- Match on purpose and on tag/role, not on wording alone. A <button> that was
  lost is far more likely to still be a button than to have become a link.
- Your reason must say why the element you picked IS the lost one. If your reason
  would say it is merely similar, plausible, or the closest available, answer -1.

Answer with JSON only, in exactly this shape:
{{"index": <the index number of your pick, or -1>, "reason": "<one short sentence>"}}"""

    try:
        raw = _complete(prompt, json_mode=True)
    except Exception as e:
        return None, f"healer call failed: {e}"

    answer = _extract_json(raw)
    if answer is None:
        return None, f"could not parse model reply: {raw[:200]}"

    reason = str(answer.get("reason", ""))
    try:
        index = int(answer.get("index", -1))
    except (TypeError, ValueError):
        return None, f"model returned a non-numeric index: {answer.get('index')!r}"

    if index == -1:
        return None, reason or "model found no plausible match"

    # The model may hallucinate an index that was never in the list. Look it up
    # rather than trusting it — an out-of-range pick is a give-up, not a crash.
    for el in elements:
        if el["index"] == index:
            return el, reason
    return None, f"model picked index {index}, which is not on the page"


def ask_llm(elements, goal, recent_history):
    model = os.getenv("MODEL")
    with open("commands.md", "r", encoding="utf-8") as f:
        commands_doc = f.read()

    element_text = ""
    for el in elements:
        element_text += f"{el['index']}: {el['tag']} \"{el['name']}\"\n"

    history_text = ""
    for entry in recent_history:
        history_text += f"- {entry['cmd'] } ->  {entry['result'] }\n"

    prompt = f"""You are controlling a web browser to accomplish a goal.

GOAL: {goal}

IMPORTANT NAVIGATION RULES:
- In the Navigator, "Expand ..." links do nothing and time out. To open a section, click the plain section-name item, never the "Expand ..." one.

Here are the actionable elements on the current page (index: tag "name"):
{element_text}

Recent actions you already tried (do NOT repeat ones that failed or caused no change):
{history_text}

Here are the commands you can use and how they work:
{commands_doc}



Respond with EXACTLY ONE action, nothing else.

Your action:"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
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

    answer = ask_llm(fake_elements, "Click on My Client Groups", [])
    print("AI said:")
    print(answer)