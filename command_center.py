import threading
import queue
import tkinter as tk

command_queue = queue.Queue()

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

    styled(root, "✓  DONE", "done", "#40a02b").pack(pady=4)
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