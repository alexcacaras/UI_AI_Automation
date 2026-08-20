from flask import Flask, jsonify, request, Response, send_from_directory
import threading
import queue
import json
import time
import os
from pathlib import Path

app = Flask(
    __name__,
    static_folder="dashboard/dist",
    static_url_path=""
)

PROJECT_ROOT = Path(__file__).resolve().parent
RECORDINGS_DIR = PROJECT_ROOT / "recordings"


state = {
    "page": None,
    "log_queue": queue.Queue(),

    # worker signals
    "pending_action": None,   # "record" / "playback"
    "should_close": False,

    # lifecycle
    "browser_open": False,
    "worker_active": False,
    "busy": False,

    # current request
    "mode": "overlay",
    "name": "",
    "goal": "",
    "suite_tests": [],

    "url": "",
}


def push_event(event_type, **data):
    payload = {
        "type": event_type,
        **data
    }

    state["log_queue"].put(payload)


def log(msg):
    print(msg)

    push_event(
        "log",
        text=str(msg)
    )


# ============================================================
# PLAYWRIGHT WORKER
# ============================================================

def automation_thread():
    """
    ONE thread owns Playwright for the entire browser session.

    Flask never directly touches the Playwright page/browser.
    It only places work into shared state.
    """

    from playwright.sync_api import sync_playwright
    from overlay import click_queue
    from loop import run_loop
    from replay import replay

    state["worker_active"] = True

    p = None
    browser = None

    try:
        log("Starting Playwright worker...")

        p = sync_playwright().start()

        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )

        page = browser.new_page(
            no_viewport=True
        )

        page.expose_function(
            "badgeClicked",
            lambda info: click_queue.put(info)
        )

        log(f"Opening Oracle: {state['url']}")

        page.goto(state["url"])

        state["page"] = page
        state["browser_open"] = True

        log(
            "Browser opened. Log into Oracle, "
            "then choose Record or Playback."
        )

        push_event("browser_opened")

        # Existing overlay command center
        from command_center import start_command_center
        start_command_center()

        # ====================================================
        # SESSION LOOP
        # ====================================================

        while True:

            # Wait for Record / Playback / Close request
            while (
                state["pending_action"] is None
                and not state["should_close"]
            ):
                time.sleep(0.25)

            # ------------------------------------------------
            # EXPLICIT SESSION CLOSE
            # ------------------------------------------------

            if state["should_close"]:
                log("Closing browser session...")
                break

            action = state["pending_action"]
            state["pending_action"] = None

            # ------------------------------------------------
            # RECORD
            # ------------------------------------------------

            if action == "record":

                state["busy"] = True

                current_name = state["name"]
                current_goal = state["goal"]
                current_mode = state["mode"]

                log(
                    f"Recording: {current_name} "
                    f"(mode={current_mode})"
                )

                push_event(
                    "recording_started",
                    name=current_name,
                    mode=current_mode
                )

                try:

                    signal = run_loop(
                        page,
                        current_mode,
                        current_name,
                        current_goal,
                        interactive=False
                    )

                    log(
                        f"Saved recording: {current_name}"
                    )

                    state["busy"] = False

                    # =========================================
                    # NEW RECORDING
                    # =========================================

                    if signal == "new":

                        log(
                            "New Recording selected. "
                            "Browser session remains open."
                        )

                        push_event(
                            "recording_finished",
                            name=current_name,
                            signal="new"
                        )

                        push_event(
                            "ready_for_recording"
                        )

                        # Loop back and wait for React to send
                        # the next recording name + goal.
                        continue

                    # =========================================
                    # FINISH
                    # =========================================

                    else:

                        log(
                            "Finish selected. "
                            "Closing browser session."
                        )

                        push_event(
                            "recording_finished",
                            name=current_name,
                            signal="exit"
                        )

                        # Leave the session loop.
                        break

                except Exception as e:

                    state["busy"] = False

                    log(
                        f"Recording error: {e}"
                    )

                    push_event(
                        "recording_error",
                        name=current_name,
                        message=str(e)
                    )

                    # Keep browser alive so the user can recover.
                    continue

            # ------------------------------------------------
            # PLAYBACK
            # ------------------------------------------------
            elif action == "suite":

                state["busy"] = True

                tests = list(state["suite_tests"])

                log(
                    f"Starting suite with {len(tests)} test(s)"
                )

                push_event(
                    "suite_started",
                    tests=tests
                )

                results = []

                for position, test_name in enumerate(tests, start=1):

                    log(
                        f"[{position}/{len(tests)}] "
                        f"Running: {test_name}"
                    )

                    push_event(
                        "suite_test_started",
                        name=test_name,
                        position=position,
                        total=len(tests)
                    )

                    try:

                        ok = replay(
                            page,
                            test_name
                        )

                        result = "PASS" if ok else "FAIL"

                    except Exception as e:

                        result = "ERROR"

                        log(
                            f"{test_name} crashed: {e}"
                        )

                    results.append({
                        "name": test_name,
                        "result": result
                    })

                    log(
                        f"{result}: {test_name}"
                    )

                    push_event(
                        "suite_test_finished",
                        name=test_name,
                        result=result,
                        position=position,
                        total=len(tests)
                    )

                state["busy"] = False

                passed = sum(
                    1 for item in results
                    if item["result"] == "PASS"
                )

                failed = len(results) - passed

                log(
                    f"Suite complete: "
                    f"{passed} passed, "
                    f"{failed} failed"
                )

                push_event(
                    "suite_finished",
                    results=results,
                    passed=passed,
                    failed=failed,
                    total=len(results)
                )

                continue

            elif action == "playback":

                state["busy"] = True

                current_name = state["name"]

                log(
                    f"Starting playback: {current_name}"
                )

                push_event(
                    "playback_started",
                    name=current_name
                )

                try:

                    ok = replay(
                        page,
                        current_name
                    )

                    state["busy"] = False

                    if ok:

                        log(
                            f"Playback PASS: {current_name}"
                        )

                        push_event(
                            "playback_finished",
                            name=current_name,
                            result="PASS"
                        )

                    else:

                        log(
                            f"Playback FAIL: {current_name}"
                        )

                        push_event(
                            "playback_finished",
                            name=current_name,
                            result="FAIL"
                        )

                except Exception as e:

                    state["busy"] = False

                    log(
                        f"Playback error: {e}"
                    )

                    push_event(
                        "playback_finished",
                        name=current_name,
                        result="ERROR",
                        message=str(e)
                    )

                # Keep the Oracle/browser session open.
                # User can playback something else,
                # start recording, or end session.
                continue

    except Exception as e:

        log(
            f"Automation worker error: {e}"
        )

        push_event(
            "worker_error",
            message=str(e)
        )

    finally:

        # ====================================================
        # ONE PLACE DOES ALL PLAYWRIGHT CLEANUP
        # ====================================================

        state["busy"] = False
        state["browser_open"] = False
        state["page"] = None
        state["pending_action"] = None
        state["should_close"] = False

        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

        try:
            if p is not None:
                p.stop()
        except Exception:
            pass

        state["worker_active"] = False

        log("Browser session closed.")

        push_event(
            "browser_closed"
        )


# ============================================================
# LAUNCH BROWSER
# ============================================================

@app.route("/api/launch", methods=["POST"])
def launch():

    if state["browser_open"]:
        return jsonify({
            "status": "error",
            "message": "Browser is already open"
        }), 409

    if state["worker_active"]:
        return jsonify({
            "status": "error",
            "message": "Browser is already starting"
        }), 409

    data = request.json or {}

    url = data.get(
        "url",
        ""
    ).strip()

    if url:
        state["url"] = url

    state["pending_action"] = None
    state["should_close"] = False

    thread = threading.Thread(
        target=automation_thread,
        daemon=True
    )

    thread.start()

    return jsonify({
        "status": "launching"
    })


# ============================================================
# START RECORDING
# ============================================================

@app.route("/api/start", methods=["POST"])
def start_recording():

    if not state["browser_open"]:
        return jsonify({
            "status": "error",
            "message": "Launch the browser first"
        }), 400

    if state["busy"]:
        return jsonify({
            "status": "error",
            "message": "Automation is already running"
        }), 409

    data = request.json or {}

    mode = data.get("mode", "overlay").strip()
    name = data.get("name", "").strip()
    goal = data.get("goal", "").strip()
    overwrite = bool(data.get("overwrite", False))

    if mode not in ("overlay", "manual", "ai"):
        return jsonify({
            "status": "error",
            "message": "Invalid recording mode"
        }), 400

    if not name:
        return jsonify({
            "status": "error",
            "message": "Recording name is required"
        }), 400

    if not goal:
        return jsonify({
            "status": "error",
            "message": "Goal is required"
        }), 400

    recording_path = RECORDINGS_DIR / f"{name}.json"

    # Web mode must never silently overwrite.
    if recording_path.exists() and not overwrite:
        return jsonify({
            "status": "exists",
            "message": f"Recording '{name}' already exists",
            "name": name
        }), 409

    state["mode"] = mode
    state["name"] = name
    state["goal"] = goal
    state["pending_action"] = "record"

    return jsonify({
        "status": "started",
        "name": name,
        "mode": mode
    })

# ============================================================
# RECORDINGS LIST
# ============================================================

@app.route("/api/recordings")
def recordings():

    RECORDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    items = []

    for path in sorted(
        RECORDINGS_DIR.glob("*.json")
    ):

        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

            if isinstance(data, dict):
                goal = data.get(
                    "goal",
                    ""
                )

                steps = len(
                    data.get(
                        "steps",
                        []
                    )
                )

            else:
                goal = ""
                steps = len(data)

        except Exception:
            goal = ""
            steps = 0

        items.append({
            "name": path.stem,
            "goal": goal,
            "steps": steps
        })

    return jsonify({
        "recordings": items
    })


# ============================================================
# PLAYBACK
# ============================================================

@app.route("/api/playback", methods=["POST"])
def playback():

    if not state["browser_open"]:
        return jsonify({
            "status": "error",
            "message": "Launch the browser first"
        }), 400

    if state["busy"]:
        return jsonify({
            "status": "error",
            "message": "Automation is already running"
        }), 409

    data = request.json or {}

    name = data.get(
        "name",
        ""
    ).strip()

    if not name:
        return jsonify({
            "status": "error",
            "message": "Recording name is required"
        }), 400

    recording_path = (
        RECORDINGS_DIR
        / f"{name}.json"
    )

    if not recording_path.exists():
        return jsonify({
            "status": "error",
            "message": f"Recording '{name}' does not exist"
        }), 404

    state["name"] = name
    state["pending_action"] = "playback"

    return jsonify({
        "status": "started",
        "name": name
    })

@app.route("/api/run-suite", methods=["POST"])
def run_suite_web():

    if not state["browser_open"]:
        return jsonify({
            "status": "error",
            "message": "Launch the browser first"
        }), 400

    if state["busy"]:
        return jsonify({
            "status": "error",
            "message": "Automation is already running"
        }), 409

    data = request.json or {}

    tests = data.get("tests", [])

    if not isinstance(tests, list):
        return jsonify({
            "status": "error",
            "message": "tests must be a list"
        }), 400

    tests = [
        str(test).strip()
        for test in tests
        if str(test).strip()
    ]

    if not tests:
        return jsonify({
            "status": "error",
            "message": "Choose at least one recording"
        }), 400

    missing = []

    for name in tests:
        path = RECORDINGS_DIR / f"{name}.json"

        if not path.exists():
            missing.append(name)

    if missing:
        return jsonify({
            "status": "error",
            "message": "Some recordings do not exist",
            "missing": missing
        }), 404

    state["suite_tests"] = tests
    state["pending_action"] = "suite"

    return jsonify({
        "status": "started",
        "tests": tests
    })
# ============================================================
# END SESSION
# ============================================================

@app.route("/api/close", methods=["POST"])
def close():

    if not state["browser_open"]:
        return jsonify({
            "status": "error",
            "message": "No browser session is open"
        }), 400

    if state["busy"]:
        return jsonify({
            "status": "error",
            "message": (
                "Automation is running. "
                "Finish it before ending the session."
            )
        }), 409

    state["should_close"] = True

    return jsonify({
        "status": "closing"
    })
# ============================================================
# LOCAL FILE ACCESS
# ============================================================

@app.route("/api/open-recordings", methods=["POST"])
def open_recordings_folder():

    RECORDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        os.startfile(str(RECORDINGS_DIR))

        return jsonify({
            "status": "opened",
            "path": str(RECORDINGS_DIR)
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/open-docs", methods=["POST"])
def open_docs_folder():

    docs_dir = RECORDINGS_DIR / "docs"

    docs_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        os.startfile(str(docs_dir))

        return jsonify({
            "status": "opened",
            "path": str(docs_dir)
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ============================================================
# STATUS
# ============================================================

@app.route("/api/status")
def status():

    return jsonify({
        "browser_open": state["browser_open"],
        "worker_active": state["worker_active"],
        "busy": state["busy"],
        "pending_action": state["pending_action"],
        "mode": state["mode"],
        "name": state["name"]
    })


# ============================================================
# SSE LOG STREAM
# ============================================================

@app.route("/api/stream")
def stream():

    def gen():

        while True:

            try:

                msg = state[
                    "log_queue"
                ].get(
                    timeout=30
                )

                yield (
                    f"data: "
                    f"{json.dumps(msg)}"
                    f"\n\n"
                )

            except queue.Empty:

                yield (
                    "data: "
                    + json.dumps({
                        "type": "keepalive"
                    })
                    + "\n\n"
                )

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================
# BUILT REACT FRONTEND
# ============================================================

@app.route("/")
def index():

    dist = Path(
        app.static_folder
    )

    if (
        dist
        / "index.html"
    ).exists():

        return send_from_directory(
            dist,
            "index.html"
        )

    return """
    <h2>UI AI Automation</h2>
    <p>
        React development server:
        <a href="http://localhost:5173">
            http://localhost:5173
        </a>
    </p>
    """


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print(" UI AI AUTOMATION")
    print("=" * 60)
    print(" Backend:   http://localhost:5000")
    print(" React dev: http://localhost:5173")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )