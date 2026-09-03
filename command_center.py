import threading
import queue
import tkinter as tk

command_queue = queue.Queue()
def get_recording_info():
    """Modal popup: collects recording name + goal. Returns (name, goal) or (None, None) if cancelled."""
    result = {"name": None, "goal": None}

    win = tk.Tk()
    win.title("New Recording")
    win.attributes("-topmost", True)
    win.configure(bg="#1e1e2e")
    win.geometry("360x220")

    tk.Label(win, text="NEW RECORDING", bg="#1e1e2e", fg="#89b4fa",
             font=("Segoe UI", 13, "bold")).pack(pady=(16, 12))

    tk.Label(win, text="Recording name", bg="#1e1e2e", fg="#94a3b8",
             font=("Segoe UI", 9)).pack(anchor="w", padx=20)
    name_entry = tk.Entry(win, width=38, bg="#313244", fg="white",
                          insertbackground="white", relief="flat", font=("Segoe UI", 10))
    name_entry.pack(padx=20, pady=(2, 10), ipady=4)
    name_entry.focus()

    tk.Label(win, text="Goal (one line)", bg="#1e1e2e", fg="#94a3b8",
             font=("Segoe UI", 9)).pack(anchor="w", padx=20)
    goal_entry = tk.Entry(win, width=38, bg="#313244", fg="white",
                          insertbackground="white", relief="flat", font=("Segoe UI", 10))
    goal_entry.pack(padx=20, pady=(2, 14), ipady=4)

    def submit():
        result["name"] = name_entry.get().strip()
        result["goal"] = goal_entry.get().strip()
        win.destroy()

    tk.Button(win, text="Start Recording", command=submit,
              bg="#3b82f6", fg="white", font=("Segoe UI", 11, "bold"),
              relief="flat", width=20, height=1, cursor="hand2").pack()

    win.bind("<Return>", lambda e: submit())   # Enter submits
    win.mainloop()

    return result["name"], result["goal"]

BG = "#1e1e2e"
FIELD = "#313244"


def _scrollable(root):
    """A vertically scrollable container.

    tkinter has no scrolling Frame, so the standard trick is: put a Frame inside
    a Canvas via create_window, and keep the canvas scrollregion synced to the
    frame's real size. Without this the panel silently clips anything past the
    window height — which is what hid FINISH and the NAV box.
    """
    outer = tk.Frame(root, bg=BG)
    outer.pack(fill="both", expand=True)

    canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
    bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG)

    # grow the scrollregion whenever the content changes size
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    # keep the inner frame as wide as the canvas so buttons stay centred
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))

    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    return inner


def _run_window():
    root = tk.Tk()
    root.title("Command Center")
    root.attributes("-topmost", True)
    root.configure(bg=BG)
    root.geometry("300x600")
    root.minsize(280, 320)

    body = _scrollable(root)

    tk.Label(body, text="COMMAND CENTER", bg=BG, fg="#89b4fa",
             font=("Segoe UI", 12, "bold")).pack(pady=(12, 8))

    def styled(parent, text, cmd_value, color, fg="white"):
        return tk.Button(parent, text=text,
                         command=lambda: command_queue.put(cmd_value),
                         bg=color, fg=fg, font=("Segoe UI", 10, "bold"),
                         relief="flat", width=24, height=2, cursor="hand2",
                         activebackground="#313244", activeforeground="white")

    # ---- scrolling ------------------------------------------------------
    # ONE shared amount box for all four targets. Four separate boxes all
    # reading "600" cost ~520px of height and pushed FINISH off screen.
    tk.Label(body, text="scroll amount (px, negative = back)", bg=BG, fg="#94a3b8",
             font=("Segoe UI", 8)).pack(pady=(4, 2))
    amount = tk.Entry(body, width=10, bg=FIELD, fg="white", justify="center",
                      insertbackground="white", relief="flat", font=("Segoe UI", 10))
    amount.pack(ipady=3)
    amount.insert(0, "600")

    def amt():
        return amount.get().strip() or "600"

    grid_f = tk.Frame(body, bg=BG)
    grid_f.pack(pady=(8, 4))

    def scroll_btn(text, target, color, r, c, fg="white"):
        tk.Button(grid_f, text=text,
                  command=lambda: command_queue.put(f"scroll {target} {amt()}"),
                  bg=color, fg=fg, font=("Segoe UI", 9, "bold"), relief="flat",
                  width=11, height=2, cursor="hand2").grid(row=r, column=c, padx=3, pady=3)

    scroll_btn("↓ TABLE", "table", "#8d1ef5", 0, 0)
    scroll_btn("↓ PAGE", "page", "#c9a800", 0, 1, fg="black")
    scroll_btn("↓ NAV", "navigator", "#179299", 1, 0)
    # Time card day columns run left-to-right and are virtualized: later days
    # aren't in the DOM and get no badge until scrolled to. Only HORIZONTAL one.
    scroll_btn("→ GRID", "grid", "#e64553", 1, 1)

    tk.Frame(body, bg="#313244", height=1).pack(fill="x", padx=16, pady=(10, 6))

    # ---- actions --------------------------------------------------------
    styled(body, "✓  FINISH (save & exit)", "done_exit", "#40a02b").pack(pady=3)
    styled(body, "➕  NEW RECORDING", "done_new", "#3b82f6").pack(pady=3)
    styled(body, "⏱  WAIT", "wait", "#df8e1d").pack(pady=3)

    tk.Frame(body, bg="#313244", height=1).pack(fill="x", padx=16, pady=(10, 6))

    # ---- navigate -------------------------------------------------------
    nav_entry = tk.Entry(body, width=26, bg=FIELD, fg="white",
                         insertbackground="white", relief="flat", font=("Segoe UI", 10))
    nav_entry.pack(pady=(2, 4), ipady=4)
    tk.Button(body, text="→  NAV", command=lambda: command_queue.put(f"nav {nav_entry.get()}"),
              bg="#1e66f5", fg="white", font=("Segoe UI", 10, "bold"), relief="flat",
              width=24, height=2, cursor="hand2").pack(pady=(0, 12))

    root.mainloop()

def start_command_center():
    threading.Thread(target=_run_window, daemon=True).start()