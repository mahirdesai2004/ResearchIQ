import subprocess, os
try:
    out = subprocess.check_output('netstat -ano | findstr :8000', shell=True).decode()
    for line in out.splitlines():
        if 'LISTENING' in line:
            pid = line.strip().split()[-1]
            print(f"Killing PID {pid}")
            os.system(f'taskkill /F /PID {pid}')
except Exception as e:
    print(e)
