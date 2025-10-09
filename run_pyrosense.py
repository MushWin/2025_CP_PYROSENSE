#!/usr/bin/env python3
"""
PyroSense Main Runner — starts/stops all apps cleanly.
Press Ctrl+C once to stop all servers.
"""

import os
import sys
import time
import signal
import subprocess
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # use the venv/python you're running with


def spawn(script_name: str) -> subprocess.Popen:
    """Start a child process in its own group so we can signal it cleanly."""
    kwargs = {"cwd": SCRIPT_DIR}
    if os.name == "nt":
        # On Windows, start in a new process group so CTRL_BREAK works
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([PY, script_name], **kwargs)


def gentle_stop(p: subprocess.Popen):
    """Ask the child to stop (platform-appropriate)."""
    if p.poll() is not None:
        return
    try:
        if os.name == "nt":
            p.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            p.terminate()
    except Exception:
        pass


def hard_kill(p: subprocess.Popen):
    if p.poll() is None:
        try:
            p.kill()
        except Exception:
            pass


def main():
    print("🔥🔥 Starting PyroSense Complete System 🔥🔥")
    print("=" * 60)
    print("Starting all servers...")
    procs = []

    # Start servers
    procs.append(spawn("login.py"))
    time.sleep(1.5)  # small head start for login
    procs.append(spawn("history.py"))
    procs.append(spawn("dashboard.py"))

    print("Opening login page in your browser…")
    webbrowser.open("http://localhost:5000")

    print("\n🌟 PyroSense System is Running 🌟")
    print("=" * 60)
    print("Login Server:    http://localhost:5000")
    print("History Server:  http://localhost:5001")
    print("Dashboard:       http://localhost:5002")
    print("\nPress Ctrl+C once in this window to stop all servers.")
    print("=" * 60)

    try:
        # keep main process alive while children run
        while any(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹ Stopping servers…")
        for p in procs:
            gentle_stop(p)

        # grace period
        t0 = time.time()
        while any(p.poll() is None for p in procs) and time.time() - t0 < 5:
            time.sleep(0.2)

        # force kill leftovers
        for p in procs:
            hard_kill(p)

        print("✅ All servers stopped.")
    finally:
        # absolute cleanup on exit
        for p in procs:
            hard_kill(p)


if __name__ == "__main__":
    main()
