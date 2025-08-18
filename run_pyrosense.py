#!/usr/bin/env python3
"""
PyroSense Main Runner - Launches Both Login and History Servers
"""

import multiprocessing
import os
import sys
import time
import webbrowser

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_login_server():
    """Run the login server module"""
    os.chdir(SCRIPT_DIR)
    os.system("python login.py")

def run_history_server():
    """Run the history server module"""
    os.chdir(SCRIPT_DIR)
    os.system("python history.py")

if __name__ == "__main__":
    print("🔥🔥 Starting PyroSense Complete System 🔥🔥")
    print("=" * 60)
    print("Starting both servers simultaneously...")
    
    # Start the login server in a separate process
    login_process = multiprocessing.Process(target=run_login_server)
    login_process.start()
    
    # Give the login server a moment to initialize
    time.sleep(2)
    
    # Start the history server in a separate process
    history_process = multiprocessing.Process(target=run_history_server)
    history_process.start()
    
    # Open the login page in the default browser
    print("Opening login page in your browser...")
    webbrowser.open('http://localhost:5000')
    
    print("\n🌟 PyroSense System is Running 🌟")
    print("=" * 60)
    print("Login Server: http://localhost:5000")
    print("History Server: http://localhost:5001")
    print("\nTo stop both servers, press Ctrl+C in this window")
    print("=" * 60)
    
    try:
        # Keep the main process running to handle keyboard interrupts
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down PyroSense servers...")
        
        # Terminate the server processes
        login_process.terminate()
        history_process.terminate()
        
        # Wait for processes to complete shutdown
        login_process.join()
        history_process.join()
        
        print("PyroSense servers have been shut down.")
        sys.exit(0)
