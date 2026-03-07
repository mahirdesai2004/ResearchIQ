import subprocess
import time
import sys

print("Starting servers...")

try:
    backend_log = open(r"c:\Users\abhin\OneDrive\Desktop\college\ett\ResearchIQ\backend_output.txt", "w")
    frontend_log = open(r"c:\Users\abhin\OneDrive\Desktop\college\ett\ResearchIQ\frontend_output.txt", "w")

    backend_proc = subprocess.Popen(
        "uv run uvicorn main:app --host 0.0.0.0 --port 8000",
        cwd=r"c:\Users\abhin\OneDrive\Desktop\college\ett\ResearchIQ\backend",
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        shell=True
    )

    frontend_proc = subprocess.Popen(
        "npm run dev",
        cwd=r"c:\Users\abhin\OneDrive\Desktop\college\ett\ResearchIQ\frontend",
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        shell=True
    )

    print(f"Backend PID: {backend_proc.pid}")
    print(f"Frontend PID: {frontend_proc.pid}")

    time.sleep(10)
    print("Startup script finished waiting. Check output files in the root directory.")
except Exception as e:
    print(f"Error starting servers: {e}")
