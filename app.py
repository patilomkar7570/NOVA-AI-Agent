import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import queue
import sys
import os


# =========================================================
# CONFIG
# =========================================================

AGENT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agent.py"
)


# =========================================================
# APP
# =========================================================

class AgentApp:

    def __init__(self, root):

        self.root = root
        self.root.title("AI Browser Agent")
        self.root.geometry("850x600")

        self.process = None
        self.output_queue = queue.Queue()

        # -------------------------------------------------
        # TITLE
        # -------------------------------------------------

        title = tk.Label(
            root,
            text="🤖 AI Browser Agent",
            font=("Segoe UI", 20, "bold")
        )

        title.pack(
            pady=(15, 5)
        )

        subtitle = tk.Label(
            root,
            text="Qwen3 8B + Playwright + Brave",
            font=("Segoe UI", 10)
        )

        subtitle.pack(
            pady=(0, 10)
        )

        # -------------------------------------------------
        # COMMAND
        # -------------------------------------------------

        tk.Label(
            root,
            text="What should I do?",
            font=("Segoe UI", 11, "bold")
        ).pack(
            anchor="w",
            padx=20
        )

        self.command = tk.Entry(
            root,
            font=("Segoe UI", 12)
        )

        self.command.pack(
            fill="x",
            padx=20,
            pady=8
        )

        self.command.bind(
            "<Return>",
            lambda event: self.run_command()
        )

        # -------------------------------------------------
        # BUTTONS
        # -------------------------------------------------

        button_frame = tk.Frame(root)

        button_frame.pack(
            pady=5
        )

        self.run_button = tk.Button(
            button_frame,
            text="▶ Run",
            width=12,
            command=self.run_command
        )

        self.run_button.pack(
            side="left",
            padx=5
        )

        self.stop_button = tk.Button(
            button_frame,
            text="🛑 Stop",
            width=12,
            command=self.stop_agent
        )

        self.stop_button.pack(
            side="left",
            padx=5
        )

        # -------------------------------------------------
        # OUTPUT
        # -------------------------------------------------

        tk.Label(
            root,
            text="Activity",
            font=("Segoe UI", 11, "bold")
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        self.output = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            font=("Consolas", 10),
            state="disabled"
        )

        self.output.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )

        self.write_output(
            "✅ Interface ready.\n"
        )

        self.write_output(
            "Starting AI agent...\n\n"
        )

        # -------------------------------------------------
        # START OUTPUT CHECKER
        # -------------------------------------------------

        self.root.after(
            100,
            self.check_output
        )

        # -------------------------------------------------
        # START BACKEND
        # -------------------------------------------------

        self.start_agent()

    # =====================================================
    # OUTPUT
    # =====================================================

    def write_output(self, text):

        self.output.configure(
            state="normal"
        )

        self.output.insert(
            tk.END,
            text
        )

        self.output.see(
            tk.END
        )

        self.output.configure(
            state="disabled"
        )

    # =====================================================
    # START AGENT
    # =====================================================

    def start_agent(self):

        if self.process is not None:
            return

        try:

            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-u",
                    AGENT_FILE
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env={
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8"
                }
            )

        except Exception as e:

            self.process = None

            self.write_output(
                "\n❌ Could not start agent:\n"
                + str(e)
                + "\n"
            )

            return

        threading.Thread(
            target=self.read_agent_output,
            daemon=True
        ).start()

    # =====================================================
    # READ AGENT OUTPUT
    # =====================================================

    def read_agent_output(self):

        if self.process is None:
            return

        try:

            for line in iter(
                self.process.stdout.readline,
                ""
            ):

                self.output_queue.put(
                    line
                )

        except Exception as e:

            self.output_queue.put(
                "\n❌ Output error: "
                + str(e)
                + "\n"
            )

        finally:

            self.output_queue.put(
                "\n⚠️ Agent process stopped.\n"
            )

    # =====================================================
    # DISPLAY OUTPUT
    # =====================================================

    def check_output(self):

        while True:

            try:

                line = (
                    self.output_queue
                    .get_nowait()
                )

            except queue.Empty:

                break

            self.write_output(
                line
            )

        self.root.after(
            100,
            self.check_output
        )

    # =====================================================
    # SEND COMMAND
    # =====================================================

    def run_command(self):

        command = (
            self.command
            .get()
            .strip()
        )

        if not command:
            return

        # Start backend if it isn't running.
        if self.process is None:

            self.start_agent()

            if self.process is None:
                return

        # Check whether the backend crashed.
        if self.process.poll() is not None:

            self.write_output(
                "\n❌ Agent is not running.\n"
                "Please restart the app.\n"
            )

            return

        try:

            self.process.stdin.write(
                command + "\n"
            )

            self.process.stdin.flush()

        except Exception as e:

            self.write_output(
                "\n❌ Could not send command:\n"
                + str(e)
                + "\n"
            )

            return

        self.command.delete(
            0,
            tk.END
        )

    # =====================================================
    # STOP
    # =====================================================

    def stop_agent(self):

        if self.process is None:
            return

        if self.process.poll() is not None:
            return

        self.write_output(
            "\n🛑 Stopping agent...\n"
        )

        try:

            self.process.terminate()

        except Exception:
            pass

    # =====================================================
    # CLOSE APP
    # =====================================================

    def close(self):

        try:

            if (
                self.process is not None
                and self.process.poll() is None
            ):

                self.process.terminate()

        except Exception:
            pass

        self.root.destroy()


# =========================================================
# START
# =========================================================

root = tk.Tk()

app = AgentApp(
    root
)

root.protocol(
    "WM_DELETE_WINDOW",
    app.close
)

root.mainloop()