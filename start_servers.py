import subprocess
import time
import os

print("Starting servers...")

# Base project directory
BASE_DIR = os.path.expanduser("/Users/mahir/ResearchIQ")

# Log file paths
backend_log_path = os.path.join(BASE_DIR, "backend_output.txt")
frontend_log_path = os.path.join(BASE_DIR, "frontend_output.txt")

try:
    with open(backend_log_path, "w") as backend_log, open(frontend_log_path, "w") as frontend_log:
        # Start backend FastAPI server
        backend_proc = subprocess.Popen(
            ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=os.path.join(BASE_DIR, "backend"),
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            shell=False,
        )

        # Start frontend dev server (assumes npm is configured)
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=os.path.join(BASE_DIR, "frontend"),
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
            shell=False,
        )

        print(f"Backend PID: {backend_proc.pid}")
        print(f"Frontend PID: {frontend_proc.pid}")

        # Wait a short while for servers to initialize
        time.sleep(10)
        print("Startup script finished waiting. Check log files in the project root.")
except Exception as e:
    print(f"Error starting servers: {e}")
