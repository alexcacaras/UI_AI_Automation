# Phase 7 — Web Frontend (delivery)

Architecture A: web frontend for launch/config/record/playback/suite/output;
tkinter command center STAYS as the floating recording-control panel (its buttons
feed run_loop via command_queue in real time — putting them in the web tab would need
bidirectional IPC). Overlay recording always needs the live Oracle browser as a separate
window anyway, so a floating control panel is the right pattern.

In-process (NOT subprocess): Flask runs Playwright in ONE dedicated automation thread
that owns the browser for its whole life; Flask endpoints only set flags in shared state,
never touch the page directly (avoids Playwright's sync-API thread-affinity crash).
Chosen over subprocess because the existing command_queue shared-memory design makes
web input free — a web button and a tkinter button both just put on a queue, no stdin
piping. This also makes manual-mode-via-web tractable later (command → shared queue).

Staged flow: /api/launch opens browser → user logs into Oracle by hand → /api/start
begins the record loop + command center. Two-step because login is manual (not automated).

- server.py: Flask + SSE event stream; endpoints launch/start/playback/run-suite/close/
  recordings/status + open-recordings/open-docs (os.startfile — Windows-only, fine).
- run_loop: interactive flag — True (terminal, keeps overwrite prompt) / False (web,
  never blocks on input()). Solves the terminal-input()-hangs-web-thread problem.
- React (dashboard/): launch form, operation picker (record/playback/suite), live log,
  recordings list (select-not-type), folder-access buttons.
- Distribution: launch_dashboard.vbs (pythonw silent Flask + open browser) + adapted
  create_shortcut.py (OneDrive-aware). setup.bat still TODO (add flask/playwright/docx).
- main.py terminal entry point PRESERVED as dev/fallback path (get_recording_info popup,
  interactive=True default).

Known: manual-mode-via-web (bidirectional) deferred; distribution unproven on clean machine.