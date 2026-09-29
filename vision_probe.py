"""Throwaway: can gemma4:e4b actually READ a dense Oracle screenshot?

Not "can it heal" - just "does it see". Tier 3 is worthless if the model
cannot resolve small grey Redwood text at 1920 wide, and that is a ten-minute
question, not an end-of-day surprise. Same reasoning as test_heal.py: no
browser, no Oracle login, seconds per iteration.
"""
import base64
import os
import sys
import time

import requests
from dotenv import load_dotenv
load_dotenv()

MODEL = os.getenv("HEALER_MODEL") or os.getenv("MODEL")
URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


def ask(image_path, question):
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = {
        "model": MODEL,
        "prompt": question,
        "images": [b64],          # <- the whole Tier 3 plumbing change, one field
        "stream": False,
        "options": {"num_ctx": int(os.getenv("HEALER_NUM_CTX", "16384")),
                    "temperature": 0},
    }
    t0 = time.time()
    r = requests.post(f"{URL}/api/generate", json=body, timeout=600)
    data = r.json()
    if "error" in data:
        return f"ERROR: {data['error']}", time.time() - t0, None
    return data.get("response", ""), time.time() - t0, data.get("prompt_eval_count")


if __name__ == "__main__":
    img = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else (
        "This is a screenshot of an Oracle Fusion page. "
        "1) What is the page title? "
        "2) What is the User Name field's value? "
        "3) List the buttons along the top right."
    )
    print(f"model: {MODEL}   image: {os.path.basename(img)} "
          f"({os.path.getsize(img)} bytes)\n")
    answer, secs, tokens = ask(img, q)
    print(answer)
    print(f"\n--- {secs:.1f}s, prompt_eval_count={tokens}")
