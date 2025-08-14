import tkinter as tk

GAMES = {
    "League of Legends": ("league_of_legends", "live"),
    "Valorant": ("valorant", "live"),
    "Teamfight Tactics": ("bacon", "live"),
    "Legends of Runeterra": ("lor", "live")
}

class GameLauncherUI:
    def __init__(self, on_select):
        self.on_select = on_select
        self.root = tk.Tk()
        self.root.title("Riot Game Launcher")
        self.root.geometry("500x400")

        # Game selection section
        tk.Label(self.root, text="Select a game to launch:", font=("Arial", 14)).pack(pady=10)
        for name, (gid, pl) in GAMES.items():
            tk.Button(
                self.root, text=name, font=("Arial", 12),
                command=lambda g=gid, p=pl: self.start_game_thread(g, p)
            ).pack(pady=5, fill="x", padx=20)

        # Console log section
        tk.Label(self.root, text="Status Log:", font=("Arial", 12)).pack(pady=(15, 5))
        
        # Frame for text + scrollbar
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_box = tk.Text(frame, height=12, state="disabled", wrap="word", bg="#1e1e1e", fg="#00ff00")
        self.log_box.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(frame, command=self.log_box.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_box.config(yscrollcommand=scrollbar.set)

    def log(self, message):
        """Append message to the log box."""
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"{message}\n")
        self.log_box.see("end")  # Auto scroll
        self.log_box.config(state="disabled")
        self.root.update_idletasks()

    def start_game_thread(self, game_id, patchline):
        """Run the on_select callback in a new thread to avoid freezing the UI."""
        import threading
        threading.Thread(target=self.on_select, args=(game_id, patchline), daemon=True).start()

    def run(self):
        self.root.mainloop()
