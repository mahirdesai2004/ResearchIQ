@echo off
FOR /F "tokens=5" %%P IN ('netstat -a -n -o ^| findstr :8000') DO taskkill /F /PID %%P
