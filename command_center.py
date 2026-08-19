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

def _run_window():
    root = tk.Tk()
    root.title("Command Center")
    root.attributes("-topmost", True)
    root.configure(bg="#1e1e2e")
    root.geometry("260x560")

    tk.Label(root, text="COMMAND CENTER", bg="#1e1e2e", fg="#89b4fa",
             font=("Segoe UI", 12, "bold")).pack(pady=(14, 10))

    def styled(parent, text, cmd_value, color):
        return tk.Button(parent, text=text,
                         command=lambda: command_queue.put(cmd_value),
                         bg=color, fg="white", font=("Segoe UI", 11, "bold"),
                         relief="flat", width=22, height=2, cursor="hand2",
                         activebackground="#313244", activeforeground="white")

    scroll_table_frame = tk.Frame(root, bg="#1e1e2e")
    scroll_table_frame.pack(pady=(12, 4))
    scroll_table_entry = tk.Entry(scroll_table_frame, width=20, bg="#313244", fg="white",
                         insertbackground="white", relief="flat", font=("Segoe UI", 10))
    scroll_table_entry.pack(pady=4, ipady=4)
    scroll_table_entry.insert(0, "600")
    tk.Button(scroll_table_frame, text="↓  SCROLL TABLE",
              command=lambda: command_queue.put(f"scroll table {scroll_table_entry.get()}"),
              bg="#8d1ef5", fg="white", font=("Segoe UI", 11, "bold"), relief="flat",
              width=22, height=2, cursor="hand2").pack(pady=4)

    scroll_page_frame = tk.Frame(root, bg="#1e1e2e")
    scroll_page_frame.pack(pady=(12, 4))
    scroll_page_entry = tk.Entry(scroll_page_frame, width=20, bg="#313244", fg="white",
                         insertbackground="white", relief="flat", font=("Segoe UI", 10))
    scroll_page_entry.pack(pady=4, ipady=4)
    scroll_page_entry.insert(0, "600")
    tk.Button(scroll_page_frame, text="↓  SCROLL PAGE",
              command=lambda: command_queue.put(f"scroll page {scroll_page_entry.get()}"),
              bg="#c9a800", fg="black", font=("Segoe UI", 11, "bold"), relief="flat",
              width=22, height=2, cursor="hand2").pack(pady=4)

    scroll_nav_frame = tk.Frame(root, bg="#1e1e2e")
    scroll_nav_frame.pack(pady=(12, 4))
    scroll_nav_entry = tk.Entry(scroll_nav_frame, width=20, bg="#313244", fg="white",
                         insertbackground="white", relief="flat", font=("Segoe UI", 10))
    scroll_nav_entry.pack(pady=4, ipady=4)
    scroll_nav_entry.insert(0, "600")
    tk.Button(scroll_nav_frame, text="↓  SCROLL NAV",
              command=lambda: command_queue.put(f"scroll navigator {scroll_nav_entry.get()}"),
              bg="#179299", fg="white", font=("Segoe UI", 11, "bold"), relief="flat",
              width=22, height=2, cursor="hand2").pack(pady=4)

    styled(root, "✓  FINISH (save & exit)", "done_exit", "#40a02b").pack(pady=4)
    styled(root, "➕  NEW RECORDING", "done_new", "#3b82f6").pack(pady=4)
    styled(root, "⏱  WAIT", "wait", "#df8e1d").pack(pady=4)

    nav_frame = tk.Frame(root, bg="#1e1e2e")
    nav_frame.pack(pady=(12, 4))
    nav_entry = tk.Entry(nav_frame, width=20, bg="#313244", fg="white",
                         insertbackground="white", relief="flat", font=("Segoe UI", 10))
    nav_entry.pack(pady=4, ipady=4)
    tk.Button(nav_frame, text="→  NAV", command=lambda: command_queue.put(f"nav {nav_entry.get()}"),
              bg="#1e66f5", fg="white", font=("Segoe UI", 11, "bold"), relief="flat",
              width=22, height=2, cursor="hand2").pack(pady=4)

    root.mainloop()

def start_command_center():
    threading.Thread(target=_run_window, daemon=True).start()